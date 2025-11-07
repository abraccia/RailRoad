import socket
import threading
import json
import time
from datetime import datetime

class ClientManager:
    def __init__(self):
        self.clients = {}
        self.lock = threading.Lock()
    
    def add_client(self, conn, addr):
        client_id = f"{addr[0]}:{addr[1]}"
        with self.lock:
            self.clients[client_id] = {
                'connection': conn,
                'address': addr,
                'last_seen': datetime.now().isoformat(),
                'active': True
            }
        return client_id
    
    def remove_client(self, client_id):
        with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]
    
    def get_clients(self):
        with self.lock:
            return {cid: {**info, 'connection': None} for cid, info in self.clients.items()}
    
    def send_command(self, client_id, command):
        with self.lock:
            if client_id in self.clients and self.clients[client_id]['active']:
                try:
                    conn = self.clients[client_id]['connection']
                    conn.sendall(command.encode() + b"\n")
                    return True
                except:
                    self.clients[client_id]['active'] = False
        return False
    
    def broadcast_command(self, command):
        results = {}
        with self.lock:
            for client_id in list(self.clients.keys()):
                results[client_id] = self.send_command(client_id, command)
        return results

class CommandHandler:
    @staticmethod
    def receive_result(conn):
        data = b""
        while True:
            part = conn.recv(4096)
            if not part:
                break
            data += part
            if b"--END--\n" in data:
                data = data.replace(b"--END--\n", b"")
                break
        return data.decode(errors="ignore")

class SocketServer:
    def __init__(self, host="0.0.0.0", port=6769):
        self.host = host
        self.port = port
        self.client_manager = ClientManager()
        self.running = False
        self.server_socket = None
    
    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"Server listening on {self.host}:{self.port}")
        
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(conn, addr)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:
                    print(f"Accept error: {e}")
    
    def handle_client(self, conn, addr):
        client_id = self.client_manager.add_client(conn, addr)
        print(f"Client connected: {client_id}")
        
        buffer = b""
        while self.running:
            try:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                
                while b"\n" in buffer:
                    line, _, buffer = buffer.partition(b"\n")
                    cmd = line.decode().strip()
                    
                    if cmd.lower() == "exit":
                        conn.sendall(b"Exiting\n" + b"--END--\n")
                        break
                    
                    # For now, just acknowledge commands
                    # In a real implementation, you'd process the output
                    conn.sendall(b"Command received by server\n" + b"--END--\n")
            
            except Exception as e:
                print(f"Error with client {client_id}: {e}")
                break
        
        self.client_manager.remove_client(client_id)
        conn.close()
        print(f"Client disconnected: {client_id}")
    
    def stop_server(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()

# Global server instance
server_instance = SocketServer()

def start_socket_server():
    server_instance.start_server()

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_socket_server)
    server_thread.daemon = True
    server_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down server...")
        server_instance.stop_server()
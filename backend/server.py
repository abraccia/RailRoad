import socket
import threading
import json
import time
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ClientManager:
    def __init__(self):
        self.clients = {}
        self.lock = threading.Lock()
        self.frontend_callbacks = []
    
    def add_frontend_callback(self, callback):
        """Add callback to notify frontend of changes"""
        self.frontend_callbacks.append(callback)
    
    def notify_frontend(self, event_type, data):
        """Notify all frontend callbacks"""
        for callback in self.frontend_callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Frontend callback error: {e}")
    
    def add_client(self, conn, addr):
        client_id = f"{addr[0]}:{addr[1]}"
        with self.lock:
            self.clients[client_id] = {
                'connection': conn,
                'address': addr,
                'last_seen': datetime.now().isoformat(),
                'active': True,
                'connected_at': datetime.now().isoformat()
            }
        
        # Notify frontend
        self.notify_frontend('client_connected', {
            'client_id': client_id,
            'client_info': self.clients[client_id]
        })
        
        logger.info(f"Client connected: {client_id}")
        return client_id
    
    def remove_client(self, client_id):
        with self.lock:
            if client_id in self.clients:
                client_info = self.clients[client_id].copy()
                del self.clients[client_id]
        
        # Notify frontend
        self.notify_frontend('client_disconnected', {
            'client_id': client_id,
            'client_info': client_info
        })
        
        logger.info(f"Client disconnected: {client_id}")
    
    def update_client_activity(self, client_id):
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id]['last_seen'] = datetime.now().isoformat()
                self.clients[client_id]['active'] = True
    
    def get_clients(self):
        with self.lock:
            return {cid: {**info, 'connection': None} for cid, info in self.clients.items()}
    
    def send_command(self, client_id, command):
        with self.lock:
            if client_id in self.clients and self.clients[client_id]['active']:
                try:
                    conn = self.clients[client_id]['connection']
                    conn.sendall(command.encode() + b"\n")
                    
                    # Notify frontend of command sent
                    self.notify_frontend('command_sent', {
                        'client_id': client_id,
                        'command': command,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    return True
                except Exception as e:
                    self.clients[client_id]['active'] = False
                    logger.error(f"Error sending command to {client_id}: {e}")
        return False
    
    def broadcast_command(self, command):
        results = {}
        with self.lock:
            for client_id in list(self.clients.keys()):
                results[client_id] = self.send_command(client_id, command)
        return results

class SocketServer:
    def __init__(self, host="0.0.0.0", port=6769):
        self.host = host
        self.port = port
        self.client_manager = ClientManager()
        self.running = False
        self.server_socket = None
    
    def add_frontend_callback(self, callback):
        self.client_manager.add_frontend_callback(callback)
    
    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        logger.info(f"Server listening on {self.host}:{self.port}")
        
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
                    logger.error(f"Accept error: {e}")
    
    def handle_client(self, conn, addr):
        client_id = self.client_manager.add_client(conn, addr)
        
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
                    
                    # Update client activity
                    self.client_manager.update_client_activity(client_id)
                    
                    if cmd.lower() == "exit":
                        conn.sendall(b"Exiting\n" + b"--END--\n")
                        break
                    
                    # For demonstration, echo the command back
                    response = f"Command executed: {cmd}\n".encode()
                    conn.sendall(response + b"--END--\n")
            
            except Exception as e:
                logger.error(f"Error with client {client_id}: {e}")
                break
        
        self.client_manager.remove_client(client_id)
        conn.close()
    
    def stop_server(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()

# Global server instance
server_instance = SocketServer()

def start_socket_server():
    server_instance.start_server()
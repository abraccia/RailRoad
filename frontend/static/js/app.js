class RailRoadC2 {
    constructor() {
        this.socket = io();
        this.currentClient = 'broadcast';
        this.commandHistory = [];
        
        this.initializeEventListeners();
        this.setupSocketEvents();
        this.loadInitialData();
    }

    initializeEventListeners() {
        // Command form submission
        document.getElementById('commandForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendCommand();
        });

        // Client selection
        document.getElementById('clientSelect').addEventListener('change', (e) => {
            this.currentClient = e.target.value;
        });
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            this.updateConnectionStatus(true);
        });

        this.socket.on('disconnect', () => {
            this.updateConnectionStatus(false);
        });

        this.socket.on('clients_update', (clients) => {
            this.updateClientList(clients);
        });

        this.socket.on('command_sent', (command) => {
            this.addToCommandHistory(command);
        });

        this.socket.on('command_broadcast', (command) => {
            this.addToCommandHistory(command);
        });
    }

    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connectionStatus');
        if (connected) {
            statusElement.className = 'badge bg-success';
            statusElement.innerHTML = '<i class="fas fa-circle"></i> Connected';
        } else {
            statusElement.className = 'badge bg-danger';
            statusElement.innerHTML = '<i class="fas fa-circle"></i> Disconnected';
        }
    }

    updateClientList(clients) {
        const clientList = document.getElementById('clientList');
        const clientSelect = document.getElementById('clientSelect');
        
        // Clear existing options except "Broadcast to All"
        clientList.innerHTML = '';
        while (clientSelect.children.length > 1) {
            clientSelect.removeChild(clientSelect.lastChild);
        }

        // Update total clients count
        document.getElementById('totalClients').textContent = Object.keys(clients).length;

        // Add clients to list and dropdown
        Object.entries(clients).forEach(([clientId, clientInfo]) => {
            // Add to sidebar list
            const clientElement = document.createElement('div');
            clientElement.className = `list-group-item client-item ${clientInfo.active ? 'status-connected' : 'status-disconnected'}`;
            clientElement.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <i class="fas fa-desktop me-2"></i>
                        <small>${clientId}</small>
                    </div>
                    <span class="badge ${clientInfo.active ? 'bg-success' : 'bg-danger'}">
                        ${clientInfo.active ? 'Active' : 'Inactive'}
                    </span>
                </div>
                <div class="small text-muted">Last seen: ${new Date(clientInfo.last_seen).toLocaleTimeString()}</div>
            `;
            clientList.appendChild(clientElement);

            // Add to dropdown
            const option = document.createElement('option');
            option.value = clientId;
            option.textContent = clientId;
            clientSelect.appendChild(option);
        });
    }

    async sendCommand() {
        const commandInput = document.getElementById('commandInput');
        const command = commandInput.value.trim();

        if (!command) return;

        try {
            const response = await fetch('/api/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    client_id: this.currentClient,
                    command: command
                })
            });

            const result = await response.json();
            
            if (response.ok) {
                this.showResult('success', result.message);
                commandInput.value = '';
            } else {
                this.showResult('error', result.error);
            }
        } catch (error) {
            this.showResult('error', 'Failed to send command: ' + error.message);
        }
    }

    addToCommandHistory(command) {
        this.commandHistory.unshift(command);
        this.renderCommandHistory();
    }

    renderCommandHistory() {
        const historyContainer = document.getElementById('commandHistory');
        historyContainer.innerHTML = '';

        this.commandHistory.slice(0, 10).forEach(cmd => {
            const commandElement = document.createElement('div');
            commandElement.className = `command-item ${cmd.type === 'broadcast' ? 'broadcast-command' : ''}`;
            commandElement.innerHTML = `
                <div class="d-flex justify-content-between">
                    <div>
                        <strong>${cmd.client_id}</strong>
                        <code>${cmd.command}</code>
                    </div>
                    <small class="text-muted">${new Date(cmd.timestamp).toLocaleTimeString()}</small>
                </div>
            `;
            historyContainer.appendChild(commandElement);
        });
    }

    showResult(type, message) {
        const resultsContainer = document.getElementById('commandResults');
        const resultElement = document.createElement('div');
        resultElement.className = `alert alert-${type === 'success' ? 'success' : 'danger'} mt-3`;
        resultElement.textContent = message;
        resultsContainer.appendChild(resultElement);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            resultElement.remove();
        }, 5000);
    }

    async loadInitialData() {
        try {
            // Load command history
            const historyResponse = await fetch('/api/history');
            this.commandHistory = await historyResponse.json();
            this.renderCommandHistory();

            // Load clients
            const clientsResponse = await fetch('/api/clients');
            const clients = await clientsResponse.json();
            this.updateClientList(clients);
        } catch (error) {
            console.error('Failed to load initial data:', error);
        }
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new RailRoadC2();
});
How to run (serverFlask.py and clientflask.py)

Controller machine (server):
1. pip install flask
2. python3 server_flask.py
3. Open frontend: http://0.0.0.0:5000/

Client VM(s):
Copy client.py and edit SERVER_HOST to the controller IP.
1.  Run: python3 client.py
 or
1. pyinstaller --onefile client.py
# copy dist/client to the target and run it with ./client


NEW INSTRUCTIONS

# on both controller and client machine (do once)
sudo apt update
sudo apt install -y python3-venv python3-pip

# in your project folder (controller/server)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install flask flask-socketio eventlet

# on client machine (if running client with python)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install "python-socketio[client]"

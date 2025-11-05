#Client VM: Kali 4001
#Clients IP: 192.168.204.209
#Port: 4444

import socket

#HOST = input("Enter the Server's IP Address: ")
#PORT = input("Enter the port used by the server: ")

HOST = "192.168.193.113"  # The server's hostname or IP address
PORT = 65432  # The port used by the server

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(b"Hello, world")
    data = s.recv(1024)

print(f"Received {data!r}")

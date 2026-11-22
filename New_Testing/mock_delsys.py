import socket
import struct
import time
import threading

CMD_PORT = 50040
EMG_PORT = 50041

def cmd_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', CMD_PORT))
    server.listen(5)
    print("Mock Command Server listening")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_cmd, args=(conn,), daemon=True).start()

def handle_cmd(conn):
    try:
        while True:
            data = conn.recv(1024)
            if not data: break
            if b"START" in data: conn.sendall(b"OK\r\n\r\n")
            elif b"STOP" in data: conn.sendall(b"OK\r\n\r\n")
    except:
        pass

def emg_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', EMG_PORT))
    server.listen(5)
    print("Mock EMG Server listening")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_emg, args=(conn,), daemon=True).start()

def handle_emg(conn):
    try:
        while True:
            vals = [float(i) for i in range(16)]
            data = struct.pack('<16f', *vals)
            conn.sendall(data)
            time.sleep(0.001)
    except:
        pass

t1 = threading.Thread(target=cmd_server, daemon=True)
t2 = threading.Thread(target=emg_server, daemon=True)
t1.start()
t2.start()

while True:
    time.sleep(1)

import socket
import struct
import zmq

# Helper function to ensure we read exact byte chunks from the TCP stream
# Updated Helper Function
def recv_exact(sock, n_bytes):
    data = bytearray()
    while len(data) < n_bytes:
        try:
            packet = sock.recv(n_bytes - len(data))
            if not packet:
                return None
            data.extend(packet)
        except socket.timeout:
            # Yields control back to Python for a split second to catch Ctrl+C
            continue 
    return data

# ==========================================
# 1. ZMQ SETUP (Destination)
# ==========================================
import subprocess

def clean_port(port_num):
    try:
        res = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if f":{port_num}" in line and 'LISTENING' in line:
                pid = line.strip().split()[-1]
                if pid != '0':
                    print(f"Cleaning ghost process (PID {pid}) on port {port_num}...")
                    subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
    except:
        pass

clean_port(3999)

context = zmq.Context()
socket0 = context.socket(zmq.PUB)
socket0.setsockopt(zmq.CONFLATE, True)
socket0.setsockopt(zmq.LINGER, 0)

# Set the IP address and port
sender_ip = '127.0.0.1'  # Bind locally to guarantee matching IPv4 with subscriber
port = 3000                 # Port number on the sender PC
socket0.bind(f"tcp://{sender_ip}:{port}")
print(f"ZMQ Publisher bound to tcp://{sender_ip}:{port}")


# ==========================================
# 2. DELSYS TRIGNO SETUP (Source)
# ==========================================
# Default Delsys Trigno TCP settings
DEL_HOST = 'localhost'
CMD_PORT = 50040  # Port for sending START/STOP commands
EMG_PORT = 50041  # Port where EMG data streams

print('Connecting to Delsys Trigno Control Utility...')

# Open Command Socket
cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cmd_socket.connect((DEL_HOST, CMD_PORT))

# Open EMG Data Socket
data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
data_socket.connect((DEL_HOST, EMG_PORT))
data_socket.settimeout(0.5)  # <--- ADD THIS LINE (0.5 second timeout)

# Send START command to Trigno Base Station
# Delsys requires commands to end with double carriage-return/line-feed
cmd_socket.sendall(b"START\r\n\r\n")
response = cmd_socket.recv(1024)
print(f"Trigno Response: {response.decode('utf-8').strip()}")
print('EMG Connected Successfully.')


# ==========================================
# 3. DATA ACQUISITION & STREAMING LOOP
# ==========================================
# Delsys systems typically output 16 channels of float32 data.
# 16 channels * 4 bytes (float32) = 64 bytes per packet.
PACKET_SIZE = 64  
channels_of_interest = [9, 10, 12, 13] 

# --- NEW: Create a buffer ---
BUFFER_SIZE = 100  # Collect 100 samples before sending
data_buffer = [[] for _ in channels_of_interest]

try:
    print("Streaming data... Press Ctrl+C to stop.")
    while True:
        raw_bytes = recv_exact(data_socket, PACKET_SIZE)
        
        if not raw_bytes:
            print("\nConnection to Delsys lost.")
            break
            
        emg_data = struct.unpack('<16f', raw_bytes)
        
        # --- NEW: Add to buffer instead of printing/sending immediately ---
        for i, ch in enumerate(channels_of_interest):
            data_buffer[i].append(emg_data[ch])
        
        # When the buffer hits 100, send it over ZMQ and clear it
        if len(data_buffer[0]) >= BUFFER_SIZE:
            # Flatten buffer: [muscle1_samples, muscle2_samples, ...]
            flat_buffer = []
            for channel_data in data_buffer:
                flat_buffer.extend(channel_data)
            # print(flat_buffer)
            socket0.send_pyobj(flat_buffer)
            data_buffer = [[] for _ in channels_of_interest] # Reset for the next batch

except socket.error as e:
    print(f"Network error: {e}")

except KeyboardInterrupt:
    print('\n-- Program Terminated by user. Closing sockets --')

finally:
    # Graceful shutdown: Tell the Delsys system to stop streaming
    try:
        cmd_socket.sendall(b"STOP\r\n\r\n")
        cmd_socket.close()
        data_socket.close()
    except:
        pass
    socket0.close()
    print("Sockets closed successfully.")
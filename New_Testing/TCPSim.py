import socket
import json
import time
import random
import threading
import sys

# Configuration based on the user's C-Mill research manual (Section 4.1)
HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 8089         # Default port for CueFors live data feed
STREAM_RATE_HZ = 200
STREAM_DELAY = 1.0 / STREAM_RATE_HZ  # 0.005 seconds for 200 Hz

# Streams to simulate (Using only the ones requested by the user for efficiency)
STREAMS_TO_SEND = [
    1,  # Speed
    4,  # Distance
    8,  # Fz
    9,  # COPx
    10, # COPy
]

# Lock to ensure only one thread writes to the socket at a time (crucial for concurrency)
socket_lock = threading.Lock()

# --- Message Definitions ---

def create_stream_message(stream_id, value):
    """Generates an ActualValue message (Command 5) for a specific stream."""
    message_data = {
        "command": 5,        # ActualValue
        "stream": stream_id, 
        "streamID": 0,       
        "value": value,      
        "stringValue": None
    }
    return json.dumps(message_data) + '\n'

def create_event_message():
    """Generates a dynamic Event message (Command 7)."""
    events = ["MidSSL", "MidSSR", "HSL", "HSR", "TOL", "TOR"]
    message_data = {
        "command": 7,        # Event
        "stream": 0,         # None
        "streamID": 0,
        "value": 0,
        "stringValue": random.choice(events)
    }
    return json.dumps(message_data) + '\n'

def generate_dynamic_value(stream_id):
    """Generates realistic-looking dynamic values for simulation."""
    if stream_id == 1: # Speed (m/s)
        return round(random.uniform(0.5, 2.5), 3)
    elif stream_id == 4: # Distance (m)
        return round(random.uniform(50.0, 100.0), 2)
    elif stream_id == 8: # Fz (Force Z - Newton)
        return round(random.uniform(100.0, 500.0), 2)
    elif stream_id in (9, 10): # COPx, COPy (meters)
        return round(random.uniform(-0.1, 0.1), 3)
    return 0.0

def event_generator_thread(conn, addr):
    """
    Separate thread to randomly send event messages.
    Runs independently of the high-frequency stream thread.
    """
    print(f"Event generator started for {addr}.")
    while True:
        try:
            # Send an event roughly every 2 to 4 seconds (average 3 seconds)
            time.sleep(random.uniform(2, 4))
            
            event_message = create_event_message()
            
            # Use the lock before writing to the socket to prevent corruption
            with socket_lock:
                conn.sendall(event_message.encode('ascii'))
            
            # print(f"-> Sent Event: {event_message.strip()}") # Uncomment for detailed debugging
            
        except socket.error:
            # Client disconnected, so this thread should stop
            break
        except Exception as e:
            print(f"Error in event generator for {addr}: {e}")
            break

def handle_client(conn, addr):
    """Handles communication with a single connected client."""
    print(f"Connected by {addr}. Starting {STREAM_RATE_HZ} Hz data stream simulation...")
    
    # 1. Send initial AuthenticationOK message
    auth_ok_message = '{"command":6,"stream":0,"streamID":0,"value":0,"stringValue":null}\n'
    try:
        conn.sendall(auth_ok_message.encode('ascii'))
        print(f"-> Sent initial AuthenticationOK to {addr}")
    except socket.error:
        print(f"Error sending auth message to {addr}. Client disconnected.")
        return

    # Start the independent event generator thread
    event_thread = threading.Thread(target=event_generator_thread, args=(conn, addr))
    event_thread.daemon = True 
    event_thread.start()

    # 2. Start streaming the high-frequency data
    while True:
        start_time = time.time()
        
        try:
            # Send a burst of ActualValue messages for each stream
            for stream_id in STREAMS_TO_SEND:
                value = generate_dynamic_value(stream_id)
                message = create_stream_message(stream_id, value)
                
                # Use the lock before writing to the socket
                with socket_lock:
                    conn.sendall(message.encode('ascii'))

            # Wait to maintain the 200 Hz rate across the burst of packets
            elapsed_time = time.time() - start_time
            sleep_time = STREAM_DELAY - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time) 
            
        except socket.error:
            # Client disconnected
            print(f"Client {addr} disconnected.")
            break
        except Exception as e:
            print(f"An unexpected error occurred in client handler: {e}")
            break

    print(f"Data stream simulation ended for {addr}.")
    conn.close()

def start_server():
    """Sets up the TCP socket server and listens for connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, PORT))
            s.listen()
            print(f"TCP Stream Simulator started, listening on {HOST}:{PORT}")
            print(f"Simulating core streams at {STREAM_RATE_HZ} Hz. Events are random.")
        except socket.error as e:
            print(f"Could not bind to port {PORT}. Error: {e}")
            print("Please ensure no other program is using this port.")
            return

        while True:
            try:
                conn, addr = s.accept()
                client_thread = threading.Thread(target=handle_client, args=(conn, addr))
                client_thread.daemon = True 
                client_thread.start()

            except KeyboardInterrupt:
                print("\nServer shutting down.")
                sys.exit(0) # Use sys.exit for clean exit
            except Exception as e:
                print(f"Server error: {e}")
                
if __name__ == "__main__":
    start_server()

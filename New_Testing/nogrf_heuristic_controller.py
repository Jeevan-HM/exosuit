import numpy as np
from time import time, sleep
import zmq
import threading
import pickle
import os
import msvcrt

def setup_communication_rcv(ip, port):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    socket.setsockopt(zmq.CONFLATE, True)
    socket.connect(f"tcp://{ip}:{port}")
    return socket

def terminate_experiment(event, sockets):
    print("Terminating Experiment...")
    try:
        event.set()
        print("Stopping Execution of Multi-Threads")
        sleep(1)
    except:
        pass
    for s in sockets:
        try:
            s.close()
        except:
            pass
    print("---------- EXPERIMENT FINALIZED ----------")
    os._exit(0)

def receiver_thread_hs(event, ip, port):
    global data_hs
    print(f'Starting Heel Strike thread on port {port}')
    socket_hs = setup_communication_rcv(ip, port)
    
    while True:
        if event.is_set():
            print(f'Closing Thread for Port: {port}')
            break 
        try:
            value = socket_hs.recv_pyobj()
            data_hs = value
        except Exception:
            pass
    socket_hs.close()

def main_thread():
    global data_hs
    
    # Initialize Data with reasonable defaults
    data_hs = {"hs_flag": 0, "k1_pct": 15, "k2_pct": 50, "k3_pct": 80, "duration": 1.1}
    
    t0_gaitcycle = time()
    Pd = [0, 0]
    
    context = zmq.Context()
    
    # Socket to Export Pressure Commands Data (to raspi)
    ip_export = "192.168.0.103"
    port_export = "8888" 
    socket_export = context.socket(zmq.PUB)
    socket_export.setsockopt(zmq.LINGER, 0)
    socket_export.setsockopt(zmq.CONFLATE, True)
    socket_export.bind(f"tcp://{ip_export}:{port_export}")
    
    # Receive HS events directly from nogrf_gaittiming
    ip_hs = "localhost"
    port_hs = "5555"
    
    # Multi-Threading
    event = threading.Event()
    
    # We only need the HS/Tracking thread (port 5555) now, no RL (4444)
    thread_hs = threading.Thread(target=receiver_thread_hs, args=(event, ip_hs, port_hs))
    thread_hs.daemon = True
    thread_hs.start()
    
    print("\n" + "="*50)
    print(" READY. Pressure Commands are currently PAUSED.")
    print(" Press SPACEBAR in this window to START / PAUSE.")
    print("="*50 + "\n")
    
    is_sending_active = False
    
    try:
        while True:
            # Check for Keyboard Toggle
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key in [b' ', b'\r']:
                    is_sending_active = not is_sending_active
                    state_str = "ACTIVE / SENDING" if is_sending_active else "PAUSED / IDLE"
                    print(f"\n>>> EXOSUIT ACTUATION: {state_str} <<<")
                    
            clock_gaitcycle = time() - t0_gaitcycle  
            
            # Parse dynamic broadcast from nogrf_gaittiming.py
            hs_flag = data_hs.get("hs_flag", 0)
            dur = data_hs.get("duration", 1.1)
            k1_pct = data_hs.get("k1_pct", 15.0)
            k2_pct = data_hs.get("k2_pct", 50.0)
            k3_pct = data_hs.get("k3_pct", 80.0)
            
            # Denormalize dynamic thresholds directly into seconds (Heuristic logic)
            tA = (k1_pct / 100.0) * dur
            tB = (k2_pct / 100.0) * dur
            tC = (k3_pct / 100.0) * dur
            tD = dur
            
            # Detect Heelstrikes from Boolean event
            if hs_flag == 1:
                print(f"==> Heelstrike Detected! Denormalized States: tA={tA:.2f}s, tB={tB:.2f}s, tC={tC:.2f}s")
                t0_gaitcycle = time() 
                data_hs["hs_flag"] = 0 # manually clear local flag to avoid re-triggering logic
                
            """ Determine Pressure Commands on Timings """
            # Identical core to RL method, fully controlled by the GaitEstimator timings
            if clock_gaitcycle < tA:
                Pd = [0, 5] 
            elif tA <= clock_gaitcycle < tB:
                Pd = [5, 0]  
            elif tB <= clock_gaitcycle < tC: 
                Pd = [0, 5]
            elif tC <= clock_gaitcycle < tD:
                Pd = [5, 0] 
            else:
                Pd = [0, 0] # Failsafe if cycle drifts extremely long without HS
                
            # Override with [0,0] if user paused actuation
            if not is_sending_active:
                Pd = [0, 0]
                
            # Send Pressure Command to raspberry pi
            array = Pd
            socket_export.send(pickle.dumps(array, protocol=2))
    
            # Sleep for frequency control (~300 Hz)
            frequency_sampling = 300 
            sleep(1 / frequency_sampling)
            
    except KeyboardInterrupt:
        terminate_experiment(event, [socket_export])

if __name__ == "__main__":
    main_thread()

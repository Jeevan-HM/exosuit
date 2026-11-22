import numpy as np
from time import time, sleep
import zmq
import threading
import pickle
import msvcrt
import os

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
        if len(sockets) > 0:
            import pickle
            sockets[0].send(pickle.dumps([0, 0], protocol=2))
            print("==> Deflation Command [0, 0] sent safely before closing.")
            sleep(0.5) # allow ZMQ to flush
    except Exception as e:
        print("Notice: Failed to send deflation command locally:", e)
        
    try:
        event.set()
        print("Stopping Execution of Multi-Threads")
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

def receiver_thread_timing(event, ip, port):
    global data_timing
    print(f'Starting gait timings thread on port {port}')
    socket_timing = setup_communication_rcv(ip, port)
    
    while True:
        if event.is_set():
            print(f'Closing Thread for Port: {port}')
            break 
        try:
            value = socket_timing.recv_pyobj()
            data_timing = value
        except Exception:
            pass
    socket_timing.close()


def main_thread():   
    global data_hs, data_timing
    
    # Initialize Data
    data_hs = {"hs_flag": 0}
    data_timing = [0.13, 0.264, 0.632, 1.27]
    
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
    
    # Receive RL timing actions
    ip_timing = "localhost"
    port_timing = "4444"
    
    # Multi-Threading
    event = threading.Event()
    
    thread_hs = threading.Thread(target=receiver_thread_hs, args=(event, ip_hs, port_hs))
    thread_timing = threading.Thread(target=receiver_thread_timing, args=(event, ip_timing, port_timing))
    
    # Set daemons so they don't block exit
    thread_hs.daemon = True
    thread_timing.daemon = True
    
    thread_hs.start()
    thread_timing.start()
    
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
            
            tA, tB, tC, tD = data_timing
            hs_flag = data_hs.get("hs_flag", 0)
            
            # Detect Heelstrikes from Boolean event
            # if hs_flag == 1:
            #     print("==> Heelstrike Detected")
            #     t0_gaitcycle = time() 
            #     data_hs["hs_flag"] = 0 # manually clear local flag to avoid re-triggering logic before next thread read

            if clock_gaitcycle > 1.27:
                print("==> Heelstrike Detected")
                t0_gaitcycle = time() 
                data_hs["hs_flag"] = 0

            """ Determine Pressure Commands on Timings """
            if clock_gaitcycle < tA:
                Pd = [0, 10] 
            elif tA <= clock_gaitcycle < tB:
                Pd = [10, 0]  
            elif tB <= clock_gaitcycle < tC: 
                Pd = [0, 10]
            elif tC <= clock_gaitcycle < tD:
                Pd = [10, 0] 
                
            # Override with [0,0] if user paused actuation
            if not is_sending_active:
                Pd = [0, 0]
                
            # Send Pressure Command to raspberry pi
            array = Pd
            print(array)
            socket_export.send(pickle.dumps(array, protocol=2))
    
            # Sleep for frequency control (~300 Hz)
            frequency_sampling = 300 
            sleep(1 / frequency_sampling)
            
    except KeyboardInterrupt:
        terminate_experiment(event, [socket_export])

if __name__ == "__main__":
    main_thread()

import os
import sys
import time
import subprocess
import zmq

def launch_script(script_name, env):
    print(f"Launching {script_name}...")
    # Using cmd /k to keep the terminal open even if the Python script crashes!
    return subprocess.Popen(["cmd.exe", "/k", sys.executable, script_name], env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)

def main():
    print("=== EXOSUIT PROTOCOL LAUNCHER ===")
    subject = input("Enter Subject Name [Subject1]: ").strip() or "Subject1"
    condition = input("Enter Trial Condition [Cond1]: ").strip() or "Cond1"
    trial = input("Enter Trial Number [1]: ").strip() or "1"
    incline = input("Enter Incline (e.g., 0, 5, 10) [0]: ").strip() or "0"
    speed = input("Enter Speed (e.g., 1.0, 1.25) [1.0]: ").strip() or "1.0"
    
   # mvc_VL = 0.000310726102982913
   # mvc_RF = 0.00037249038207918996
   # mvc_BF = 6.007187876334844e-05
   # mvc_ST = 4.091189501939166e-05


#    mvc_VL = 5.1762972517466294e-05
#    mvc_RF = 0.00015296808900011998
#    mvc_BF = 5.3551696394109834e-05
#    mvc_ST = 2.7256698880588948e-05



# Amir

# mvc_VL = 0.001044106340017487
# mvc_RF = 0.00033875425505852923
# mvc_BF = 4.251991348564341e-05
# mvc_ST = 4.0079296203444185e-05



#Mason
# mvc_VL = 0.00021694004690864943
# mvc_RF = 0.0006952421681286414
# mvc_BF = 6.0630176137569e-05
# mvc_ST = 0.0018490477291853277

    print("\n--- MVC VALUES ---")
    mvc_vl = input("Enter MVC_VL: ").strip() or "0.001044106340017487"
    mvc_rf = input("Enter MVC_RF: ").strip() or "0.00033875425505852923"
    mvc_bf = input("Enter MVC_BF: ").strip() or "4.251991348564341e-05"
    mvc_st = input("Enter MVC_ST: ").strip() or "4.0079296203444185e-05"
    
    print("\n--- CONTROLLER MODE ---")
    print("1: Reinforcement Learning (RL)")
    print("2: Baseline Heuristic Controller")
    print("3: Data Collection ONLY (No Actuation)")
    
    if condition.upper() in ["NOEXO", "EXOINACTIVE"]:
        print(f">> Auto-selected Mode 3 (Data Collection ONLY) for condition '{condition}'")
        mode = "3"
    else:
        mode = input("Select Mode [1]: ").strip() or "1"
        
    mode_map = {"1": "RL", "2": "Baseline", "3": "DataCollect"}
    mode_str = mode_map.get(mode, "UnknownMode")
    
    env = os.environ.copy()
    env["EXO_SUBJECT"] = subject
    env["EXO_CONDITION"] = condition
    env["EXO_TRIAL"] = trial
    env["EXO_MODE"] = mode_str
    env["EXO_INCLINE"] = incline
    env["EXO_SPEED"] = speed
    env["EXO_MVC_VL"] = mvc_vl
    env["EXO_MVC_RF"] = mvc_rf
    env["EXO_MVC_BF"] = mvc_bf
    env["EXO_MVC_ST"] = mvc_st
    
    processes = []
    
    try:
        # 1. multi_udp_v2.py
        processes.append(launch_script("multi_udp_v2.py", env))
        
        # Delay 5 seconds
        print("Waiting 5 seconds...")
        time.sleep(5)
        
        # 2. emg_novicon.py
        processes.append(launch_script("emg_novicon.py", env))
        
        # Delay 5 seconds
        print("Waiting 5 seconds...")
        time.sleep(5)
        
        # 3. nogrf_gaittiming.py
        processes.append(launch_script("nogrf_gaittiming.py", env))
        
        # Delay 15 seconds
        print(f"\nWaiting 15 seconds before launching {'RL online' if mode == '1' else 'Heuristic Controller'}...")
        for i in range(15):
            time.sleep(1)
            if i % 5 == 0 and i > 0:
                print(f"... {15-i} seconds left")
        
        if mode == "1":
            # 4. main_RL_online.py
            processes.append(launch_script("main_RL_online.py", env))
            
            # Wait till training starts and first action timings start
            print("Monitoring ZMQ port 4444 for first action timings from RL node...")
            context = zmq.Context()
            socket_sub = context.socket(zmq.SUB)
            socket_sub.setsockopt(zmq.LINGER, 0)
            socket_sub.setsockopt_string(zmq.SUBSCRIBE, "")
            # Connect to where RL publisher runs
            socket_sub.connect("tcp://localhost:4444")
            
            # Block until we receive something (using Poller so Ctrl+C isn't ignored)
            poller = zmq.Poller()
            poller.register(socket_sub, zmq.POLLIN)
            while True:
                # Poll for 1 second intervals to process KeyboardInterrupts safely
                socks = dict(poller.poll(1000))
                if socket_sub in socks:
                    first_timing = socket_sub.recv_pyobj()
                    print(f"-> Received first timings: {first_timing}")
                    print("RL Training has officially started!")
                    break
            
            socket_sub.close()
            
            # 5. nogrf_pressure_commands.py
            processes.append(launch_script("nogrf_pressure_commands.py", env))
        elif mode == "2":
            # 4. nogrf_heuristic_controller.py
            processes.append(launch_script("nogrf_heuristic_controller.py", env))
        else:
            print("\nSkipping Actuation Controllers (Data Collection Only)")
            
        print("\nLaunching Universal Nodes...")
        # 6. visualizer.py
        processes.append(launch_script("visualizer.py", env))
        
        print("\n=============================================")
        print("✅ All protocol scripts launched successfully!")
        print("=============================================")
        print("You can close this window to automatically terminate all running scripts.")
        print("Or Press [Enter] here to clean up and exit.")
        input()
        
    except KeyboardInterrupt:
        print("\nLauncher interrupted. Terminating processes...")
    finally:
        print("\nCleaning up processes...")
        for p in processes:
            # Recursively kill the cmd.exe process tree so the python child closes cleanly
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                p.wait(timeout=2)
            except:
                pass
                
        if mode != "3":
            print("\nEnsuring exosuit is deflated safely...")
            import pickle
            try:
                # Re-bind to the port now that children are dead
                deflate_context = zmq.Context()
                socket_export = deflate_context.socket(zmq.PUB)
                socket_export.setsockopt(zmq.LINGER, 500)
                socket_export.bind("tcp://192.168.0.103:8888")
                
                # ZMQ Pub/Sub requires a brief connection window
                time.sleep(0.5) 
                socket_export.send(pickle.dumps([0, 0], protocol=2))
                socket_export.close()
                deflate_context.term()
                print("==> Deflation Command [0, 0] published securely to Exosuit.")
            except Exception as e:
                print(f"Notice: Failed to send direct deflation command ({e})")
                
        print("All processes closed.")

if __name__ == "__main__":
    main()

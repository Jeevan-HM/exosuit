import numpy as np
from scipy import signal
from scipy.interpolate import splev, splrep 
import math
import zmq
from time import time, sleep
import csv
import itertools
from scipy.signal import find_peaks
import pandas as pd
from collections import deque
import threading
import queue
import os

from Gaitestimator_v2 import AdaptiveGaitController

# --- PARAMETERS ---
SubjectName = os.environ.get("EXO_SUBJECT", "Subject1")
TrialCondition = os.environ.get("EXO_CONDITION", "Cond1")
Trialnumber = os.environ.get("EXO_TRIAL", "1")
Incline = os.environ.get("EXO_INCLINE", "0").replace('.', 'p')
Speed = os.environ.get("EXO_SPEED", "1.0").replace('.', 'p')
Mode = os.environ.get("EXO_MODE", "RL")

mvc_VL = float(os.environ.get("EXO_MVC_VL", "2.8589158393545354e-05"))
mvc_RF = float(os.environ.get("EXO_MVC_RF", "8.45895919587837e-05"))
mvc_BF = float(os.environ.get("EXO_MVC_BF", "1.675776697178965e-05"))
mvc_ST = float(os.environ.get("EXO_MVC_ST", "1.0e-05"))

# IMU
ip_IMU = "localhost"
port_IMU = "1212"

# EMG
ip_EMG = "127.0.0.1"
port_EMG = "3000"

# RL Output
port_export = "3333"

# Fast Realtime Export (for Pressure Commands tracking)
port_realtime = "5555"

buffer_flush_size = 100

def terminate_experiment(event, sockets):
    print("Terminating Experiment...")
    try:
        event.set()
        sleep(1.5)
    except:
        pass
    for s in sockets:
        s.close()
    print("Closed.")
    exit()

def setup_communication_rcv(ip, port, context):
    socket = context.socket(zmq.SUB)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    socket.setsockopt(zmq.CONFLATE, True)
    socket.connect(f"tcp://{ip}:{port}")
    return socket

def test_connection(socket_input, socket_label):
    timeout_limit = 3000
    poller = zmq.Poller()
    poller.register(socket_input, zmq.POLLIN)
    socks = dict(poller.poll(timeout_limit))
    if socks:
        if socks.get(socket_input) == zmq.POLLIN:
            print(f"Connection Succesfull for: {socket_label}")
    else:
        print(f"**** ERROR: Connection FAILED for: {socket_label} ****")
        exit()

def receive_data(socket, port, result_queue, event):
    while True:
        value = socket.recv_pyobj()
        value = np.array(value)
        result_queue.put((port, value))
        if event.is_set():
            break

def emg_processing(emg_raw):
    # Exactly matching full_gait_timing.py
    fs = 2000
    lowcut = 20
    highcut = 450
    order = 4
    
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = signal.butter(order, [low, high], btype="band")
    emg_filtered = signal.lfilter(b, a, emg_raw)
    
    window = 0.25
    Hz = 2000
    method = 2
    
    emg_to_process = emg_filtered
    integral_window = round(window * Hz / method)
    signallength = len(emg_to_process)
    h = method / Hz
        
    I = np.zeros(math.ceil(signallength / 2))
    for a in range(math.floor(signallength / 2 - 1)):
        I[a] = h / 3 * (emg_to_process[a * 2 - 1]**2 + 4 * emg_to_process[a * 2]**2 + emg_to_process[a * 2 + 1]**2)
    
    cuml = np.zeros(len(I))
    cuml[0] = I[0]
    RMS = np.zeros(len(I))
    RMS[0] = math.sqrt(cuml[0] / h)
    
    for b in range(1, integral_window + 1):
        cuml[b] = cuml[b - 1] + I[b]
        RMS[b] = math.sqrt(cuml[b] / (b * h))
        
    for b in range(integral_window, len(I)):
        cuml[b] = cuml[b - 1] + I[b] - I[b - integral_window]
        RMS[b] = math.sqrt(cuml[b] / window)
        
    time_vect_temp = np.arange(0.002, 0.002 * (len(RMS) + 1), 0.002)
    time_vect_temp = (time_vect_temp * 1000).round()
    y = np.zeros(int(time_vect_temp[-1]))
    
    for i in range(len(time_vect_temp) - 2):
        lamda = (RMS[i + 1] - RMS[i]) / (time_vect_temp[i + 1] - time_vect_temp[i])
        t1 = round(time_vect_temp[i] + 1)
        t2 = round(time_vect_temp[i + 1])
        yy = RMS[i] + lamda * (np.arange(t1, t2 + 1, 1) - time_vect_temp[i])
        y[t1:t2 + 1] = yy
        
    RMS = y  
    
    temp = np.arange(1, len(RMS) + 1)
    x = 100 * (temp - np.min(temp)) / (np.max(temp) - np.min(temp))
    pgc = np.linspace(0, 100, 1001)

    spl = splrep(x, RMS)
    RMS_pgc = splev(pgc, spl) 

    N_Percent = 50
    N = int(len(RMS_pgc) * N_Percent / 100)
    RMS_sorted = np.sort(RMS_pgc)
    RMS_topN = RMS_sorted[-N:]
    
    integral_EMG = np.trapezoid(RMS_topN)
    return integral_EMG  

if __name__ == "__main__":
    import os
    import subprocess
    from time import sleep
    print(f"Ensuring export port {port_export} is clear...")
    try:
        res = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if f":{port_export}" in line and 'LISTENING' in line:
                pid = line.strip().split()[-1]
                if pid != '0':
                    subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
    except Exception:
        pass
    sleep(0.5)

    context = zmq.Context()
    
    socket_IMU = setup_communication_rcv(ip_IMU, port_IMU, context)
    socket_EMG = setup_communication_rcv(ip_EMG, port_EMG, context)
    
    socket_export = context.socket(zmq.PUB)
    socket_export.setsockopt(zmq.CONFLATE, True)
    socket_export.bind(f"tcp://*:{port_export}")
    
    socket_realtime = context.socket(zmq.PUB)
    socket_realtime.setsockopt(zmq.CONFLATE, True)
    socket_realtime.bind(f"tcp://*:{port_realtime}")
    
    Sockets_All = [socket_IMU, socket_EMG, socket_export, socket_realtime]

    test_connection(socket_IMU, "IMU")
    test_connection(socket_EMG, "EMG")
    sleep(2)
    
    result_queue = queue.Queue()
    event = threading.Event()
    
    thread_IMU = threading.Thread(target=receive_data, args=(socket_IMU, port_IMU, result_queue, event))
    thread_EMG = threading.Thread(target=receive_data, args=(socket_EMG, port_EMG, result_queue, event))
    
    thread_IMU.start()
    thread_EMG.start()
    
    controller = AdaptiveGaitController(calibration_duration=10.0)

    emg_VL, emg_RF, emg_BF, emg_ST = [], [], [], []
    no_muscles = 4
    
    emg_calibrated = False
    emg_scalar_VL = 1.0
    emg_scalar_RF = 1.0
    emg_scalar_BF = 1.0
    emg_scalar_ST = 1.0
    
    # Block-wise Averaging
    step_count = 0
    number_data_rcvd = 10
    average_array = np.zeros(number_data_rcvd)
    data_matrix = np.zeros((5, number_data_rcvd))
    
    os.makedirs(f"New_Collected_Data/Raw_data/{SubjectName}", exist_ok=True)
    os.makedirs(f"New_Collected_Data/Processed_data/{SubjectName}", exist_ok=True)
    
    raw_filename = f"New_Collected_Data/Raw_data/{SubjectName}/Raw_{SubjectName}_{TrialCondition}_{Mode}_inc{Incline}_spd{Speed}_{Trialnumber}.csv"
    processed_filename = f"New_Collected_Data/Processed_data/{SubjectName}/Processed_{SubjectName}_{TrialCondition}_{Mode}_inc{Incline}_spd{Speed}_{Trialnumber}.csv"
    
    raw_file = open(raw_filename, 'w', newline='')  # 'w' = fresh file each run, no header collision
    raw_writer = csv.writer(raw_file)
    raw_header = ["Time", "HS_Flag", "Knee_Angle", "EMG_VL", "EMG_RF", "EMG_BF", "EMG_ST"]
    raw_writer.writerow(raw_header)
    raw_buffer = []
    
    latest_emg = ["[]", "[]", "[]", "[]"]  # One 100-sample array string per muscle: VL, RF, BF, ST
    
    processed_file = open(processed_filename, 'a', newline='')
    processed_writer = csv.writer(processed_file)
    processed_writer.writerow([
        "u2_time", "u3_time", "u4_time",
        "stance_max_angle", "swing_max_angle",
        "emg_integral_VL", "emg_integral_RF", "emg_integral_BF", "emg_integral_ST", "gait_cycle_time"
    ])

    print("Starting Main Loop...")
    t0 = time()
    total_steps = 0
    try:
        while True:
            while not result_queue.empty():
                port, value = result_queue.get()
                
                if port == port_EMG:
                    emg_temp = value
                    no_samples = int(len(emg_temp) / no_muscles)
                    
                    chunk_VL = list(emg_temp[:no_samples])
                    chunk_RF = list(emg_temp[no_samples:no_samples*2])
                    chunk_BF = list(emg_temp[no_samples*2:no_samples*3])
                    chunk_ST = list(emg_temp[no_samples*3:no_samples*4])
                    
                    # Store each muscle's full 100-sample chunk as a string for the raw CSV
                    latest_emg = [
                        str(chunk_VL),
                        str(chunk_RF),
                        str(chunk_BF),
                        str(chunk_ST),
                    ]
                    
                    # Accumulate full raw samples for gait-cycle-level processing
                    emg_VL.extend(chunk_VL)
                    emg_RF.extend(chunk_RF)
                    emg_BF.extend(chunk_BF)
                    emg_ST.extend(chunk_ST)
                    
                elif port == port_IMU:
                    latest_imu = list(value)
                    current_time_from_zero = time() - t0
                    
                    # Based on logic parsed from multi_udp_v2.py
                    t_ang = value[0]
                    s_ang = value[1]
                    t_vel = value[2]
                    s_vel = value[3]
                    raw_knee_ang = value[4]
                    
                    res = controller.process_packet(
                        t_ang, s_ang, raw_knee_ang, t_vel, s_vel, timestamp=current_time_from_zero
                    )
                    
                    hs_flag = 1 if res.get('hs', False) else 0
                    if hs_flag == 1:
                        total_steps += 1
                        print(f"--- Heel Strike Detected! Step #{total_steps} ---")
                        
                    raw_buffer.append([current_time_from_zero, hs_flag, raw_knee_ang] + latest_emg)
                    
                    # Broadcast Heel Strike, Knee Angle, and Gait States to Visualizer
                    try:
                        k1_pct, k2_pct, k3_pct = res.get('thresholds', [15, 50, 80])
                        socket_realtime.send_pyobj({
                            "hs_flag": hs_flag, 
                            "knee_angle": raw_knee_ang,
                            "k1_pct": k1_pct,
                            "k2_pct": k2_pct,
                            "k3_pct": k3_pct,
                            "duration": controller.stride_duration
                        })
                    except:
                        pass
                    
                    if len(raw_buffer) >= 100:
                        raw_writer.writerows(raw_buffer)
                        raw_file.flush()
                        raw_buffer = []
                    
                    if res.get('status') == 'CALIBRATING':
                        continue
                        
                    if not emg_calibrated:
                        print("Calibrating EMG Scalars from 10s collected buffer...")
                        if len(emg_VL) > 200:
                            int_VL = emg_processing(np.array(emg_VL))
                            int_RF = emg_processing(np.array(emg_RF))
                            int_BF = emg_processing(np.array(emg_BF))
                            int_ST = emg_processing(np.array(emg_ST))
                            
                            val_VL = int_VL / mvc_VL
                            val_RF = int_RF / mvc_RF
                            val_BF = int_BF / mvc_BF
                            val_ST = int_ST / mvc_ST
                            
                            emg_scalar_VL = 0.25 / val_VL if val_VL > 0 else 1.0
                            emg_scalar_RF = 0.25 / val_RF if val_RF > 0 else 1.0
                            emg_scalar_BF = 0.25 / val_BF if val_BF > 0 else 1.0
                            emg_scalar_ST = 0.25 / val_ST if val_ST > 0 else 1.0
                            
                            print(f"Learned EMG Scalars -> VL: {emg_scalar_VL:.4f}, RF: {emg_scalar_RF:.4f}, BF: {emg_scalar_BF:.4f}, ST: {emg_scalar_ST:.4f}")
                        
                        emg_calibrated = True
                        emg_VL = []; emg_RF = []; emg_BF = []; emg_ST = []
                    
                    curr_time = res.get('time', current_time_from_zero)
                    
                    # Estimate stance vs swing using threshold logic used in Gaitestimator
                    stance_thr = 62 + 10 * (controller.stride_duration - 1.1)
                    is_stance = res['phase'] <= stance_thr
                    phase_label = 'stance' if is_stance else 'swing'
                    
                    if res.get('hs', False) == True and controller.is_calibrated:
                        duration = controller.stride_duration 
                        
                        stance_max_angle = res.get('k1_angle', 0.0)
                        swing_max_angle = res.get('k3_angle', 0.0)
                        
                        emg_gait_cycle_VL = emg_VL
                        emg_gait_cycle_RF = emg_RF
                        emg_gait_cycle_BF = emg_BF
                        emg_gait_cycle_ST = emg_ST
                        
                        emg_VL = []; emg_RF = []; emg_BF = []; emg_ST = []
                        
                        emg_integral_VL, emg_integral_RF, emg_integral_BF, emg_integral_ST = 0.0, 0.0, 0.0, 0.0
                        if len(emg_gait_cycle_VL) > 200:
                            emg_integral_VL = emg_processing(np.array(emg_gait_cycle_VL))
                            emg_integral_RF = emg_processing(np.array(emg_gait_cycle_RF))
                            emg_integral_BF = emg_processing(np.array(emg_gait_cycle_BF))
                            emg_integral_ST = emg_processing(np.array(emg_gait_cycle_ST))
                        
                        emg_integral_VL = (emg_integral_VL / mvc_VL) * emg_scalar_VL
                        emg_integral_RF = (emg_integral_RF / mvc_RF) * emg_scalar_RF
                        emg_integral_BF = (emg_integral_BF / mvc_BF) * emg_scalar_BF
                        emg_integral_ST = (emg_integral_ST / mvc_ST) * emg_scalar_ST
                        
                        u2_time = res['thresholds'][0] / 100.0  
                        u3_time = res['thresholds'][1] / 100.0  
                        u4_time = res['thresholds'][2] / 100.0  
                        
                        data_array = np.array([
                            u2_time, u3_time, u4_time, 
                            stance_max_angle, swing_max_angle, 
                            emg_integral_VL, emg_integral_RF, emg_integral_BF, emg_integral_ST,
                            duration
                        ])
                        
                        data_matrix[step_count] = data_array
                        step_count += 1
                        average_array += data_array
                        
                        processed_writer.writerow(data_array)
                        processed_file.flush()
                        
                        if step_count == 5:
                            combinations = list(itertools.combinations(range(5), 4))
                            best_std = float('inf')
                            best_avg = None

                            for combo in combinations:
                                subset = data_matrix[list(combo), :]
                                std_sum = np.sum(np.std(subset, axis=0))
                                if std_sum < best_std:
                                    best_std = std_sum
                                    best_avg = np.mean(subset, axis=0)
                            
                            print("Sending Data to RL")
                            socket_export.send_pyobj(best_avg)
                            
                            print("\n=== SENT TO RL (Best Avg of 4 out of 5 cycles) ===")
                            print(f"u2_time: {best_avg[0]:.4f}")
                            print(f"u3_time: {best_avg[1]:.4f}")
                            print(f"u4_time: {best_avg[2]:.4f}")
                            print(f"Stance Max Angle: {best_avg[3]:.4f}")
                            print(f"Swing Max Angle:  {best_avg[4]:.4f}")
                            print(f"EMG Integrals (VL, RF, BF, ST): {best_avg[5]:.6f}, {best_avg[6]:.6f}, {best_avg[7]:.6f}, {best_avg[8]:.6f}")
                            print(f"EMG SUM: {best_avg[5] + best_avg[6] + best_avg[7] + best_avg[8]:.6f}")
                            print(f"Gait Cycle Time:  {best_avg[9]:.4f}")
                            print("==================================================\n")
                            
                            step_count = 0
                            data_matrix[:] = 0
                            average_array = np.zeros(number_data_rcvd)
                        
                        knee_phase_buffer = []

            sleep(0.001)

    except KeyboardInterrupt:
        print("Stopped by User.")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if raw_buffer:
            raw_writer.writerows(raw_buffer)
            raw_file.flush()
        raw_file.close()
        processed_file.close()
        terminate_experiment(event, Sockets_All)

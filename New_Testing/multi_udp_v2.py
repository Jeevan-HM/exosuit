# -*- coding: utf-8 -*-
"""
Created on Thu Aug 28 13:45:32 2025

@author: Jahnav Rokalaboina
"""

# -*- coding: utf-8 -*-

# Two-IMU UDP receiver that:
#  - Parses IMU frames using your DeviceModel
#  - Publishes a 14-float array over ZMQ PUB (same shape you had)
#  - NEW: On first contact per device, sends CALSW=0x0008 ("set current orientation as angle reference")
#         so roll/pitch/yaw all zero at startup.
import asyncio
import signal
import socket
import zmq
import numpy as np
from scipy.spatial.transform import Rotation as R
from device_model import DeviceModel
from time import time, sleep
from typing import Dict, Tuple, Optional
import csv
import os

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
SubjectName = os.environ.get("EXO_SUBJECT", "Subject1")
TrialCondition = os.environ.get("EXO_CONDITION", "Cond1")
Trialnumber = os.environ.get("EXO_TRIAL", "1")
Incline = os.environ.get("EXO_INCLINE", "0").replace('.', 'p')
Speed = os.environ.get("EXO_SPEED", "1.0").replace('.', 'p')
Mode = os.environ.get("EXO_MODE", "RL")

HOST = "192.168.0.103"
PORT1 = 1398
PORT2 = 1399
ZMQ_BIND = "tcp://*:1212"

# TARGET FREQUENCY (Hz) - The Metronome
TARGET_FPS = 150.0 

WT_HEADER0 = 0x57
WT_HEADER1 = 0x54
FULL_FRAME_LEN = 54 
print("running")
def _build_write_frame(addr_reg: int, value: int) -> bytes:
    return bytes([0xFF, 0xAA, addr_reg & 0xFF, value & 0xFF, (value >> 8) & 0xFF])

# ---------------------------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------------------------
os.makedirs(f"Raw_IMU_Data/{SubjectName}", exist_ok=True)
raw_data_filename = f"Raw_IMU_Data/{SubjectName}/Raw_IMU_{SubjectName}_{TrialCondition}_{Mode}_inc{Incline}_spd{Speed}_{Trialnumber}.csv"
raw_data_file = open(raw_data_filename, 'w', newline='')
raw_data_writer = csv.writer(raw_data_file)
# Note: Added 'Timestamp' to header
raw_data_writer.writerow(["timestamp", "Thigh X", "Thigh Y", "Thigh Z", "Thigh Xd", "Thigh Yd", "Thigh Zd", "Shank X", "Shank Y", "Shank Z", "Shank Xd", "Shank Yd", "Shank Zd", "Knee Angle"])

raw_data_buffer = []
buffer_flush_size = 100

def flush_raw_buffer():
    global raw_data_buffer
    if raw_data_buffer:
        raw_data_writer.writerows(raw_data_buffer)
        raw_data_file.flush()
        raw_data_buffer = []

CALSW_ADDR = 0x01
SET_ANGLE_REF_NOW = 0x0008 

def calculate_knee_angle(thigh_angles, shank_angles):
    q_thigh = R.from_euler('xyz', thigh_angles, degrees=True).as_quat()
    q_shank = R.from_euler('xyz', shank_angles, degrees=True).as_quat()
    r_thigh = R.from_quat(q_thigh)
    r_shank = R.from_quat(q_shank)
    r_relative = r_shank * r_thigh.inv()
    relative_euler = r_relative.as_euler('xyz', degrees=True)
    return relative_euler[0]

async def update_data(port, device: DeviceModel, queue: asyncio.Queue):
    try:
        angles = np.array([
            device.deviceData.get("AngleX", 0.0),
            device.deviceData.get("AngleY", 0.0),
            device.deviceData.get("AngleZ", 0.0),
        ], dtype=float)

        ang_vel = np.array([
            device.deviceData.get("AsX", 0.0),
            device.deviceData.get("AsY", 0.0),
            device.deviceData.get("AsZ", 0.0),
        ], dtype=float)

        await queue.put((port, angles, ang_vel))
    except Exception as e:
        print(f"Error in update_data: {e}")

async def start_udp_service(host: str, port: int, queue: asyncio.Queue):
    device_list: Dict[str, DeviceModel] = {}
    device_addr: Dict[str, Tuple[str, int]] = {}   
    sent_zero: set[str] = set()                    
    temp_buffer = bytearray()
    current_device_id: Optional[str] = None

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setblocking(False) 
    try:
        udp_socket.bind((host, port))
    except Exception as e:
        print(f"Bind Error on {port}: {e}")
        return

    print(f"UDP server started on {host}:{port}.")
    loop = asyncio.get_event_loop()

    while True:
        try:
            data, addr = await loop.run_in_executor(None, lambda: udp_socket.recvfrom(1024))
            for b in data:
                temp_buffer.append(b)
                if len(temp_buffer) == 2 and not (temp_buffer[0] == WT_HEADER0 and temp_buffer[1] == WT_HEADER1):
                    del temp_buffer[0]
                    continue

                if current_device_id is None and len(temp_buffer) >= 12:
                    try:
                        dev_id = bytes(temp_buffer[:12]).decode('ascii', errors='ignore')
                        if dev_id:
                            current_device_id = dev_id
                            device_addr[dev_id] = addr
                            if dev_id not in device_list:
                                device_list[dev_id] = DeviceModel(
                                    dev_id,
                                    lambda d, p=port: asyncio.create_task(update_data(p, d, queue))
                                )
                            if dev_id not in sent_zero:
                                frame = _build_write_frame(CALSW_ADDR, SET_ANGLE_REF_NOW)
                                udp_socket.sendto(frame, device_addr[dev_id])
                                sent_zero.add(dev_id)
                                print(f"[{port}] Zeroed {dev_id}")
                    except Exception:
                        pass

                if len(temp_buffer) == FULL_FRAME_LEN:
                    dev = device_list.get(current_device_id or "")
                    if dev:
                        dev.onDataReceived(temp_buffer)
                    temp_buffer.clear()
                    current_device_id = None
        except Exception:
            await asyncio.sleep(0.001)

async def main():
    host = HOST
    data_queue = asyncio.Queue()

    # ZMQ PUB
    context = zmq.Context()
    socket_data_export = context.socket(zmq.PUB)
    # CONFLATE=True ensures the subscriber only gets the LATEST message if it falls behind
    socket_data_export.setsockopt(zmq.CONFLATE, True)
    socket_data_export.bind(ZMQ_BIND)
    print(f"ZMQ PUB bound at {ZMQ_BIND} | Streaming at {TARGET_FPS} Hz")

    task1 = asyncio.create_task(start_udp_service(host, PORT1, data_queue))
    task2 = asyncio.create_task(start_udp_service(host, PORT2, data_queue))

    export_array = np.zeros(14, dtype=float)
    fin_exp = np.zeros(6, dtype=float)

    shutdown_signal = asyncio.Future()
    def stop_loop(*args): shutdown_signal.set_result(None)
    signal.signal(signal.SIGINT, stop_loop)
    
    t0 = time()
    
    # --- METRONOME SETUP ---
    period = 1.0 / TARGET_FPS
    next_tick = time() + period

    try:
        while not shutdown_signal.done():
            # 1. Drain the Queue (Update State)
            # We process ALL pending UDP packets to get the absolute latest state
            # but we DO NOT send ZMQ here.
            while not data_queue.empty():
                port, angles, ang_vel = await data_queue.get()
                
                if port == PORT1:
                    export_array[1:4] = angles
                    export_array[4:7] = ang_vel
                elif port == PORT2:
                    export_array[7:10] = angles
                    export_array[10:13] = ang_vel

            # 2. Check Clock (Transmit Phase)
            now = time()
            if now >= next_tick:
                # Calculate Knee Angle on the synced state
                export_array[13] = calculate_knee_angle(export_array[1:4], export_array[7:10])
                export_array[0] = now - t0 # Accurate Timestamp

                # Pack for ZMQ
                fin_exp[0] = export_array[1] # T_X
                fin_exp[1] = export_array[7] # S_X
                fin_exp[2] = export_array[4] # T_Vel
                fin_exp[3] = export_array[10]# S_Vel
                fin_exp[4] = export_array[13]# Knee
                fin_exp[5] = export_array[0] # Timestamp
                
                # Send & Log
                # We send even if data hasn't changed (Zero-Order Hold) to maintain frequency
                socket_data_export.send_pyobj(fin_exp.tolist())
                
                raw_data_buffer.append(export_array.copy())
                if len(raw_data_buffer) >= buffer_flush_size:
                    flush_raw_buffer()

                # Schedule next tick
                next_tick += period
                # Catch up if we lagged significantly (prevent burst of sends)
                if now > next_tick + period:
                    next_tick = now + period

            # 3. Sleep briefly to yield to the asyncio loop (UDP listeners)
            # Calculate remaining time to minimize jitter
            time_to_wait = next_tick - time()
            if time_to_wait > 0:
                await asyncio.sleep(time_to_wait)
            else:
                await asyncio.sleep(0.001) # Minimal yield if running late
            
    finally:
        flush_raw_buffer()
        raw_data_file.close()
        task1.cancel()
        task2.cancel()
        print("Closed.")

if __name__ == "__main__":
    asyncio.run(main())
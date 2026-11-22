import zmq
import time
import math
import numpy as np
import pandas as pd
from scipy import signal
from collections import deque

# ==========================================
# CONFIGURATION
# ==========================================
# Nominal frequency for filter design (must match roughly what you expect)
SYSTEM_FS = 150.0 

# ==========================================================
# HELPER CLASS: STATEFUL BUTTERWORTH FILTER
# ==========================================================
class ButterFilter:
    def __init__(self, fs, fc=20.0, order=2):
        """
        Stateful Butterworth Filter. 
        Maintains internal state (zi) to allow stream processing.
        """
        self.sos = signal.butter(order, fc, 'low', fs=fs, output='sos')
        self.zi = signal.sosfilt_zi(self.sos)
    
    def process(self, x):
        x_filt, self.zi = signal.sosfilt(self.sos, [x], zi=self.zi)
        return x_filt[0]

# ==========================================================
# MAIN CONTROLLER CLASS
# ==========================================================
class AdaptiveGaitController:
    def __init__(self, fs=SYSTEM_FS, calibration_duration=4.0):
        # --- CONFIGURATION ---
        self.fs = fs
        self.dt = 1.0 / fs
        self.calibration_duration = calibration_duration
        
        # --- CONTROL FLAGS ---
        self.ENABLE_START_STOP   = True 
        self.ENABLE_SPEED_EST    = True
        self.ENABLE_NORM_KNEE    = True 
        self.ENABLE_ROBUST_LEARN = True
        self.ENABLE_LOGGING      = True
        
        # --- SYSTEM STATE ---
        self.is_calibrated = False
        self.calibration_buffer = [] 
        self.start_time = 0.0 
        self.current_time = 0.0
        self.log_buffer = []
        self.learning_count = 0 
        
        # Anthropometry (Meters)
        self.L_thigh = 0.45
        self.L_shank = 0.43
        
        # --- FILTERS ---
        self.fil_t_ang = ButterFilter(fs, fc=6)
        self.fil_s_ang = ButterFilter(fs, fc=6)
        self.fil_k_ang = ButterFilter(fs, fc=6)
        self.fil_t_vel = ButterFilter(fs, fc=10) # Higher cutoff for velocity
        self.fil_s_vel = ButterFilter(fs, fc=10)

        # --- PHASE PORTRAIT STATS ---
        # Learned during calibration, updated slowly in real-time
        self.theta_mean = 0.0
        self.theta_var = 1.0
        self.w_mean = 0.0
        self.w_var = 1.0
        self.alpha = 0.001 # Slow adaptation rate

        # --- GAIT STATE VARIABLES ---
        self.last_hs_time = 0.0
        self.stride_duration = 1.1
        self.gait_phase_percent = 0.0
        self.prev_gait_phase = 0.0
        self.is_stance = True
        self.current_zone = 4 
        
        # Start/Stop Logic
        self.is_walking = False 
        self.stop_timer = 0.0
        self.start_timer = 0.0
        self.orbit_radius = 0.0
        self.radius_filtered = 0.0 
        self.est_speed = 0.0
        
        # Knee Normalization Bounds
        self.thigh_min_curr = 999; self.thigh_max_curr = -999
        self.knee_min_hist = 0.0; self.knee_max_hist = 60.0 
        self.curr_k_min = 999; self.curr_k_max = -999
        self.normalized_knee = 0.0
        self.knee_zero_offset = 0.0  # Calibration offset: subtracted from all raw peak angles

        # --- ADAPTIVE THRESHOLDS ---
        # Defaults (overwritten by calibration)
        self.thr_k1 = 15.0
        self.thr_k2 = 50.0
        self.thr_k3 = 80.0
        
        # History buffers for median/smoothing logic
        self.hist_k1 = deque(maxlen=5)
        self.hist_k2 = deque(maxlen=5)
        self.hist_k3 = deque(maxlen=5)
        
        self.last_k1_angle = 15.0
        self.last_k3_angle = 60.0
        
        self.reset_stride_trackers()

    def reset_stride_trackers(self):
        """Resets min/max trackers for the new stride."""
        self.thigh_min_curr = 999; self.thigh_max_curr = -999
        self.curr_k_min = 999; self.curr_k_max = -999
        # Reset peak locations to defaults so they don't carry over if not found
        self.loc_k1_peak = 15; self.loc_k2_valley = 50; self.loc_k3_peak = 80
        # Internal temp storage
        self._temp_k1_val = -999; self._temp_k2_val = 999; self._temp_k3_val = -999
        self.k1_angle_raw = 0.0; self.k3_angle_raw = 0.0

    # ==========================================================
    # 1. CORE MATH
    # ==========================================================
    
    def _update_filters(self, t, s, k, tv, sv):
        ft = self.fil_t_ang.process(t)
        fs = self.fil_s_ang.process(s)
        fk = self.fil_k_ang.process(k)
        ftv = self.fil_t_vel.process(tv)
        fsv = self.fil_s_vel.process(sv)
        return ft, fs, fk, ftv, fsv

    def _calculate_phase(self, q_t, q_s, w_t, w_s):
        # Geometry
        q_t_rad = np.deg2rad(q_t); q_s_rad = np.deg2rad(q_s)
        x = self.L_thigh * np.sin(q_t_rad) + self.L_shank * np.sin(q_s_rad)
        z = self.L_thigh * np.cos(q_t_rad) + self.L_shank * np.cos(q_s_rad)
        theta = -np.arctan2(x, z) 
        
        # Velocity
        w_t_rad = np.deg2rad(w_t); w_s_rad = np.deg2rad(w_s)
        x_dot = self.L_thigh * np.cos(q_t_rad) * w_t_rad + self.L_shank * np.cos(q_s_rad) * w_s_rad
        z_dot = -self.L_thigh * np.sin(q_t_rad) * w_t_rad - self.L_shank * np.sin(q_s_rad) * w_s_rad
        
        num = (x_dot * z) - (x * z_dot)
        den = (x**2 + z**2)
        if den == 0: den = 0.0001
        theta_dot = -(num / den)
        
        # Normalize
        MIN_VAR = 0.01 
        std_theta = np.sqrt(max(self.theta_var, MIN_VAR))
        std_w = np.sqrt(max(self.w_var, MIN_VAR))
        
        norm_pos = (theta - self.theta_mean) / std_theta
        norm_vel = (theta_dot - self.w_mean) / std_w
        
        # Radius Calculation
        self.orbit_radius = math.sqrt(norm_pos**2 + norm_vel**2)
        self.radius_filtered = 0.1 * self.orbit_radius + 0.9 * self.radius_filtered
        
        # Phase Angle
        phase_raw = np.arctan2(-norm_vel, norm_pos)
        if phase_raw < 0: phase_raw += 2 * np.pi
        
        return (phase_raw / (2 * np.pi)) * 100.0, norm_pos, norm_vel, theta, theta_dot

    # ==========================================================
    # 2. BATCH CALIBRATION (FULL IMPLEMENTATION)
    # ==========================================================
    
    def _run_batch_calibration(self):
        """
        Analyzes the calibration buffer to:
        1. Center the Phase Portrait (Mean/Var).
        2. Learn user-specific Zone Thresholds (K1/K2/K3).
        """
        print(f"[CALIBRATION] Processing {len(self.calibration_buffer)} samples...")
        data = np.array(self.calibration_buffer)
        
        thetas = []
        theta_dots = []
        
        # --- A. Phase Portrait Stats ---
        for i in range(len(data)):
            t, s, k, tv, sv = data[i]
            q_t_rad = np.deg2rad(t); q_s_rad = np.deg2rad(s)
            x = self.L_thigh * np.sin(q_t_rad) + self.L_shank * np.sin(q_s_rad)
            z = self.L_thigh * np.cos(q_t_rad) + self.L_shank * np.cos(q_s_rad)
            th = -np.arctan2(x, z)
            
            w_t_rad = np.deg2rad(tv); w_s_rad = np.deg2rad(sv)
            x_dot = self.L_thigh * np.cos(q_t_rad) * w_t_rad + self.L_shank * np.cos(q_s_rad) * w_s_rad
            z_dot = -self.L_thigh * np.sin(q_t_rad) * w_t_rad - self.L_shank * np.sin(q_s_rad) * w_s_rad
            th_d = -((x_dot * z) - (x * z_dot)) / (x**2 + z**2)
            
            thetas.append(th)
            theta_dots.append(th_d)
            
        self.theta_mean = np.mean(thetas)
        self.theta_var = np.var(thetas)
        self.w_mean = np.mean(theta_dots)
        self.w_var = np.var(theta_dots)
        self.radius_filtered = 0.0 # Reset to avoid spike
        
        print(f"[CALIBRATION] Stats -> Theta Mean: {self.theta_mean:.3f}")

        # --- B. Retroactive Peak Learning ---
        phases = []
        std_theta = np.sqrt(max(self.theta_var, 0.01))
        std_w = np.sqrt(max(self.w_var, 0.01))
        
        # Calculate Phase for the whole buffer
        for i in range(len(thetas)):
            np_pos = (thetas[i] - self.theta_mean) / std_theta
            np_vel = (theta_dots[i] - self.w_mean) / std_w
            ph = np.arctan2(-np_vel, np_pos)
            if ph < 0: ph += 2*np.pi
            phases.append((ph / (2*np.pi)) * 100.0)
            
        # Detect Heel Strikes
        hs_idx = [i for i in range(1, len(phases)) if phases[i-1] > 90 and phases[i] < 10]
        
        if len(hs_idx) < 2:
            print("[CALIBRATION] Not enough strides found. Using defaults (15/50/80).")
        else:
            print(f"[CALIBRATION] Learning from {len(hs_idx)-1} strides...")
            knee_data = data[:, 2] # Col 2 is Knee
            
            # Find Global Min/Max for Normalization
            k_min = np.min(knee_data)
            k_max = np.max(knee_data)
            self.knee_min_hist = k_min
            self.knee_max_hist = k_max
            # Use calibration minimum as the zero-extension reference to correct
            # for IMU mounting offset. All reported peak angles will be relative
            # to this standing/extension baseline.
            self.knee_zero_offset = k_min
            print(f"[CALIBRATION] Knee zero offset set to {self.knee_zero_offset:.2f} deg (sensor mounting correction)")
            
            # Iterate strides
            for k in range(len(hs_idx)-1):
                start = hs_idx[k]; end = hs_idx[k+1]
                s_phase = phases[start:end]
                s_knee = knee_data[start:end]
                
                # Normalize using the bounds we just found
                s_knee_norm = (s_knee - k_min) / (k_max - k_min + 0.001)
                
                # Default Peaks
                l_k1, l_k2, l_k3 = 15, 50, 80
                
                # K1 (Max Flexion in 0-25%)
                mask = [p < 25 for p in s_phase]
                if any(mask): 
                    # Note: Need index relative to stride, not buffer
                    valid_indices = [j for j, m in enumerate(mask) if m]
                    # Find index of max knee within valid indices
                    relative_idx = valid_indices[np.argmax([s_knee_norm[j] for j in valid_indices])]
                    l_k1 = s_phase[relative_idx]
                    
                # K2 (Min Extension in 25-65%)
                mask = [(p > 25 and p < 65) for p in s_phase]
                if any(mask):
                    valid_indices = [j for j, m in enumerate(mask) if m]
                    relative_idx = valid_indices[np.argmin([s_knee_norm[j] for j in valid_indices])]
                    l_k2 = s_phase[relative_idx]
                    
                # K3 (Max Flexion in 65-98%)
                mask = [(p > 65 and p < 98) for p in s_phase]
                if any(mask):
                    valid_indices = [j for j, m in enumerate(mask) if m]
                    relative_idx = valid_indices[np.argmax([s_knee_norm[j] for j in valid_indices])]
                    l_k3 = s_phase[relative_idx]
                
                self.hist_k1.append(l_k1)
                self.hist_k2.append(l_k2)
                self.hist_k3.append(l_k3)
            
            # Apply Learned Averages
            if len(self.hist_k1) > 0: self.thr_k1 = np.mean(self.hist_k1)
            if len(self.hist_k2) > 0: self.thr_k2 = np.mean(self.hist_k2)
            if len(self.hist_k3) > 0: self.thr_k3 = np.mean(self.hist_k3)
            
            print(f"[CALIBRATION] Zones Set -> K1:{self.thr_k1:.1f} | K2:{self.thr_k2:.1f} | K3:{self.thr_k3:.1f}")
        
        self.calibration_buffer = []
        self.is_calibrated = True

    # ==========================================================
    # 3. LOGIC & LEARNING
    # ==========================================================

    def _check_start_stop(self):
        STOP_THRESHOLD = 0.5 
        WALK_THRESHOLD = 0.8 
        TIME_TO_STOP = 0.2
        TIME_TO_START = 0.1 
        
        if self.radius_filtered < STOP_THRESHOLD:
            self.stop_timer += self.dt
            self.start_timer = 0 
            if self.stop_timer > TIME_TO_STOP:
                self.is_walking = False
        elif self.radius_filtered > WALK_THRESHOLD:
            self.start_timer += self.dt
            self.stop_timer = 0 
            if self.start_timer > TIME_TO_START:
                self.is_walking = True
        return self.is_walking

    def _update_learning_ema(self):
        alpha = 0.3
        self.learning_count += 1
        
        # Sanity check: Ensure peaks are sequential
        if self.loc_k1_peak < self.loc_k2_valley:
             self.thr_k1 = (1-alpha)*self.thr_k1 + alpha*self.loc_k1_peak
        if self.loc_k2_valley < self.loc_k3_peak:
             self.thr_k2 = (1-alpha)*self.thr_k2 + alpha*self.loc_k2_valley
        if self.loc_k3_peak > 60:
             self.thr_k3 = (1-alpha)*self.thr_k3 + alpha*self.loc_k3_peak

        # Update Knee Normalization Bounds
        if (self.curr_k_max - self.curr_k_min) > 10:
            self.knee_min_hist = (1 - alpha) * self.knee_min_hist + alpha * self.curr_k_min
            self.knee_max_hist = (1 - alpha) * self.knee_max_hist + alpha * self.curr_k_max

    def _track_peaks(self, phase, raw_knee, raw_thigh):
        # Track Extremas
        if raw_thigh > self.thigh_max_curr: self.thigh_max_curr = raw_thigh
        if raw_thigh < self.thigh_min_curr: self.thigh_min_curr = raw_thigh
        if raw_knee > self.curr_k_max: self.curr_k_max = raw_knee
        if raw_knee < self.curr_k_min: self.curr_k_min = raw_knee
        
        # Normalize
        rng = max(1.0, self.knee_max_hist - self.knee_min_hist)
        k_norm = (raw_knee - self.knee_min_hist) / rng
        self.normalized_knee = k_norm
        
        # Track Peaks relative to Phase
        if phase < 25:
            if k_norm > self._temp_k1_val:
                self._temp_k1_val = k_norm; self.loc_k1_peak = phase
                # Subtract calibration offset so angle is relative to full-extension baseline
                self.k1_angle_raw = raw_knee - self.knee_zero_offset
        elif 25 < phase < 65:
            if k_norm < self._temp_k2_val:
                self._temp_k2_val = k_norm; self.loc_k2_valley = phase
        elif 65 < phase < 98:
            if k_norm > self._temp_k3_val:
                self._temp_k3_val = k_norm; self.loc_k3_peak = phase
                # Subtract calibration offset so angle is relative to full-extension baseline
                self.k3_angle_raw = raw_knee - self.knee_zero_offset

    # ==========================================================
    # 4. REAL-TIME LOOP
    # ==========================================================

    def process_packet(self, t_ang, s_ang, raw_knee_ang, t_vel, s_vel, timestamp=None):
        # --- TIME HANDLING (FIXED) ---
        if timestamp is not None:
            # DEPLOYMENT: Use real timestamp
            if self.current_time == 0.0:
                self.start_time = timestamp
                self.current_time = timestamp
            else:
                self.dt = timestamp - self.current_time # Dynamic dt
                self.current_time = timestamp
        else:
            # SIMULATION: Fixed step
            self.current_time += self.dt
            if self.start_time == 0.0: self.start_time = 0.0

        # 1. Filter
        ft, fs, fk, ftv, fsv = self._update_filters(t_ang, s_ang, raw_knee_ang, t_vel, s_vel)
        
        # --- CALIBRATION ---
        if not self.is_calibrated:
            self.calibration_buffer.append([ft, fs, fk, ftv, fsv])
            elapsed = self.current_time - self.start_time
            if elapsed > self.calibration_duration:
                self._run_batch_calibration()
            return {"status": "CALIBRATING", "time": elapsed}

        # --- ACTIVE STATE ---
        new_phase, n_pos, n_vel, theta, theta_dot = self._calculate_phase(ft, fs, ftv, fsv)
        
        # Update Stats (Running Average)
        self.theta_mean = (1 - self.alpha) * self.theta_mean + self.alpha * theta
        self.theta_var = (1 - self.alpha) * self.theta_var + self.alpha * (theta - self.theta_mean)**2
        self.w_mean = (1 - self.alpha) * self.w_mean + self.alpha * theta_dot
        self.w_var = (1 - self.alpha) * self.w_var + self.alpha * (theta_dot - self.w_mean)**2

        # Start/Stop
        if self.ENABLE_START_STOP:
            is_walking = self._check_start_stop()
            if is_walking: 
                self.gait_phase_percent = new_phase
            else:
                pass
        else:
            self.gait_phase_percent = new_phase
            self.is_walking = True

        # Heel Strike Logic
        hs_event = False
        if self.is_walking and (self.prev_gait_phase > 90 and self.gait_phase_percent < 10):
            hs_event = True
            dur = self.current_time - self.last_hs_time
            if dur < 3.0: 
                self.stride_duration = max(0.6, min(dur, 2.0))
            self.last_hs_time = self.current_time
            
            # Update Estimators
            if self.ENABLE_SPEED_EST:
                cadence = 1.0 / self.stride_duration
                rom = self.thigh_max_curr - self.thigh_min_curr
                self.est_speed = 0.015 * cadence * rom
            
            if self.ENABLE_ROBUST_LEARN:
                self._update_learning_ema()
                
            self.last_k1_angle = self.k1_angle_raw
            self.last_k3_angle = self.k3_angle_raw
                
            self.reset_stride_trackers()

        # Peak Tracking
        if self.ENABLE_NORM_KNEE:
            self._track_peaks(self.gait_phase_percent, fk, ft)

        # Zone Classification
        stance_thr = 62 + 10 * (self.stride_duration - 1.1)
        self.is_stance = (self.gait_phase_percent <= stance_thr)
        
        gp = self.gait_phase_percent
        if gp <= self.thr_k1: zone = 1
        elif gp <= self.thr_k2: zone = 2
        elif gp <= self.thr_k3: zone = 3
        else: zone = 4
        self.current_zone = zone

        self.prev_gait_phase = self.gait_phase_percent
        
        if self.ENABLE_LOGGING:
            row = [
                self.current_time,
                t_ang, s_ang, raw_knee_ang, t_vel, s_vel,
                ft, fs, fk, ftv, fsv,
                self.gait_phase_percent, int(self.is_stance), self.current_zone, int(hs_event), int(self.is_walking),
                self.est_speed, self.normalized_knee,
                self.thr_k1, self.thr_k2, self.thr_k3
            ]
            self.log_buffer.append(row)
        
        # return {
        #     "status": "RUNNING", "phase": self.gait_phase_percent, "zone": self.current_zone, 
        #     "hs": hs_event, "walking": self.is_walking, "speed": self.est_speed, "knee_norm": self.normalized_knee
        # }
        # ... inside process_packet ...
        return {
            "status": "RUNNING", 
            "phase": self.gait_phase_percent, 
            "zone": self.current_zone, 
            "hs": hs_event, 
            "walking": self.is_walking, 
            "speed": self.est_speed, 
            "knee_norm": self.normalized_knee,
            "raw_knee": raw_knee_ang,
            "time": self.current_time,  # <--- ADD THIS
            "thresholds": [self.thr_k1, self.thr_k2, self.thr_k3], # <--- ADD THIS
            "k1_angle": self.last_k1_angle,
            "k3_angle": self.last_k3_angle
        }
    
    def save_log_to_csv(self, filename="Processed_Data/Jahnav_test.csv"):
        if not self.log_buffer: return
        print(f"Saving {len(self.log_buffer)} samples...")
        cols = [
            "Time", "Raw_T", "Raw_S", "Raw_K", "Raw_TV", "Raw_SV",
            "Filt_T", "Filt_S", "Filt_K", "Filt_TV", "Filt_SV",
            "Phase", "Stance", "Zone", "HS", "IsWalking", "Speed", "KneeNorm",
            "Thr_K1", "Thr_K2", "Thr_K3"
        ]
        pd.DataFrame(self.log_buffer, columns=cols).to_csv(filename, index=False)
        print("Saved.")

def run_zmq_listener():
    context = zmq.Context()
    
    # 1. INPUT: Subscribe to sensor stream
    sub_socket = context.socket(zmq.SUB)
    sub_socket.connect("tcp://localhost:1111")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, '')
    
    # 2. OUTPUT: Publish to Visualizer
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://*:5555")
    
    print("Listening on :1111 | Publishing to :5555...")

    controller = AdaptiveGaitController(calibration_duration=10.0)
    IDX_T=0; IDX_S=1; IDX_TV=2; IDX_SV=3; IDX_K=4; IDX_TIME=5

    try:
        while True:
            data = sub_socket.recv_pyobj()
            t_stamp = float(data[IDX_TIME]) if len(data) >= 6 else None

            res = controller.process_packet(
                float(data[IDX_T]), float(data[IDX_S]), float(data[IDX_K]), 
                float(data[IDX_TV]), float(data[IDX_SV]),
                timestamp=t_stamp
            )
            
            # Send data to Visualizer
            if res['status'] == "RUNNING":
                pub_socket.send_json(res)
                
                # Optional Console Log
                # z_str = {1:"K1", 2:"K2", 3:"K3", 4:"K4"}.get(res['zone'], "?")
                # print(f"Ph:{res['phase']:5.1f}% | {z_str}")

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        controller.save_log_to_csv()
        sub_socket.close()
        pub_socket.close()
        context.term()
        
        
if __name__ == "__main__":
    run_zmq_listener()
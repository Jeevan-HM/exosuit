"""
main.py - Reinforcement Learning Algorithm for Exosuit

Versions:
    v1 - junmin modified, first implementation of the offline RL algorithm
    v2 - bug-fixed online version (see header notes below)

Fixes applied in this version (keeps original structure):
    Bug #1 - online actor/target updates now actually fire: a step counter is
             passed into policy.train(...) so `step % policy_freq` can hit 0.
    Bug #2 - argparse hyperparameters are now wired into TDR via kwargs
             (policy_noise, noise_clip, policy_freq were previously ignored).
    (Bugs #3, #4, #5 and the actor-loss sign are fixed inside TDR_SM_fixed.py.)
"""

import numpy as np
import csv
from numpy import genfromtxt
from TDR_SM import TDR   # FIX: import the bug-fixed TDR module
import matplotlib.pyplot as plt
import numpy as np
import argparse
import os
import ReplayBuffer
import torch
#ZMQ Communication Libraries:
import zmq
import math

plt.close('all')  #close all plots

#Remove All Variables in Spyder Console:
from sys import exit #for debug: adds exit() function to spyder
try:
    from IPython import get_ipython
    get_ipython().magic('reset -f') #clear memory/variables
    get_ipython().magic('clear')  #clear screen
except:
    pass

def denormalize(x_norm, x_min, x_max):
    return (x_norm + 1) * 0.5 * (x_max - x_min) + x_min


def normalize(x,  x_min, x_max):
    return 2 * (x - x_min) / (x_max - x_min) - 1

def setup_communication(ip, port, rcv_or_send):
    #note: rcv_or_send is a char that specifies if the port is to send data or receive data

    #Setup for sending data
    if (rcv_or_send == "receive"):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.LINGER, 0) # Prevents ZMQ from hanging on exit
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        socket.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only
        socket.connect(f"tcp://{ip}:{port}")  # Replace with the appropriate address and port
        return socket

    #Setup for receiving data
    elif (rcv_or_send == "send"):
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        socket.setsockopt(zmq.LINGER, 0) # Prevents ZMQ from hanging on exit
        socket.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
        socket.bind(f"tcp://{ip}:{port}")
        return socket

#Setup communication to receive data from gait_timing.py
ip_0 = "localhost"  #local IP
port_0 = "3333"
socket0 = setup_communication(ip_0, port_0, 'receive')

#Socket to export/send the RL action (timing), to the pressure_commands.py
ip_export = "*"  #localhost IP
port_export = "4444"
socket_export = setup_communication(ip_export, port_export, "send")

# --- PARAMETERS ---
SubjectName = os.environ.get("EXO_SUBJECT", "Subject1")
TrialCondition = os.environ.get("EXO_CONDITION", "Cond1")
Trialnumber = os.environ.get("EXO_TRIAL", "1")
Incline = os.environ.get("EXO_INCLINE", "0").replace('.', 'p')
Speed = os.environ.get("EXO_SPEED", "1.0").replace('.', 'p')
Mode = os.environ.get("EXO_MODE", "RL")


""" Select Options """
Deploy_RL = 0
Train_RL = 1
Realtime_Run = True  #(T/F). (True)= Run Realtime/online training. (False)= use offline data



if __name__ == "__main__":


    parser = argparse.ArgumentParser()
    parser.add_argument("--MAX_EPISODES", default=50, type=int)    # Max EP to run environment
    parser.add_argument("--expl_noise", default=0.05)                # Std of Gaussian exploration noise
    parser.add_argument("--batch_size", default=5, type=int)        # Batch size for both actor and critic
    parser.add_argument("--max_mem_size", default=10, type=int)     # max buffer size
    parser.add_argument("--discount", default=0.95)                 # Discount factor
    parser.add_argument("--tau", default=0.5)                      # Target network update rate
    parser.add_argument("--policy_noise", default=0.00)             # Noise added to target policy during critic update
    parser.add_argument("--noise_clip", default=0.1)                # Range to clip target policy noise
    parser.add_argument("--policy_freq", default=4, type=int)       # FIX (Bug #2): delayed actor/target update period
    parser.add_argument("--save_model", default = False)             # Save model and optimizer parameters
    parser.add_argument("--load_model", default="newdevice")          # Model load file name, "" doesn't load, "default" uses file_name
    args = parser.parse_args()


    #Setup folders
    if not os.path.exists("./results"):
        os.makedirs("./results")

    os.makedirs(f"./results/{SubjectName}", exist_ok=True)

    if args.save_model and not os.path.exists("./models"):
        os.makedirs("./models")

    if args.save_model:
        os.makedirs(f"./models/{SubjectName}", exist_ok=True)

    # set RL env
    state_dim = 5
    action_dim = 4
    max_action = 1
    # FIX (Bug #2): wire policy_noise / noise_clip / policy_freq into TDR.
    # Previously these argparse values were parsed but never passed in, so TDR
    # silently used its own hardcoded defaults (0.1 / 0.2 / 4).
    kwargs = {
        "state_dim": state_dim,
        "action_dim": action_dim,
        "max_action": max_action,
        "discount": args.discount,
        "tau": args.tau,
        "policy_noise": float(args.policy_noise),
        "noise_clip": float(args.noise_clip),
        "policy_freq": int(args.policy_freq),
    }

    # set RL method (continuous)
    policy = TDR(**kwargs)


    """ ----------- TRAINING RL Loop (Simulates Real-Time Implementation) ----------- """
    if Train_RL:

        # #Load a trained policy
        policy_file = "SM_WEIJIA"
        policy.load(f"./models/{policy_file}")
        print("Model Loaded: ", f"./models/{policy_file}")



        replay_buffer = ReplayBuffer.ReplayBuffer(state_dim, action_dim,args.max_mem_size)
        counter_samples = 0
        run_exp = True

        filename_data = f"results/{SubjectName}/RL_TrainingData_{SubjectName}_{TrialCondition}_{Mode}_inc{Incline}_spd{Speed}_{Trialnumber}.csv"
        fields = ['steps','training cost','t1 error','d1 error','t2 error','d2 error','kinematic errorA','kinematic errorC','state','action','next state','emg_vl_ext1','emg_rf_ext2','emg_bf_flex','emg_st_flex']
        csvfile = open(filename_data, 'a', newline='')
        csvwriter = csv.writer(csvfile)
        if os.path.getsize(filename_data) == 0:
            csvwriter.writerow(fields)

        print("---------------------------------------")
        print(" Start RL Training")
        print("---------------------------------------")

        #Get initial Gait Data, this we can get from warm up session by assign initial data to mocap average
        if Realtime_Run:
            #Receive Gait Data Array
            data = socket0.recv_pyobj()


        # state = (data[0],data[2]) #first gait state data
        state = [data[0],data[1],data[2],#3 timing TA,TB,TC
                 data[3],data[4]]#2 ANGLE  #first gait state data

        state[0] = normalize(state[0], 0.05, 0.20)   # TA: observed range [0.04, 0.20] across all subjects
        state[1] = normalize(state[1], 0.21, 0.41)   # TB: UPDATED from [0.3,0.5] — observed range [0.21,0.40]
        state[2] = normalize(state[2], 0.50, 0.70)   # TC: UPDATED from [0.5,0.75] — observed range [0.50,0.68] (Amir ~0.654, others ~0.51-0.58)
        state[3] = math.radians(state[3])
        state[4] = math.radians(state[4])


        #Run training loop for the number of max episodes. One episode is one run of the whole data set.
        # for j in range(int(args.MAX_EPISODES)): #no need for
        while run_exp:
        # for j in range(1):
            try:
                #Compute RL action
                action = (
                        policy.select_action(np.array(state))  #policy from state
                        + np.random.normal(0, max_action * args.expl_noise, size=action_dim)  #add some noise
                            ).clip(-max_action, max_action)

                """ Send action data to pressure controller """
                #Convert the action from normalized values to seconds (junmin)
                #Junmin add here the denormalization (a + 1)*(max - min)/2 + min
                org_ta = (denormalize(action[0], 0.05, 0.20))*data[9]
                org_tb = (denormalize(action[1], 0.21, 0.41))*data[9]  # TB: UPDATED to match state
                org_tc = (denormalize(action[2], 0.50, 0.70))*data[9]  # TC: UPDATED to match state
                org_td = (denormalize(action[3], 0.9, 1))*data[9]



                #Send the RL timings (action) to the pressure controller (emiliano)
                timing_export_array = np.array([org_ta, org_tb, org_tc, org_td])
                socket_export.send_pyobj(timing_export_array) #send data to pressure_commands.py
                print("action timings (sec) =", timing_export_array)


                """ RL """
                ###double check this read data will wait 5 steps average?
                ###apply action to plant
                if Realtime_Run:
                    #Receive Gait Data Array
                    data = socket0.recv_pyobj()

                # next_state = (data[0],data[2]) #first gait state data
                emg_VL = data[5]
                emg_RF = data[6]
                emg_BF = data[7]
                emg_ST = data[8]
                emg_state = emg_VL + emg_RF + emg_BF + emg_ST

                next_state = [data[0],data[1],data[2],#3 timing TA,TB,TC
                         data[3],data[4]]#2 ANGLE  #first gait next_state data

                next_state[0] = normalize(next_state[0], 0.05, 0.20)
                next_state[1] = normalize(next_state[1], 0.21, 0.41)   # TB: UPDATED to match state
                next_state[2] = normalize(next_state[2], 0.50, 0.70)   # TC: UPDATED to match state

                next_state[3] = math.radians(next_state[3])
                next_state[4] = math.radians(next_state[4])

                ####in online training we should compare real human data with target. NOT ACTION anymore.
                ta_error = data[0] - 0.13
                tb_error = data[1]- 0.37
                tc_error = data[2]- 0.68

                kinematic_errorA =  math.radians(data[3]) - 0.248
                kinematic_errorC =  math.radians(data[4])- 1.07


                ####state action alignment
                action1_error =  action[0] - state[0]
                action2_error =  action[1] - state[1]
                action3_error =  action[2] - state[2]
                action4_error =  action[3] - 1


                coeff_state_timing = 1.0
                coeff_kine = 0.25
                coeff_action = 0.25
                coeff_emg = 0.5

                error_state_timing = (ta_error**2 + tb_error**2 + tc_error**2 )
                error_kinematic = kinematic_errorA**2 + kinematic_errorC**2
                error_action = ((action1_error)**2 + (action2_error)**2 + (action3_error)**2 + (action4_error)**2 )

                cost = (coeff_state_timing*error_state_timing
                            + coeff_action* error_action
                           + coeff_kine* error_kinematic
                           + coeff_emg*(emg_state)**2) #cost for timing and duration

                done = 0
                counter_samples += 1  #add to counter
                replay_buffer.add(state, action, next_state, cost, done)

                if counter_samples >= 2:  #collect at least 10 samples of data before training

                    # FIX (Bug #1): pass a step counter so the delayed actor/target
                    # update inside TDR.train (`step % policy_freq == 0`) actually
                    # fires. Previously step defaulted to 1 -> 1 % 4 != 0 every call,
                    # so the actor and target nets NEVER updated online.
                    policy.train(replay_buffer, args.batch_size, counter_samples) #training

                row_data = [counter_samples,cost,
                                      action1_error,action2_error,action3_error,action4_error,
                                      kinematic_errorA, kinematic_errorC,
                                      state,action,next_state,emg_VL,emg_RF,emg_BF,emg_ST]
                csvwriter.writerow(row_data)
                csvfile.flush()

                state = next_state

                #Print results for current sample training
                print('Sample=', counter_samples,
                       '\t Cost=', cost,
                       '\t timing ta error=', action1_error,
                       '\t timing tb error=', action2_error,
                       '\t timing tc error=', action3_error,
                       '\t timing td error=', action4_error,
                       '\t kinematic error A=', kinematic_errorA,
                       '\t kinematic error C=', kinematic_errorC,
                       '\t EMG state=', emg_state,
                       '\t EMG VL=', emg_VL,
                       '\t EMG RF=', emg_RF,
                       '\t EMG BF', emg_BF,
                       '\t EMG ST=', emg_ST)

                if counter_samples > 51:
                    run_exp = False

            except KeyboardInterrupt:
                if Realtime_Run:
                    socket0.close()
                    socket_export.close()
                    print("---------------------------------------")
                    print('Connection to Socket Closed.')
                    run_exp = False
                    break
                # exit()
                break




        csvfile.close()

        #Export Policy Model
        export_filename = f"dhdp_online_{SubjectName}_{TrialCondition}_{Mode}_inc{Incline}_spd{Speed}_{Trialnumber}"
        os.makedirs(f"./models/{SubjectName}", exist_ok=True)
        policy.save(f"./models/{SubjectName}/{export_filename}")
        print('Policy files saved to:', f"./models/{SubjectName}/{export_filename}")


        print("RL TRAINING Fininshed.")
        if Realtime_Run:
            try:
                socket0.close()
                socket_export.close()
            except:
                pass
        import os
        os._exit(0)

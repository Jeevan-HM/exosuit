"""
main.py - Reinforcement Learning Algorithm for Exosuit

Versions:
    v1 - junmin modified, first implementation of the offline RL algorithm
    v2 - emiliano modified to simulate the real-time implementation
    v3 - emiliano modified, incorporate mocap data features in the training (from gait_data_extraction_v5.py)  
    v4 - junmin modified, tuned training parameters
    v5 - emiliano modified. implemented the realtime online RL
    v6 - junmin modified (6/19), tuned the training parameters, improved the code and cost function.  emiliano modified (6/20) for debugging and added sending the RL action to the exosuit/plant

"""

import numpy as np
import csv
from numpy import genfromtxt
from DHDP import DHDP
import matplotlib.pyplot as plt
import numpy as np
import argparse
import os
import utils
import torch
#ZMQ Communication Libraries:
import zmq


plt.close('all')  #close all plots

#Remove All Variables in Spyder Console:
from sys import exit #for debug: adds exit() function to spyder
try:
    from IPython import get_ipython
    get_ipython().magic('reset -f') #clear memory/variables
    get_ipython().magic('clear')  #clear screen
except:
    pass



def setup_communication(ip, port, rcv_or_send):
    #note: rcv_or_send is a char that specifies if the port is to send data or receive data
    
    #Setup for sending data
    if (rcv_or_send == "receive"):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        socket.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only 
        socket.connect(f"tcp://{ip}:{port}")  # Replace with the appropriate address and port
        return socket
    
    #Setup for receiving data
    elif (rcv_or_send == "send"):
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
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



""" Select Options """
Deploy_RL = 0
Train_RL = 1
Realtime_Run = True  #(T/F). (True)= Run Realtime/online training. (False)= use offline data



if __name__ == "__main__":
    
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--MAX_EPISODES", default=50, type=int)    # Max EP to run environment
    parser.add_argument("--expl_noise", default=0.01)                # Std of Gaussian exploration noise
    parser.add_argument("--batch_size", default=10, type=int)        # Batch size for both actor and critic
    parser.add_argument("--max_mem_size", default=200, type=int)     # max buffer size
    parser.add_argument("--discount", default=0.9)                 # Discount factor
    parser.add_argument("--tau", default=0.5)                      # Target network update rate
    parser.add_argument("--policy_noise", default=0.00)             # Noise added to target policy during critic update
    parser.add_argument("--noise_clip", default=0.1)                # Range to clip target policy noise
    parser.add_argument("--save_model", default = True)             # Save model and optimizer parameters
    parser.add_argument("--load_model", default="default")          # Model load file name, "" doesn't load, "default" uses file_name
    args = parser.parse_args()
    

    # #Load Offline Data
    # # data = genfromtxt(r"C:\Users\jz5zh\eclipse-workspace\soft_suit\gait_data_2control.csv", dtype=float,delimiter=',')
    # data = genfromtxt(r"gait_data_1.csv", dtype=float,delimiter=',')
    #   # 0:Total gait time
    #   # 1: period time stf to ste
    #   # 2: control 1
    #   # 5: normalized control [-1 1]
    # print(data.shape[0],'total data length') #row number
    
    #Setup folders
    if not os.path.exists("./results"):
        os.makedirs("./results")
        
    if args.save_model and not os.path.exists("./models"):
        os.makedirs("./models")
    
    # set RL env
    state_dim = 4
    action_dim = 4
    max_action = 1
    kwargs = {
        "state_dim": state_dim,
        "action_dim": action_dim,
        "max_action": max_action,
        "discount": args.discount,
        "tau": args.tau,
    }

    # set RL method (continuous)
    policy = DHDP(**kwargs)
    
    
    data_mocap = [34, 34, 34, 987]
    
    """ ----------- DEPLOYMENT RL Loop (Simulates Real-Time Implementation) ----------- """
    if Deploy_RL:
        
        #Load trained Policy
        policy_file = "dhdp_mocap"
        policy.load(f"./models/{policy_file}")
        print("Model Loaded: ", f"./models/{policy_file}")
        
        #Load Offline Data
        if not Realtime_Run:
            data_csv = genfromtxt(r"gait_data/gait_data_v6.csv", dtype=float,delimiter=',')
            data_mocap_csv = genfromtxt(r"gait_data/gait_data_v5_mocap.csv", dtype=float,delimiter=',')
            print(data_csv.shape[0],'total data length') #row number
            print(data_csv.shape[0],'total mocap data length') #row number
        
        
        valid_data = []
        ep_c = 0  #cost sum
        
        print("---------------------------------------")
        print(f"start RL deployment/validation")
        print("---------------------------------------")
        
        
        # while True:
        for i in range(data_csv):  #alternative loop statement. 214 = number of gait cycles in the offline data

            try:
                if Realtime_Run:
                    #Receive Gait Data Array
                    data = socket0.recv_pyobj()
                else:
                    #Read Gait Data Array from data structure
                    data = data_csv[i][4:8]
                    data_mocap = data_mocap_csv[i][4:8]

                
                # state = (data[0],data[1],data[3])
                state = (data[0],data[1],data[2],data[3])
                
                action = policy.select_action(np.array(state))
                
                
                # cost = 0.5*((action[0] - data[4])**2 + (action[1]- data[5])**2) #cost between two duration
                cost = 0.5*((action[0] - data_mocap[0])**2 + (action[1]- data_mocap[1])**2 + (action[2]- data_mocap[2])**2 + (action[3]- data_mocap[3])**2) #cost for timing and duration
                
                valid_data.append((cost,action[0],action[1]))
                done = 0
                ep_c += cost
                
                print('Data = ', data)
                                
                print('Cost = ', cost, '  Action 0 =', action[0], '  Action 1 =', action[1])
                # print('Validation Data = ', valid_data)


            except KeyboardInterrupt:
                socket0.close()
                print("---------------------------------------")
                print('Connection to Socket Closed.')
                # exit()
                break
                
                
        #Export Validation (deployment) Results
        filename = "results/valid_mocap.csv"
        with open(filename, 'w') as csvfile: 
            # creating a csv writer object 
            csvwriter = csv.writer(csvfile,lineterminator = '\n') 
        
            # writing the data rows 
            csvwriter.writerows(valid_data)   
            print("Validation/Deployment data saved to: ", filename)
        
        
        print("RL Deployment Fininshed.")
        if Realtime_Run: socket0.close()
        exit()
        
          
        
     


    """ ----------- TRAINING RL Loop (Simulates Real-Time Implementation) ----------- """
    if Train_RL:
        
        # # #Load a trained policy
        # policy_file = "dhdp2"
        # policy.load(f"./models/{policy_file}")
        # print("Model Loaded: ", f"./models/{policy_file}")
        
        #Load Offline Data
        if not Realtime_Run:
            data_csv = genfromtxt(r"gait_data/gait_data_v6.csv", dtype=float,delimiter=',')
            data_mocap_csv = genfromtxt(r"gait_data/gait_data_v5_mocap.csv", dtype=float,delimiter=',')
            print(data_csv.shape[0],'total data length') #row number
            print(data_csv.shape[0],'total mocap data length') #row number
        
        
        replay_buffer = utils.ReplayBuffer(state_dim, action_dim,args.max_mem_size)
        training_data = []
        all_epc = []
        counter_samples = 0
        run_exp = True
        print("---------------------------------------")
        print(f" Start RL Training")
        print("---------------------------------------")
        
        #Get initial Gait Data, this we can get from warm up session by assign initial data to mocap average
        if Realtime_Run:
            #Receive Gait Data Array
            data = socket0.recv_pyobj()
        else:
            #Read Gait Data Array from data structure
            data = data_csv[0][4:8]
            data_mocap = data_mocap_csv[0][4:8]
            
        
        # state = (data[0],data[2]) #first gait state data
        state = (data[0],data[1],data[2],data[3]) #first gait state data
        
        #Run training loop for the number of max episodes. One episode is one run of the whole data set.
        # for j in range(int(args.MAX_EPISODES)): #no need for
        while run_exp:
        # for j in range(1):
            ep_c = 0
            try:
                #Compute RL action
                action = (
                        policy.select_action(np.array(state))  #policy from state
                        + np.random.normal(0, max_action * args.expl_noise, size=action_dim)  #add some noise
                            ).clip(-max_action, max_action)
                
                """ Send action data to pressure controller """
                #Convert the action from normalized values to seconds (junmin)
                #Junmin add here the denormalization (a + 1)*(max - min)/2 + min
                t1 = (action[0] + 1)*(0.4-0.2)/2 + 0.2
                u1 = (action[1] + 1)*(0.81-0.57)/2 + 0.57
                t2 = (action[2] + 1)*(1.78-1.16)/2 + 1.16
                u2 = (action[3] + 1)*(0.77-0.33)/2 + 0.33
                
                #Send the RL timings (action) to the pressure controller (emiliano)
                timing_export_array = np.array([t1, u1, t2, u2])
                socket_export.send_pyobj(timing_export_array) #send data to pressure_commands.py
                print("action timings (sec) =", timing_export_array)
                
                
                """ RL """
                ###double check this read data will wait 5 steps average?
                ###apply action to plant
                if Realtime_Run:
                    #Receive Gait Data Array
                    data = socket0.recv_pyobj()
                else:
                    #Read Gait Data Array from data structure
                    data = data_csv[i][4:8]
                    data_mocap = data_mocap_csv[i][4:8]
                
                # next_state = (data[0],data[2]) #first gait state data
                next_state = (data[0],data[1],data[2],data[3])
                
                ####in online training we should compare real human data with target. NOT ACTION anymore.
                cost = 0.5*((data[0] - data_mocap[0])**2 + (data[1]- data_mocap[1])**2 + (data[2]- data_mocap[2])**2 + (data[3]- data_mocap[3])**2) #cost for timing and duration
                
                done = 0
                ep_c += cost
                counter_samples += 1  #add to counter
                replay_buffer.add(state, action, next_state, cost, done)
            
                if counter_samples >= 10:  #collect at least 10 samples of data before training
                    
                    policy.train(replay_buffer, args.batch_size) #training
                    
                state = next_state
                
                #Print results for current sample training
                print('Sample=', counter_samples,  '\t Cost=', cost,  '\t Episode_Cost_Sum= ', ep_c)
                #Print Results for complete episode (1 pass of training data)
                all_epc += [ep_c]
                training_data.append((counter_samples,ep_c))
                print('Ep: %i  | ep_c: %.1f | ' % (counter_samples, ep_c ))
                
                
                    
            except KeyboardInterrupt:
                if Realtime_Run: 
                    socket0.close()
                    socket_export.close()
                    print("---------------------------------------")
                    print('Connection to Socket Closed.')
                    run_exp = False
                # exit()
                break    


            
            
            
        #Export Training Data
        filename = "results/training_mocap.csv"
        fields = ['Episode number','training Episode cost']
        with open(filename, 'w') as csvfile: 
            # creating a csv writer object 
            csvwriter = csv.writer(csvfile,lineterminator = '\n') 
            # writing the fields 
            csvwriter.writerow(fields) 
            # writing the data rows 
            csvwriter.writerows(training_data)   
            print("Training data saved to: ", filename)     

        #Export Policy Model
        export_filename = "dhdp_mocap"
        policy.save(f"./models/{export_filename}")
        print('Policy files saved to:', f"./models/{export_filename}")
        
            
        print("RL TRAINING Fininshed.")
        if Realtime_Run: socket0.close()
        exit()
            
        
        


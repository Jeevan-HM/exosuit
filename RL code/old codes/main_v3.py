"""
main.py

Versions:
    v1 - junming modified, first implementation of the offline RL algorithm
    v2 - emiliano modified to simulate the real-time implementation
    v3 - emiliano modified, incorporate mocap data features in the training (from gait_data_extraction_v5.py)   

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
import zlib
import pickle

plt.close('all')  #close all plots

#Remove All Variables in Spyder Console:
from sys import exit #for debug: adds exit() function to spyder
try:
    from IPython import get_ipython
    get_ipython().magic('reset -f') #clear memory/variables
    get_ipython().magic('clear')  #clear screen
except:
    pass



#Function: Receive Data message using ZMQ
def recv_data_socket0(flags=0):
    """reconstruct a Python object sent with zipped_pickle"""
    zobj = socket0.recv(flags)
    pobj = zlib.decompress(zobj)
    return pickle.loads(pobj)


# ##Setup ZMQ Connection:
# context = zmq.Context()
# # socket0 = Destination where data is received
# socket0 = context.socket(zmq.SUB)
# socket0.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only
# # socket0.setsockopt(zmq.SUBSCRIBE,'')  #python 2
# socket0.setsockopt(zmq.SUBSCRIBE,b'')  #python 3, Note; the b'' term added
# socket0.bind("tcp://127.0.0.1:2424") #check IP:port number matches sender. Using asterisk '*' is local IP.
# print("Connected ZMQ successfully.")





""" Select Options """
Deploy_RL = 0
Train_RL = 1
Simulate_Realtime = False  #(T/F) simulate realtime training (True) or use offline data (False)



if __name__ == "__main__":
    
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--MAX_EPISODES", default=200, type=int)    # Max EP to run environment
    parser.add_argument("--expl_noise", default=0.1)                # Std of Gaussian exploration noise
    parser.add_argument("--batch_size", default=10, type=int)       # Batch size for both actor and critic
    parser.add_argument("--max_mem_size", default=200, type=int)   # max buffer size
    parser.add_argument("--discount", default=0.95)                 # Discount factor
    parser.add_argument("--tau", default=0.05)                     # Target network update rate
    parser.add_argument("--policy_noise", default=0.05)              # Noise added to target policy during critic update
    parser.add_argument("--noise_clip", default=0.5)                # Range to clip target policy noise
    parser.add_argument("--policy_freq", default=2, type=int)       # Frequency of delayed policy updates
    parser.add_argument("--save_model", default = True)        # Save model and optimizer parameters
    parser.add_argument("--load_model", default="default")                 # Model load file name, "" doesn't load, "default" uses file_name
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
    
    
    
    
    """ ----------- DEPLOYMENT RL Loop (Simulates Real-Time Implementation) ----------- """
    if Deploy_RL:
        
        #Load trained Policy
        policy_file = "dhdp_mocap"
        policy.load(f"./models/{policy_file}")
        print("Model Loaded: ", f"./models/{policy_file}")
        
        #Load Offline Data
        if not Simulate_Realtime:
            data_csv = genfromtxt(r"gait_data/gait_data_v5.csv", dtype=float,delimiter=',')
            data_mocap_csv = genfromtxt(r"gait_data/gait_data_v5_mocap.csv", dtype=float,delimiter=',')
            print(data_csv.shape[0],'total data length') #row number
            print(data_csv.shape[0],'total mocap data length') #row number
        
        
        valid_data = []
        ep_c = 0  #cost sum
        
        print("---------------------------------------")
        print(f"start RL deployment/validation")
        print("---------------------------------------")
        
        
        # while True:
        for i in range(178):  #alternative loop statement. 214 = number of gait cycles in the offline data

            try:
                if Simulate_Realtime:
                    #Receive Gait Data Array
                    data = recv_data_socket0()
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
        if Simulate_Realtime: socket0.close()
        exit()
        
          
        
     


    """ ----------- TRAINING RL Loop (Simulates Real-Time Implementation) ----------- """
    if Train_RL:
        
        # #Load a trained policy
        # policy_file = "dhdp2"
        # policy.load(f"./models/{policy_file}")
        # print("Model Loaded: ", f"./models/{policy_file}")
        
        #Load Offline Data
        if not Simulate_Realtime:
            data_csv = genfromtxt(r"gait_data/gait_data_v5.csv", dtype=float,delimiter=',')
            data_mocap_csv = genfromtxt(r"gait_data/gait_data_v5_mocap.csv", dtype=float,delimiter=',')
            print(data_csv.shape[0],'total data length') #row number
            print(data_csv.shape[0],'total mocap data length') #row number
        
        
        replay_buffer = utils.ReplayBuffer(state_dim, action_dim,args.max_mem_size)
        training_data = []
        all_epc = []

        
        print("---------------------------------------")
        print(f" Start RL Training")
        print("---------------------------------------")
        
        #Run training loop for the number of max episodes. One episode is one run of the whole data set.
        for j in range(int(args.MAX_EPISODES)):
        # for j in range(1):
            ep_c = 0
            counter_samples = 0
            
            #Get First Gait Data
            if Simulate_Realtime:
                #Receive Gait Data Array
                data = recv_data_socket0()
            else:
                #Read Gait Data Array from data structure
                data = data_csv[0][4:8]
                data_mocap = data_mocap_csv[0][4:8]
                
            
            # state = (data[0],data[2]) #first gait state data
            state = (data[0],data[1],data[2],data[3]) #first gait state data
            
            # while True:
            for i in range(177):  #debug, alternative loop statement. 214 = number of gait cycles in the offline data
                try:           
                    if Simulate_Realtime:
                        #Receive Gait Data Array
                        data = recv_data_socket0()
                    else:
                        #Read Gait Data Array from data structure
                        data = data_csv[i][4:8]
                        data_mocap = data_mocap_csv[i][4:8]
                    
                    # next_state = (data[0],data[2]) #first gait state data
                    next_state = (data[0],data[1],data[2],data[3])
                    
                    action = (
                            policy.select_action(np.array(state))  #policy from state
                            + np.random.normal(0, max_action * args.expl_noise, size=action_dim)  #add some noise
                                ).clip(-max_action, max_action)
                    
                    # cost = 0.5*((action[0] - data_mocap[0])**2 + (action[1]- data_mocap[2])**2) #cost for timing
                    cost = 0.5*((action[0] - data_mocap[0])**2 + (action[1]- data_mocap[1])**2 + (action[2]- data_mocap[2])**2 + (action[3]- data_mocap[3])**2) #cost for timing and duration
                    
                    done = 0
                    ep_c += cost   
                    counter_samples += 1  #add to counter
                    
                    replay_buffer.add(state, action, next_state, cost, done)
                    
                
                    if counter_samples >= 10:  #collect at least 10 samples of data before training
                        
                        policy.train(replay_buffer, args.batch_size) #training
                        
                    state = next_state
                    
                    # #Print results for current sample training
                    # print('Sample=', counter_samples,  '\t Cost=', cost,  '\t Episode_Cost_Sum= ', ep_c)
                        
                        
                        
                except KeyboardInterrupt:
                    if Simulate_Realtime: 
                        socket0.close()
                        print("---------------------------------------")
                        print('Connection to Socket Closed.')
                    # exit()
                    break    


            #Print Results for complete episode (1 pass of training data)
            all_epc += [ep_c]
            training_data.append((j,ep_c))
            print('Ep: %i  | ep_c: %.1f | ' % (j, ep_c ))
            
            
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
        if Simulate_Realtime: socket0.close()
        exit()
            
        
        
        
        #### RL DEPLOYMENT ORIGINAL OFFLINE #### 
  ## Original Looop for RL VALIDATION / DEPLOYMENT      
#         state = (data[0][0],data[0][1],data[0][3]) #first gait data
        
#         for j in range(1000):
#         # for j in range(data.shape[0]):
#             action = policy.select_action(np.array(state))
               
#             if j != (data.shape[0] - 1): #check not in last sample  
            
#                 next_state = (data[j+1][0],data[j+1][1],data[j+1][3]) #next gait data

#                 cost = 0.5*((action[0] - data[j][4])**2 + (action[1]- data[j][5])**2) #cost between two duration
# #                 print(cost)
#                 done = 0
#                 ep_c += cost
                
#                 state = next_state
                
#                 valid_data.append((cost,action[0],action[1]))
#             else:
#                 cost = 0.5*((action[0] - data[j][4])**2 + (action[1]- data[j][5])**2) #cost between two duration
# #                 print(cost)
#                 done = 0
#                 ep_c += cost
#                 valid_data.append((cost,action[0],action[1]))
                
#                 break
  

        

        
#     #### TRAINING ORIGINAL OFFLINE ####    
#     replay_buffer = utils.ReplayBuffer(state_dim, action_dim,args.max_mem_size)
#     training_data = []
#     all_epc = []
#     for i in range(int(args.MAX_EPISODES)):
#         state = (data[0][0],data[0][1],data[0][3]) #first gait data
#         ep_c = 0.
#         for j in range(data.shape[0]): 
#             action = (
#                     policy.select_action(np.array(state))  #policy from state
#                     + np.random.normal(0, max_action * args.expl_noise, size=action_dim)  #add some noise
#                 ).clip(-max_action, max_action)
                
#             if j != (data.shape[0] - 1):   #check not in penultimo value
#                 next_state = (data[j+1][0],data[j+1][1],data[j+1][3]) #next gait data
# #                 print(data[j][5])
#                 cost = 0.5*((action[0] - data[j][4])**2 + (action[1]- data[j][5])**2) #cost between two duration
# #                 print(cost)
#                 done = 0
#                 ep_c += cost
#                 replay_buffer.add(state, action, next_state, cost, done)
#                 if (j + data.shape[0]*i) >= 10:  #collect at least 10 samples of data before training (???)
#                     policy.train(replay_buffer, args.batch_size) #training
                
#                 state = next_state
                
#             else:
#                 all_epc += [ep_c]
#                 training_data.append((i,ep_c))
#                 print('Ep: %i  | ep_c: %.1f | ' % (i, ep_c ))
#                 break
    
#     #Export Training Data
#     filename = "results/training%d.csv"%(1)
#     fields = ['Epois number','training Epois cost']
#     with open(filename, 'w') as csvfile: 
#         # creating a csv writer object 
#         csvwriter = csv.writer(csvfile,lineterminator = '\n') 
#         # writing the fields 
#         csvwriter.writerow(fields) 
#         # writing the data rows 
#         csvwriter.writerows(training_data)   
#         print("Training data saved to: ", filename)     

#     #Export Policy Model
#     policy.save(f"./models/{file_name}")
#     print('Policy files saved to:', file_name)

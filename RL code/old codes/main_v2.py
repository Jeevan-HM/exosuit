"""
main.py

Versions:
    v1 - first implementation of the offline RL algorithm
    v2 - modified to simulate the real-time implementation

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
import csv
#ZMQ Communication Libraries:
import zmq
import zlib
import pickle



#Remove All Variables in Spyder Console:
from sys import exit #for debug: adds exit() function to spyder
try:
    from IPython import get_ipython
    get_ipython().magic('clear')
    get_ipython().magic('reset -f')
    # import matplotlib.pyplot as plt
    plt.close('all')
except:
    pass


#Function: Receive Data message using ZMQ
def recv_data_socket0(flags=0):
    """reconstruct a Python object sent with zipped_pickle"""
    zobj = socket0.recv(flags)
    pobj = zlib.decompress(zobj)
    return pickle.loads(pobj)


##Setup ZMQ Connection:
context = zmq.Context()
# socket0 = Destination where data is received
socket0 = context.socket(zmq.SUB)
socket0.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only
# socket0.setsockopt(zmq.SUBSCRIBE,'')  #python 2
socket0.setsockopt(zmq.SUBSCRIBE,b'')  #python 3, Note; the b'' term added
socket0.bind("tcp://127.0.0.1:2424") #check IP:port number matches sender. Using asterisk '*' is local IP.
print("Connected ZMQ successfully.")


if __name__ == "__main__":
    
    """ Select Options """
    Deploy_RL = 0
    Train_RL = 1
    
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--MAX_EPISODES", default=100, type=int)    # Max EP to run environment
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
    state_dim = 3
    action_dim = 2
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
        policy_file = "dhdp2"
        policy.load(f"./models/{policy_file}")
        print("Model Loaded: ", f"./models/{policy_file}")
        
        valid_data = []
        ep_c = 0  #cost sum
        
        print("---------------------------------------")
        print(f"start RL deployment/validation")
        print("---------------------------------------")
        
        
        # while True:
        for i in range(200):  #alternative loop statement. 214 = number of gait cycles in the offline data

            try:
                #Receive Gait Data Array
                data = recv_data_socket0()
                
                state = (data[0],data[1],data[3])
                
                action = policy.select_action(np.array(state))
                
                cost = 0.5*((action[0] - data[4])**2 + (action[1]- data[5])**2) #cost between two duration
                
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
        filename = "results/valid_realtime.csv"
        with open(filename, 'w') as csvfile: 
            # creating a csv writer object 
            csvwriter = csv.writer(csvfile,lineterminator = '\n') 
        
            # writing the data rows 
            csvwriter.writerows(valid_data)   
            print("Validation/Deployment data saved to: ", filename)
        
        
        print("RL Deployment Fininshed.")
        socket0.close()
        exit()
        
          
        
     


    """ ----------- TRAINING RL Loop (Simulates Real-Time Implementation) ----------- """
    if Train_RL:
        
        
        policy_file = "dhdp2"
        policy.load(f"./models/{policy_file}")
        print("Model Loaded: ", f"./models/{policy_file}")
        
        replay_buffer = utils.ReplayBuffer(state_dim, action_dim,args.max_mem_size)
        training_data = []
        all_epc = []
        
        print("---------------------------------------")
        print(f" Start RL Training")
        print("---------------------------------------")
        
        #Run training loop for the number of max episodes. One episode is one run of the whole data set.
        # for i in range(int(args.MAX_EPISODES)):
        for i in range(1):
            ep_c = 0
            counter_samples = 0
            
            #Receive Gait Data Array
            data = recv_data_socket0()
            
            state = (data[0],data[1],data[3]) #first gait state data
            
            # while True:
            for i in range(200):  #debug, alternative loop statement. 214 = number of gait cycles in the offline data
                try:
                    #Receive Gait Data Array
                    data = recv_data_socket0()
                    
                    next_state = (data[0],data[1],data[3])
                    
                    action = (
                            policy.select_action(np.array(state))  #policy from state
                            + np.random.normal(0, max_action * args.expl_noise, size=action_dim)  #add some noise
                                ).clip(-max_action, max_action)
                    
                    cost = 0.5*((action[0] - data[4])**2 + (action[1]- data[5])**2) #cost between two duration
                    
                    done = 0
                    ep_c += cost   
                    counter_samples += 1  #add to counter
                    
                    replay_buffer.add(state, action, next_state, cost, done)
                    
                
                    if counter_samples >= 10:  #collect at least 10 samples of data before training
                        
                        policy.train(replay_buffer, args.batch_size) #training
                        
                    state = next_state
                    
                    #Print results for current sample training
                    print('Sample=', counter_samples,  '\t Cost=', cost,  '\t Episode_Cost_Sum= ', ep_c)
                        
                        
                        
                except KeyboardInterrupt:
                    socket0.close()
                    print("---------------------------------------")
                    print('Connection to Socket Closed.')
                    # exit()
                    break    


            #Print Results for complete episode (1 pass of training data)
            all_epc += [ep_c]
            training_data.append((i,ep_c))
            print('Ep: %i  | ep_c: %.1f | ' % (i, ep_c ))
            
            
            #Export Training Data
            filename = "results/training_realtime.csv"
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
            export_filename = "dhdp_realtime"
            policy.save(f"./models/{export_filename}")
            print('Policy files saved to:', f"./models/{export_filename}")
            
            
        print("RL TRAINING Fininshed.")
        socket0.close()
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

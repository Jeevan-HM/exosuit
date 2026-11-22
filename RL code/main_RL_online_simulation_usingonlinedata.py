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
import pandas as pd
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






if __name__ == "__main__":
    
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--MAX_EPISODES", default=1, type=int)    # Max EP to run environment
    parser.add_argument("--expl_noise", default=0.05)                # Std of Gaussian exploration noise
    parser.add_argument("--batch_size", default=2, type=int)        # Batch size for both actor and critic
    parser.add_argument("--max_mem_size", default=50, type=int)     # max buffer size
    parser.add_argument("--discount", default=0.95)                 # Discount factor
    parser.add_argument("--tau", default=0.9)                      # Target network update rate
    parser.add_argument("--policy_noise", default=0.0)             # Noise added to target policy during critic update
    parser.add_argument("--noise_clip", default=0.1)                # Range to clip target policy noise
    parser.add_argument("--save_model", default = True)             # Save model and optimizer parameters
    parser.add_argument("--load_model", default="")          # Model load file name, "" doesn't load, "default" uses file_name
    args = parser.parse_args()
    

  
    
    #Setup folders
    if not os.path.exists("./results"):
        os.makedirs("./results")
        
    if args.save_model and not os.path.exists("./models"):
        os.makedirs("./models")
    
    # set RL env
    state_dim = 5
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
    


    # #Load a trained policy
    policy_file = "dhdp_6_22_percent"
    policy.load(f"./models/{policy_file}")
    print("Model Loaded: ", f"./models/{policy_file}")
    
    data_csv = pd.read_csv(r"gait_data/dhdp_online_7_12_trial2.csv")
#     data_csv = genfromtxt(r"gait_data/dhdp_online_7_12_trial2.csv", dtype=float,delimiter=',')
    print(data_csv.shape[0],'total data length') #row number
#     print(data_csv.values[0][7])
#     ddd = data_csv.values[0][7]
#     array = [float(num) for num in ddd[1:-1].split(',')]
    
    replay_buffer = utils.ReplayBuffer(state_dim, action_dim,args.max_mem_size)
    training_data = []
    all_epc = []

    
    print("---------------------------------------")
    print(f" Start RL Training")
    print("---------------------------------------")
    

    action_hist = []
    state_hist = []
    counter_samples = 0
    array = data_csv.values[0][7]
    data = [float(num) for num in array[1:-1].split(',')]
    state = (data[0],data[1]/2,data[2],data[3],data[4]) #first gait state data
    num_data = 45
    for i in range(num_data):  #debug, alternative loop statement. 214 = number of gait cycles in the offline data
            
        array = data_csv.values[i][9]
        data = [float(num) for num in array[1:-1].split(',')]   
        next_state = (data[0],data[1]/2,data[2],data[3], data[4])
        emg_state = data_csv.values[i][10]+data_csv.values[i][11]+data_csv.values[i][12]
        
                
        action = (
                policy.select_action(np.array(state))  #policy from state
                + np.random.normal(0, max_action * args.expl_noise, size=action_dim)  #add some noise
                    ).clip(-max_action, max_action)
          
                            
        t1 = (((action[0] + 1)*(0.2-0)/2) + 0)*1.75
        u1 = (((action[1] + 1)*(0.25-0)/2) + 0)*1.75
        t2 = (((action[2] + 1)*(0.74-0.5)/2) + 0.5)*1.75
        u2 = (((action[3] + 1)*(0.28-0)/2) + 0)*1.75       
        #############for unnormalized offline RL controller
#         t1 = action[0]*1.75
#         u1 = action[1]*1.75
#         t2 = action[2]*1.75
#         u2 = action[3]*1.75
                
        t1_error = data[0] - 0.124 ####t1 12.4%
        d1_error = data[1] - 0.375/2 ####d1 
        t2_error = data[2] - 0.71
        d2_error = data[3] - 0.168
        kinematic_error = data[4]- 0.698
        emg_VL = data_csv.values[i][10]
        emg_RF = data_csv.values[i][11]
        emg_BF = data_csv.values[i][12]
        ####state action alignment
        action1_error =  (2*(data[0])/(0.2) - 1) - action[0]
        action2_error =  (2*(data[1]/2)/(0.25) - 1) - action[1]
        action3_error =  (2*(data[2]-0.5)/(0.24) - 1) - action[2]
        action4_error =  (2*(data[3])/(0.28) - 1) - action[3]
#         #############for unnormalized offline RL controller
#         action1_error =  data[0] - action[0]
#         action2_error =  data[1] - action[1]
#         action3_error =  data[2] - action[2]
#         action4_error =  data[3] - action[3]

        
        coeff_t1 = 20
        coeff_d1 = 20
        coeff_t2 = 10
        coeff_d2 = 15
        coeff_a1 = 2
        coeff_a2 = 2
        coeff_a3 = 1
        coeff_a4 = 1.5
        coeff_kine = 0.02
        coeff_emg = 0.2
                
        error_state = coeff_t1*(t1_error)**2 + coeff_d1*(d1_error)**2 + coeff_t2*(t2_error)**2 + coeff_d2*(d2_error)**2
        error_action = coeff_a1*(action1_error)**2 + coeff_a2*(action2_error)**2 + coeff_a3*(action3_error)**2 + coeff_a4*(action4_error)**2
                
        cost = 0.5*(error_state + error_action
                   + coeff_kine*(kinematic_error)**2 
                   + coeff_emg*(emg_state)**2) #cost for timing and duration
                
        done = 0
        counter_samples += 1  #add to counter
        replay_buffer.add(state, action, next_state, cost, done)
            
        if counter_samples >= 2:  #collect at least 10 samples of data before training
            
            policy.train(replay_buffer, args.batch_size) #training
        
        training_data.append((counter_samples,cost,t1_error,d1_error,t2_error,d2_error,kinematic_error,state,action,next_state,emg_VL,emg_RF,emg_BF))  
        state = next_state
                
        #Print results for current sample training
        print('Sample=', counter_samples, 
               '\t Cost=', cost)
                
        print('\t t1=', t1/1.75,
               '\t d1=', u1/1.75,
               '\t t2=', t2/1.75,
               '\t d2=', u2/1.75)
        action_hist.append((t1/1.75,u1/1.75,t2/1.75,u2/1.75))
        state_hist.append((state[0],state[1],state[2],state[3]))
#         print('\t t1 error', 0.5*coeff_a1*(action1_error)**2,
#                '\t d1 error', 0.5*coeff_a2*(action2_error)**2,
#                '\t t2 error', 0.5*coeff_a3*(action3_error)**2,
#                '\t d2 error', 0.5*coeff_a4*(action4_error)**2)

#         print('error state',error_state)
#         print('error action',error_action*0.5)
#         print('error kinematic',0.2*kinematic_error**2)   
#         print('EMG',0.5*emg_state**2)    
    Gaits = []
    Costs = []
    T1 = []
    D1 = []
    T2 = []
    D2 = []
    AT1 = []
    AD1 = []
    AT2 = []
    AD2 = []
    for row in training_data:
        Gaits.append(row[0])
        Costs.append(row[1])
    
    for row in action_hist:
        T1.append(row[0])
        D1.append(row[1])
        T2.append(row[2])    
        D2.append(row[3])
    for row in state_hist:
        AT1.append(row[0])
        AD1.append(row[1])
        AT2.append(row[2])    
        AD2.append(row[3])
        
    plt.plot(Gaits,Costs) 
    plt.xlabel('Gaits')
    plt.ylabel('Costs')
    plt.title('Online data simulation for normalized RL controller')   
    plt.show() 
    
    plt.plot(Gaits,T1, label='T1 action') 
    plt.plot(Gaits,AT1, label='actual human') 
    plt.xlabel('Gaits')
    plt.ylabel('Ta in percent')
    plt.title('Online data simulation for normalized RL controller')   
    plt.legend()
    plt.show() 
    
    plt.plot(Gaits,T2, label='T2 action') 
    plt.plot(Gaits,AT2, label='actual human') 
    plt.xlabel('Gaits')
    plt.ylabel('Tc in percent')
    plt.title('Online data simulation for normalized RL controller')   
    plt.legend()
    plt.show() 
    
    plt.plot(Gaits,D1, label='D1 RL action') 
    plt.plot(Gaits,AD1, label='actual human') 
    plt.xlabel('Gaits')
    plt.ylabel('D1 in percent')
    plt.title('Online data simulation for normalized RL controller')   
    plt.legend()
    plt.show() 
    
    plt.plot(Gaits,D2, label='D2 RL action') 
    plt.plot(Gaits,AD2, label='actual human') 
    plt.xlabel('Gaits')
    plt.ylabel('D2 in percent')
    plt.title('Online data simulation for normalized RL controller')   
    plt.legend()
    plt.show() 
    
    #Export Training Data
    filename = "results/dhdp_online_7_12_simulation.csv"
    fields = ['steps','training cost','t1 error','d1 error','t2 error','d2 error','kinematic error','state','action','next state','emg_vl_ext1','emg_rf_ext2','emg_bf_flex']
    with open(filename, 'w') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile,lineterminator = '\n') 
        # writing the fields 
        csvwriter.writerow(fields) 
        # writing the data rows 
        csvwriter.writerows(training_data)   
        print("Training data saved to: ", filename)     

    #Export Policy Model
    export_filename = "dhdp_online_7_12_simulation"
    policy.save(f"./models/{export_filename}")
    print('Policy files saved to:', f"./models/{export_filename}")
    
        
    print("RL TRAINING Fininshed.")
    
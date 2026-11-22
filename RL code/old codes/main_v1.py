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


if __name__ == "__main__":
    
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
    parser.add_argument("--load_model", default="dhdp2")                 # Model load file name, "" doesn't load, "default" uses file_name
    args = parser.parse_args()

    file_name = f"dhdp2"
    print("---------------------------------------")
    print(f"start training")
    print("---------------------------------------")

    if not os.path.exists("./results"):
        os.makedirs("./results")

    if args.save_model and not os.path.exists("./models"):
        os.makedirs("./models")

    #load data
    # data = genfromtxt(r"C:\Users\jz5zh\eclipse-workspace\soft_suit\gait_data_2control.csv", dtype=float,delimiter=',')
    data = genfromtxt(r"gait_data_1.csv", dtype=float,delimiter=',')
     # 0:Total gait time
     # 1: period time stf to ste
     # 2: control 1
     # 5: normalized control [-1 1]
    print(data.shape[0],'total data length') #row number
    # set env
    
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
    
    if args.load_model != "":
        policy_file = file_name if args.load_model == "default" else args.load_model
        policy.load(f"./models/{policy_file}")
        
        valid_data = []
        state = (data[0][0],data[0][1],data[0][3]) #first gait data
        ep_c = 0
        for j in range(data.shape[0]):
            action = policy.select_action(np.array(state))
               
            if j != (data.shape[0] - 1):   
                next_state = (data[j+1][0],data[j+1][1],data[j+1][3]) #next gait data
#                 print(data[j][5])
                cost = 0.5*((action[0] - data[j][4])**2 + (action[1]- data[j][5])**2) #cost between two duration
#                 print(cost)
                done = 0
                ep_c += cost
                
                state = next_state
                
                valid_data.append((cost,action[0],action[1]))
            else:
                cost = 0.5*((action[0] - data[j][4])**2 + (action[1]- data[j][5])**2) #cost between two duration
#                 print(cost)
                done = 0
                ep_c += cost
                valid_data.append((cost,action[0],action[1]))
                
                break
        
        filename = "results/valid%d.csv"%(1)
        with open(filename, 'w') as csvfile: 
            # creating a csv writer object 
            csvwriter = csv.writer(csvfile,lineterminator = '\n') 
        
            # writing the data rows 
            csvwriter.writerows(valid_data)   
            print("Validation data saved to: ", filename)
            
            exit()

        
    #### TRAINING ####    
    replay_buffer = utils.ReplayBuffer(state_dim, action_dim,args.max_mem_size)
    training_data = []
    all_epc = []
    for i in range(int(args.MAX_EPISODES)):
        state = (data[0][0],data[0][1],data[0][3]) #first gait data
        ep_c = 0.
        for j in range(data.shape[0]): 
            action = (
                    policy.select_action(np.array(state))
                    + np.random.normal(0, max_action * args.expl_noise, size=action_dim)
                ).clip(-max_action, max_action)
                
            if j != (data.shape[0] - 1):   
                next_state = (data[j+1][0],data[j+1][1],data[j+1][3]) #next gait data
#                 print(data[j][5])
                cost = 0.5*((action[0] - data[j][4])**2 + (action[1]- data[j][5])**2) #cost between two duration
#                 print(cost)
                done = 0
                ep_c += cost
                replay_buffer.add(state, action, next_state, cost, done)
                if (j + data.shape[0]*i) >= 10:
                    policy.train(replay_buffer, args.batch_size) #training
                
                state = next_state
                
            else:
                all_epc += [ep_c]
                training_data.append((i,ep_c))
                print('Ep: %i  | ep_c: %.1f | ' % (i, ep_c ))
                break
    
    filename = "results/training%d.csv"%(1)
    fields = ['Epois number','training Epois cost']
    with open(filename, 'w') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile,lineterminator = '\n') 
        # writing the fields 
        csvwriter.writerow(fields) 
        # writing the data rows 
        csvwriter.writerows(training_data)   
        print("Training data saved to: ", filename)     

    policy.save(f"./models/{file_name}")
    print('Policy files saved to:', file_name)

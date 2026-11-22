"""
gait_data_extraction_v3.py

version 2.1 = junmin modified the code to do the swing phase control (u2) feature extraction within the same loop of the stance phase part.
version 3 = (last modified: March 21) emiliano modified the complete code structure so the data processing is closer to a real-time gait feature extraction implementation.

"""

import numpy as np
import csv
import matplotlib.pyplot as plt


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


## Load data
# data = np.loadtxt(r"C:\Users\jz5zh\Desktop\Experiment 01_25\controller_realtime_data\active_20psi.txt", dtype=float,delimiter=",")
data = np.loadtxt(r"data/active_20psi.txt", dtype=float,delimiter=",")
# print(data[0][0]) row 0 column 0
print(data.shape[0],'total data length') #row number
print(data.shape[1],'total data column') #column number
# 0: time
# 1: mocap sync
# 2: grf_l
# 3: grf_r
# 4: knee angle L
# 5: knee angle R
# 6: Pressure commanded
# 7: Pressure measured
# 8: inflate command
# 9: stance L
# 10: stance R
# 11: kneeMax detected
# 12: First kneeMax detected for current gait

## Store data into variables:
timestamp = data[:,0]  #(sec) timestamps for controller data
grf = data[:,2]        #(unitless) GRF from left shoe
kneeAngle = data[:,4]  #(deg) Knee Joint Angle left leg
Pd = data[:,6]         #(psi) Desired pressure
stanceL_flags = data[:,9]    #[1/0] flags for stance phase detected by LEFT smart shoe. 1=stance phase. 0=swing phase.
stanceR_flags = data[:,10]   #[1/0] flags for stance phase detected by RIGHT smart shoe. 1=stance phase. 0=swing phase.
kneeMax_flags = data[:,11]   #[1/0] flags for when a Maximum/peak Knee angle is detected. 1=peak knee angle detected. 2=no peak angle detected in current sample data.


########## -------  Process Gait Data for Feature Extraction  ------- ##########

######  Initialize Variables  ######

#Flags for event detection. These flags are used to prevent multiple detections of the same event in a single gait cycle.
heelstrike_detected = 0  #[1/0] flag for heelstrike detected in current gait cycle. 1=heelstrike was detected in current gait cycle, 0=heelstrike not detected yet
u1_t0_detected = 0  #[1/0] flag for u1 START detected in current gait cycle. 1= u1 START was detected, 0= u1 START not detected yet
u1_tf_detected = 0  #[1/0] flag for u1 END detected in current gait cycle. 1= u1 END was detected, 0= u1 END not detected yet
u2_t0_detected = 0  #[1/0] flag for u2 START detected in current gait cycle. 1=u2 START was detected, 0= u2 START not detected yet
u2_tf_detected = 0  #[1/0] flag for u2 END detected in current gait cycle. 1= u2 END was detected, 0= u2 END not detected yet
computed_timings = False  #[True/False] flag for when timings were computed for the current gait cycle. 1=timings computed. 2=timings not computed yet in current cycle

#Flags for when control signal is active
u1_flag = 0 #[1/0] flag for when u1 is active. 1=u1 is on (providing torque). 0=u1 is off (no torque)
u1_flag_last = 0 #[1/0]. this stores the u1_flag variable for the previous/last sample index
u2_flag = 0 #[1/0] flag for when u2 is active. 1=u2 is on (providing torque). 0=u2 is off (no torque)
u2_flag_last = 0 #[1/0]. this stores the u2_flag variable for the previous/last sample index

#Vector to store the INDEX for timings of interest
heelstrike_index = [0]  #store indexes of Heelstrikes
u1_t0_index = [0]  #store indexes of u1 START
u1_tf_index = [0]  #store indexes of u1 END
u2_t0_index = [0]  #store indexes of u2 START
u2_tf_index = [0]  #store indexes of u2 END

#Variable/vector to store the TIME/timing data of interest
u1_timing = [] #(sec) store timing values of u1 START
u2_timing = [] #(sec) store timing values of u2 START
u1_duration = [] #(sec) duration values for u1
u2_duration = [] #(sec) duration values for u2
gait_cycle_duration = [] #(sec) store gait cycle time values 

#Itteration Counters
num_outliers_removed = 0 #counter for number of outliers removed

#Varibles for knee max detection (not used)
# vect_kneeAngle = []
# knee_max_flag = 0


######  Main Loop through each data sample (simulate data stream)  ######
for i in range(data.shape[0]):
    
    print('i =',i)

    #Detect when u1 (stance inflation) is active & providing torque:
    if (stanceL_flags[i] == 1) and (stanceR_flags[i] == 0):  #check for left leg single support phase
        u1_flag = 1  #1=u1 is on & providing torque
    else:
        u1_flag = 0
      
        
    #Detect Start of Inflation for Stance Phase, U1 start timing
    if (u1_flag == 1) and (u1_flag_last == 0) and (u1_t0_detected == 0): #check when u1 activates/starts (u1 goes from 0 to 1)
        u1_t0_index.append( i )
        u1_t0_detected = 1
        print('u1_t0_index =', u1_t0_index[-1])    


    #Detect End of Inflation for Stance Phase, U1 end timing
    if (u1_flag == 0) and (u1_flag_last == 1) and (u1_tf_detected == 0): #check when u1 deactivates/ends (u1 goes from 1 to 0)
        u1_tf_index.append( i )
        u1_tf_detected = 1
        print('u1_tf_index = ',u1_tf_index[-1])
           
        
    #Store u1_flag for next itteration
    u1_flag_last = u1_flag
    
    #Reset u1 Flags in Swing Phase:
    if (stanceL_flags[i] == 0): #check for swing phase
        heelstrike_detected = 0  #reset heelstrike detected flag
        u1_t0_detected = 0       #reset u1_t0 detected flag
        u1_tf_detected = 0       #reset u1_tf detected flag
        
        
    # ### Detect Knee Max Angles ### (not used since the data collection code already detects this in the variable: kneeMax_flags = data[:,11]).
    # #Create Vector of last 3 knee angles:
    # if i<2:
    #     vect_kneeAngle.append( kneeAngle[i] )
    #     knee_max_flag = 0
    # else:
    #     vect_kneeAngle = [vect_kneeAngle[1], vect_kneeAngle[2], kneeAngle_left] #Add Current Knee Angle Value to end of Vector that keeps track, and remove first value from vector.
        
    #     #Detect Knee Max Angle
    #     if (vect_kneeAngle[0] < vect_kneeAngle[1]) and (vect_kneeAngle[1] > vect_kneeAngle[2]):
    #         knee_max_flag = 1
    #     else:
    #         knee_max_flag = 0
     
       
    #Detect Start of Inflation in SWING phase, U2 start timing
    if (kneeMax_flags[i] == 1) and (u2_t0_detected == 0) and (stanceL_flags[i] == 0):  #check for first knee max detected, and verify it's in swing phase
        u2_t0_index.append( i )
        u2_t0_detected = 1
        print('u2_t0_index =', u2_t0_index[-1])
          
        
    #Detect when u2 (swing inflation) is active & providing torque:
    if (u2_t0_detected == 1) and (stanceL_flags[i] == 0):  #check that u2_t0 has started and left leg is in swing
        u2_flag = 1  #1=u2 is on & providing torque
    else:
        u2_flag = 0
     
        
    #Detect End of Inflation for SWING Phase, u2 end timing
    if (u2_flag == 0) and (u2_flag_last == 1) and (u2_tf_detected == 0):  #check when u2 deactivates/ends (u2 goes from 1 to 0)
        u2_tf_index.append( i )
        u2_tf_detected = 1
        print('u2_tf_index =', u2_tf_index[-1])
   
        
    #Store u2_flag for next itteration
    u2_flag_last = u2_flag
    
    #Reset u2 Flags in Stance Phase:
    if (stanceL_flags[i] == 1):
        u2_t0_detected = 0    #reset u2_t0 detected flag
        u2_tf_detected = 0    #reset u2_tf detected flag
        
        
    #Detect Heelstrike:
    #Note: the Heelstrike detection occurs at the same instance as u2_tf
    if (stanceL_flags[i] == 1) and (heelstrike_detected == 0):  #detect for first instance of stance phase/heelstrike
        heelstrike_index.append( i )  #store data index for Heelstrike
        heelstrike_detected = 1  #set flag to 1 since HS has been detected
        computed_timings = False #reset flag when new HS is detected
        print('Heelstrike =',heelstrike_index[-1])
        
        
    ### Compute Timing Values ###
    #IF statement: Check that the event indexes are in correct order
    #Note: the Heelstrike detection occurs at the same instance as u2_tf. Within the IF statement below, heelstrike_index[-2] is the start of the gait cycle, and heelstrike_index[-1] is the end of the gait cycle.
    if (computed_timings == False) and (heelstrike_index[-2] < u1_t0_index[-1]) and (u1_t0_index[-1] < u1_tf_index[-1]) and (u1_tf_index[-1] < u2_t0_index[-1]) and (u2_t0_index[-1] < u2_tf_index[-1]):
        ##Compute timings now that all events have been detected
        gait_cycle_duration.append( timestamp[heelstrike_index[-1]] - timestamp[heelstrike_index[-2]]  )
        u1_timing.append( timestamp[u1_t0_index[-1]] - timestamp[heelstrike_index[-2]] )
        u2_timing.append( timestamp[u2_t0_index[-1]] - timestamp[heelstrike_index[-2]] )
        u1_duration.append( timestamp[u1_tf_index[-1]] - timestamp[u1_t0_index[-1]] )
        u2_duration.append( timestamp[u2_tf_index[-1]] - timestamp[u2_t0_index[-1]] )
        computed_timings = True
        

        ### Remove Outliers ###
        #Outlier parameters: mean and std deviation of data (computed beforehand, w/ subject #2 20psi data)
        mean_data_outliers = np.array([1.97614, 0.241304, 0.756088, 1.57679, 0.399352])
        std_data_outliers = np.array([0.20801, 0.147171, 0.22686, 0.195508, 0.172512])
        
        #Create temporary data vector to compare with mean+std vector
        data_vector_temp = np.array([gait_cycle_duration[-1], u1_timing[-1], u2_timing[-1], u1_duration[-1], u2_duration[-1]])
        
        #Remove Outliers with Mean+Std treshold
        std_factor = 5  #number of standard deviations used as threshold to detect outliers
        if any(data_vector_temp > mean_data_outliers + std_factor*std_data_outliers):
            u1_timing = u1_timing[:-1]
            u2_timing = u2_timing[:-1]
            u1_duration = u1_duration[:-1]
            u2_duration = u2_duration[:-1]
            gait_cycle_duration = gait_cycle_duration[:-1]
            num_outliers_removed = num_outliers_removed + 1
           
print('Number of outliers removed =', num_outliers_removed)

        # #Remove Outliers MANUALLY (OLD method, used only for initial mean & std computation)
        # if (u2_timing[-1] > 2.3) and (gait_cycle_duration[-1] > 3): #selected manually
        #     gait_cycle_duration = gait_cycle_duration[:-1]
        #     u1_timing = u1_timing[:-1]
        #     u2_timing = u2_timing[:-1]
        #     u1_duration = u1_duration[:-1]
        #     u2_duration = u2_duration[:-1]


########## -------  Data Export  ------- ##########

## Store timing data into variable for export
# gait_data = np.array([gait_cycle_duration, u1_timing, u1_duration, u2_timing, u2_duration]).transpose()
gait_data = np.array([u1_timing, u1_duration, u2_timing, u2_duration]).transpose() #without gait_cycle_duration

#Normalize export data
gait_data_norm = -1 + 2*(gait_data - np.min(gait_data, axis=0))/(np.max(gait_data, axis=0) - np.min(gait_data, axis=0) )

#Merge the gait_data and the (normalized) gait_data_norm
gait_data_export = np.append(gait_data, gait_data_norm, axis=1)


## Export CSV file: gait_data_x.csv
filename = "gait_data_%d.csv"%(1)
with open(filename, 'w') as csvfile: 
    # creating a csv writer object 
    csvwriter = csv.writer(csvfile,lineterminator = '\n') 
    # writing the data rows 
    csvwriter.writerows(gait_data_export) 
print('Data Exported to:', filename)



########## -------  Debugging and Plotting  ------- ##########

# ### For outlier selection (run only for initial mean & std threshold computation)
# #Compute mean and std deviation of data
# mean_gait_data = np.mean(gait_data, axis=0)
# std_gait_data = np.std(gait_data, axis=0)


# ## Plot Event Detection through the Gait Data/Kinematics sample INDEX
# plt.figure(0)
# plt.clf()
# plt.title("Gait Event Detection")
# plt.plot( kneeAngle, label='Knee Angle')
# plt.scatter( [u1_t0_index], kneeAngle[u1_t0_index], c='C1', marker='x', label='U1 Start')
# plt.scatter( [u1_tf_index], kneeAngle[u1_tf_index], c='C2', marker='o', label='U1 End')
# plt.scatter( [u2_t0_index], kneeAngle[u2_t0_index], c='C3', marker='x', label='U2 Start')
# plt.scatter( [u2_tf_index], kneeAngle[u2_tf_index], c='C4', marker='o', label='U2 End')
# plt.plot(Pd, label='Pd')
# for xline in heelstrike_index:
#     plt.axvline(xline, color = 'grey' , linestyle='--')
# plt.axvline([heelstrike_index[-1]], color = 'grey' , linestyle='--', label='Heelstrikes')  #for legend label
# plt.legend()
# plt.xlabel('Sample Index')
# plt.show()


## Plot Event Detection through time with Knee Kinematics
plt.figure(1)
plt.clf()
plt.title("Gait Event Detection")
plt.plot(timestamp, kneeAngle, label='Knee Angle')
plt.scatter( timestamp[u1_t0_index], kneeAngle[u1_t0_index], c='C1', marker='x', label='U1 Start')
plt.scatter( timestamp[u1_tf_index], kneeAngle[u1_tf_index], c='C2', marker='o', label='U1 End')
plt.scatter( timestamp[u2_t0_index], kneeAngle[u2_t0_index], c='C3', marker='x', label='U2 Start')
plt.scatter( timestamp[u2_tf_index], kneeAngle[u2_tf_index], c='C4', marker='o', label='U2 End')
plt.plot(timestamp, Pd, label='Pd')
for xline in timestamp[heelstrike_index]: #plot heelstrikes
    plt.axvline(xline, color = 'grey' , linestyle='--')  #plot heelstrikes as vertical lines
plt.axvline(timestamp[heelstrike_index[-1]], color = 'grey' , linestyle='--', label='Heelstrikes')  #for legend label only
# plt.legend()
plt.legend(ncol=10)  #ncol=10, allows horizontal legend
plt.xlabel('Time (sec)')
plt.show()


#Plot the TIMING values computed
plt.figure(2)
plt.clf()
plt.title("Timing Values Computed")
plt.plot(u1_timing, label='U1 Timing')
plt.plot(u2_timing, label='U2 Timing')
plt.plot(u1_duration, label='U1 Duration')
plt.plot(u2_duration, label='U2 Duration')
plt.plot(gait_cycle_duration, label='Gait Cycle Duration')
# plt.legend()
plt.legend(ncol=10)  #ncol=10, allows horizontal legend
plt.xlabel('Gait Cycle')
plt.ylabel('Time (sec)')
# plt.grid()
plt.show()


# #Plot the normalization of the export data
# plt.figure(3)
# plt.clf()
# plt.plot(u1_timing, label='U1 Timing')
# plt.plot(u1_timing_norm, label='U1 Timing Norm')
# plt.title("Normalization Export Data")
# plt.legend()
# plt.xlabel('Sample Index')
# plt.ylabel('Time (sec)')
# plt.show()



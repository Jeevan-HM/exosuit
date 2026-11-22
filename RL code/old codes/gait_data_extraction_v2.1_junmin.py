"""
gait_data_extraction_v2.1_junmin.py

version 2 = added extraction of timings for the swing phase control (u2)
version 2.1 = junmin modified the code to do the swing phase control (u2) feature extraction within the same loop of the stance phase part.

"""

import numpy as np
import csv
import matplotlib.pyplot as plt
# from sys import exit #for debug in spyder


## Load data
data = np.loadtxt(r"C:\Users\jz5zh\Desktop\Experiment 01_25\controller_realtime_data\active_20psi.txt", dtype=float,delimiter=",")
# data = np.loadtxt(r"data\active_20psi.txt", dtype=float,delimiter=",")
print(data.shape[0],'total data length') #row number
print(data.shape[1],'total data column') #column number
# print(data[0][0]) row 0 column 0
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

#Store data into variables:
timestamp = data[:,0]
grf = data[:,2]
kneeAngle = data[:,4]
Pd = data[:,6]
stanceL_flags = data[:,9]
kneeMaxControl_flags = data[:,12]  #flag for control signal 2 (swing phase, SWF)


# #Plot Knee Angle to test data load:
# plt.plot(timestamp, kneeAngle)
# plt.plot(timestamp, Pd)
# plt.plot(timestamp, stanceL_flags*30)
# # plot.scatter(timestamp)
# plt.legend(['Knee Angle', 'Pd', 'Stance'])
# plt.ylabel('Knee Angle (deg)')
# plt.xlabel('Time (sec)')
# plt.show()



####preprocess data into gaits
Gait_data = []
Temp_data = []
Pd_temp = []
stanceL_temp = []
heelstrike_index = []
for t in range(data.shape[0]):
    if t == 0 or (t != 0 and stanceL_flags[t-1] == 0.0 and stanceL_flags[t] == 1.0): #if (1: first itteration) OR (2: detect Heelstrike / beginning of stance phase)
        print('begin gait detect',t)
        Temp_data.append(data[t])
        Pd_temp.append( Pd[t] )
        stanceL_temp.append( stanceL_flags[t] )
        
        heelstrike_index.append( t )
          

    elif (stanceL_flags[t] == 0.0 and stanceL_flags[t+1] == 1.0) or t == (data.shape[0] - 1): #if (3: detect end of stance phase, after detecting Heelstrike(2) ) OR (4: detect reached end of data set)
        print('end gait detect',t)
        Temp_data.append(data[t])
        Pd_temp.append( Pd[t] )
        stanceL_temp.append( stanceL_flags[t] )
        Total_gait_t = Temp_data[-1][0] - Temp_data[0][0]
        print('total gait time',Total_gait_t)
        #extract feature in the gait
        STF_STE = 0
        SWF_SWE = 0
        flag_stf = 0
        flag_swf = 0
        #markers for stf to ste
        t1 = 0
        t2 = 0
        #markers for swf to swe
        t3 = 0
        t4 = 0
        #markers for control command for stf to ste
        t5 = 0
        t6 = 0

        
        
        for i in range(len(Temp_data)):
            #get stf to ste time
            if (Temp_data[i][9] == 1) and (Temp_data[i][10] == 0) and flag_stf == 0:
                t1 = i
                flag_stf = 1
            if ((Temp_data[i][9] != 1) or (Temp_data[i][10] != 0)) and flag_stf == 1:
                t2 = i
                flag_stf = 0
                    
                    
            if i != (len(Temp_data) - 1):
                
                if Temp_data[i-1][8] == 0 and Temp_data[i][8] == 1 and t5 == 0:
                    t5 = i
                elif Temp_data[i+1][8] == 0 and Temp_data[i][8] == 1 and t5 != 0 and t6 == 0:
                    t6 = i
                    
            #Detect SWF (start of assistance):        
            if (i != 0) and (Temp_data[i][6] == 20) and (Temp_data[i-1][6] == 0) and (Temp_data[i][9] == 0)  and flag_swf == 0:
                t3 = i
                print(t3,'t3')
                flag_swf = 1
                 
            if (flag_swf == 1) and (Temp_data[i][6] == 0) and (Temp_data[i-1][6] == 20) and t4 == 0:
                t4 = i
                print(t4,'t4')
                flag_swf == 0
                
            

              
        STF_STE = Temp_data[t2][0] - Temp_data[t1][0]
        if t4 == 0 and t3 != 0:
            SWF_SWE = Temp_data[-1][0] - Temp_data[t3][0]
        else:
            SWF_SWE = 0
        T_c1 = Temp_data[t6][0] - Temp_data[t5][0]
        T_c2 = SWF_SWE
        
        if T_c1 < 0:
            T_c1 = 0



        #store gait data
        #Total gait time, period time stf to ste, control 1
        Gait_data.append((Total_gait_t, STF_STE,T_c1,SWF_SWE))
        
        Temp_data = []
        Pd_temp = []
        stanceL_temp = []
    else:
        Temp_data.append(data[t])
        Pd_temp.append( Pd[t] )
        stanceL_temp.append( stanceL_flags[t] )


## Export CSV file: gait_data for stance phase
filename = "gait_data%d.csv"%(1)
with open(filename, 'w') as csvfile: 
    # creating a csv writer object 
    csvwriter = csv.writer(csvfile,lineterminator = '\n') 

    # writing the data rows 
    csvwriter.writerows(Gait_data)        




########  Extract features for control signal u2 (swing phase)

u2_index0 = [] #index for start of u2
u2_indexf = [] #index for end of u2
flag_u2_started = False  #flag when u2 has started. True=started. False=not started.

for t in range(data.shape[0]):
    #Detect SWF (start of assistance):
    if (t != 0) and (Pd[t] == 20) and (Pd[t-1] == 0) and (stanceL_flags[t] == 0):
        
        #Obtain index for u2 start (index0)
        u2_index0.append( t )
        
        flag_u2_started = True  #flag when u2 has started. True=started. False=not started.
        
    
    elif (flag_u2_started == True) and (Pd[t] == 0) and (Pd[t-1] == 20):
        
        #Obtain index for u2 final/end (indexf)
        u2_indexf.append( t )
        
        flag_u2_started = False #Reset Flag:


### Compute Timing and Duration for u2

## Compute Duration of u2
u2_duration = timestamp[u2_indexf] - timestamp[u2_index0]

## Compute Timing (when u2 starts/engages):
heelstrike_timestamps = timestamp[heelstrike_index]  #vector of timestamps for heelstrikes
u2_timing = []
for i in range(len(u2_index0)):
    #find the heelstrike index before the start of u2 (t0). This is done by searching for the first True instance when the timestamp of interest is smaller than values of the timevector
    heelstrike_before_u2t0_index = np.argmax( heelstrike_timestamps > timestamp[u2_index0[i]] ) - 1   #the -1 is becuase the logical check detects the HS after and not the one before.

    u2_timing.append( timestamp[u2_index0[i]] - heelstrike_timestamps[heelstrike_before_u2t0_index] )


## Store u2 timing data into variable for export
gait_data_swing = np.array([u2_timing, u2_duration]).transpose()


## Export CSV file: gait_data_swing.csv
filename = "gait_data_swing_%d.csv"%(1)
with open(filename, 'w') as csvfile: 
    # creating a csv writer object 
    csvwriter = csv.writer(csvfile,lineterminator = '\n') 

    # writing the data rows 
    csvwriter.writerows(gait_data_swing)  



### Debuggin and Plotting:

## Plot Gait Data:
# plt.clf()
# plt.plot(timestamp, kneeAngle)
# plt.scatter( timestamp[u2_index0], kneeAngle[u2_index0], c='C1', marker='x')
# plt.scatter( timestamp[u2_indexf], kneeAngle[u2_indexf], c='C2', marker='o')
# for xline in timestamp[heelstrike_index]:
#     plt.axvline(xline, color = 'grey' , linestyle='--')
# # plt.scatter(gait_data_swing, kneeAngle[u2_index0], c='C1', marker='x')
# # plt.scatter(gait_data_swing, np.ones(len(gait_data_swing))*30, c='C1', marker='x')
# plt.legend(['Knee Angle', 'U_2 START', 'U_2 END', 'Heelstrikes'])
# plt.xlabel('Time (sec)')
# plt.show()

# ##Plot GRFs and heelstrikes:   
# plt.clf()
# plt.scatter(timestamp[heelstrike_index], grf[heelstrike_index] )
# plt.plot(timestamp, grf)
# plt.legend(['Heelstrikes', 'GRF Left'])
# plt.ylabel('Time Per Gait Cycle (sec)')
# plt.xlabel('Gait Cycle Number')
# plt.show()

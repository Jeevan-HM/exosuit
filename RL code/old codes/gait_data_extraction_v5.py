"""
gait_data_extraction_v5.py

version 2.1 = junmin modified the code to do the swing phase control (u2) feature extraction within the same loop of the stance phase part.
version 3 = emiliano modified the complete code structure so the data processing is closer to a real-time gait feature extraction implementation.
version 4 = emiliano modified to stream the gait data to the main code (v2) to simulate realtime sensor data.
version 5 = emiliano modified to incorporate the Mocap offline data for gait feature extraction as ground truth timings

"""

import numpy as np
import csv
import matplotlib.pyplot as plt
from time import time,sleep
from scipy.signal import find_peaks
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
    # plt.close('all')
except:
    pass


# #Function: Send Data message using ZMQ
# def send_data_socket0(obj, flags=0, protocol=-1):
#     """pack and compress an object with pickle and zlib."""
#     pobj = pickle.dumps(obj, protocol)
#     zobj = zlib.compress(pobj)
#     socket0.send(zobj, flags=flags)


# ## Setup ZMQ Connection:
# context = zmq.Context()
# #Socket0 = Destination to SEND data:
# socket0 = context.socket(zmq.PUB)
# socket0.setsockopt(zmq.CONFLATE,True)
# socket0.connect("tcp://127.0.0.1:2424") #check "IP:Port" number of the receiver.
# #note: Use ".bind()" command to connect to a local IP:port (e.g. this PC). Use ".connect" to connect to a remote IP:port (e.g. another PC, Raspberry Pi)
# print("Connected")



""" OPTIONS """

Export_Data = False



""" PROCESS SENSOR REALTIME DATA """
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



#Truncate data to match mocap data set (eliminate additional data)
sync_mocap = (data[:,1] == 1)  #(True/False)  Data synced with mocap
data = data[sync_mocap, :]

print(data.shape[0],'total data length') #row number
print(data.shape[1],'total data column') #column number



## Store data into variables:
timestamp = data[:,0]  #(sec) timestamps for controller data
timestamp = timestamp - timestamp[0]  #zero time values
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
heelstrike_export_sensor = []  #sotre indexes of HS of good data sets
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


#Get Time values:
t0 = time()  #get t=0 timesamp of loop start
time_now = time() - t0  #(sec) current time
outlier_detected_flag = False  #reset flag

######  Main Loop through each data sample (simulate data stream)  ######
for i in range(data.shape[0]):
    
    time_now = time() - t0
    # print('i =',i)
    outlier_detected_flag = False  #reset flag
    
    
    # #Wait until next timestamp is reached
    # while (time_now < timestamp[i]):
    #     time_now = time() - t0
    #     # print('waiting')
        
    # print('Time stamp reached.','t_now =', time_now, '  timesamp[i] =', timestamp[i])
    

    #Detect when u1 (stance inflation) is active & providing torque:
    if (stanceL_flags[i] == 1) and (stanceR_flags[i] == 0):  #check for left leg single support phase
        u1_flag = 1  #1=u1 is on & providing torque
    else:
        u1_flag = 0
      
        
    #Detect Start of Inflation for Stance Phase, U1 start timing
    if (u1_flag == 1) and (u1_flag_last == 0) and (u1_t0_detected == 0): #check when u1 activates/starts (u1 goes from 0 to 1)
        u1_t0_index.append( i )
        u1_t0_detected = 1
        # print('u1_t0_index =', u1_t0_index[-1])    


    #Detect End of Inflation for Stance Phase, U1 end timing
    if (u1_flag == 0) and (u1_flag_last == 1) and (u1_tf_detected == 0): #check when u1 deactivates/ends (u1 goes from 1 to 0)
        u1_tf_index.append( i )
        u1_tf_detected = 1
        # print('u1_tf_index = ',u1_tf_index[-1])
           
        
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
        # print('u2_t0_index =', u2_t0_index[-1])
          
        
    #Detect when u2 (swing inflation) is active & providing torque:
    if (u2_t0_detected == 1) and (stanceL_flags[i] == 0):  #check that u2_t0 has started and left leg is in swing
        u2_flag = 1  #1=u2 is on & providing torque
    else:
        u2_flag = 0
     
        
    #Detect End of Inflation for SWING Phase, u2 end timing
    if (u2_flag == 0) and (u2_flag_last == 1) and (u2_tf_detected == 0):  #check when u2 deactivates/ends (u2 goes from 1 to 0)
        u2_tf_index.append( i )
        u2_tf_detected = 1
        # print('u2_tf_index =', u2_tf_index[-1])
   
        
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
        # print('Heelstrike =',heelstrike_index[-1])
        
        
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
            continue  #skip to next itteration to avoid sending the data through zmq
        
        heelstrike_export_sensor.append( heelstrike_index[-1] ) #store heelstrikes of data export
           
        
        ## Stream/send data to RL main code
        #Send Data for Recording
        data_array = np.array([u1_timing[-1], u1_duration[-1], u2_timing[-1], u2_duration[-1] ])
        # data_array = 3.14
        
        #Min and Max values of gait data array (pre-computed)
        min_array = np.array([0.016539, 0.035189, 0.945412, 0.016353])
        max_array = np.array([2.687467, 2.799994, 8.171465, 5.699494])
        
        data_array_norm = -1 + 2*(data_array - min_array)/( max_array - min_array )
        
        data_array_stream = np.append(data_array, data_array_norm)
        
        ## Send Data through ZMQ socket
        # send_data_socket0(data_array_stream)
        # print("Data Sent: ", data_array_stream)
        
        # #Add a Delay to control sampling rate
        # sleep(0.1)


heelstrike_index = heelstrike_index[2:]  #remove the first two zero index values


########## -------  Data Export  ------- ##########

print('Number of outliers removed =', num_outliers_removed)

## Store timing data into variable for export
# gait_data = np.array([gait_cycle_duration, u1_timing, u1_duration, u2_timing, u2_duration]).transpose()
gait_data = np.array([u1_timing, u1_duration, u2_timing, u2_duration]).transpose() #without gait_cycle_duration

#Normalize export data
gait_data_norm = -1 + 2*(gait_data - np.min(gait_data, axis=0))/(np.max(gait_data, axis=0) - np.min(gait_data, axis=0) )

#Merge the gait_data and the (normalized) gait_data_norm
gait_data_export = np.append(gait_data, gait_data_norm, axis=1)


## Export CSV file: gait_data_x.csv
if Export_Data:
    filename = "gait_data/gait_data_v5.csv"
    with open(filename, 'w') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile,lineterminator = '\n') 
        # writing the data rows 
        csvwriter.writerows(gait_data_export) 
    print('Data Exported to:', filename)


# print("Gait Extraction Fininshed.")
# socket0.close()
# exit()






""" PROCESS MOCAP OFFLINE DATA """

## Load Data
trial_name = 'active_20psi'
# trial_name = 'inactive'
# emg = np.loadtxt(f"data/{trial_name}_emg.csv", delimiter=',', skiprows=5, usecols=0)
kinematics_mocap = np.loadtxt(f"data/{trial_name}_JointAngles.csv", delimiter=',', skiprows=5, usecols=2)
grf_L_mocap =  -np.loadtxt(f"data/{trial_name}_grf.csv", delimiter=',', skiprows=5, usecols=2)
grf_R_mocap =  -np.loadtxt(f"data/{trial_name}_grf.csv", delimiter=',', skiprows=5, usecols=3)

grf_L_mocap = grf_L_mocap - min(grf_L_mocap)
grf_R_mocap = grf_R_mocap - min(grf_R_mocap)

#Resample GRFs to match kinematics sampling rate
resample_vector = np.arange(0, len(grf_L_mocap), 20)
grf_L_mocap = grf_L_mocap[resample_vector]
grf_R_mocap = grf_R_mocap[resample_vector]



time_kinematics = np.arange(0, len(kinematics_mocap)/100, 1/100)  #100 Hz
time_grf = np.arange(0, len(grf_L_mocap)/2000, 1/2000)       #2000 Hz
# time_emg = np.arange(0, len(emg)/2000, 1/2000)       #2000 Hz
time_mocap = time_kinematics  #use the 100Hz as the mocap data sampling rate

# plt.plot(time_kinematics, kinematics_mocap)
# plt.plot(time_mocap, grf_L_mocap*(70/max(grf_L_mocap)))
# plt.plot(time_mocap, grf_R_mocap*(70/max(grf_R_mocap)))
# plt.legend(['Kinematics', 'GRFs Left', 'GRFs Right'])



# Find the Peaks of the Kinematics signal
ind_C, _ = find_peaks(kinematics_mocap, height=35, distance=150)  #Max Knee Angle (using kinematics)
ind_D, _ = find_peaks(-kinematics_mocap, height=-14, prominence=1)  #Min Knee Angle after swing
# peaks_A, _ = find_peaks(kinematics_mocap, height=(0, 30), prominence=1)  #does not provide the best performance


#Remove repeated values for feature D
ind_D_mod = []
for i in range(len(ind_D)):
    if i == 0:
        ind_D_mod.append( ind_D[i] ) 
        
    elif (ind_D[i] - ind_D[i-1]) > 100:
        ind_D_mod.append( ind_D[i] ) 
    
# ind_D = ind_D_mod


## Use GRFs to determine stance/swing phases to detect the points of interest
stance_L_mocap = ( grf_L_mocap > 100 )
stance_R_mocap = ( grf_R_mocap > 100 )
singlesupport_mocap = ( (stance_L_mocap == 1) & (stance_R_mocap == 0) )


#Find A,B using the single stance support phase
ind_A = []
ind_B = []
# ind_A = np.array([])
# ind_B = np.array([])

heelstrikes_L = []

for i in range(len(stance_L_mocap)):
    
    if i == 0:
        continue
        
    elif (singlesupport_mocap[i-1] == False) and (singlesupport_mocap[i] == True):
        ind_A.append(i)
        # ind_A = np.append(ind_A, i)
        
    elif (singlesupport_mocap[i-1] == True) and (singlesupport_mocap[i] == False):
        ind_B.append(i)
        # ind_B = np.append(ind_B, i)
        
    elif (stance_L_mocap[i-1] == False) and (stance_L_mocap[i] == True):
        # ind_D.append(i)  #does not provide the exact timing for Min Angle. Not best performance.
        heelstrikes_L.append(i)
        


#Plot GRFs and stance phases
plt.clf()
plt.plot(kinematics_mocap, label='kinematics')
msz = 15  #marker size
plt.plot(ind_A, kinematics_mocap[ind_A], '*', markersize=msz,  label='ind_A')
plt.plot(ind_B, kinematics_mocap[ind_B], '*', markersize=msz,  label='ind_B')
plt.plot(ind_C, kinematics_mocap[ind_C], '*', markersize=msz,  label='ind_C')
plt.plot(ind_D, kinematics_mocap[ind_D], '*', markersize=msz,  label='ind_D')
plt.plot(ind_D_mod, kinematics_mocap[ind_D_mod], '*', markersize=15,  label='ind_D_mod')

plt.axvline(heelstrikes_L[0], color='grey', linestyle='--', label='Heelstrikes')
for i in range(len(heelstrikes_L)):
    plt.axvline(heelstrikes_L[i], color='grey', linestyle='--')


plt.xlim((0, 1000))
plt.legend()
plt.grid()



bad_A = 0
bad_B = 0
bad_C = 0
bad_D = 0

gait_data_mocap = np.array([])
heelstrike_export_mocap = []

## Organize data by each gait cycle
for i in range(len(heelstrikes_L)-1):
# for i in range(1):
    
    print('Heelstrike index: ',heelstrikes_L[i])
    
    
    #Find A index
    # Find the index of the first value greater than valX
    indA_temp = ind_A[int( np.argwhere( np.array(ind_A) > heelstrikes_L[i])[0] )]
    print("Closes index A to heelstrike:",indA_temp)
    
    if indA_temp > heelstrikes_L[i+1]:  #check that A corresponds to current gait cycle (heelstrike) and not the next one
        print('index A is out of the current gait cycle')
        bad_A += 1
        continue
    
    
    #Find B index
    indB_temp = ind_B[int( np.argwhere( np.array(ind_B) > indA_temp)[0] )]
    # print("Closes index B to heelstrike:",indB_temp)

    if indB_temp > heelstrikes_L[i+1]:  #check that A corresponds to current gait cycle (heelstrike) and not the next one
        # print('index B is out of the current gait cycle')
        bad_B += 1
        continue
    
    
    #Find C index
    indC_temp = ind_C[int( np.argwhere( np.array(ind_C) > indB_temp)[0] )]
    # print("Closes index C to heelstrike:",indC_temp)

    if indC_temp > heelstrikes_L[i+1]:  #check that A corresponds to current gait cycle (heelstrike) and not the next one
        # print('index C is out of the current gait cycle')
        bad_C += 1
        continue
    
    
    #Find D index
    indD_temp = ind_D[int( np.argwhere( np.array(ind_D) > indC_temp)[0] )]
    print("Closes index D to heelstrike:",indD_temp)
    
    indA_temp_next = ind_A[int( np.argwhere( np.array(ind_A) > heelstrikes_L[i])[1] )]  #check index of next A point
    if indD_temp > indA_temp_next:  #Check that the D point is before the next/future A point
        print('index D is out of the current gait cycle')
        bad_D += 1
        continue
    
    
    #Compute timings
    A_timing = time_mocap[indA_temp] - time_mocap[heelstrikes_L[i]]
    B_timing = time_mocap[indB_temp] - time_mocap[heelstrikes_L[i]]
    C_timing = time_mocap[indC_temp] - time_mocap[heelstrikes_L[i]]
    D_timing = time_mocap[indD_temp] - time_mocap[heelstrikes_L[i]]
    u1_duration_mocap = time_mocap[indB_temp] - time_mocap[indA_temp]
    u2_duration_mocap = time_mocap[indD_temp] - time_mocap[indC_temp]
    gait_time = time_mocap[heelstrikes_L[i+1]] - time_mocap[heelstrikes_L[i]]
    
    heelstrike_export_mocap.append( heelstrikes_L[i] )
    
    print(gait_time)
    
    
    #Data Set for Export
    array_export = np.array([A_timing, u1_duration_mocap, C_timing, u2_duration_mocap])
    # array_export = np.array([indA_temp, indB_temp, indC_temp, indD_temp])
    
    if gait_data_mocap.size == 0:
        gait_data_mocap = array_export
    else:
        gait_data_mocap = np.vstack((gait_data_mocap, array_export))
    

#Check the gait cycles in mocap data that match the sensor data set
index_match_mocap = [] #indexes of mocap data that match the sensor export data set
for time_heelstrike in timestamp[heelstrike_export_sensor]:  #itterate over heelstrike times of sensor export data
    
    index_temp = np.abs(time_mocap[heelstrike_export_mocap] - time_heelstrike).argmin()
    
    index_match_mocap.append( index_temp )  #indexes of mocap data that match the sensor export data set
    
    #Check the matching of the heelstrikes for each gait cycle
    print('Time HS Sensor:', time_heelstrike)
    print('Time HS Mocap:', time_mocap[heelstrike_export_mocap[index_temp]])
    print('Index:', index_temp)
    print('................')
    
# Remove mocap gait cycles that does not match the sensor data set
gait_data_mocap = gait_data_mocap[index_match_mocap,:]

#Normalize export data
gait_data_mocap_norm = -1 + 2*(gait_data_mocap - np.min(gait_data_mocap, axis=0))/(np.max(gait_data_mocap, axis=0) - np.min(gait_data_mocap, axis=0) )

#Merge the gait_data and the (normalized) gait_data_norm
gait_data_mocap_export = np.append(gait_data_mocap, gait_data_mocap_norm, axis=1)


## Export CSV file: gait_data_x.csv
if Export_Data:
    filename = "gait_data/gait_data_v5_mocap.csv"
    with open(filename, 'w') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile,lineterminator = '\n') 
        # writing the data rows 
        csvwriter.writerows(gait_data_mocap_export) 
    print('Data Exported to:', filename)







""" ----------- Debugging and Plotting ----------- """


## New: check MOcap data vs Sensor Data

plt.clf()
plt.plot(time_mocap, kinematics_mocap, label='Mocap')
plt.plot(timestamp, kneeAngle, label='Sensor')

    
for xline in timestamp[heelstrike_index]: #plot heelstrikes
    plt.axvline(xline, color = 'green' , linestyle='--')  #plot heelstrikes as vertical lines
plt.axvline(timestamp[heelstrike_index[-1]], color = 'green' , linestyle='--', label='Heelstrikes Sensors')  #for legend label only


for xline in time_mocap[heelstrikes_L]: #plot heelstrikes
    plt.axvline(xline, color = 'c' , linestyle='--')  #plot heelstrikes as vertical lines
plt.axvline(timestamp[heelstrike_index[-1]], color = 'c' , linestyle='--', label='Heelstrikes Mocap')  #for legend label only

plt.legend()


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


# ## Plot Event Detection through time with Knee Kinematics
# plt.figure(1)
# plt.clf()
# plt.title("Gait Event Detection")
# plt.plot(timestamp, kneeAngle, label='Knee Angle')
# plt.scatter( timestamp[u1_t0_index], kneeAngle[u1_t0_index], c='C1', marker='x', label='U1 Start')
# plt.scatter( timestamp[u1_tf_index], kneeAngle[u1_tf_index], c='C2', marker='o', label='U1 End')
# plt.scatter( timestamp[u2_t0_index], kneeAngle[u2_t0_index], c='C3', marker='x', label='U2 Start')
# plt.scatter( timestamp[u2_tf_index], kneeAngle[u2_tf_index], c='C4', marker='o', label='U2 End')
# plt.plot(timestamp, Pd, label='Pd')
# for xline in timestamp[heelstrike_index]: #plot heelstrikes
#     plt.axvline(xline, color = 'grey' , linestyle='--')  #plot heelstrikes as vertical lines
# plt.axvline(timestamp[heelstrike_index[-1]], color = 'grey' , linestyle='--', label='Heelstrikes')  #for legend label only
# # plt.legend()
# plt.legend(ncol=10)  #ncol=10, allows horizontal legend
# plt.xlabel('Time (sec)')
# plt.show()


# #Plot the TIMING values computed
# plt.figure(2)
# plt.clf()
# plt.title("Timing Values Computed")
# plt.plot(u1_timing, label='U1 Timing')
# plt.plot(u2_timing, label='U2 Timing')
# plt.plot(u1_duration, label='U1 Duration')
# plt.plot(u2_duration, label='U2 Duration')
# plt.plot(gait_cycle_duration, label='Gait Cycle Duration')
# # plt.legend()
# plt.legend(ncol=10)  #ncol=10, allows horizontal legend
# plt.xlabel('Gait Cycle')
# plt.ylabel('Time (sec)')
# # plt.grid()
# plt.show()


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



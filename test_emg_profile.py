"""
gait_timing.py
Emiliano Quinones Yumbla  -- May 2023
Python 3

This code generate the gait timing features in realtime.

Versions:
    - v0 = emiliano created. First draft partially working version. Merged the two following codes: heurisctic_controller.py and gait_data_extraction.py
    - v1 = emiliano modified. Fully functional version, compute the timings of interest in realtime. Uses sensor data from sensors_read.py
    - v2 = junmin modified (6/19). Compute average of 5 gait cycles before sending to the online RL.
    - v3 = emiliano modified (6/21). Added Force Plate data for grf measurements. The smart shoes connection was disabled. also modified on 6/26 to add emg data send
    - v4 = emiliano modified (6/26). The EMG data is now being received, organized and processed for each corresponding muscle. The export data now includes the three EMG muscles of left leg (VL, RF, BF).
    - v5 = emiliano modified (7/12). Modified to temporally normalize the EMG rms vector to percent gait cycle. Also modified to normalize the timing values to percent gait cycle (from seconds to percent gait cycle). Also modified to normalize the EMG magnitude to the MVC. 
    - v6 = emiliano modified (7/16). Include the gait time data to be send out in the data stream.


"""

import numpy as np
from scipy import signal #for emg processing
from scipy.interpolate import splev, splrep 
import math #for emg processing
import zmq #communication
from time import time,sleep
import matplotlib.pyplot as plt



## Remove All Variables in Spyder Console:
from sys import exit #for debug: adds exit() function to spyder
try:
    from IPython import get_ipython
    get_ipython().magic('reset -f') #clear memory/variables
    # get_ipython().magic('clear')  #clear screen
except:
    pass


# ## Disable Warnings Deprecation
# import warnings
# warnings.filterwarnings("ignore", category=DeprecationWarning)
# print('NOTE: Deprecation WARNINGS were disabled. To re-enable warnings for debugging, comment this and restart kernel.')


def setup_communication_rcv(ip, port):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    socket.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only 
    socket.connect(f"tcp://{ip}:{port}")  # Replace with the appropriate address and port
    return socket



#Function: Test receive data from socket
def test_connection(socket_input, socket_label, flags=0):
    #socket_label = string. Specifies the sensor/device name of port to test
    
    #Setup ZMQ poller for Message rcv Timeout:
    timeout_limit = 3000 #(ms) Time limit to wait before timeout flag/error
    
    poller = zmq.Poller()
    poller.register(socket_input, zmq.POLLIN)

    socks = dict(poller.poll(timeout_limit))
    if socks:
        if socks.get(socket_input) == zmq.POLLIN:
            print(f"Connection Succesfull for: {socket_label}")
    else:
        print(f"**** ERROR: Connection FAILED for: {socket_label} ****")
        terminate_experiment()


def terminate_experiment():
    print("Terminating Experiment...")

    ## Close Communications:
    socket_data.close()
    socket_emg.close()
    socket_export.close()
    print("Connection to Communication Sockets Closed.")

    print("---------- EXPERIMENT FINALIZED ----------")
    exit() #close program
    


def emg_processing(emg_raw):
    #emg_raw: input numpy vector containing the raw emg signal

    """ Filtering """
    # Filter parameters
    fs = 2000  # (Hz) Sample rate (change accordingly)
    lowcut = 20  # (Hz) Low cut-off frequency of the bandpass filter (change accordingly)
    highcut = 450  # (Hz) High cut-off frequency of the bandpass filter (change accordingly)
    order = 4  # Filter order (change accordingly)
    
    # Apply a bandpass filter to the EMG samples
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = signal.butter(order, [low, high], btype="band")
    emg_filtered = signal.lfilter(b, a, emg_raw)
    
    # #Check Filtering with Plots
    # plt.plot(emg_raw)
    # plt.plot(emg_filtered)
    # plt.legend(['Raw','Filtered'])
    # plt.title('EMG Filtering')
    # exit()
    
    
    """ Compute Envelope/Profile of the EMG Signal """
    
    #RMS Envelope parameters
    window = 0.25; #[sec]  
    Hz = 2000;  #[Hz] Sampling Rate
    method = 2; #Method 2 = Simpson's Rule 
    
    #EMG signal to process the envelope
    emg_to_process = emg_filtered
    
    integral_window=round(window*Hz/method) #Steps in integral window. The method unit accounts for the number of points used per estimate
    signallength=len(emg_to_process)
    h=method/Hz  #steps / (steps/second) = duration of time step
        
    I=np.zeros(math.ceil(signallength/2))
    
    for a in range( math.floor(signallength/2-1) ):
        I[a] = h/3*(emg_to_process[a*2-1]**2 + 4*emg_to_process[a*2]**2 + emg_to_process[a*2+1]**2)
    
    cuml=np.zeros(len(I)) #cumulative integral
    cuml[0]=I[0]
    RMS=np.zeros(len(I)) #RMS value
    RMS[0] = math.sqrt(cuml[0]/h); #cumulative integral needs to be divided by the integral window)
    
    for b in range(1,integral_window+1):
        cuml[b]=cuml[b-1]+I[b];
        RMS[b]=math.sqrt(cuml[b]/(b*h));
        
    # for b=(integral_window+1):length(I)
    for b in range(integral_window, len(I)):
        cuml[b]=cuml[b-1]+I[b]-I[b-integral_window];
        RMS[b]=math.sqrt(cuml[b]/window);
    
    
    """ Resample RMS Envelope """        
    
    time_vect_temp = np.arange(0.002, 0.002*(len(RMS)+1), 0.002 )  # note: added +1 to match RMS length
    time_vect_temp = (time_vect_temp*1000).round()
    y = np.zeros(int(time_vect_temp[-1]))
    # t = np.arange(1, time_vect_temp[-1]+1, 1)  #note: +1 added to match length
    # time_rms = t  #resampled time vector
    
    for i in range(len(time_vect_temp)-2):
    
        lamda = (RMS[i+1]-RMS[i]) / (time_vect_temp[i+1]-time_vect_temp[i])  #this yields different than the matlab code.
        
        t1 = round(time_vect_temp[i]+1)
        t2 = round(time_vect_temp[i+1])
        
        yy = RMS[i] + lamda*( np.arange(t1, t2+1, 1) - time_vect_temp[i])  
        
        y[t1:t2+1] = yy
        
    RMS = y  #resampled RMS envelope
    
    # #Plot EMG signal and processed Envelope
    # plt.plot(emg_raw)
    # plt.plot(RMS)
    # plt.legend(['Raw', 'Envelope'])
    
    
    #Temporally Normalize/Resample the EMG_RMS to percent gait cycle
    temp = np.arange(1, len(RMS) + 1)
    x = 100 * (temp - np.min(temp)) / (np.max(temp) - np.min(temp))
    pgc = np.linspace(0, 100, 1001) #percent gait cycle vector

    spl = splrep(x, RMS)
    RMS_pgc = splev(pgc, spl)  #RMS emg resampled for percent gait cycle
    
    # #Remove Bad Start Envelope
    # RMS_pgc = RMS_pgc[10:]
    # pgc = pgc[10:]
    

    #Plot temporally resampled EMG Signal for percent gait cycle
    plt.plot(pgc, RMS_pgc)
    plt.xlabel('Percent Gait Cycle')
    
    terminate_experiment()
    
    
    # Compute the integral of the EMG Envelope
    integral_EMG = np.trapz(RMS_pgc)
    
    return integral_EMG  


""" Setup ZMQ Communication """
context = zmq.Context()

#IP for sensor data stream incoming (sensor_read.py)
ip_data = "localhost"  #local IP
port_data = "1111"
socket_data = setup_communication_rcv(ip_data, port_data)

#IP for EMG sensor data stream incoming
ip_emg = "localhost"  #local IP
port_emg = "2222"
socket_emg = setup_communication_rcv(ip_emg, port_emg)


#Socket to send gait timing data to Online RL
port_export = "3333" 
socket_export = context.socket(zmq.PUB)
socket_export.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
socket_export.bind(f"tcp://*:{port_export}") 


## Test data can be received
test_connection(socket_data, "sensors_read.py - sensor stream port 1111")
test_connection(socket_emg, "sensors_read.py - emg stream port 2222")
sleep(2)




#Initialize Variables for Gait States (from "heuristic_controller.py"):
flag_stance_left = 0  #(1/0) 1=left leg in stance phase. 0=left leg in swing phase.
flag_stance_right = 0  #(1/0) 1=right leg in stance phase. 0=right leg in swing phase.
flag_kneeLeft_max = 0  #(1/0) 1=left leg knee joint angle maximum detected. 0=NO max knee angle is detected
vect_kneeLeft_max = [0]*20  #Vector that keeps track of flag_kneeLeft_max
vect_kneeAngle = [0.,0.,0]  #data_type=list. Vector that keeps track of the Knee Angles for max detection.
first_kneeLeft_max = 0  #(1/0) 1=first Max knee angle detected in current gait cycle. 0=no detection yet of first max knee angle.
inflate_command = 0   #(1/0) 1=inflation commanded. 0=deflation commanded.
t0 = time() #(sec) get initial computer time stamp


""" #Initialize Variables for Timings (from "gait_data_extraction.py) """

# #Flags for event detection. These flags are used to prevent multiple detections of the same event in a single gait cycle.
heelstrike_detected = 0  #[1/0] flag for heelstrike detected in current gait cycle. 1=heelstrike was detected in current gait cycle, 0=heelstrike not detected yet
u1_t0_detected = 0  #[1/0] flag for u1 START detected in current gait cycle. 1= u1 START was detected, 0= u1 START not detected yet
u1_tf_detected = 0  #[1/0] flag for u1 END detected in current gait cycle. 1= u1 END was detected, 0= u1 END not detected yet
u2_t0_detected = 0  #[1/0] flag for u2 START detected in current gait cycle. 1=u2 START was detected, 0= u2 START not detected yet
u2_tf_detected = 0  #[1/0] flag for u2 END detected in current gait cycle. 1= u2 END was detected, 0= u2 END not detected yet
computed_timings = False  #[True/False] flag for when timings were computed for the current gait cycle. 1=timings computed. 2=timings not computed yet in current cycle

# #Flags for when control signal is active
# u1_flag = 0 #[1/0] flag for when u1 is active. 1=u1 is on (providing torque). 0=u1 is off (no torque)
u1_flag_last = 0 #[1/0]. this stores the u1_flag variable for the previous/last sample index
# u2_flag = 0 #[1/0] flag for when u2 is active. 1=u2 is on (providing torque). 0=u2 is off (no torque)
u2_flag_last = 0 #[1/0]. this stores the u2_flag variable for the previous/last sample index


# #Itteration Counters
# num_outliers_removed = 0 #counter for number of outliers removed

hs_t_vector = [0,0,0]  #vector to keep track of the heelstrike timings


#Variables to store TIME/timing data of interest
u1_t0 = 0.0
u1_tf = 0.0
u2_t0 = 0.0
u2_tf = 0.0

#Initialize EMG vectors for processing the signal
emg_vector = []
emg_VL = []
emg_RF = []
emg_BF = []

""" Main Loop """

t0 = time()  #time for experiment start
step_count = 1
number_data_rcvd = 9  #9 for emg. 5 for kinematics. 
average_array = np.zeros(number_data_rcvd)
while True:
    
    try: 
        
        time_loop_t0 = time() #to compute loop time/frequency
        
        """ Get Sensor Data """
        data_sensors = socket_data.recv_pyobj()
        print("data sensors received =", data_sensors) #debug
        
        angle_knee = data_sensors[0]
        grf_L = data_sensors[1]
        grf_R = data_sensors[2]
        
        
        """ Get EMG data """
        data_emg = socket_emg.recv_pyobj()  #contains all emg data (multiple muscles)
        # emg_vector.extend( data_emg )  #(OLD) store rcvd emg data into a SINGLE data list
        # print("emg data rcvd =", data_emg) #debug
        
        #Clasify and store the emg data into the corresponding muscles
        no_musles = 3  #modify if necessary to change number of muscles rcvd
        no_samples = int( len(data_emg)/no_musles )  #number of samples for each emg muscle/channel
        emg_VL.extend( data_emg[:no_samples] )
        emg_RF.extend( data_emg[no_samples:no_samples*2] )
        emg_BF.extend( data_emg[no_samples*2:no_samples*3] )
        
        
        
        """ Detect Stance and Swing Phase from forceplate GRF """
        ### NOTE: below are the codes taken from the "hueristic_controller.py"
        #This section is related to gait phase detection
        
        weight_treshold = 100 #(Newton) Weight threshold to detect stance phase
        
        #Left Leg Stance Phase Detection:
        if (grf_L > weight_treshold):
            flag_stance_left = 1
            print('LEFT = STANCE')
            first_kneeLeft_max = 0  #reset First Knee Max flag during stance for current cycle
        else:
            flag_stance_left = 0
            print('LEFT = SWING') 
        
        #Right Leg Stance Phase Detection:
        if (grf_R > weight_treshold):
            flag_stance_right = 1
            print('                             RIGHT = STANCE')
        else:
            flag_stance_right = 0
            print('                             RIGHT = SWING')
        
        
        
        """ IMU detect max Knee Joint Angle during Swing"""
        #Add Current Knee Angle Value to end of Vector that keeps track, and remove first value from vector.
        if (angle_knee != vect_kneeAngle[-1]): #Check that the joint angle value is not a repeated sample
            vect_kneeAngle = [vect_kneeAngle[1], vect_kneeAngle[2], angle_knee]
        
        # flag_kneeLeft_max = 1 #debug
        # print('knee flag overrided')
        
        if (vect_kneeAngle[0] < vect_kneeAngle[1]) and (vect_kneeAngle[1] > vect_kneeAngle[2]):
            flag_kneeLeft_max = 1
            first_kneeLeft_max = 1  #max found for current lift cycle
        else:
            flag_kneeLeft_max = 0
        # print("Flag Knee Max =", flag_kneeLeft_max )
        
        
        
        """ Detect and Compute Timing Events  """
        #### Below are the codes taken from the "gait_data_extraction_v6.py" code
        #This section is related to computing the timings related to the heuristic controller
        
        time_now = time() - t0
        # print('i =',i)
        outlier_detected_flag = False  #reset flag
        
    
        #Detect when u1 (stance inflation) is active & providing torque:
        if (flag_stance_left == 1) and (flag_stance_right == 0):  #check for left leg single support phase
            u1_flag = 1  #1=u1 is on & providing torque
        else:
            u1_flag = 0
          
            
        #Detect Start of Inflation for Stance Phase, U1 start timing
        if (u1_flag == 1) and (u1_flag_last == 0) and (u1_t0_detected == 0): #check when u1 activates/starts (u1 goes from 0 to 1)
            u1_t0 = time_now  #get timing u1 start (t0) - point A
            # u1_t0_index.append( i )  #old, get index
            u1_t0_detected = 1
            # print('u1_t0 = ',u1_t0)
                
    
        #Detect End of Inflation for Stance Phase, U1 end timing
        if (u1_flag == 0) and (u1_flag_last == 1) and (u1_tf_detected == 0): #check when u1 deactivates/ends (u1 goes from 1 to 0)
            u1_tf = time_now  #get timing u1 end/final (tf) - point B
            # u1_tf_index.append( i )  #old, get index
            u1_tf_detected = 1
            # print('u1_tf = ',u1_tf)
            
            #use this transition to swing to reset the flags for computing the timings and emg
            computed_timings = False #reset flag when new HS is detected
            
               
            
        #Store u1_flag for next itteration
        u1_flag_last = u1_flag
        
        #Reset u1 Flags in Swing Phase:
        if (flag_stance_left == 0): #check for swing phase
            heelstrike_detected = 0  #reset heelstrike detected flag
            u1_t0_detected = 0       #reset u1_t0 detected flag
            u1_tf_detected = 0       #reset u1_tf detected flag
            
         
           
        #Detect Start of Inflation in SWING phase, U2 start timing
        if (flag_kneeLeft_max == 1) and (flag_stance_left == 0) and (u2_t0_detected == 0):  #check for first knee max detected, and verify it's in swing phase
            u2_t0 = time_now  #get timing u2 start (t0) - point C
            # u2_t0_index.append( i )  #old, get index
            u2_t0_detected = 1
            # print('u2_t0 = ',u2_t0)
              
            
        #Detect when u2 (swing inflation) is active & providing torque:
        if (u2_t0_detected == 1) and (flag_stance_left == 0):  #check that u2_t0 has started and left leg is in swing
            u2_flag = 1  #1=u2 is on & providing torque
        else:
            u2_flag = 0
         
            
        #Detect End of Inflation for SWING Phase, u2 end timing
        if (u2_flag == 0) and (u2_flag_last == 1) and (u2_tf_detected == 0):  #check when u2 deactivates/ends (u2 goes from 1 to 0)
            u2_tf = time_now  #get timing u2 end/final (tf) - point C
            # u2_tf_index.append( i )  #old, get index
            u2_tf_detected = 1
            # print('u2_tf = ',u2_tf)
       
            
        #Store u2_flag for next itteration
        u2_flag_last = u2_flag
        
        #Reset u2 Flags in Stance Phase:
        if (flag_stance_left == 1):
            u2_t0_detected = 0    #reset u2_t0 detected flag
            u2_tf_detected = 0    #reset u2_tf detected flag
            
            
        #Detect Heelstrike:
        #Note: the Heelstrike detection occurs at the same instance as u2_tf
        if (flag_stance_left == 1) and (heelstrike_detected == 0):  #detect for first instance of stance phase/heelstrike
            hs_t = time_now  #get timing of heelstrike
            hs_t_vector = [hs_t_vector[1], hs_t_vector[2], hs_t]  #vector to keep track fo HS timings
            
            #Reset EMG vector for new gait cycle and store the last gait cycle emg vector for processing
            # emg_gait_cycle = emg_vector  #OLD
            emg_gait_cycle_VL = emg_VL
            emg_gait_cycle_RF = emg_RF
            emg_gait_cycle_BF = emg_BF
            # emg_vector = []  #OLD
            emg_VL = []
            emg_RF = []
            emg_BF = []

            heelstrike_detected = 1  #set flag to 1 since HS has been detected
            # computed_timings = False #reset flag when new HS is detected
            print('Heelstrike Time =', hs_t)
            
            
        ### Compute Timing Values ###
        #IF statement: Check that the event indexes are in correct order
        #Note: the Heelstrike detection occurs at the same instance as u2_tf. Within the IF statement below, heelstrike_index[-2] is the start of the gait cycle, and heelstrike_index[-1] is the end of the gait cycle.
        if (computed_timings == False) and (hs_t_vector[-2] < u1_t0) and (u1_t0 < u1_tf) and (u1_tf < u2_t0) and (u2_t0 < u2_tf):
            
            ##Compute timings (seconds) now that all events have been detected
            gait_cycle_time = hs_t_vector[-1] - hs_t_vector[-2]
            u1_time = u1_t0 - hs_t_vector[-2]
            u2_time = u2_t0 - hs_t_vector[-2]
            u1_duration = u1_tf - u1_t0
            u2_duration = u2_tf - u2_t0
            
            ##Normalize timings values to percent gait cycle
            u1_time = u1_time*(1/gait_cycle_time)
            u2_time = u2_time*(1/gait_cycle_time)
            u1_duration = u1_duration*(1/gait_cycle_time)
            u2_duration = u2_duration*(1/gait_cycle_time)
            
            ##Process EMG signal and integral
            emg_integral_VL = emg_processing( np.array(emg_gait_cycle_VL) )
            emg_integral_RF = emg_processing( np.array(emg_gait_cycle_RF) )
            emg_integral_BF = emg_processing( np.array(emg_gait_cycle_BF) )
            
            ##Normalize EMG magnitude to MVC
            mvc_VL = 1.7591446246833598e-05
            mvc_RF = 4.632237754736022e-05
            mvc_BF = 3.2187985320661625e-05
            emg_integral_VL = emg_integral_VL/mvc_VL
            emg_integral_RF = emg_integral_VL/mvc_RF
            emg_integral_BF = emg_integral_VL/mvc_BF
            
            #Normalize EMG Signal to avoid diverging values
            emg_integral_VL = emg_integral_VL/1000
            emg_integral_RF = emg_integral_RF/40000000
            emg_integral_BF = emg_integral_BF/60000000            
            
            #Clear emg data list for current gait cycle
            emg_gait_cycle_VL = []
            emg_gait_cycle_RF = []
            emg_gait_cycle_BF = []
            computed_timings = True
            
               
            """ Stream/send data to RL main code """
            #Send Data for Recording
            data_array = np.array([u1_time, u1_duration, u2_time, u2_duration, angle_knee*(np.pi/180), emg_integral_VL, emg_integral_RF, emg_integral_BF, gait_cycle_time])
            # data_array = np.array([u1_time, u1_duration, u2_time, u2_duration, angle_knee*(np.pi/180)]) #without EMG
            
            #Min and Max values of gait data array (pre-computed)
            min_array = np.array([0, 0, 0, 0, 0, 0])
            max_array = np.array([3, 3, 3, 3, 1, 3])
            
            #Normalize and organize data
            # data_array_norm = -1 + 2*(data_array - min_array)/( max_array - min_array )
            # data_array_export = np.append(data_array, data_array_norm)
            
            step_count = step_count + 1
            
            ####average steps######junmin
            if step_count == 6:
                data_array_export = average_array/5  #calculate average of 5 steps
                #NOTE, THE NORMALIZATION IS BEING IGNORED
                print("normalization export overrided")
                
                ## Send Gait timing Data to Online RL
                print(" ************************** DATA SENDING BELOW ***************************")    
                socket_export.send_pyobj(data_array_export) #send data to main.py
                
                step_count = 0
                average_array = np.zeros(number_data_rcvd)
                print("Export Array: ", data_array_export)
                
            elif step_count > 1: #####blank 1 step for control active
                average_array = np.add(average_array, data_array)  #sum for average computation
        
        
        
        #Compute Loop Sampling Frequency/Time
        # sleep(0.1)
        time_loop = time() - time_loop_t0
        # print('Loop time (sec): ', time_loop)
        try: #catch error when division by 0 due to time_loop=0
            print('Loop Frequency (Hz):', 1/time_loop)
        except:
            pass
        
        
        
        try:  #catch error of printing when emg integral variable has not been computed/created yet
            print("u1_time =",u1_time)
            print("u1_duration =",u1_duration)
            print("u2_time =",u2_time)
            print("u2_duration =",u2_duration)
            print("Heel Strikes =", hs_t_vector)
            print("vect_kneeAngle =", vect_kneeAngle)
            print("EMG integrals =", emg_integral_VL, emg_integral_RF, emg_integral_BF)
        except:
            pass
        
        print('--------------------------------')  #debug
                
        
    except KeyboardInterrupt:
        print("Program Stopped by User.")
        terminate_experiment() 
        
    # except:  #comment during debugging. This catches all errors in case communication is dropped AND when error/bug is encountered. This avoids the code getting stuck but also does not catch (ignores) errors for debug.
    #     print("*** ERROR: Communication issues/dropped OR bug in code *** ")
    #     terminate_experiment()
        
    







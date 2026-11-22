"""
emg_MVC.py
Emiliano Quinones Yumbla  -- May 2023
Python 3

This code generate the gait timing features in realtime.

Versions:
    - v1 = emiliano created. Collect data and compute the EMG MVC

"""

import numpy as np
from scipy import signal #for emg processing
from scipy.interpolate import splev, splrep 
import math #for emg processing
import zmq #communication
from time import time,sleep
import matplotlib.pyplot as plt
import csv  #for export


""" Options """
Export_Data = True



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
    socket_emg.close()
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
    
    
    # #Temporally Normalize/Resample the EMG_RMS to percent gait cycle
    # temp = np.arange(1, len(RMS) + 1)
    # x = 100 * (temp - np.min(temp)) / (np.max(temp) - np.min(temp))
    # pgc = np.linspace(0, 100, 1001) #percent gait cycle vector

    # spl = splrep(x, RMS)
    # RMS_pgc = splev(pgc, spl)  #RMS emg resampled for percent gait cycle

    # # #Plot temporally resampled EMG Signal for percent gait cycle
    # # plt.plot(pgc, RMS_pgc)
    # # plt.xlabel('Percent Gait Cycle')
    
    
    # # Compute the integral of the EMG Envelope
    # integral_EMG = np.trapz(RMS_pgc)
    
    return RMS  


""" Setup ZMQ Communication """
context = zmq.Context()


# #IP for EMG sensor data stream incoming
# ip_emg = "localhost"  #local IP
# port_emg = "2222"
# socket_emg = setup_communication_rcv(ip_emg, port_emg)


#EMG Sensors
#ip_EMG = "192.168.42.184"
#ip_emg = "192.168.20.10" #ethernet
#ip_EMG = "10.203.50.34" #asu network (use this one)
ip_emg = "127.0.0.1"  #receive from local emg_novicon.py
port_emg = "3000"
socket_emg = setup_communication_rcv(ip_emg, port_emg)


## Test data can be received
test_connection(socket_emg, "emg_novicon.py - emg stream port 3000")


#Initialize EMG vectors for processing the signal
emg_vector = []
emg_VL = []
emg_RF = []
emg_BF = []
emg_ST = []


plt.ion()
fig_live, axs_live = plt.subplots(2, 2, figsize=(10, 8))
fig_live.canvas.manager.set_window_title('Live Raw EMG Data')
line_VL, = axs_live[0, 0].plot([], [])
axs_live[0, 0].set_title("VL Raw")
line_RF, = axs_live[0, 1].plot([], [])
axs_live[0, 1].set_title("RF Raw")
line_BF, = axs_live[1, 0].plot([], [])
axs_live[1, 0].set_title("BF Raw")
line_ST, = axs_live[1, 1].plot([], [])
axs_live[1, 1].set_title("ST Raw")
plt.tight_layout()
window_size = 2000 # samples to visualize (~1 second)

""" Main Loop """

t0 = time()  #time for experiment start

while True:
    
    try: 
        
        time_loop_t0 = time() - t0 #to compute loop time/frequency
        
        """ Get EMG data """
        data_emg = socket_emg.recv_pyobj()  #contains all emg data (multiple muscles)
        # print("emg data rcvd =", data_emg) #debug
        
        #Clasify and store the emg data into the corresponding muscles
        no_musles = 4  #modify if necessary to change number of muscles rcvd
        no_samples = int( len(data_emg)/no_musles )  #number of samples for each emg muscle/channel
        emg_VL.extend( data_emg[:no_samples] )
        emg_RF.extend( data_emg[no_samples:no_samples*2] )
        emg_BF.extend( data_emg[no_samples*2:no_samples*3] )
        emg_ST.extend( data_emg[no_samples*3:no_samples*4] )
        
        # Live visual update
        if len(emg_VL) > window_size:
            start_idx = len(emg_VL) - window_size
        else:
            start_idx = 0
            
        x_data = list(range(len(emg_VL) - start_idx))
        
        line_VL.set_data(x_data, emg_VL[start_idx:])
        axs_live[0, 0].relim()
        axs_live[0, 0].autoscale_view()
        
        line_RF.set_data(x_data, emg_RF[start_idx:])
        axs_live[0, 1].relim()
        axs_live[0, 1].autoscale_view()
        
        line_BF.set_data(x_data, emg_BF[start_idx:])
        axs_live[1, 0].relim()
        axs_live[1, 0].autoscale_view()
        
        line_ST.set_data(x_data, emg_ST[start_idx:])
        axs_live[1, 1].relim()
        axs_live[1, 1].autoscale_view()
        
        plt.pause(0.001)
        
        # print('Time Loop =', time_loop_t0)
        
        # if time_loop_t0 < 2:
        #     emg_vector = []
        #     emg_VL = []
        #     emg_RF = []
        #     emg_BF = []
                
        
                
        
    except KeyboardInterrupt:
        print("Program Stopped by User.")
        print("------ Processing EMG and Computing MVC  ------")
        
        
        ##Process EMG signal and integral
        VL_envelope = emg_processing( np.array(emg_VL) )
        RF_envelope = emg_processing( np.array(emg_RF) )
        BF_envelope = emg_processing( np.array(emg_BF) )
        ST_envelope = emg_processing( np.array(emg_ST) )
        
        #Delete the first samples to fix big magnitude at start
        VL_envelope = VL_envelope[1000:]
        RF_envelope = RF_envelope[1000:]
        BF_envelope = BF_envelope[1000:]
        ST_envelope = ST_envelope[1000:]
        
        mvc_VL = max(VL_envelope)
        mvc_RF = max(RF_envelope)
        mvc_BF = max(BF_envelope)
        mvc_ST = max(ST_envelope)
        
        print('mvc_VL =', mvc_VL)
        print('mvc_RF =', mvc_RF)
        print('mvc_BF =', mvc_BF)
        print('mvc_ST =', mvc_ST)
        
        # ## Export MVC data to csv file
        # mvc_export = np.array([mvc_VL, mvc_RF, mvc_BF])
        # if Export_Data:
        #     filename = "mvc_EXPORT.csv"
        #     with open(filename, 'w') as csvfile: 
        #         # creating a csv writer object 
        #         csvwriter = csv.writer(csvfile,lineterminator = '\n') 
        #         # writing the data rows 
        #         csvwriter.writerows(mvc_export) 
        #     print('-------  Data Exported to:', filename)
            
        
        #Plot Data and MVC
        plt.ioff() # Turn off interactive mode for the final plot
        plt.close(fig_live) # Close the live plot
        
        fig_final, axs_final = plt.subplots(2, 2, figsize=(10, 8))
        fig_final.canvas.manager.set_window_title('Processed EMG Envelopes (MVC)')
        
        axs_final[0, 0].plot(VL_envelope, color='blue')
        axs_final[0, 0].set_title(f"VL Envelope (MVC: {mvc_VL:.4f})")
        
        axs_final[0, 1].plot(RF_envelope, color='orange')
        axs_final[0, 1].set_title(f"RF Envelope (MVC: {mvc_RF:.4f})")
        
        axs_final[1, 0].plot(BF_envelope, color='green')
        axs_final[1, 0].set_title(f"BF Envelope (MVC: {mvc_BF:.4f})")
        
        axs_final[1, 1].plot(ST_envelope, color='red')
        axs_final[1, 1].set_title(f"ST Envelope (MVC: {mvc_ST:.4f})")
        
        plt.tight_layout()
        plt.show()
        
        terminate_experiment() 
        



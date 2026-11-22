"""
sensors_read.py
Emiliano Quinones Yumbla  -- May 2023
Python 3

Versions:
	- v1 = emiliano created. Read sensor data from the IMUs, and Smart Shoes Left & Right. Using multi-threading to avoid data loss/delays.
	- v2 = emiliano modified. Added EMG data read. Added sending/exporting data to the next code/program (zmq port). Added initialization of ports before threading, and closing of ports after ending code. 
   - v3 = emiliano modified. Added Force Plate data for grf measurements. The smart shoes connection was disabled.
   - v4 = emilian modified (6/26). Modified EMG receiving data, the incoming data contains multiple muscles/channels in a single array. The data in queue is classified by each channel, and then organized when exporting data to main so that the export array is organized by each muscle. Also, changed sent data type from numpy to list. 
    
"""

import numpy as np
import zmq
import threading
from time import time,sleep
import queue

import csv

""" Options """
Read_Sensor_Data = True  #[T/F]; True = read sensor data and use corresponding IP address. False = receive data from a script (with local IP) that generates random sensor data.



## Remove All Variables in Spyder Console:
from sys import exit #for debug: adds exit() function to spyder
try:
    from IPython import get_ipython
    get_ipython().magic('reset -f') #clear memory/variables
    # get_ipython().magic('clear')  #clear screen
except:
    pass


## Disable Warnings Deprecation
import warnings
#warnings.filterwarnings("ignore", category=DeprecationWarning)
#print('NOTE: Deprecation WARNINGS were disabled. Comment this and restart kernel during debug.')




def setup_communication_rcv(ip, port):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    socket.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only
    if Read_Sensor_Data:
        socket.connect(f"tcp://{ip}:{port}")  #Connect to IP and port corresponding to sensors
    else:
        socket.connect(f"tcp://localhost:{port}")  #Debug: local IP to get simulated/offline data from scripts (instead of reading sensors).
    return socket


#Receive Data Function for threading
def receive_data(socket, port, result_queue):
    
    while True:  #threading loop
        # Receive the data
        value = socket.recv_pyobj()
        value = np.array(value)
        result_queue.put((port, value))  # Put the received value and port into the queue
        
        #Flag/Event to stop execution of this thread
        if event.is_set():
            print(f'Closing Thread for Port: {port}')
            break 
                    
        # #Debug, print received data
        # print('Data Port: ', port)
        # print('Data rcvd: ', value)
        

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
        print(f"******** ERROR: Connection FAILED for: {socket_label} ********")
        terminate_experiment()


def terminate_experiment():
    print("Terminating Experiment...")
    
    ## Stop excecution of multi-threads
    try:
        event.set()  
        print("Stopping Execution of Multi-Treads")
        sleep(1.5)  #wait to allow stopping threads
    except:  
        print("Error ocurred while terminating multi-threads.")
        pass #catches error in case multi-threading (event object) has not been created yet

    # Close Communications:
    print("Closing Communication Sockets ...")
    for socket_to_close in Sockets_All:
        socket_to_close.close()  #close socket
        print("Socket Status: ", socket_to_close)
    print("Connection to Communication Sockets Closed.")

    print("---------- EXPERIMENT FINALIZED ----------")
    exit() #close program
    


""" Setup ZMQ Communication """
context = zmq.Context()

#IMU Sensors
#ip_IMU = "192.168.42.184" #edison network
ip_IMU = "192.168.20.10" #ethernet
#ip_IMU = "10.203.50.34" #asu network (use this one)
port_IMU = "2000"
socket_IMU = setup_communication_rcv(ip_IMU, port_IMU)

#EMG Sensors
#ip_EMG = "192.168.42.184"
ip_EMG = "192.168.20.10" #ethernet
#ip_EMG = "10.203.50.34" #asu network (use this one)
# ip_EMG = "localhost"  #test simulate data
port_EMG = "7000"
socket_EMG = setup_communication_rcv(ip_EMG, port_EMG)

#Force Plate Sensors Treadmill/Vicon
#ip_forceplate = "192.168.42.184"
ip_forceplate = "192.168.20.10" #ethernet
#ip_forceplate = "10.203.50.34" #asu network (use this one)
# ip_forceplate = "localhost"  #test simulate data
port_forceplate = "8000"
socket_forceplate = setup_communication_rcv(ip_forceplate, port_forceplate)


# #Smart Shoes Left
# ip_ShoesL = "192.168.42.3"
# # ip_ShoesL = "localhost"  #test simulate data
# port_ShoesL = "3000"
# socket_ShoesL = setup_communication_rcv(ip_ShoesL, port_ShoesL)

# #Smart Shoes Right
# ip_ShoesR = "192.168.42.6"
# # ip_ShoesR = "localhost"  #test simulate data
# port_ShoesR = "6000"
# socket_ShoesR = setup_communication_rcv(ip_ShoesR, port_ShoesR)


#Socket to Export Sensor Data
# ip_data_export = "192.168.42.101"  #laptop PC ip
port_data_export = "1111" 
socket_data_export = context.socket(zmq.PUB)
socket_data_export.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
# socket_data_export.bind(f"tcp://{ip_data_export}:{port_data_export}")
socket_data_export.bind(f"tcp://*:{port_data_export}")

#EMG socket to main.py. Note: uses the same IP address as main.py
port_emg_export = "2222" 
socket_emg_export = context.socket(zmq.PUB)
socket_emg_export.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
# socket_emg_export.bind(f"tcp://{ip_data_export}:{port_emg_export}") 
socket_emg_export.bind(f"tcp://*:{port_emg_export}") 

#Store all sockets objects into a list/variable for closing them
Sockets_All = [socket_IMU, socket_forceplate, socket_EMG, socket_data_export, socket_emg_export] #using force plates
# Sockets_All = [socket_IMU, socket_ShoesL, socket_ShoesR, socket_EMG, socket_data_export, socket_emg_export] #using smart shoes


# #DEBUG: Test emg rcv one sample
# print('testing data rcv:')
# value_test = socket_EMG.recv_pyobj()
# # value_test = np.array(value_test)
# print("test value = ",value_test)
# exit()


# Test data can be received
test_connection(socket_IMU, "IMU")
test_connection(socket_EMG, "EMG")
test_connection(socket_forceplate, "Force Plates")
# test_connection(socket_ShoesL, "Shoes Left")
# test_connection(socket_ShoesR, "Shoes Right")
sleep(2)


""" Multi-Threading to read multiple sensors simultaneously """ 
# Create a thread-safe queue to store the received values
result_queue = queue.Queue()

#Create object (event) to stop the threadings
event = threading.Event()

# Create separate threads for receiving data at different sampling rates
thread_IMU = threading.Thread(target=receive_data, args=(socket_IMU, port_IMU, result_queue))  #joint angles
thread_EMG = threading.Thread(target=receive_data, args=(socket_EMG, port_EMG, result_queue))  #emg
thread_forceplate = threading.Thread(target=receive_data, args=(socket_forceplate, port_forceplate, result_queue))  #force plates
# thread_ShoesL = threading.Thread(target=receive_data, args=(socket_ShoesL, port_ShoesL, result_queue))  #shoe left
# thread_ShoesR = threading.Thread(target=receive_data, args=(socket_ShoesR, port_ShoesR, result_queue))  #shoe right

# Start the threads
thread_IMU.start()
thread_EMG.start()
thread_forceplate.start()
# thread_ShoesL.start()
# thread_ShoesR.start()


""" Main Loop """

# Create an empty numpy array to store the received values
# received_values = np.zeros((3))
export_array = np.zeros((5))  #contains the sensor data to be sent to main.py. export_array = [Knee_Angle, GRF_Left, GRF_Right]
export_array_last = np.zeros((5))  #keep track of previous sent array
emg_export = []   #this contains all the emg samples between data transmissions
#note, data to be streamed is: export_array = [knee_angle_left, grf_left, grf_right, knee_angle_right]
emg_VL = []
emg_RF = []
emg_BF = []

save_data = np.zeros((5))

current_time = time()
print("Starting Sensor Data Stream ...")

while True:

    try:    
        t0 = time()
        
        # Check if there are new values in the queue
        while not result_queue.empty():
            port, value = result_queue.get()
            # print('Data Port: ', port)
            # print('Data rcvd: ', value)
            
            """ Classify the value based on the port number """
            if port == port_IMU:  #IMU Knee Angles
                knee_angle_L = value[2]
                export_array[0] = knee_angle_L
                
                knee_angle_R = value[3]
                export_array[3] = knee_angle_R
                
            
            elif port == port_EMG:  #EMG
                emg_temp = value
                # emg_export.extend( emg_temp )  #OLD: store all emg muscle/channels in a single list
                # print('EMG rcvd =', emg_temp)
                
                #Clasify and store the emg data into the corresponding muscles
                no_musles = 3  #modify if necessary to change number of muscles rcvd
                no_samples =   int( len(emg_temp)/no_musles )  #number of samples for each emg muscle/channel
                emg_VL.extend( emg_temp[:no_samples] )
                emg_RF.extend( emg_temp[no_samples:no_samples*2] )
                emg_BF.extend( emg_temp[no_samples*2:no_samples*3] )
                
                
            elif port == port_forceplate:  #Forceplate GRFs
                grfs_L = -value[0] #note negative to fix direction
                export_array[1] = grfs_L
                # print('GRFS_Left =', grfs_L)
                
                grfs_R = -value[1] #note negative to fix direction
                export_array[2] = grfs_R
                # print('GRFS_Right =', grfs_R) 
            
            export_array[4] = time()-current_time
            # elif port == port_ShoesL:  #Smart Shoe Left
            #     grfsL_vector = value
            #     grfs_L = sum(grfsL_vector)
            #     export_array[1] = grfs_L
            #     # print('GRFS_Left =', grfs_L)
            save_data = np.vstack((save_data, export_array))       
                
            # elif port == port_ShoesR:  #Smart Shoe Right
            #     grfsR_vector = value
            #     grfs_R = sum(grfsR_vector)
            #     export_array[2] = grfs_R
            #     # print('GRFS_Right =', grfs_R)
                

        """ Send/print the data set array to gait_timing.py code  """
        if np.count_nonzero(export_array) > 0:
            
            ## Send Sensors data
            socket_data_export.send_pyobj(export_array.tolist()) #send data to main.py
            print("Export Array: ", export_array) #note: export_array = [Knee_Angle_Left, GRF_Left, GRF_Right, Knee_Angle_Right]

            ## Send EMG data
            emg_export = emg_VL + emg_RF + emg_BF  #organize the emg export, each muscle data appended one above the other (note emg_MUSCLE is list data type, so + symbol is not sum but actually joining lists)
            socket_emg_export.send_pyobj(emg_export)  #send emg vector to main.py (O)
            # print("EMG Length Exported :", len(emg_export))
            emg_export = []  #reset emg_export vector
            emg_VL = [] #reset emg vectors
            emg_RF = []
            emg_BF = []
            
            #Check that sensors are not lost:
            # labels_sensors = ["IMU", "SHOE LEFT", "SHOE RIGHT"]
            # for i in range(len(export_array)):    
            #     if export_array[i] == export_array_last[i]:
            #         print("WARNING: Possible Data Communication lost with:", labels_sensors[i])
            export_array_last = export_array

        
        # print("-------------------")
        frequency_sampling = 100  #(Hz)
        sleep(1 / frequency_sampling)  # Delay to set sampling frequency

        #Compute Loop Sampling Frequency/Time
        time_loop = time() - t0
        # print('Loop time (sec): ', time_loop)
        # print('Loop Frequency (Hz):', 1/time_loop)
        try: #catch error when division by 0 due to time_loop=0
            # print('Loop Frequency (Hz):', 1/time_loop)
            pass
        except:
            pass
        

    except KeyboardInterrupt:
        filename = "Thursday_yousef_1.csv"
        with open(filename, 'w') as csvfile: 
            # creating a csv writer object 
            csvwriter = csv.writer(csvfile,lineterminator = '\n') 
            # writing the data rows 
            csvwriter.writerows(save_data)   
        terminate_experiment()




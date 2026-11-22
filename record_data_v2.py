""" 
#record_sensors.py    
#modified: June 2023
#Python 3

This code reads data from the local socket in this PC and exports the data into a structured csv file.

Versions:
    - v1 = emiliano created, first working version to record sensor data
    - v2 = emiliano modified, added reading the mocap sync pin (raspi pin)

"""

#Import Libraries:
import numpy as np
from time import time,sleep,gmtime, strftime
import csv
#ZMQ Communication Libraries:
import zmq


## Remove All Variables in Spyder Console:
from sys import exit #for debug: adds exit() function to spyder
try:
    from IPython import get_ipython
    get_ipython().magic('reset -f') #clear memory/variables
    # get_ipython().magic('clear')  #clear screen
except:
    pass



def setup_communication_rcv(ip, port):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    socket.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only 
    socket.connect(f"tcp://{ip}:{port}")  #Connect to IP and port corresponding to sensors
    return socket





""" Setup ZMQ Communication """

#IP for sensor data stream incoming (from local PC)
ip_data = "localhost"  #local IP
port_data = "1111"
socket_data = setup_communication_rcv(ip_data, port_data)



#IP for RaspberryPi for Mocap Sync Pin read 
ip_sync = "192.168.42.220"  #Raspi IP
#ip_sync = "169.254.62.10"
port_sync = "9999"
socket_sync = setup_communication_rcv(ip_sync, port_sync)


print('ZMQ initialized')

#Initialize variables
t0 = time()
first_sample = True #flag if current iteration is the first sample (true).


while True:
    
    try:
        
        time_stamp = time() - t0
        
        #Receive Sensor Data (from local PC)
        data_msg = socket_data.recv_pyobj()
        print('sensor data =', data_msg)
         
        #Receive Mocap Sync Pin data (from raspi)
        raspi_msg = socket_sync.recv_pyobj()
        print('Sync pin =', raspi_msg)
        
        
        export_array = np.hstack([time_stamp, data_msg, raspi_msg])  #export vector for current sample
        print('export array =', export_array)


        if first_sample == True:
            export_matrix = np.hstack([time_stamp, data_msg, raspi_msg])  #export vector for current sample
            first_sample = False #change flag after first sample
        else:
            export_matrix = np.vstack((export_matrix, export_array))  #export matrix containing all samples
        
        
        
    except KeyboardInterrupt:
        
        print("Exporting Data ....")

        print('Data matrix to export :')
        print(export_matrix)
        
        ## Export Data Matrix to csv file
        filename = "OUTPUT_sensors_11_15_24_yousef_3.csv"
        with open(filename, 'w') as csvfile: 
            # creating a csv writer object 
            csvwriter = csv.writer(csvfile,lineterminator = '\n') 
            # writing the data rows 
            csvwriter.writerows(export_matrix) 
            
        print("Data Exported Successfully to:", filename)
        
        socket_data.close()
        exit()


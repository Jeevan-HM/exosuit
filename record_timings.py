#record_data.py    
#modified: June 2023
#Python 3

""" 
This code reads data from the local socket in this PC and exports the data into a structured csv file.

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
    socket.connect("tcp://localhost:1111")  # Replace with the appropriate address and port
    return socket


""" Setup ZMQ Communication """

#IP for sensor data stream incoming
ip_data = "localhost"  #local IP
port_data = "3333"
socket_data = setup_communication_rcv(ip_data, port_data)

#Initialize variables
t0 = time()


#Store first data line
time_stamp = time() - t0
data_msg = socket_data.recv_pyobj()
data_msg = np.append(time_stamp, data_msg)
data_matrix = data_msg  #create matrix to store all data for record


while True:
    
    try:
        
        time_stamp = time() - t0
        
        data_msg = socket_data.recv_pyobj()
        
        data_msg = np.append(time_stamp, data_msg)
        
        print(data_msg)
        
        
        data_matrix = np.vstack((data_matrix, data_msg))
        
        
        
    except KeyboardInterrupt:
        
        print("Exporting Data ....")

        print('Data matrix to export :')
        print(data_matrix)
        
        ## Export Data Matrix to csv file
        filename = "OUTPUT_timings_11_15_24_yousef_3.csv"
        with open(filename, 'w') as csvfile: 
            # creating a csv writer object 
            csvwriter = csv.writer(csvfile,lineterminator = '\n') 
            # writing the data rows 
            csvwriter.writerows(data_matrix) 
            
        print("Data Exported Successfully to:", filename)
        
        socket_data.close()
        exit()


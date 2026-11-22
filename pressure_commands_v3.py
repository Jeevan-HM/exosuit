"""
pressure_commands.py
Emiliano Quinones Yumbla  -- May 2023
Python 3

Versions:
    - v1 = emiliano created. This code generate the Pressure commands (Pd) for the pressure controller. This code reads sensor data to determine heelstrikes and keep a running clock over the current gait cycle.
    - v2 = emiliano modified. Changed to receive the GRF data from the forceplates. The treshold for stance detection was changed.
    - v3 = emiliano modified (6/30). Added resetting up the socket during every sensor read, inside the threading function. This is to avoid complete loss of communication with a socket when data stream is interrupted. Also added command to terminate/stop the threads when exiting the program.


"""

import numpy as np
from time import time,sleep
import zmq #communication
import threading



## Remove All Variables in Spyder Console:
try:
    from IPython import get_ipython
    get_ipython().magic('reset -f') #clear memory/variables
    # get_ipython().magic('clear')  #clear screen
    from sys import exit #for debug: adds exit() function to spyder
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
    
    ## Stop excecution of multi-threads
    try:
        event.set()  
        print("Stopping Execution of Multi-Treads")
        sleep(1)  #wait to allow stopping threads

    except:  
        pass #catches error in case multi-threading (event object) has not been created yet

    ## Close Communications:
    socket_sensor.close()
    socket_timing.close()
    socket_export.close()
    print("Connection to Communication Sockets Closed.")

    print("---------- EXPERIMENT FINALIZED ----------")
    exit() #close program



#sensor_read.py
def receiver_thread_sensor():  
    global data_sensor
    
    print('Starting sensor thread now')
    
    while True:
        #Flag/Event to stop execution of this thread
        if event.is_set():
            print(f'Closing Thread for Port: {port_sensor}')
            break 

        socket_sensor = setup_communication_rcv(ip_sensor, port_sensor)  #reset socket connection
        # print('connection successfull')
        value1 = socket_sensor.recv_pyobj()  #read incoming data
        data_sensor = value1  #store data into variable
        
        print('data sensor =',data_sensor)
        
        socket_sensor.close()
        
        ##Note: value1 = [angle, grf_L, grf_R]  , from sensors_read.py



#gait_timing.py
def receiver_thread_timing():
    global data_timing
    
    print('Starting gait timings thread now')
    
    while True:
        #Flag/Event to stop execution of this thread
        if event.is_set():
            print(f'Closing Thread for Port: {port_timing}')
            break 

        socket_timing = setup_communication_rcv(ip_timing, port_timing)  #reset socket connection
        value2 = socket_timing.recv_pyobj()  #read incoming data
        data_timing = value2   #store data into variable
        
        socket_timing.close()
        
        ##Notes: value2 = [tA, tB, tC, tD] (timings)


""""----------------------------------------------------------------"""

""" Setup ZMQ Communication """
context = zmq.Context()


#Socket to Export Pressure Commands Data (to pressure controller)
ip_export = "192.168.42.101"  #raspi this has issues
#ip_export = "*"  #(debug) local PC ip
port_export = "8888" 
socket_export = context.socket(zmq.PUB)
socket_export.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
socket_export.bind(f"tcp://{ip_export}:{port_export}")


#Receive sensor data from sensors_read.py
ip_sensor = "localhost"  
port_sensor = "1111"
socket_sensor = setup_communication_rcv(ip_sensor, port_sensor)

#Receive RL timing actions
ip_timing = "localhost"  
port_timing = "4444"
socket_timing = setup_communication_rcv(ip_timing, port_timing)


# Test data can be received
test_connection(socket_sensor, "sensors_read.py - sensor stream port 1111")
# test_connection(socket_timing, "main_RL.py - RL timing data port 4444")  #commented to avoid stuck when RL has not started
sleep(2)

#Close connections after test before starting threads
socket_sensor.close()
socket_timing.close()


""" Multi-Threading to read multiple sensors simultaneously """ 

#Create object (event) to stop the threadings
event = threading.Event()

# Start receiver threads
thread_sensor = threading.Thread(target=receiver_thread_sensor)
thread_timing = threading.Thread(target=receiver_thread_timing)

thread_sensor.start()
thread_timing.start()



def main_thread():
    global data_sensor, data_timing
    
    # initialize data
    data_sensor = [0, 0]
    data_timing = [500, 500, 500, 500]
    
    
    flag_stance_previous = 0
    t0_gaitcycle = time()  #start time of gait cycle
    
    Pd = 0

    while True:
        
        try:
        
            clock_gaitcycle = time() - t0_gaitcycle  #clock/current time within the gaitcycle (wrt the last heelstrike)  
            # print("Time Gait Cycle:", clock_gaitcycle)
            
            #Store rcvd data in variables
            grf_L = data_sensor[1]
            tA, tB, tC, tD = data_timing
            # print('GRF left =', grf_L)
            print('Timings RL =', tA,tB,tC,tD)
            
            """ Detect Stance and Swing Phase from forceplate GRF """
            
            weight_treshold = 100 #(Newton) Weight threshold to detect stance phase
            
            #Left Leg Stance Phase Detection:
            if (grf_L > weight_treshold):
                flag_stance = 1
                # print('LEFT = STANCE')
            else:
                flag_stance = 0
                # print('LEFT = SWING') 
            
            #Detect Heelstrikes
            if (flag_stance == 1) and (flag_stance_previous == 0):
                heelstrike_flag = 1
                t0_gaitcycle = time()  #reset start time of gait cycle
                # Pd = 0  #reset pressure to 0 in case heelstrike occurs during assistance
            else:
                heelstrike_flag = 0
            
            flag_stance_previous = flag_stance
            
            
            """ Determine Pressure Commands on Timings """
            if (clock_gaitcycle <= tA):
                Pd = 0 #psi
            elif (tA <= clock_gaitcycle <= tA+tB):
                Pd = 25  #psi stance
            elif (tA+tB <= clock_gaitcycle <= tC): #here, tB is duration (between A,B)
                Pd = 0
            elif (tC <= clock_gaitcycle <= tC+tD ):
                Pd = 20 #psi swing
            elif (clock_gaitcycle >= tC+tD): #here, tD is duration (between C,D)
                Pd = 0
            # print("Pd =", Pd)
            # Pd = 10 #debug
            
            #Pd = 5
            #Send Pressure Command (Pd) to pressure controller in raspi (python 2 program)         
            array = np.array([Pd], dtype=np.float64)
            socket_export.send(array.data)
            
            
            print("Sent Pd =", Pd)
            #print('Timings rcvd =', data_timing)
            
            print("---------------------------------")
    
            # Sleep for frequency control
            frequency_sampling = 100  #Hz
            sleep(1/frequency_sampling)
            
        except KeyboardInterrupt:
            terminate_experiment()


# Start main thread
main_thread()


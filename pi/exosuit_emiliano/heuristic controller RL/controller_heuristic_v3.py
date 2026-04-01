"""
Heuristic Controller
Emiliano Quinones Yumbla  -- January 2023
Python 2.7

Version Modifications:
- v2.0 = implemented controller with electro-pneumatic hardware (pressure sensors, valves, sync pin)
- v2.1 = removed the pressure controller from this script to avoid delays in the actuation of the valves. A new script was added named "pressure_controller_v1.py" which is the pressure controller that takes care of regulating pressure.
- v3 = emiliano modified (July 2023). Changed to read GRF data from the forceplates on the treadmill/vicon. NOTE: To stream data, the programs in the mocap PC must be running the "heuristic_version_.py" codes (heuristic_forceplate_stream_v1.py) and (heuristic_imu_stream_v3.2.py)
 
"""

#Import Libraries:
import numpy as np
from time import time,sleep
#ZMQ Communication Libraries:
import zmq
import zlib
import pickle
#Hardware libraries:
import Adafruit_ADS1x15 as ADC #ADC library
import RPi.GPIO as GPIO #Raspi I/O Pins


""" --- FUNCTIONS --- """

#Function: Receive Data from socket "socket_input"
def recv_data_socket(socket_input, poller_input, flags=0):

    socks = dict(poller_input.poll(timeout_limit))
    if socks:
        if socks.get(socket_input) == zmq.POLLIN:
            #Receive zmq message & Reconstruct with pickle library:
            zobj = socket_input.recv(flags)
            # if socket_input == socket_forceplates:
            #     return zobj
            pobj = zlib.decompress(zobj)
            return pickle.loads(pobj)
    else:
        print "***** ERROR: Communication with Sensors Dropped *****"
        terminate_experiment()


#Function: Send Data for Recording
def send_data_recording(obj, flags=0, protocol=-1):
    """pack and compress an object with pickle and zlib."""
    pobj = pickle.dumps(obj, protocol)
    zobj = zlib.compress(pobj)
    socket_DataRecord.send(zobj, flags=flags)


#Function: Send Data for Pressure Controller
def send_control_pressure(obj, flags=0, protocol=-1):
    """pack and compress an object with pickle and zlib."""
    pobj = pickle.dumps(obj, protocol)
    zobj = zlib.compress(pobj)
    socket_PressureController.send(zobj, flags=flags)


#Function: Read Pressure Sensor in actuator
def pressure_read():
    adc_channel = 1  #adc channel to read from (see ADC board)
    GAIN = 1  #setting for ADC
    adc_val =adc_pressure.read_adc(adc_channel, gain=GAIN)
    psi = adc_val*0.0018-7.3134 -0.20 #original pressure sensor equation
    return psi


#Function: Terminate Experiment: Close communications, deflate actuator and close valves.
def terminate_experiment():
    print "Terminating Experiment..."
    print "Wait while experiment terminates..."

    #send P=0 command signal to Pressure Controller to remove pressure
    P_des = 0
    send_control_pressure(P_des) 
    
    #Close Communications:
    socket_JointAngles.close()
    socket_forceplates.close()
    # socket_SmartShoesLEFT.close()
    # socket_SmartShoesRIGHT.close()
    socket_PressureController.close()
    socket_DataRecord.close()
    print "Connection to Communication Sockets Closed."

    print "---------- EXPERIMENT FINALIZED ----------"
    exit() #close program


""" --- Beginning of Script --- """


""" Setup & Initialization """

##Setup ZMQ Context
context = zmq.Context()

##Setup ZMQ Connection: Receive data from IMU Sensors
socket_JointAngles = context.socket(zmq.SUB)
socket_JointAngles.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only
socket_JointAngles.setsockopt(zmq.SUBSCRIBE,'')
socket_JointAngles.connect("tcp://192.168.42.184:2000") #check IP:port number matches sender. Using asterisk '*' is local IP.
#note: Use ".bind()" command to connect to a local IP:port (e.g. this PC). Use ".connect" to connect to a remote IP:port (e.g. another PC, Raspberry Pi)
print("Connected to IMUs Joint Angles.")


##Setup ZMQ Connection: Receive data from forceplates
socket_forceplates = context.socket(zmq.SUB)
socket_forceplates.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only
# socket_forceplates.setsockopt(zmq.SUBSCRIBE,'') #original, for message from a python2 program
socket_forceplates.setsockopt(zmq.SUBSCRIBE,b'') #new, for message from a python3 program, convert to byte
socket_forceplates.connect("tcp://192.168.42.184:8000") #check IP:port number matches sender. Using asterisk '*' is local IP.
#note: Use ".bind()" command to connect to a local IP:port (e.g. this PC). Use ".connect" to connect to a remote IP:port (e.g. another PC, Raspberry Pi)
print("Connected to Force Plates.")



## Setup ZMQ Connection: SEND data to Pressure Controller
socket_PressureController = context.socket(zmq.PUB)
socket_PressureController.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
socket_PressureController.bind("tcp://192.168.42.220:8888") #IP Raspi Local
# socket_DataRecord.connect("tcp://192.168.42.101:9999") #IP Laptop PC, edison ad-hoc network
print("Connected to Pressure Controller.")


## Setup ZMQ Connection: SEND data for Data Recording
#socket_DataRecord = Destination to SEND data.
socket_DataRecord = context.socket(zmq.PUB)
socket_DataRecord.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
socket_DataRecord.bind("tcp://192.168.42.220:9999") #IP Raspi Local
# socket_DataRecord.connect("tcp://192.168.42.101:9999") #IP Laptop PC, edison ad-hoc network
print("Connected to Data Recording program.")


#Setup ZMQ poller for Message rcv Timeout:
timeout_limit = 3000 #(ms) Time limit to wait before timeout flag/error

poller_JointAngles = zmq.Poller()
poller_JointAngles.register(socket_JointAngles, zmq.POLLIN)

poller_forceplates = zmq.Poller()
poller_forceplates.register(socket_forceplates, zmq.POLLIN)

print("Communication Initialization Finished. \n")



#Initialize Variables:
flag_stance_left = 0  #(1/0) 1=left leg in stance phase. 0=left leg in swing phase.
flag_stance_right = 0  #(1/0) 1=right leg in stance phase. 0=right leg in swing phase.
flag_kneeLeft_max = 0  #(1/0) 1=left leg knee joint angle maximum detected. 0=NO max knee angle is detected
vect_kneeLeft_max = [0]*20  #Vector that keeps track of flag_kneeLeft_max
vect_kneeAngle = [0.,0.,0]  #data_type=list. Vector that keeps track of the Knee Angles for max detection.
first_kneeLeft_max = 0  #(1/0) 1=first Max knee angle detected in current gait cycle. 0=no detection yet of first max knee angle.
inflate_command = 0   #(1/0) 1=inflation commanded. 0=deflation commanded.
t0 = time() #(sec) get initial computer time stamp
P_des = 0.0 #(psi) pressure desired
P_meas = 0.0 #(psi) pressure measured inside actuator
sync_mocap = 0  #(1/0) flag to synchronize with Mocap


#Set Pi's pins, using "GPIO Pin#"" convention:
pin_sync_mocap = 26  #Pin to Synchronize w/ Mocap

#Set Pin Mode:
GPIO.setmode(GPIO.BCM) #set pin naming convention (GPIO pin#)
GPIO.setup(pin_sync_mocap,GPIO.IN)


#Intialize ADC for Pressure Sensor:
adc_pressure = ADC.ADS1115()




""" Main Loop """
raw_input("Press Enter to Begin Experiment.")

while True:

    try:

        #Read Mocap Sync Pin
        sync_mocap = GPIO.input(pin_sync_mocap)

        """ Receive Joint Angles data """
        joint_angles = recv_data_socket(socket_JointAngles,poller_JointAngles) 
        # print("Joint Angles =", joint_angles)


        ## Store received angle data in variables:
        kneeAngle_left = joint_angles[2]  #(deg)
        kneeAngle_right = joint_angles[3]  #(deg)
        
        
        """ Receive GRF Force Plate data (new, from pressure controller) """
        message = socket_forceplates.recv()
        array = np.frombuffer(message, dtype=np.float64) # Convert the received message to a NumPy array
        grf_forceplates = array
        print("grf msg =", grf_forceplates)

        # """ Receive GRF Force Plate data (old) """
        # grf_forceplates  = recv_data_socket(socket_forceplates, poller_forceplates) 
        # print("grf msg =", grf_forceplates)

        #Ground Reaction Forces:
        GRF_left  = grf_forceplates[0] #(newton)
        GRF_right = grf_forceplates[1] #(newton)
  


        """ Detect Stance and Swing Phase from forceplate GRF """
        
        weight_treshold = 100 #(Newton) Weight threshold to detect stance phase

        #Left Leg Stance Phase Detection:
        if (GRF_left > weight_treshold):
            flag_stance_left = 1
            print('LEFT = STANCE')
            first_kneeLeft_max = 0  #reset First Knee Max flag during stance for current cycle
        else:
            flag_stance_left = 0
            print('LEFT = SWING') 

        #Right Leg Stance Phase Detection:
        if (GRF_right > weight_treshold):
            flag_stance_right = 1
            print('                             RIGHT = STANCE')
        else:
            flag_stance_right = 0
            print('                             RIGHT = SWING')

           

        """ IMU detect max Knee Joint Angle during Swing"""

        #Add Current Knee Angle Value to end of Vector that keeps track, and remove first value from vector.
        vect_kneeAngle = [vect_kneeAngle[1], vect_kneeAngle[2], kneeAngle_left]
        
        if (vect_kneeAngle[0] < vect_kneeAngle[1]) and (vect_kneeAngle[1] > vect_kneeAngle[2]):
            flag_kneeLeft_max = 1
            first_kneeLeft_max = 1  #max found for current lift cycle
        else:
            flag_kneeLeft_max = 0



        """ Detect Onset of Inflation / Deflation """
        
        #Predict Left Leg Single Stance Phase to Provide Extension Torque:
        if (flag_stance_left == 1) and (flag_stance_right == 0):
            inflate_command = 1
            P_des = 15 #(psi) pressure desired

        #Predict Swing Phase and Max Knee Joint Angle for onset of Extension Torque in Swing Phase:
        elif (flag_stance_left == 0) and (first_kneeLeft_max == 1):
            inflate_command = 1
            P_des = 10 #(psi) pressure desired

        else:
            inflate_command = 0
            P_des = 0 #(psi) pressure desired


        """ Operate Valves w/ Pressure Controller """

        #Send Desired Pressure (control signal) to the pressure controller
        send_control_pressure(P_des)
        print "P_des =", P_des

        P_meas = pressure_read() #(psi) Measure pressure in actuator
        print "                                                 Pressure =", P_meas


        """ Data Recording Export """
        #Set data structure for Recording
        data_array = np.array([sync_mocap, GRF_left, GRF_right, kneeAngle_left, kneeAngle_right, P_des, P_meas, inflate_command, flag_stance_left, flag_stance_right, flag_kneeLeft_max, first_kneeLeft_max])

        #Send Data for Recording
        send_data_recording(data_array)

        # print(data_array) #print message sent
        
        print("------------------")



    except KeyboardInterrupt:
        terminate_experiment()

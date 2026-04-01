"""
Heuristic Controller
Emiliano Quinones Yumbla  -- December 2022
Python 2.7

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


#Function: Receive Data from socket "socket_input"
def recv_data_socket(socket_input, poller_input, flags=0):

    socks = dict(poller_input.poll(timeout_limit))
    if socks:
        if socks.get(socket_input) == zmq.POLLIN:
            #Receive zmq message & Reconstruct with pickle library:
            zobj = socket_input.recv(flags)
            pobj = zlib.decompress(zobj)
            return pickle.loads(pobj)
    else:
        print "***** ERROR: Communication with Sensors Dropped *****"
        terminate_experiment()

    # #ORIGINAL Code:
    # """reconstruct a Python object sent with zipped_pickle"""
    # zobj = socket_input.recv(flags)
    # pobj = zlib.decompress(zobj)
    # return pickle.loads(pobj)


#Function: Send Data for Recording
def send_data_recording(obj, flags=0, protocol=-1):
    """pack and compress an object with pickle and zlib."""
    pobj = pickle.dumps(obj, protocol)
    zobj = zlib.compress(pobj)
    socket_DataRecord.send(zobj, flags=flags)


""" Functions: Valves Operation """
def inflate_knee():
    GPIO.output(pin_knee_inf,True)
    GPIO.output(pin_knee_def,False)

def deflate_knee():
    GPIO.output(pin_knee_inf,False)
    GPIO.output(pin_knee_def,True)
    
def hold_knee():
    GPIO.output(pin_knee_inf,False)
    GPIO.output(pin_knee_def,False)


#Function: Read Pressure Sensor in actuator
def pressure_read():
    adc_channel = 1  #adc channel to read from (see ADC board)
    GAIN = 1  #setting for ADC
    adc_val =adc_pressure.read_adc(adc_channel, gain=GAIN)
    psi = adc_val*0.0018-7.3134 -0.20 #original pressure sensor equation
    return psi


#Function: Pressure Controller: measure pressure, and operate valves to control actuator pressure
def pressure_controller():
    #The pressure controller is driven by the desired pressure (P_des)

    P_error_tresh = 0.7  #(psi) Pressure error treshold for inflation/deflation operation. This is the maximum pressure error allowed.

    P_meas = pressure_read() #(psi) Measure pressure in actuator

    if (P_meas > P_des+P_error_tresh):
        deflate_knee()
    elif (P_meas < P_des-P_error_tresh):
        inflate_knee()
    else:
        hold_knee()


#Function: Terminate Experiment: Close communications, deflate actuator and close valves.
def terminate_experiment():
    print "Terminating Experiment..."
    print "Wait while experiment terminates..."
    #Close Communications:
    socket_JointAngles.close()
    socket_SmartShoesLEFT.close()
    socket_SmartShoesRIGHT.close()
    socket_DataRecord.close()
    print "Connection to Communication Sockets Closed."

    #Deflate Actuator:
    print "Deflating..."
    deflate_knee()
    sleep(2)
    #Close Valves:
    print "Closing Valves..."
    hold_knee()

    GPIO.cleanup() #I/O pins cleanup
    print "---------- EXPERIMENT FINALIZED ----------"
    exit() #close program


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


##Setup ZMQ Connection: Receive data from Smart Shoes LEFT
socket_SmartShoesLEFT = context.socket(zmq.SUB)
socket_SmartShoesLEFT.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only
socket_SmartShoesLEFT.setsockopt(zmq.SUBSCRIBE,'')
# socket_SmartShoesLEFT.connect("tcp://192.168.42.3:3000") #check IP:port number matches sender. Using asterisk '*' is local IP.
socket_SmartShoesLEFT.bind("tcp://192.168.42.220:3000") #test w\ simulated data
#NOTE: It seems the smartshoes CANNOT send data to a remote IP:Port. Therefore, the data will be populated to a local IP:port. As such, the smartshoes will use ".bind()" to stream data into local IP, and the reciever should use ".connect()" to request data from the smartshoes which is a remote IP:port for the receiver.
print("Connected to Smart Shoes LEFT.")


##Setup ZMQ Connection: Receive data from Smart Shoes LEFT
socket_SmartShoesRIGHT = context.socket(zmq.SUB)
socket_SmartShoesRIGHT.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only
socket_SmartShoesRIGHT.setsockopt(zmq.SUBSCRIBE,'')
# socket_SmartShoesRIGHT.connect("tcp://192.168.42.6:6000") #check IP:port number matches sender. Using asterisk '*' is local IP.
socket_SmartShoesRIGHT.bind("tcp://192.168.42.220:6000") #test w\ simulated data
#NOTE: It seems the smartshoes CANNOT send data to a remote IP:Port. Therefore, the data will be populated to a local IP:port. As such, the smartshoes will use ".bind()" to stream data into local IP, and the reciever should use ".connect()" to request data from the smartshoes which is a remote IP:port for the receiver.
print("Connected to Smart Shoes RIGHT.")


## Setup ZMQ Connection: SEND data for Data Recording
#socket_DataRecord = Destination to SEND data.
socket_DataRecord = context.socket(zmq.PUB)
socket_DataRecord.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
socket_DataRecord.connect("tcp://192.168.42.101:9999") #check "IP:Port" number of the receiver.
print("Connected to Data Recording program.")


#Setup ZMQ poller for Message rcv Timeout:
timeout_limit = 300 #(ms) Time limit to wait before timeout flag/error

poller_JointAngles = zmq.Poller()
poller_JointAngles.register(socket_JointAngles, zmq.POLLIN)

poller_SmartShoesLEFT = zmq.Poller()
poller_SmartShoesLEFT.register(socket_SmartShoesLEFT, zmq.POLLIN)

poller_SmartShoesRIGHT = zmq.Poller()
poller_SmartShoesRIGHT.register(socket_SmartShoesRIGHT, zmq.POLLIN)

print("Communication Initialization Finished.")



#Initialize Variables:
flag_stance_left = 0  #(1/0) 1=left leg in stance phase. 0=left leg in swing phase.
flag_stance_right = 0  #(1/0) 1=right leg in stance phase. 0=right leg in swing phase.
flag_kneeLeft_max = 0  #(1/0) 1=left leg knee joint angle maximum detected. 0=NO max knee angle is detected
vect_kneeLeft_max = [0]*20  #Vector that keeps track of flag_kneeLeft_max
vect_kneeAngle = [0.,0.,0]  #data_type=list. Vector that keeps track of the Knee Angles for max detection.
first_kneeLeft_max = 0  #(1/0) 1=first Max knee angle detected in current gait cycle. 0=no detection yet of first max knee angle.
inflate_command = 0   #(1/0) 1=inflation commanded. 0=deflation commanded.
t0 = time() #(sec) get initial computer time stamp
P_des = 0 #(psi) pressure desired
P_meas = 0 #(psi) pressure measured inside actuator


#Set Pi's pins, using "GPIO Pin#"" convention:
pin_knee_inf = 23 #input air knee = CH2 in Mosfet
pin_knee_def = 24  #vacuum knee = CH4 in Mosfet
pin_hip_inf = 18 #input air hip = CH1 in Mosfet
pin_hip_def = 9  #vacuum hip = CH3 in Mosfet
pin_sync_mocap = 26  #Pin to Synchronize w/ Mocap

#Set Pin Mode:
GPIO.setmode(GPIO.BCM) #set pin naming convention (GPIO pin#)
GPIO.setup(pin_hip_inf,GPIO.OUT)
GPIO.setup(pin_hip_def,GPIO.OUT)
GPIO.setup(pin_knee_inf,GPIO.OUT)
GPIO.setup(pin_knee_def,GPIO.OUT)
GPIO.setup(pin_sync_mocap,GPIO.IN)


#Intialize ADC for Pressure Sensor:
adc_pressure = ADC.ADS1115()



""" Smart Shoe Calibration """
raw_input("Press Enter to Start Shoe Calibration. STAND STRAIGHT")

NoSamplesForCalibration = 100 

weight_stand_L = np.array([])
weight_stand_R = np.array([])

for i2 in range(NoSamplesForCalibration):

    #Read Smart Shoe Data:
    smart_shoes_left = recv_data_socket(socket_SmartShoesLEFT,poller_SmartShoesLEFT)
    smart_shoes_right = recv_data_socket(socket_SmartShoesRIGHT,poller_SmartShoesRIGHT)
    
    #Ground Reaction Forces:
    GRF_left  = smart_shoes_left.sum()
    GRF_right = smart_shoes_right.sum()
    

    #Store in Vector:
    weight_stand_L = np.append(weight_stand_L, GRF_left)
    weight_stand_R = np.append(weight_stand_R, GRF_right)


#Compute Average:
weight_stand_L = weight_stand_L.mean()
weight_stand_R = weight_stand_R.mean()


raw_input("RAISE Left Leg. Press enter to start no-stance calibration.")
weight_swing_L = np.array([])
for i2 in range(NoSamplesForCalibration):

    smart_shoes_left = recv_data_socket(socket_SmartShoesLEFT,poller_SmartShoesLEFT)

    #Ground Reaction Forces:
    GRF_left  = smart_shoes_left.sum()

    #Store in Vector:
    weight_swing_L = np.append(weight_swing_L, GRF_left)


#Compute Average:
weight_swing_L = weight_swing_L.mean()



raw_input("RAISE Right Leg. Press enter to start no-stance calibration.")
weight_swing_R = np.array([])
for i2 in range(NoSamplesForCalibration):

    smart_shoes_right = recv_data_socket(socket_SmartShoesRIGHT,poller_SmartShoesRIGHT)

    #Ground Reaction Forces:
    GRF_right = smart_shoes_right.sum()

    #Store in Vector:
    weight_swing_R = np.append(weight_swing_R, GRF_right)

#Compute Average:
weight_swing_R = weight_swing_R.mean()

print("Shoe Calibration Finished.")




""" Main Loop """
raw_input("Press Enter to Begin Experiment.")

while True:

    try:

        """ Receive Joint Angles data """
        joint_angles = recv_data_socket(socket_JointAngles,poller_JointAngles) 


        ## Store received angle data in variables:
        kneeAngle_left = joint_angles[2]  #(deg)
        kneeAngle_right = joint_angles[3]  #(deg)


        """ Receive Smart Shoes data """
        smart_shoes_left  = recv_data_socket(socket_SmartShoesLEFT,poller_SmartShoesLEFT) 
        smart_shoes_right = recv_data_socket(socket_SmartShoesRIGHT,poller_SmartShoesRIGHT)

        
        #Ground Reaction Forces:
        GRF_left  = smart_shoes_left.sum()
        GRF_right = smart_shoes_right.sum()
  


        """ Detect Stance and Swing Phase with Smart Shoes """

        #Left Leg Stance Phase Detection:
        if (GRF_left > weight_swing_L*1.05):
            flag_stance_left = 1
            print('LEFT = STANCE')
            first_kneeLeft_max = 0  #reset First Knee Max flag during stance for current cycle
        else:
            flag_stance_left = 0
            print('LEFT = SWING') 

        #Right Leg Stance Phase Detection:
        if (GRF_right > weight_swing_R*1.05):
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
            P_des = 20 #(psi) pressure desired

        #Predict Swing Phase and Max Knee Joint Angle for onset of Extension Torque in Swing Phase:
        elif (flag_stance_left == 0) and (first_kneeLeft_max == 1):
            inflate_command = 1
            P_des = 10 #(psi) pressure desired

        else:
            inflate_command = 0
            P_des = 0 #(psi) pressure desired



        """ Operate Valves w/ Pressure Controller """
        pressure_controller()



        """ Data Recording Export """
        #Set data structure for Recording
        data_array = np.array([pin_sync_mocap,GRF_left, GRF_right, kneeAngle_left, kneeAngle_right, P_des, P_meas, flag_stance_left, flag_stance_right, flag_kneeLeft_max, inflate_command, first_kneeLeft_max])

        #Send Data for Recording
        send_data_recording(data_array)

        # print(data_array) #print message sent




    except KeyboardInterrupt:
        terminate_experiment()

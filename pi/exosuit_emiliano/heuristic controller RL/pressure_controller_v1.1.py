"""
Pressure Controller
Emiliano Quinones Yumbla  -- January 2023
Python 2.7

Version Modifications:
- v1.0 = first version, created script for pressure controller, to regulate exosuit actuator pressure
- v1.1 = added a 2nd vacuum. Used the Raspi pin "pin_hip_def" to connect/control the vacuum.

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

#Function: Read Pressure Sensor in actuator
def pressure_read():
    adc_channel = 1  #adc channel to read from (see ADC board)
    GAIN = 1  #setting for ADC
    adc_val =adc_pressure.read_adc(adc_channel, gain=GAIN)
    psi = adc_val*0.0018-7.3134 -0.20 #original pressure sensor equation
    return psi


""" Functions: Valves Operation """
def inflate_knee():
    GPIO.output(pin_knee_inf,True)
    GPIO.output(pin_knee_def,False)
    GPIO.output(pin_hip_def,False)  #operate the 2nd vacuum, connected to the gpio "pin_hip_def".
    # print "                       INFlating"

def deflate_knee():
    GPIO.output(pin_knee_inf,False)
    GPIO.output(pin_knee_def,True)
    GPIO.output(pin_hip_def,True)  #operate the 2nd vacuum.
    # print "                           DEFlating"
    
def hold_knee():
    GPIO.output(pin_knee_inf,False)
    GPIO.output(pin_knee_def,False)
    GPIO.output(pin_hip_def,False)  #operate the 2nd vacuum.
    # print "                                   Hold"


#Function: Pressure Controller: measure pressure, and operate valves to control actuator pressure
def pressure_controller():
    #The pressure controller is driven by the desired pressure (P_des)

    P_error_tresh = 1.0  #(psi) Pressure error treshold for inflation/deflation operation. This is the maximum pressure error allowed.

    if (P_des == 0) and (P_meas > -1.5 ):  #keep deflating when P_des = 0 and the measured P_meas is near ~= 0 to avoid partial inflation
        deflate_knee()
    elif (P_des == 0) and (P_meas <= -1.5 ):  #hold and stop deflation when P_meas > -1.5 psi to avoid over deflation.
        hold_knee()
    elif (P_meas > P_des+P_error_tresh): #deflate if P_meas is higher than P_des
        deflate_knee()
    elif (P_meas < P_des-P_error_tresh): #deflate if P_meas is lower than P_des
        inflate_knee()
    else:
        hold_knee()  #hold pressure if P_meas is within the error treshold



#Function: Terminate Experiment: Close communications, deflate actuator and close valves.
def terminate_experiment():
    print "Wait while pressure controller terminates..."
    #Close Communications:
    socket_PressureController.close()
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



""" --- Beginning of Script --- """

""" Setup & Initialization """

##Setup ZMQ Context
context = zmq.Context()

##Setup ZMQ Connection: Receive data from high-level controller
socket_PressureController = context.socket(zmq.SUB)
socket_PressureController.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only
socket_PressureController.setsockopt(zmq.SUBSCRIBE,'')
socket_PressureController.connect("tcp://192.168.1.5:8888") #check IP:port number matches sender. Using asterisk '*' is local IP.


#Setup ZMQ poller for Message rcv Timeout:
timeout_limit = 10 #(ms) Time limit to wait before timeout flag/error

poller_PressureController = zmq.Poller()
poller_PressureController.register(socket_PressureController, zmq.POLLIN)

print("Communication Initialization Finished.")



#Initialize Variables:
t0 = time() #(sec) get initial computer time stamp
P_des = 0.0 #(psi) pressure desired
P_meas = 0.0 #(psi) pressure measured inside actuator


#Set Pi's pins, using "GPIO Pin#"" convention:
pin_knee_inf = 23 #input air knee = CH2 in Mosfet
pin_knee_def = 24  #vacuum knee = CH4 in Mosfet
pin_hip_inf = 18 #input air hip = CH1 in Mosfet
pin_hip_def = 9  #vacuum hip = CH3 in Mosfet. For this experiment, a 2nd vacuum for the knee was connected at this port.

#Set Pin Mode:
GPIO.setmode(GPIO.BCM) #set pin naming convention (GPIO pin#)
GPIO.setup(pin_knee_inf,GPIO.OUT)
GPIO.setup(pin_knee_def,GPIO.OUT)
GPIO.setup(pin_hip_def,GPIO.OUT)  # 2nd vacuum (for knee) is connected to this gpio "pin_hip_def"
# GPIO.setup(pin_hip_inf,GPIO.OUT)

#Intialize ADC for Pressure Sensor:
adc_pressure = ADC.ADS1115()


while True:

    try: 
        """ Receive Control Signal Data from High Level Controller """

        #settings:
        socket_input = socket_PressureController
        poller_input = poller_PressureController
        flags = 0

        #Receive ZMQ message with timeout option
        socks = dict(poller_input.poll(timeout_limit))
        if socks:
            if socks.get(socket_input) == zmq.POLLIN:
                #Receive zmq message & Reconstruct with pickle library:
                zobj = socket_input.recv(flags)
                pobj = zlib.decompress(zobj)
                # return pickle.loads(pobj)
                mess_recons = pickle.loads(pobj)

                #Store message into variable
                P_des = mess_recons #(psi) Desired Pressure

                # print "Message Received"
        else:
            # print "Delay in Message"
            pass



        #Measure Pressure in Actuator:
        P_meas = pressure_read() #(psi) Measure pressure in actuator

        #Print Data for Check:
        print "P_des = ", P_des, "    P_meas = ", P_meas


        """ Operate Valves w/ Pressure Controller """
        pressure_controller()


    except KeyboardInterrupt:
        terminate_experiment()


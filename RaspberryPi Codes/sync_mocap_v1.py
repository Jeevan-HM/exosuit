"""
sync_mocap.py
Mocap Sync Pin Read
Emiliano Quinones Yumbla  -- January 2023
Python 2.7

This codes read the Mocap sync pin in the Raspberry Pi and sends the value to the laptop PC.

Versions:
    - v1 = emiliano created. Read the sync pin from the Raspberry Pi. Send read data to the PC through ZMQ port.

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



#Function: Read Pressure Sensor in actuator
def pressure_read():
    adc_channel = 1  #adc channel to read from (see ADC board)
    GAIN = 1  #setting for ADC
    adc_val =adc_pressure.read_adc(adc_channel, gain=GAIN)
    psi = adc_val*0.0018-7.3134 -0.20 #original pressure sensor equation
    return psi



#Function: Terminate Experiment: Close communications, deflate actuator and close valves.
def terminate_experiment():
    print("Terminating Experiment...")
    
    #Close Communications:
    socket_DataRecord.close()
    print("Connection to Communication Sockets Closed.")

    print("---------- EXPERIMENT FINALIZED ----------")
    exit() #close program



#Function: Send Data for Recording
def send_data_recording(obj, flags=0, protocol=-1):
    """pack and compress an object with pickle and zlib."""
    pobj = pickle.dumps(obj, protocol)
    zobj = zlib.compress(pobj)
    socket_DataRecord.send(zobj, flags=flags)


""" Setup & Initialization """

##Setup ZMQ Context
context = zmq.Context()

## Setup ZMQ Connection: SEND data to PC
socket_DataRecord = context.socket(zmq.PUB)
socket_DataRecord.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
socket_DataRecord.bind("tcp://*:9999") #IP Raspi Local
# socket_DataRecord.connect("tcp://192.168.42.101:9999") #IP Laptop PC, edison ad-hoc network
print("Connected to Laptop PC receiver.")


""" Setup Raspi Pins """

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

        ## Read Mocap Sync Pin
        sync_mocap = GPIO.input(pin_sync_mocap)
        print('                 Sync Pin =', sync_mocap)


        ## Measure pressure in actuator
        P_meas = pressure_read() #(psi) 
        print("                                                 Pressure =", P_meas)


        """ Data Recording Export """
        #Set data structure for Recording
        data_list = [P_meas, sync_mocap]
        
        
        
        # Send Data for Recording (new to send to python3 program)
        socket_DataRecord.send_pyobj(data_list)  # Send the NumPy array as a Python object
        
        
        print('Exported Data = ',data_list) #print message sent
        print('----------------------------------')



    except KeyboardInterrupt:
        terminate_experiment()

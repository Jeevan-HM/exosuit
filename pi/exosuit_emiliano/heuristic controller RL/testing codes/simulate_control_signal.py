"""
Heuristic Controller
Emiliano Quinones Yumbla  -- January 2023
Python 2.7

Version Modifications:
- v2.0 = implemented controller with electro-pneumatic hardware (pressure sensors, valves, sync pin)
- v2.1 = removed the pressure controller from this script to avoid delays in the controller signal. A new script was added named "pressure_controller_v1.py" which is the pressure controller that takes care of regulating pressure.

"""

#Import Libraries:
import numpy as np
from time import time,sleep
#ZMQ Communication Libraries:
import zmq
import zlib
import pickle

""" --- FUNCTIONS --- """

#Function: Send Data for Pressure Controller
def send_control_pressure(obj, flags=0, protocol=-1):
    """pack and compress an object with pickle and zlib."""
    pobj = pickle.dumps(obj, protocol)
    zobj = zlib.compress(pobj)
    socket_PressureController.send(zobj, flags=flags)


#Function: Terminate Experiment: Close communications, deflate actuator and close valves.
def terminate_experiment():
    print "Terminating Test..."
    P_des = 0
    send_control_pressure(P_des) #send P=0 command signal to remove pressure
    socket_PressureController.close()

    print "---------- EXPERIMENT FINALIZED ----------"
    exit() #close program


""" Setup & Initialization """

##Setup ZMQ Context
context = zmq.Context()


## Setup ZMQ Connection: SEND data to Pressure Controller
socket_PressureController = context.socket(zmq.PUB)
socket_PressureController.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
socket_PressureController.bind("tcp://192.168.42.220:8888") #IP Raspi Local
# socket_DataRecord.connect("tcp://192.168.42.101:9999") #IP Laptop PC, edison ad-hoc network
print("Connected to Pressure Controller.")

#Initialize Variables:
t0 = time() #(sec) get initial computer time stamp
P_des = 0.0 #(psi) pressure desired
P_meas = 0.0 #(psi) pressure measured inside actuator


P_des = 10

print "P_des = ", P_des

while True:

    try:

        """ Operate Valves w/ Pressure Controller """
        #Send Desired Pressure (control signal) to the pressure controller
        send_control_pressure(P_des)

        # print P_des

        sleep(1/15)


    except KeyboardInterrupt:
        terminate_experiment()

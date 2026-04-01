#simulate_imu_data_stream.py     Created: Dec 10, 2020
#Last modified: 
""" 
This code sends blank data to simulate communication from the IMU sensors.
This code was used for debugging the controller algorithm.

"""

#Communication Libraries
import zmq
import zlib
import pickle
#Time, Math libraries:
from time import time,sleep,gmtime, strftime
import numpy as np
import math
from math import *
#Quaternion library:
from pyquaternion import Quaternion


class code_structure(object):
    """docstring for code_structure"""
    def __init__(self):
        
        #Options:
        self.Include_Torso_IMU = True  #include torso IMU
        self.First_Loop = True  #flag to determine first itteration run

        """ Initiate ZMQ communication"""
        context = zmq.Context()
        
        """  Set Sockets  """
        # Socket to Record Data Locally:
        self.context = zmq.Context()
        self.socket0 = context.socket(zmq.PUB)
        self.socket0.setsockopt(zmq.CONFLATE,1)
        self.socket0.bind("tcp://127.0.0.1:5555")



    #Function: Send message to socket for recording
    def send_zipped_socket0(self, obj, flags=0, protocol=-1):
        """pack and compress an object with pickle and zlib."""
        pobj = pickle.dumps(obj, protocol)
        zobj = zlib.compress(pobj)
        self.socket0.send(zobj, flags=flags)



    def compute_joint_angles(self):
    
        #Create Blank Data Structure to send to the controller:
        Angle_Knee = 60
        Angle_Hip = 30
        Speed_Knee = 1.5
        Speed_Hip = 2.3
        Speed_Thigh = 2.3


        #Send Data to Exosuit Controller
        exportArray = np.array([Angle_Knee, Angle_Hip, Speed_Knee, Speed_Hip, Speed_Thigh, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]) #array to export for data structure

        self.send_zipped_socket0(exportArray)

        print time(), "Sending Data To Controller"

        # print exportArray

        # print Angle_Knee, Angle_Hip, Speed_Knee, Speed_Hip

    




def main():
    try:

        code_struct=code_structure()  #this is the variable to call the main object with functions
        
        while True:
            code_struct.compute_joint_angles()



    except KeyboardInterrupt:
        exit()


if __name__ == '__main__':
    main()



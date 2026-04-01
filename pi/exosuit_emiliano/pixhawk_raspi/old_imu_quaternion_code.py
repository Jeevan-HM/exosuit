#Joint_Angles_IMU.py      Dec 10, 2020   Emiliano

""" 

Last Modified: Dec 10, 2020		Emiliano

""" 

from math import *
from time import time,sleep
import numpy as np
from numpy import savetxt
from numpy.linalg import norm as mag

import zmq
import capnp
import caliHipKnee_capnp
from pyquaternion import Quaternion


## Main Function
if __name__ == "__main__":

    #Initialize Communication with Edison on the IMU
    context = zmq.Context()
    socket1 = context.socket(zmq.SUB)
    socket1.setsockopt(zmq.CONFLATE,1)
    socket1.setsockopt(zmq.SUBSCRIBE,'')
    socket1.connect("tcp://192.168.42.4:1000")#Thigh


    #Initialize Communication with Edison on the IMU
    context = zmq.Context()
    socket2 = context.socket(zmq.SUB)
    socket2.setsockopt(zmq.CONFLATE,1)
    socket2.setsockopt(zmq.SUBSCRIBE,'')
    socket2.connect("tcp://192.168.42.5:1000")#Shank

    #Initialize Variables
    t0 = time()  #inintial time [sec]
    quat1 = [0,0,0,0]
    quat2 = [0,0,0,0]


    while True:
        try:
            #Receive Message
            en_msg1=socket1.recv()
            msg1=caliHipKnee_capnp.Message.from_bytes(en_msg1)

            en_msg2=socket2.recv()
            msg2=caliHipKnee_capnp.Message.from_bytes(en_msg2)

            t=round((time()-t0),4)

            ## Hip Joint Angle: Get Pitch Euler Angle and store as hip joint angle variable
            hip_angle = msg1.pitch  #[deg] Hip Joint Angle


            ## KNEE JOINT ANGLE: Calculate Knee Joint Angle Using Quaternions

            ##Store Quaternion Values into vector: Thigh=quat1; Shank=quat2
            #Thigh Quaternion = quat1
            quat1[0] = msg1.q1
            quat1[1] = msg1.q2
            quat1[2] = msg1.q3
            quat1[3] = msg1.q4

            #Shank Quaternion = quat2
            quat2[0] = msg2.q1
            quat2[1] = msg2.q2
            quat2[2] = msg2.q3
            quat2[3] = msg2.q4            


            ## Calculations for Knee Joint Angle using Quaternions
            offset = 150

            # Create quaternion object for first quat
            quat1 = Quaternion(quat1)

            # Create quaternion object for second quat
            # This quaternion is the inverse rotation
            quat2_inv = Quaternion(quat2).inverse

            # Combine the rotations to get a net rotation
            qd = quat1*quat2_inv

            # Rotate some vector to get a new vector
            vector = np.array([0.,0.,1.])
            vector_prime = qd.rotate(vector)

            # normalize vectors (redundant but safe)
            vector = vector / np.linalg.norm(vector)
            vector_prime = vector_prime  / np.linalg.norm(vector_prime)

            # Measure the angles between the vectors
            dot_product = np.dot(vector, vector_prime)
            knee_angle = degrees(np.arccos(dot_product))  #[deg] Knee Joint Angle

            # print round(hip_angle,2), round(knee_angle,2)
            print 'Hip Angle [deg] = ', round(hip_angle,2), 'Knee Angle [deg] = ', round(knee_angle,2)
            # print 'Knee Angle [deg] = ', round(knee_angle,2)


        except KeyboardInterrupt:
            print " Stopped by User"
            exit()
                        
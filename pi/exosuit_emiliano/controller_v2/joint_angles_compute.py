#join_angles_compute.py      Created: Dec 10, 2020
#Last modified: 
""" 
This code reads the data from Pixhawks and computes the joint angles

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
        self.Include_Torso_IMU = False  #include torso IMU
        self.First_Loop = True  #flag to determine first itteration run

        """ Initiate ZMQ communication"""
        context = zmq.Context()
        
        """  Set Sockets  """
        # Socket to Record Data Locally:
        self.context = zmq.Context()
        self.socket0 = context.socket(zmq.PUB)
        self.socket0.setsockopt(zmq.CONFLATE,1)
        self.socket0.bind("tcp://127.0.0.1:5555")

        # 1st Pixhawk: (Shank)
        self.socket1=context.socket(zmq.SUB) ### sub to PC socket0
        self.socket1.setsockopt(zmq.SUBSCRIBE,'')
        self.socket1.setsockopt(zmq.CONFLATE,True)
        self.socket1.connect("tcp://127.0.0.1:1111")

        # 2nd Pixhawk: (Thigh)
        self.socket2=context.socket(zmq.SUB) ### sub to PC socket0
        self.socket2.setsockopt(zmq.SUBSCRIBE,'')
        self.socket2.setsockopt(zmq.CONFLATE,True)
        self.socket2.connect("tcp://127.0.0.1:2222")

        if self.Include_Torso_IMU:
            # 3rd Pixhawk: (Torso)
            self.socket3=context.socket(zmq.SUB) ### sub to PC socket0
            self.socket3.setsockopt(zmq.SUBSCRIBE,'')
            self.socket3.setsockopt(zmq.CONFLATE,True)
            self.socket3.connect("tcp://127.0.0.1:3333")



    #Function: Send message to socket for recording
    def send_zipped_socket0(self, obj, flags=0, protocol=-1):
        """pack and compress an object with pickle and zlib."""
        pobj = pickle.dumps(obj, protocol)
        zobj = zlib.compress(pobj)
        self.socket0.send(zobj, flags=flags)

    #Receive Message Data    
    def recv_zipped_pickle1(self,flags=0):
        """reconstruct a Python object sent with zipped_pickle"""
        zobj = self.socket1.recv(flags)
        pobj = zlib.decompress(zobj)
        return pickle.loads(pobj)

    #Receive Message Data    
    def recv_zipped_pickle2(self,flags=0):
        """reconstruct a Python object sent with zipped_pickle"""
        zobj = self.socket2.recv(flags)
        pobj = zlib.decompress(zobj)
        return pickle.loads(pobj)

    #Receive Message Data    
    def recv_zipped_pickle3(self,flags=0):
        """reconstruct a Python object sent with zipped_pickle"""
        zobj = self.socket3.recv(flags)
        pobj = zlib.decompress(zobj)
        return pickle.loads(pobj)

    
    #Convert Quaternion to Euler Angles
    def quat2euler(self, Quat):
        #Get Quaternion elements
        q0 = Quat[0] #w
        q1 = Quat[1] #x
        q2 = Quat[2] #y
        q3 = Quat[3] #z

        #Compute roll, pitch, yaw  
        roll  = math.atan2(2*(q0*q1+q2*q3),  1-2*(q1*q1 + q2*q2));
        pitch = math.asin(2*(q0*q2-q3*q1));
        yaw = math.atan2(2*(q0*q3+q1*q2),  1-2*(q2*q2 + q3*q3));

        #Convert to Degrees:
        roll = math.degrees(roll)
        pitch = math.degrees(pitch)
        yaw = math.degrees(yaw)

        return roll,pitch,yaw


    def stand_calibration(self):
        #Receive Message From Pixhawk IMUs
        msg1=self.recv_zipped_pickle1() #Shank
        msg2=self.recv_zipped_pickle2() #Thigh
        if self.Include_Torso_IMU:
            msg3=self.recv_zipped_pickle3() #Torso


        #Store Initial Quaternion Values as Quaternion object
        self.quat_shank0 = Quaternion( msg1[:4] )
        self.quat_thigh0 = Quaternion( msg2[:4] )
        if self.Include_Torso_IMU:
            self.quat_torso0 = Quaternion( msg3[:4] )




    def compute_joint_angles(self):
        #Receive Message From Pixhawk IMUs
        msg1=self.recv_zipped_pickle1() #Shank
        msg2=self.recv_zipped_pickle2() #Thigh
        if self.Include_Torso_IMU:
            msg3=self.recv_zipped_pickle3() #Torso

        #Create Quaternion Object
        quat_shank = Quaternion( msg1[:4] )
        quat_thigh = Quaternion( msg2[:4] )
        if self.Include_Torso_IMU:
            quat_torso = Quaternion( msg3[:4] )


        #Align each IMU to its initial orientation
        quat_shank = self.quat_shank0.conjugate * quat_shank
        quat_thigh = self.quat_thigh0.conjugate * quat_thigh
        if self.Include_Torso_IMU:
            quat_torso = self.quat_torso0.conjugate * quat_torso


        #Quaternion Difference (Joint Angle in Quaternion)

        quat_knee = quat_shank.conjugate * quat_thigh
        if self.Include_Torso_IMU:
            quat_hip = quat_thigh.conjugate * quat_torso


        #Convert Quaternion to Euler Angles
        [_,pitch_thigh,_] = self.quat2euler(quat_thigh)  #Thigh Pitch Angle
        [_,pitch_knee,_] = self.quat2euler(quat_knee) #Knee Pitch Angle
        if self.Include_Torso_IMU:
            [_,pitch_hip,_] = self.quat2euler(quat_hip)  #Hip Pitch Angle


        #Store Joint Angle Value
        Angle_Knee = pitch_knee
        if self.Include_Torso_IMU:
            Angle_Hip = pitch_hip
        else:
            Angle_Hip = pitch_thigh  #Use Thigh Pitch (Phase) Angle for the hip joint angle


        # Hip Angular Speed (from thigh gyro):
        Speed_Thigh = msg2[5]  #read thigh gyroscope reading (rad/s)
        Speed_Hip = math.degrees(Speed_Thigh)  #(deg/s) store into variable
        

        #Compute Knee Joint Speed (numerical derivative):
        t_now = time() #(sec)
        if (self.First_Loop == False):
            dt = t_now - self.t_last  #change in time (sec)
            Speed_Knee = (Angle_Knee - self.last_angle_knee) / dt
        else:
            Speed_Knee = 0.0 #firs loop value


        #Update last Values for Next Itteration
        self.t_last = t_now
        self.last_angle_knee = Angle_Knee
        self.last_angle_hip = Angle_Hip
        self.First_Loop = False



        #Send Data to Exosuit Controller
        exportArray = np.array([Angle_Knee, Angle_Hip, Speed_Knee, Speed_Hip, Speed_Thigh, quat_shank[0], quat_shank[1], quat_shank[2], quat_shank[3], quat_thigh[0], quat_thigh[1], quat_thigh[2], quat_thigh[3]]) #array to export for data structure

        self.send_zipped_socket0(exportArray)
        # print exportArray

        print Angle_Knee, Angle_Hip, Speed_Knee, Speed_Hip





def main():
    try:

        code_struct=code_structure()  #this is the variable to call the main object with functions
        
        raw_input("Press Enter to Start Standing Calibration. Stand Still.")

        code_struct.stand_calibration()

        raw_input("Press Enter to Start Data Collection.")

        # code_struct.get_zero_time()

        while True:
            code_struct.compute_joint_angles()





    except KeyboardInterrupt:
        exit()


if __name__ == '__main__':
    main()



#Test that Raspi is recieving the joint angles from the Mocap/Noraxon_IMU PC
#This Code runs on the Raspberry Pi (or destination of the IMU Joint Angle data)

#Time, Math Libraries:
from time import time,sleep
import numpy as np
#ZMQ Communication Libraries:
import zmq
import zlib
import pickle


#Function: Receive Joint Angle Data message
def recv_zipped_pickle1(flags=0):
    """reconstruct a Python object sent with zipped_pickle"""
    zobj = socket0.recv(flags)
    pobj = zlib.decompress(zobj)
    return pickle.loads(pobj)


##Setup ZMQ Connection:
context = zmq.Context()
# socket0 = RECEIVE Joint Angles from Python code
socket0 = context.socket(zmq.SUB)
socket0.setsockopt(zmq.CONFLATE,1)
socket0.setsockopt(zmq.SUBSCRIBE,'')
# socket0.connect("tcp://192.168.42.184:2000")  #chech IP:port matches IMU stream sender code
# socket0.connect("tcp://10.203.49.180:2000")  #IP of Mocap PC in asu network
socket0.connect("tcp://192.168.42.184:2000")  #IP of Mocap PC in ad-hoc edison network
# socket0.bind("tcp://192.168.42.101:2000") #IP of this laptop PC-local in ad-hoc edison network

print('Connected.')


while True:

    print("Trying to Receive Data:")

    """ Read and Update IMU Joint Angles """
    msg_imu = recv_zipped_pickle1() 

    print(msg_imu) #for debug

    #Store received angle data in variables:
    hip_left = msg_imu[0]
    hip_right = msg_imu[1]
    knee_left = msg_imu[2]
    knee_right = msg_imu[3]
    ankle_left = msg_imu[4]
    ankle_right = msg_imu[5]

    print('Knee Angle Left = ',knee_left) #for debug

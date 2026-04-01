#### This version calculates the parameters in raspi3 while the recording and ploting
#### is done on the laptop
### Modified: September 8, 2020
import zmq
from time import time,sleep
import capnp
import cali_capnp
import numpy as np



if __name__ == '__main__':
    #####
    samples=1
    g1=[0.0]*3
    g2=[0.0]*3
    w1=[0.0]*3
    w2=[0.0]*3
    num=0.
    den=0.
    told=0.
    i = 0. 
    
    #Setup Connection to Edison IP address
    context = zmq.Context()
    socket1 = context.socket(zmq.SUB)
    socket1.setsockopt(zmq.CONFLATE,1)
    socket1.setsockopt(zmq.SUBSCRIBE,'')
    socket1.connect("tcp://192.168.42.10:1000") #Thigh Edison IMU

    t0=time()
    
    print "STANDING CALIBRATION"
    raw_input("Press Enter to Begin Standing Calibration")
    
    #Get angle values for 5 seconds and use this average to zero (tare) the joint angle wrt straight
    for i_cal in range (1,100):
        en_msg1=socket1.recv()
        msg1=cali_capnp.Message.from_bytes(en_msg1)
        
        hip_angle = msg1.pitch
        
        
    print "Ini Done"
    while True:
        try:
            en_msg1=socket1.recv()
            msg1=cali_capnp.Message.from_bytes(en_msg1)
            t=round((time()-t0),4)
            
            hip_angle = msg1.pitch
            
            print "Time:",round(t,1)," Pitch=", round(hip_angle,2)
            
            sleep(0.1)


        except KeyboardInterrupt:
                print " Stopped by User"
                exit()
                                


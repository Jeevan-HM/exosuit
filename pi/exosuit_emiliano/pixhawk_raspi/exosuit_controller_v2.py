""" exosuit_controller.py       October 12, 2020   Emiliano
    This code is the controller for the exosuit.
    Joint angle data is received from a python code that published computed joint angles to socket 0.
    Last Modified: December 14, 2020    Emiliano
"""

#Time, Match Libraries
from time import time,sleep
import numpy as np
from numpy import savetxt
from numpy.linalg import norm as mag

#Communication Libraries
import zmq
import zlib
import pickle


class exosuit_control(object):
    """docstring for ClassName"""
    def __init__(self):    
        context = zmq.Context()
        #IMU Connection Setup

        #Socket0 =  Local Socket on this PC for data record
        self.socket0 = context.socket(zmq.PUB)
        self.socket0.setsockopt(zmq.CONFLATE,1)
        self.socket0.bind("tcp://127.0.0.1:9999")

        # socket1 = Joint Angles from Python code
        self.socket1 = context.socket(zmq.SUB)
        self.socket1.setsockopt(zmq.CONFLATE,1)
        self.socket1.setsockopt(zmq.SUBSCRIBE,'')
        self.socket1.connect("tcp://127.0.0.1:5555") 


    def send_zipped_socket0(self, obj, flags=0, protocol=-1):
        """pack and compress an object with pickle and zlib."""
        pobj = pickle.dumps(obj, protocol)
        zobj = zlib.compress(pobj)
        self.socket0.send(zobj, flags=flags)


    #Receive Joint Angle Data message: = [knee_angle, hip_angle, knee_vel, hip_vel]
    def recv_zipped_pickle1(self,flags=0):
        """reconstruct a Python object sent with zipped_pickle"""
        zobj = self.socket1.recv(flags)
        pobj = zlib.decompress(zobj)
        return pickle.loads(pobj)


    def update_Joint_Angles(self):
        """ Read and Update IMU Joint Angles """
        msg_imu=self.recv_zipped_pickle1() #[knee_angle, hip_angle, knee_vel, hip_vel]

        self.knee_angle = msg_imu[1] #- self.knee_0_angle
        self.hip_angle = msg_imu[2] #- self.hip_0_angle
        self.knee_vel = msg_imu[3]
        self.hip_vel = msg_imu[4]

        print 'Hip Angle [deg] = ', round(self.hip_angle,2), 'Knee Angle [deg] = ', round(self.knee_angle,2)
        


    def zero_Joint_Angles(self):
    
        """ Zero Joint Angles wrt to standing straight. The joint angles are averaged for NoSamples itterations """
        NoSamples = 4 #500  #number of samples to take to zero the joint angles   
        samples=0
        hip_00_angle = 0; #Hip Angle Zero value (tare) [deg]
        knee_00_angle = 0; #Knee Angle Zero value (tare) [deg]
        print "Number of Samples = ", NoSamples
        raw_input("Press Enter to Begin Zero Joint Angles. STAND STRAIGHT")
        while samples < NoSamples:

            self.update_Joint_Angles()        

            #Add angle values
            hip_00_angle = self.hip_angle + hip_00_angle
            knee_00_angle = self.knee_angle + knee_00_angle

            samples = samples + 1

            print samples, round(self.hip_angle,2), round(self.knee_angle,2),'       ', round(hip_0_angle,2), round(knee_0_angle,2)

        # Calculate the mean zero (tare) angle value:
        hip_00_angle = hip_00_angle/NoSamples
        knee_00_angle = knee_00_angle/NoSamples

        #Store Cero Angle into shared memory variables
        self.hip_0_angle = hip_00_angle
        self.knee_0_angle = knee_00_angle

        print "Hip Zero Angle = ", self.hip_0_angle, "Knee Zero Angle = ", self.knee_0_angle,




    def Gait_Detection(self):
        """ Detect Gait Phases for instances of inflation and deflation """


####       """ GAIT DETECTION USING IMU  """      ####

        #Notes on Gait Detection Strategy:
        #   - A velocity treshold absolute value was used to define when the velocity was near cero.
        #   - Heelstrike prediction (point A) seems to be highly dependant to the velocity treshold. Specifically the negative velocity treshold (when moving in negative speed and decelerating.)
        #   - Toe-Off prediction (point D) seems to be more sensitive to the angle treshold. This because during stance phase velocity doesn't vary much, but angle does. We moved the angle treshold to before the hip is straight.

        tresh_vel = 30  #Velocity Treshold for velocity near cero, to detect heelstrike and toeoff


        """ Gait Detection: HIP: inflation/deflation = A/C """
        if self.hip_angle > 15   and  abs(self.hip_vel) <= tresh_vel:
        # if hip_angle > 15  and  knee_angle < 10:
            A_inflate_signal = 1
            C_deflate_signal = 0

            A = A_inflate_signal
            C = C_deflate_signal

            print "                     HIP-INFLATE", A_inflate_signal, C_deflate_signal
        
        #Toe Off Detection: Hip DEFLATE
        # elif hip_angle < 5  and  abs(self.hip_vel) <= tresh_vel:
        elif abs(self.hip_angle) < 5  and  abs(self.hip_vel) <= tresh_vel:
            A_inflate_signal = 0
            C_deflate_signal = 1

            A = A_inflate_signal
            C = C_deflate_signal

            print "                                         HIP-DEFLATE", A_inflate_signal, C_deflate_signal
        else:
            A_inflate_signal = 0
            C_deflate_signal = 0

            A = A_inflate_signal
            C = C_deflate_signal

            print "No Condition"

        # return A,C




        """ Gait Detection: KNEE: inflation/deflation = B/D """

        # KNEE INFLATION: Midstance detection
        # if hip_angle > 15   and  abs(self.hip_vel) <= tresh_vel:
        if self.hip_angle < 10 and self.hip_angle > 5  and  self.knee_angle < 10:
            B_inflate_signal = 1
            D_deflate_signal = 0

            B = B_inflate_signal
            D = D_deflate_signal

            print "                                                     KNEE-INFLATE", B_inflate_signal, D_deflate_signal
        
        #KNEE DEFLATE: Toe-off detection
        # elif hip_angle < 5  and  abs(self.hip_vel) <= tresh_vel:
        elif self.hip_angle < 0  and  abs(self.hip_vel) <= tresh_vel:
            B_inflate_signal = 0
            D_deflate_signal = 1

            B = B_inflate_signal
            D = D_deflate_signal

            print "                                                                         KNEE-DEFLATE", B_inflate_signal, D_deflate_signal
        else:
            B_inflate_signal = 0
            D_deflate_signal = 0

            B = B_inflate_signal
            D = D_deflate_signal

            print "No Condition"

        return A,B,C,D




    
    """ ------  Main Loop  ------ """
    def main_loop(self, Joint_0_angles, Quat1_zero, Quat2_zero):
        

        #Update Joint Angles
        self.update_Joint_Angles


        # #Gait Detect
        [A,B,C,D] = self.Gait_Detection()
        # [A,B,C,D] = [0]*4





        #Set message structure and send message:
        self.messageArray = np.array([hip_angle, knee_angle, self.hip_vel, self.knee_vel, A,C,B,D, kneeAngle_Quat2])  #hip
        self.send_zipped_socket0(self.messageArray)  #Send message      
        print self.messageArray

        print hip_angle,knee_angle





""" ----- MAIN FUNCTION ----- """                     
def main():
    try:
        controls=exosuit_control()

        # Zero (Tare) Joint Angles wrt standing straight:
        raw_input("Stand Straight Calibration. Press ENTER to Begin Zero Joint Angle Calibration")
        controls.zero_Joint_Angles()

        raw_input("Press ENTER to Begin Experiment")

        """ ------  Main Loop  ------ """
        while 1:
            

            # angle = controls.angBetweenQuat()
            # print round(angle,2)

            controls.main_loop(Joint_0_angles, Quat1_zero, Quat2_zero)




    


    except KeyboardInterrupt:
        exit()

if __name__ == '__main__':
    main()









                        
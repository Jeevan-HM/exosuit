""" 
    exosuit_controller.py       October 12, 2020   Emiliano
    This code is the controller for the exosuit.
    Joint angle data is received from a python code that published computed joint angles to socket 0.
    Last Modified: December 22, 2020    Emiliano
    
"""

#Time, Math Libraries:
from time import time,sleep
import numpy as np
from numpy import savetxt
from numpy.linalg import norm as mag

#Communication Libraries:
import zmq
import zlib
import pickle

#Pins and Sensors Libraries:
# import RPi.GPIO as GPIO  #Pin library
# import Adafruit_ADS1x15 as ADC  #Pressure Sensor library


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


        #Initialize Variables
        self.t0 = time()  #initial time
        self.First_Loop = True  #flag to determine first itteration run
        self.tA_learn = 0.0
        self.tB_learn = 0.0
        self.tC_learn = 0.0
        self.tD_learn = 0.0
        self.gait_cycle = 0 #gait cycle counter
        self.SampleCount = 0
        self.vectE = [0]*20
        self.FirstA = 0
        self.FirstB = 0
        self.FirstC = 0
        self.FirstD = 0
        self.FirstE = 0
        self.A = 0
        self.B = 0
        self.C = 0
        self.D = 0
        self.E = 0


        #Set Pi's pins:
        self.pin_hip_inf = 18 #input air hip = CH1 in Mosfet
        self.pin_hip_def = 9  #vacuum hip = CH3 in Mosfet
        self.pin_knee_inf = 23 #input air knee = CH2 in Mosfet
        self.pin_knee_def = 24  #vacuum knee = CH4 in Mosfet
        print 'Warning: need to change the pins for the knee valves'
        # GPIO.setmode(GPIO.BCM)
        # GPIO.setup(self.pin_hip_inf,GPIO.OUT)
        # GPIO.setup(self.pin_hip_def,GPIO.OUT)
        # GPIO.setup(self.pin_knee_inf,GPIO.OUT)
        # GPIO.setup(self.pin_knee_def,GPIO.OUT)


    """    Valves Operation    """
    # def inflate_hip(self):
    #     GPIO.output(self.pin_hip_inf,True)
    #     GPIO.output(self.pin_hip_def,False)

    # def deflate_hip(self):
    #     GPIO.output(self.pin_hip_inf,False)
    #     GPIO.output(self.pin_hip_def,True)
        
    # def hold_hip(self):
    #     GPIO.output(self.pin_hip_inf,False)
    #     GPIO.output(self.pin_hip_def,False)

    # def inflate_knee(self):
    #     GPIO.output(self.pin_knee_inf,True)
    #     GPIO.output(self.pin_knee_def,False)

    # def deflate_knee(self):
    #     GPIO.output(self.pin_knee_inf,False)
    #     GPIO.output(self.pin_knee_def,True)
        
    # def hold_knee(self):
    #     GPIO.output(self.pin_knee_inf,False)
    #     GPIO.output(self.pin_knee_def,False)


    #Send Data message for Data Recording
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

        self.knee_angle = msg_imu[0] #- self.knee_0_angle
        self.hip_angle = msg_imu[1] #- self.hip_0_angle
        self.knee_vel = msg_imu[2]
        self.hip_vel = msg_imu[3]
        self.thigh_speed = msg_imu[4]

        self.QuatShank = msg_imu[5:9]
        self.QuatThigh = msg_imu[9:13]
        # self.QuatTorso = msg_imu[13:17]
        self.QuatTorso = [0,0,0,0]

        # print 'Hip Angle [deg] = ', round(self.hip_angle,2), 'Knee Angle [deg] = ', round(self.knee_angle,2)
        

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

            print samples, round(self.hip_angle,2), round(self.knee_angle,2),'       ', round(hip_00_angle,2), round(knee_00_angle,2)

        # Calculate the mean zero (tare) angle value:
        hip_00_angle = hip_00_angle/NoSamples
        knee_00_angle = knee_00_angle/NoSamples

        #Store Cero Angle into shared memory variables
        self.hip_0_angle = hip_00_angle
        self.knee_0_angle = knee_00_angle

        print "Hip Zero Angle = ", self.hip_0_angle, "Knee Zero Angle = ", self.knee_0_angle



    def Gait_Detection_OLDVERSION(self):  #Old alrogithm. consider DELETE

        """ Gait Detection: inflation/deflation = A/C """

        vel0_tresh = 0.01  #Velocity Treshold for velocity near cero, to detect heelstrike and toeoff

        # Detect Maximum Knee Flexion = point E
        if (abs(self.knee_vel) <= vel0_tresh)   and   (self.hip_vel < 0):
            E = 1
        else: E = 0

        # Detect Hip Inflation = point A
        if (abs(self.knee_vel) <= vel0_tresh)   and   (self.hip_vel > 0):
            A = 1
        else: A = 0 

        # Detect Hip Deflation = point C
        if (abs(self.hip_angle) <= vel0_tresh)  and   (self.hip_vel > 0):
            C = 1
        else: C = 0

        # Detect Knee Inflation = point B
        if (abs(self.knee_vel) <= vel0_tresh)   and   (self.hip_vel > 0):
            B = 1
        else: B = 0

        # Detect Knee Deflation = point D
        if (abs(self.knee_vel) <= vel0_tresh)   and   (self.hip_angle > 0):
            D = 1
        else: D = 0


    def Gait_Detection(self):

        """ Gait Event Detection    """

                
        #Threshold for Gait Detect Events
        tresh_E = 30;
        tresh_C = 1;


        #Point E: Detect Maximum Knee Flexion (Gait Cycle Begin)
        if (abs(self.knee_vel) <= tresh_E) and (self.hip_vel < 0) and (self.knee_angle > 20):
            detect_E = 1
        else:
            detect_E = 0

        #Point A:
        if (-10 < self.hip_vel) and (self.hip_vel < 1) and (self.knee_vel < 0)  and (self.hip_angle < -10):
            detect_A = 1
        else:
            detect_A = 0

        #Point B:
        if (0 < self.knee_vel) and (self.knee_vel < 5) and (self.hip_vel > 0) and (self.hip_angle < -5):
            detect_B = 1
        else:
            detect_B = 0

        #Point C: 
        if (abs(self.hip_angle) <= tresh_C) and (self.hip_vel > 0):
            detect_C = 1
        else:
            detect_C = 0

        #Point D:
        if (-10 < self.knee_vel) and (self.knee_vel < 10) and (self.hip_angle > 2):
            detect_D = 1
        else:
            detect_D = 0



        """ Detect Only First Instance For Each Gait Cycle """
        #This sections detects only first instance and eliminates the repeated instances


        ## Variables to initialize:
        FlagFirst = 0; FlagA = 0; FlagB = 0; FlagC = 0; FlagD = 0;

        #Create Vector of E detection values to verify for repeated instances:
        self.vectE.append( detect_E ) #Add current value to last index of vectorE
        self.vectE.pop(0)  #delete first value from list

        #Detect only first E event and store into variable:
        if (sum(self.vectE) == 1) and (self.FirstE == 0):
            self.E = 1
            self.FirstE = 1
            #Reset all flags of first event (new gait cycle begins):
            self.FirstA = 0;  self.FirstB = 0;  self.FirstC = 0;   self.FirstD = 0
        elif (sum(self.vectE) == 0):
            self.FirstE = 0
        else:
            self.E = 0


        #Detect First Events only of A,B,C,D
        if (detect_A == 1) and  (self.FirstA == 0):
            self.A = 1
            self.FirstA = 1
        else:
            self.A = 0
        
        
        if (detect_B == 1)  and  (self.FirstB == 0):
            self.B = 1
            self.FirstB = 1
        else:
            self.B = 0
        

        if (detect_C == 1)  and  (self.FirstC == 0):
            self.C = 1
            self.FirstC = 1
        else:
            self.C = 0
        
        
        if (detect_D == 1)  and  (self.FirstD == 0):
            self.D = 1
            self.FirstD = 1
        else:
            self.D = 0




    def learning_algorithm(self):

        """ Itterative Learning Algorithm: Hip/Knee inflation/deflation = A/C """

        # Input Variables: knee_angle, hip_angle, knee_vel, hip_vel, 

        # if (self.First_Loop == True):
        dtA = 0.1
        dtB = 0.1
        dtC = 0.1
        dtD = 0.1


        #Gains:
        K = 1

        #Error computation
        # error = 

        #Time delay
        # dtA = dtA_last + K*errorA
        # dtB = 0.1
        # dtC = 0.1
        # dtD = 0.1


        vel0_tresh = 1.0  #Velocity Treshold for velocity near cero, to detect heelstrike and toeoff

        # Detect Maximum Knee Flexion = point E
        if (abs(self.knee_vel) <= vel0_tresh)   and   (self.hip_vel < 0):
            tE = time() - self.t0   #time for E
            self.E = 1
            self.tA_learn = tE + dtA   #time learned for A
        # else:  #Consider using this else statement to prevent E = 1 always
            # self.E = 0



        # Detect Hip Inflation = point A
        elif (abs(self.knee_vel) <= vel0_tresh)   and   (self.hip_vel > 0):
            tA = time() - self.t0   #time for A
            self.tB_learn = tA + dtB   #time learned for B
            self.tC_learn = tA + dtC   #time learned for c


        # Detect Hip Deflation = point C
        elif (abs(self.hip_angle) <= vel0_tresh)  and   (self.hip_vel > 0):
            tC = time() - self.t0   #time for C
            self.tD_learn = tC + dtD   #time learned for D

        ## Add the learning portion for pressure tuning
        ##


        #Operation of Valves:   #NEED TO ADD HOLD OPERATION WITH PRESSURE LIMIT
        t_now = time() - self.t0

        if (t_now >= self.tA_learn): #A = inflate hip
            # self.inflate_hip()
            self.A = 1
        else:
            self.A = 0

        if (t_now >= self.tB_learn): #B = inflate knee
            # self.inflate_knee()
            self.B = 1
        else:
            self.B = 0

        if (t_now >= self.tC_learn): #C = deflate hip
            # self.deflate_hip()
            self.C = 1
        else:
            self.C = 0

        if (t_now >= self.tD_learn): #D = deflate knee
            # self.deflate_knee()
            self.D = 1
        else:
            self.D = 0



        """ Gait Cycle Detection """
        #Verify if all A,B,C,D,E instances have occur, i.e. check if: (A+B+C+D+E) = 5
        if (self.A+self.B+self.C+self.D+self.E) == 5:
            self.A = 0
            self.B = 0
            self.C = 0
            self.D = 0
            self.E = 0
            self.gait_cycle = self.gait_cycle + 1







    """ ------  Main Loop  ------ """
    def main_loop(self):
        

        #Update Joint Angles
        self.update_Joint_Angles()

        #Gait Detection Algorithm:
        self.Gait_Detection()

        #Controller Learning Algorithm
        # self.learning_algorithm()


        #Set message structure and send message:
        self.messageArray = np.array([self.knee_angle, self.hip_angle, self.knee_vel, self.hip_vel, self.thigh_speed, self.A, self.B, self.C, self.D, self.E, self.QuatShank[0], self.QuatShank[1], self.QuatShank[2], self.QuatShank[3],self.QuatThigh[0], self.QuatThigh[1], self.QuatThigh[2], self.QuatThigh[3], self.QuatTorso[0], self.QuatTorso[1], self.QuatTorso[2], self.QuatTorso[3]])  #hip
        self.send_zipped_socket0(self.messageArray)  #Send message      
        # print self.messageArray

        print  round(self.knee_angle,1), round(self.hip_angle,1), round(self.knee_vel,1), round(self.hip_vel,1), self.A, self.B, self.C, self.D, self.E





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

            controls.main_loop()




    


    except KeyboardInterrupt:
        exit()

if __name__ == '__main__':
    main()



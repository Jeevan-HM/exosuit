## imu_read_data.pyj        October 1, 2020
## This code detects gait phases using 1 IMU sensor at the thigh. The timing of the gait phase detection is aimed to predict their phases for proper inflation and deflation onse of the hip exosuit.


import zmq
from time import time,sleep
import capnp
import cali_capnp
import numpy as np

import Adafruit_ADS1x15 as ADC
import RPi.GPIO as GPIO

#Inflation and Deflation functions for valve operation
def inflate():
    GPIO.output(valve1,True)
    GPIO.output(valve2,False)

def deflate():
    GPIO.output(valve1,False)
    GPIO.output(valve2,True)
    
def holding():
    GPIO.output(valve1,False)
    GPIO.output(valve2,False)


if __name__ == '__main__':

    #Initialize Communication with Edison on the IMU
    context = zmq.Context()
    socket1 = context.socket(zmq.SUB)
    socket1.setsockopt(zmq.CONFLATE,1)
    socket1.setsockopt(zmq.SUBSCRIBE,'')
    socket1.connect("tcp://192.168.42.4:1000")#Thigh

    inflate_signal = 0
    deflate_signal = 0
    inflate_count = 0
    deflate_count = 0

    Pd = 15.0 #[psi] Desired pressure
    psi = 0.0 #[psi] Pressure Reading

    #Set Valves and Pi's pins
    valve1 = 18
    valve2 = 9

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(valve1,GPIO.OUT)
    GPIO.setup(valve2,GPIO.OUT)

    adc = ADC.ADS1115() #ADC for Pressure sensor
    GAIN=1


    #Zero Joint Angles wrt to standing straight
    raw_input("Press Enter to Being Zero Joint Angles. STAND STRAIGHT")
    NoSamples = 500  #number of samples to take to zero the joint angles   
    samples=0
    pitch0_hip = 0; #Pitch Zero value (tare) [deg]
    while samples < NoSamples:
        en_msg1=socket1.recv()
        msg1=cali_capnp.Message.from_bytes(en_msg1)

        pitch_hip = msg1.pitch  #[deg]

        pitch0_hip = pitch_hip + pitch0_hip

        samples = samples + 1

        print samples, round(pitch_hip,2), round(pitch0_hip,2)

    pitch0_hip = pitch0_hip/NoSamples  #calculate mean zero pitch value

    print "Pitch Zero = ", pitch0_hip

    raw_input("BREAK POINT")

    t0=time()
    print "Ini Done"

    #Set Save Data Output File
    lines=''
    file_name='OUTPUT_DATA.txt'
    print file_name
    with open(file_name,'w+') as data_file:

        while True:
            try:
                en_msg1=socket1.recv()
                msg1=cali_capnp.Message.from_bytes(en_msg1)
                t=round((time()-t0),4)

                psi = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1  #get pressure measurement [psi]
      #       
                pitch_hip = msg1.pitch - pitch0_hip  #[deg]

                vel_hip = msg1.wz  #angular speed for pitch [deg/s]
                #Wz seems to be the angular velocity for pitch in the sagittal plane

                print round(pitch_hip,1), round(psi,2) #, inflate_signal, deflate_signal

                #Save Export Data
                #Data Structure:    [ time, pitch_hip, velocity_hip, inflate_signal, deflate_signal]
                lines=(str(round(t,4))+' '+str(round(psi,4)) +' '+str(round(pitch_hip,1))+' '+str(round(vel_hip,2))+' '+str(inflate_signal)+' '+str(deflate_signal)+'\n')
                data_file.write(lines)
                data_file.flush()     



  ####       """ GAIT DETECTION USING IMU  """      ####

                #Notes on Gait Detection Strategy:
                #   - A velocity treshold absolute value was used to define when the velocity was near cero.
                #   - Heelstrike prediction seems to be highly dependant to the velocity treshold. Specifically the negative velocity treshold (when moving in negative speed and decelerating.)
                #   - Toe-Off prediction seems to be more sensitive to the angle treshold. This becuase during stance phase velocity doesn't vary much, but angle does. We moved the angle treshold to before the hip is straight.

                tresh_vel = 30  #Velocity Treshold for velocity near cero, to detect heelstrike and toeoff

                #Heelstrike detection: INFLATE
                if pitch_hip > 15   and  abs(vel_hip) <= tresh_vel:
                    inflate_signal = 1
                    deflate_signal = 0

                    inflate_count = inflate_count + 1
                    deflate_count = 0
                    print "                     HeelStrike-INFLATE", inflate_signal, deflate_signal
                
                #Toe Off Detection: DEFLATE
                elif pitch_hip < 5  and  abs(vel_hip) <= tresh_vel:
                    inflate_signal = 0
                    deflate_signal = 1

                    inflate_count = 0
                    deflate_count = deflate_count + 1
                    print "                                         Toe Off-DEFLATE", inflate_signal, deflate_signal
                
                else:
                    inflate_signal = 0
                    deflate_signal = 0
                    print "No Condition"

                # if  and vel_hip >= 20 : #need to fix this
                    # print "                       MidStance"

                # if pitch_hip < -5.0 and abs(vel_hip) <= tresh_vel:
                    # print "                       Toe Off"



                ## Operate the valves for inflation and deflation:
                if inflate_count > 0:
                    if psi < Pd:
                        inflate()
                        print "     Inflating"
                    elif psi >= Pd:
                        holding()
                        print "holding"

                if deflate_count > 0:
                    deflate()
                    print "         Deflating"

                # sleep(0.2)

            except KeyboardInterrupt:
                GPIO.output(valve1,GPIO.LOW)
                GPIO.output(valve2,GPIO.LOW)
                print " Stopped by User"
                print "Data Saved to: ", file_name 
                exit()
                                    

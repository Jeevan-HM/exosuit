#test_valve_operation.py

#Import Libraries:
import numpy as np
from time import time,sleep
import RPi.GPIO as GPIO


#Set Pi's pins:
pin_knee_inf = 23 #input air knee = CH2 in Mosfet
pin_knee_def = 24  #vacuum knee = CH4 in Mosfet
pin_hip_inf = 18 #input air hip = CH1 in Mosfet
pin_hip_def = 9  #vacuum hip = CH3 in Mosfet
#Set Pin Mode:
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin_hip_inf,GPIO.OUT)
GPIO.setup(pin_hip_def,GPIO.OUT)
GPIO.setup(pin_knee_inf,GPIO.OUT)
GPIO.setup(pin_knee_def,GPIO.OUT)



""" Functions: Valves Operation """
def inflate_knee():
    GPIO.output(pin_knee_inf,True)
    GPIO.output(pin_knee_def,False)

def deflate_knee():
    GPIO.output(pin_knee_inf,False)
    GPIO.output(pin_knee_def,True)
    
def hold_knee():
    GPIO.output(pin_knee_inf,False)
    GPIO.output(pin_knee_def,False)



raw_input("Verify inlet pressure is LOW (<5 psi). Press Enter to Begin Valve Operation.")

while True:

    try:

        time_wait = 2 #(sec) time to wait between operations
        
        #Inflation Process:
        print("Inflating")
        inflate_knee()
        sleep(time_wait)

        #Deflation Process:
        print("Deflating")
        deflate_knee()
        sleep(time_wait)


        #Hold Process:
        print("Holding")
        hold_knee()
        sleep(time_wait)



    except KeyboardInterrupt:
        print('Test Finished.')

        print('Deflating:')
        deflate_knee()
        sleep(2)

        print("Closing Valves:")
        hold_knee()

        GPIO.cleanup() #I/O pins cleanup
        exit()

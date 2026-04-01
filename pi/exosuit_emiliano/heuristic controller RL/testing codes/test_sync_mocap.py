#Test Sync Mocap Pin
import RPi.GPIO as GPIO

from time import time,sleep

#Set Pi's pins, using "GPIO Pin#"" convention:
pin_sync_mocap = 26  #Pin to Synchronize w/ Mocap

#Set Pin Mode:
GPIO.setmode(GPIO.BCM) #set pin naming convention (GPIO pin#)
GPIO.setup(pin_sync_mocap,GPIO.IN)


while True:
	#Read Mocap Sync Pin
	sync_mocap = GPIO.input(pin_sync_mocap)

	print(sync_mocap)

	sleep(0.05)
	

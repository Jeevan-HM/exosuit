import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)
GPIO.setup(7,GPIO.OUT)
GPIO.setup(11,GPIO.OUT)
GPIO.setup(12,GPIO.OUT)
GPIO.setup(13,GPIO.OUT)

#STBY = Pin 13
#PWMA = Pin 7
#AIN2 = Pin 11
#AIN1 = Pin 12

#Rotate CW
GPIO.output(12, GPIO.HIGH)
GPIO.output(11,GPIO.LOW)

#Motor speed
GPIO.output(7, GPIO.HIGH)

#Disable STBY
GPIO.output(13, GPIO.HIGH)

#5 sec delay
time.sleep(5)

#Rotate CCW
GPIO.output(12, GPIO.LOW)
GPIO.output(11,GPIO.HIGH)

#set motor speed
GPIO.output(7, GPIO.HIGH)

#Disable STBY
GPIO.output(13, GPIO.HIGH)

#delay
time.sleep(5)

#reset all pins
GPIO.output(7, GPIO.LOW)
GPIO.output(11, GPIO.LOW)
GPIO.output(12, GPIO.LOW)
GPIO.output(13, GPIO.LOW)

GPIO.cleanup()
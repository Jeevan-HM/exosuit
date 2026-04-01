# Basic Step response code for a set source pressure
# Code will not track prssure and is only meant to open and close valves at particular times

from time import time,sleep
import RPi.GPIO as GPIO
import Adafruit_ADS1x15

adc = Adafruit_ADS1x15.ADS1115()
GAIN = 1

valve1 = 18
valve2 = 9
k = True
mode = False
limitstate = False

GPIO.setmode(GPIO.BCM)
GPIO.setup(valve1,GPIO.OUT)
GPIO.setup(valve2,GPIO.OUT)

def inflate():
    GPIO.output(valve1,True)
    GPIO.output(valve2,False)

def deflate():
    GPIO.output(valve1,False)
    GPIO.output(valve2,True)
    
def holding():
    GPIO.output(valve1,False)
    GPIO.output(valve2,False)

file_name='data_def_OUTPUT.txt'
print file_name
raw_input("Press Enter to Start")
ini=time()
lines=''
with open(file_name,'w+') as data_file:
    while True:
        try:
            pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
            print(float(round(time()-ini,6)),pressure)
            lines=(str(round(time()-ini,6))+' '+str(pressure)+' '+'\n')
            data_file.write(lines)
            data_file.flush()
            
            while round(time()-ini,6)<=10:
                deflate()
                pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
                print(float(round(time()-ini,6)),pressure)
                lines=(str(round(time()-ini,6))+' '+str(pressure)+' '+'\n')
                data_file.write(lines)
                data_file.flush()
                
            while round(time()-ini,6)>10 and round(time()-ini,6)<=15:
                inflate()
                pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
                print(float(round(time()-ini,6)),pressure)
                lines=(str(round(time()-ini,6))+' '+str(pressure)+' '+'\n')
                data_file.write(lines)
                data_file.flush()
                
            while round(time()-ini,6)>10 and round(time()-ini,6)>15:
                deflate()
                pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
                print(float(round(time()-ini,6)),pressure)
                lines=(str(round(time()-ini,6))+' '+str(pressure)+' '+'\n')
                data_file.write(lines)
                data_file.flush()


        except KeyboardInterrupt:
                GPIO.output(valve1,GPIO.LOW)
                GPIO.output(valve2,GPIO.LOW)
                print " Stopped by User"
                exit()
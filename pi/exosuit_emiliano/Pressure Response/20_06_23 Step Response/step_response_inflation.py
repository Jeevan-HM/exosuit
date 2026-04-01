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


t_d = 100 #initialize variable, time for desired pressure (Pd) reached
pressure_reached = False  #flag to indicate that desired pressure (Pd) was reached
Pd = 30 #desired pressure to reach

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

file_name='data_inf_OUTPUT.txt'
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
            
            #Begin deflated and wait for a few seconds before initiation of pressurization
            while round(time()-ini,6)<=10:
                deflate()
                pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
                print(float(round(time()-ini,6)),pressure)
                lines=(str(round(time()-ini,6))+' '+str(pressure)+' '+'\n')
                data_file.write(lines)
                data_file.flush()
            
            #inflate until desired pressure (Pd) is reached    
            while round(time()-ini,6)>10 and pressure<=Pd:
                inflate()
                pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
                print(float(round(time()-ini,6)),pressure)
                lines=(str(round(time()-ini,6))+' '+str(pressure)+' '+'\n')
                data_file.write(lines)
                data_file.flush()
             
             #get time when desired pressure (Pd) is reached   
            if pressure>Pd and round(time()-ini,6)<t_d:
                 t_d = round(time()-ini,6)
                 pressure_reached = True  #flag to indicate that desired pressure (Pd) was reached
             
             #hold for 5sec at desired pressure (Pd)   
            while round(time()-ini,6)>10 and pressure_reached and round(time()-ini,6)<(t_d+5):
                holding()
                pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
                print(float(round(time()-ini,6)),pressure)
                lines=(str(round(time()-ini,6))+' '+str(pressure)+' '+'\n')
                data_file.write(lines)
                data_file.flush()
            
            #deflate after holding 5sec at desired pressure (Pd)    
            while round(time()-ini,6)>10 and round(time()-ini,6)>(t_d+5):
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

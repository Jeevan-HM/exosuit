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


t_d = 100 #initialize variable (as non-zero), time elapsed since desired pressure (Pd) was reached [sec]
pressure_reached = False  #flag to indicate that desired pressure (Pd) was reached
Pd = 31.3 #desired pressure to reach
t_wait = 5

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

def data_update_write():
    pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1-0.27
    print round(time()-t0,2), round(pressure,2)
    lines=(str(round(time()-t0,6))+' '+str(pressure)+' '+'\n')
    data_file.write(lines)
    data_file.flush()
    return(pressure)
    

file_name='data_inf2m_5.txt'
print "Data will be saved to: ", file_name
print "DESIRED PRESSURE =", Pd
raw_input("Press Enter to Start")
t0 = time()
lines=''
with open(file_name,'w+') as data_file:
    while True:
        try:
            pressure = data_update_write()
            
            #Begin deflated and wait for a few seconds (5 or 10 sec) before initiation of pressurization
            while round(time()-t0,6)<=t_wait:
                deflate()
                pressure = data_update_write()
            
            #inflate until desired pressure (Pd) is reached and a few seconds have passed (5 or 10 sec)  
            while round(time()-t0,6)>t_wait and pressure<=Pd:
                inflate()
                pressure = data_update_write()
             
             #get time when desired pressure (Pd) is reached   
            if pressure>Pd and round(time()-t0,6)<t_d:
                t_d = round(time()-t0,6)
                pressure_reached = True  #flag to indicate that desired pressure (Pd) was reached
             
             
             #hold for 3sec at desired pressure (Pd)   
            while round(time()-t0,6)>t_wait and pressure_reached and round(time()-t0,6)<(t_d+3):
                holding()
                pressure = data_update_write()
            
            #deflate after holding 3sec at desired pressure (Pd)    
            while round(time()-t0,6)>t_wait and round(time()-t0,6)>(t_d+3):
                deflate()
                pressure = data_update_write()


        except KeyboardInterrupt:
                deflate()
                GPIO.output(valve1,GPIO.LOW)
                GPIO.output(valve2,GPIO.LOW)
                print " Stopped by User"
                print "Data saved to: ", file_name
                exit()

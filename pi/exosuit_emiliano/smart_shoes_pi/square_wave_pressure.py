# square_wave_pressure.py    Last Modified: October 22, 2020     Emiliano
# Original date created: Oct/3/2020
# Code to perform a square wave pressure input to the actuators.

from time import time,sleep
import RPi.GPIO as GPIO
import Adafruit_ADS1x15

#CHANGE
Pd = 25  #[psi] desired pressure to reach. the +1.5 is to prevent undershoot FOR HIP only

Pd = Pd + 0.5 #to maintain hold pressure
P0 = -0.0 #[psi] desired deflation pressure limit (to prevent vacuum negative pressures)


adc = Adafruit_ADS1x15.ADS1115()
GAIN = 1
t_d = 1000000 #initialize variable (as non-zero), time elapsed since desired pressure (Pd) was reached [sec]
pressure_reached = False  #flag to indicate that desired pressure (Pd) was reached
t_hold = 3  #time to wait at beginning of experiment
cycle_count = 0 
 #conter for cycles of square wave (inflation & deflation)
command_inflate = 0 #binary signal for inflation valve open
command_deflate = 0 #binary signal for deflation valve open

#Set Pi's pins:
valve1 = 18
valve2 = 9
GPIO.setmode(GPIO.BCM)
GPIO.setup(valve1,GPIO.OUT)
GPIO.setup(valve2,GPIO.OUT)

#valve1 = pin#18 = input air = channel 3 in MOSFET
#valve2 = pin #9 = out air = channel 2 in MOSFET

def inflate():
    GPIO.output(valve1,True)
    GPIO.output(valve2,False)

def deflate():
    GPIO.output(valve1,False)
    GPIO.output(valve2,True)
    
def holding():
    GPIO.output(valve1,False)
    GPIO.output(valve2,False)

def data_read_and_export():
    pressure = adc.read_adc(1, gain=GAIN)*0.0018-7.3134+0.1-0.27
    print round(time()-t0,2),'  ',round(pressure,2),'       ', command_inflate, command_deflate
    lines=(str(round(time()-t0,6))+' '+str(pressure)+' '+str(command_inflate)+' '+str(command_deflate)+'\n')
    data_file.write(lines)
    data_file.flush()
    return(pressure)
    

file_name='OUTPUT.txt'
print "Data will be saved to: ", file_name
print "DESIRED PRESSURE =", Pd
raw_input("Press Enter to Start")
t0 = time()  #get initial time of experiment
lines=''
with open(file_name,'w+') as data_file:


    #Begin deflated and wait for a few seconds (t_hold sec) before initiation of pressurization
    while round(time()-t0,6)<=t_hold:
        pressure = data_read_and_export()
        if pressure>P0:
            deflate()
            command_inflate = 0
            command_deflate = 1
        elif pressure<=P0:
            holding()
            command_inflate = 0
            command_deflate = 0

        t0_cyc = time() #get initial time of the cycle

        # while cycle_count in xrange(1,12):
        while cycle_count < 20:
            print cycle_count
            try:
                pressure = data_read_and_export()

                #Note: At this point in the script, the actuators should be deflated, and will hold in that state for t_hold seconds

                #inflate until desired pressure (Pd) is reached. But only begin inflating after a few seconds have passed (after t_hold seconds), and before the reach time has occur (time< t_d)
                while (round(time()-t0_cyc,6) > t_hold) and pressure<=Pd and round(time()-t0_cyc,6)<(t_d):
                    pressure = data_read_and_export()
                    inflate()
                    p0_reached = 0
                    command_inflate = 1
                    command_deflate = 0


                #get time when desired pressure (Pd) is reached   
                if pressure>Pd and round(time()-t0,6)<t_d:
                    t_d = round(time()-t0_cyc,6)
                    pressure_reached = True  #flag to indicate that desired pressure (Pd) was reached


                #hold for 3sec at desired pressure (Pd)   
                while round(time()-t0_cyc,6)>t_hold and pressure_reached and round(time()-t0_cyc,6)<(t_d+t_hold):
                    pressure = data_read_and_export()
                    holding()
                    command_inflate = 0
                    command_deflate = 0


                #deflate after holding t_hold seconds at desired pressure (Pd)    
                while round(time()-t0_cyc,6)>t_hold and round(time()-t0_cyc,6)>(t_d+t_hold):
                    pressure = data_read_and_export()
                    if pressure>P0:
                        deflate()
                        p0_reached = 0
                        command_inflate = 0
                        command_deflate = 1
                    elif pressure<=P0:
                        p0_reached = p0_reached + 1
                        
                        if p0_reached >=20:  #confirm a few measurements of P = 0 before moving to next cycle
                            holding()
                            command_inflate = 0
                            command_deflate = 0
                            #Reinitializ variables to begin new cycle:
                            t0_cyc = time()  #reinitialize cycle time to restart the loop
                            t_d = 100000  #reinitialize time of reach pressure, to prevent the above lines to run twice
                            pressure_reached = False
                            cycle_count = cycle_count + 1
                            print "NEW CYCLE"
                            
                            
                        


            except KeyboardInterrupt:
                print "Stopped By User"
                print "Data saved to: ", file_name
                print "Deflating Valves, Please Wait"
                #Deflate the Actuators:
                t_end = time()
                while round(time()-t_end,6)<=3.0:  #deflate for 3 sec
                    if pressure>P0:
                        deflate()
                        command_inflate = 0
                        command_deflate = 1
                    elif pressure<=P0:
                        holding()
                        command_inflate = 0
                        command_deflate = 0
                #Turn off valves (to prevent overheat):
                GPIO.output(valve1,GPIO.LOW)
                GPIO.output(valve2,GPIO.LOW)
                exit()



        #Experiment Finished:
        print "Experiment Finished!"
        print "Data saved to: ", file_name
        print "Pressure tested:", Pd, ' psi'
        print "Deflating Valves, Please Wait"
        #Deflate the Actuators:
        t_end = time()
        while round(time()-t_end,6)<=3.0:  #deflate for 3 sec
            if pressure>P0:
                deflate()
                command_inflate = 0
                command_deflate = 1
            elif pressure<=P0:
                holding()
                command_inflate = 0
                command_deflate = 0
        #Turn off valves (to prevent overheat):
        GPIO.output(valve1,GPIO.LOW)
        GPIO.output(valve2,GPIO.LOW)
        print "Experiment Finished"

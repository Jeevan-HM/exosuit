#Plots one square wave

from time import time,sleep
import RPi.GPIO as GPIO
import Adafruit_ADS1x15 #ADC
import sys
import matplotlib.pyplot as plt

Pd = 25 #[psi] desired pressure to reach. the +1.5 is to prevent undershoot FOR HIP only

Pd = Pd + 0.5 #to maintain hold pressure
P0 = -0.0 #[psi] desired deflation pressure limit (to prevent vacuum negative pressures)

total_cycles = 2 #total number of pulses you want
t_hold = 3  #time to wait at beginning of experiment
#Initialize ADC
adc = Adafruit_ADS1x15.ADS1115()
GAIN = 1
t_d = 1000000 #initialize variable (as non-zero), time elapsed since desired pressure (Pd) was reached [sec]
pressure_reached = False  #flag to indicate that desired pressure (Pd) was reached

cycle_count = 0

#These flags are to know whether the inflate and deflate valve are on or off
command_inflate = 0 #binary signal for inflation valve open
command_deflate = 0 #binary signal for deflation valve open

#Setup GPIO
input_valve = 18 #input air = channel 3 in MOSFET
output_valve = 9  #output air = channel 2 in MOSFET
GPIO.setmode(GPIO.BCM)
GPIO.setup(input_valve,GPIO.OUT)
GPIO.setup(output_valve,GPIO.OUT)

GPIO.output(input_valve, GPIO.LOW)
GPIO.output(output_valve, GPIO.LOW)

#To plot at the end
T_axis = []
P_meausred = []


def inflate():
    GPIO.output(input_valve, GPIO.HIGH)
    GPIO.output(output_valve, GPIO.LOW)

def deflate():
    GPIO.output(input_valve, GPIO.LOW)
    GPIO.output(output_valve, GPIO.HIGH)
    
def holding():
    GPIO.output(input_valve, GPIO.LOW)
    GPIO.output(output_valve, GPIO.LOW)

def data_read_and_export():
    pressure = adc.read_adc(1, gain=GAIN)*0.0018-7.3134+0.1-0.27
    print round(time()-t0,2),'  ',round(pressure,2),'       ', command_inflate, command_deflate
    lines=(str(round(time()-t0,6))+' '+str(pressure)+' '+str(command_inflate)+' '+str(command_deflate)+'\n')
    data_file.write(lines)
    data_file.flush()
    T_axis.append(round(time()-t0,6))
    P_meausred.append(pressure)
    return(pressure)


#Summary of steps:
#1. Verify P is 0 before starting
#2. Keep P at 0 for t_hold sec
#3. Inflate until Pd is reached
#4. Flag that Pd is reached
#5. Keep P at Pd fot t_hold sec
#6. Deflate
#7. After P=0 for > 20 entries, P is assumed to be 0
# Repeat cycles
#8. Shutdown (deflates for 3 sec and cleansup GPIO)
#9. Plots data

file_name='OUTPUT_' + str(sys.argv[0]) + '.txt'
print ("Data will be saved to: ", file_name)
print ("DESIRED PRESSURE = ", Pd)
raw_input("Press Enter to Start")
t0 = time()  #get initial time of experiment
lines=''
with open(file_name,'w+') as data_file:
    
#1
    #Begin deflated and wait for a few seconds (t_hold sec) before initiation of pressurization
    #Basically read pressure continuously, and IF pressure rises above 0, deflate
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

#2 
    while cycle_count < total_cycles:
        print ("Cycle: ", cycle_count)

        try:
            pressure = data_read_and_export()

            #Note: At this point in the script, the actuators should be deflated,
            #and will hold in that state for t_hold seconds

            #inflate until desired pressure (Pd) is reached.
            #But only begin inflating after a few seconds have passed
            #(after t_hold seconds), and before the reach time has occur (time< t_d)
            #In other words, after t_hold seconds, inflate until it reaches Pd
            #Every cycle also has a timeout of t_d seconds
            while (round(time()-t0_cyc,6) > t_hold) and pressure<=Pd and round(time()-t0_cyc,6)<(t_d):
#3
                pressure = data_read_and_export()
                inflate()
                p0_reached = 0
                command_inflate = 1
                command_deflate = 0
                #when pressure is reached, exit out of while loop

            #Changes t_d to at what t pressure was reached and flags that pressure was reached
            #Get time when desired pressure (Pd) is reached   
#4
            if pressure>Pd and round(time()-t0,6)<t_d:
                t_d = round(time()-t0_cyc,6)
                pressure_reached = True  #flag to indicate that desired pressure (Pd) was reached
            

            #holds Pd for t_hold sec
            #(time cycle began is less than pressure reached time plus t_hold)
#5
            while round(time()-t0_cyc,6)>t_hold and pressure_reached and round(time()-t0_cyc,6)<(t_d+t_hold):
                pressure = data_read_and_export()
                holding()
                command_inflate = 0
                command_deflate = 0


            #deflate after holding t_hold seconds at desired pressure (Pd)
            #This condition looks really wordy
#6
            while round(time()-t0_cyc,6)>t_hold and round(time()-t0_cyc,6)>(t_d+t_hold):
                pressure = data_read_and_export()
                if pressure>P0:
                    deflate()
                    p0_reached = 0
                    command_inflate = 0
                    command_deflate = 1
                #This section is used to verify P really is 0 by checking if P is several 0's in a row
                elif pressure<=P0:
                    p0_reached = p0_reached + 1
                    #confirm a few measurements of P = 0 before moving to next cycle
#7
                    if p0_reached >=20:  
                            holding()
                            command_inflate = 0
                            command_deflate = 0
                            #Reinitializ variables to begin new cycle:
                            t0_cyc = time()  #reinitialize cycle time to restart the loop
                            t_d = 100000  #reinitialize time of reach pressure, to prevent the above lines to run twice
                            pressure_reached = False
                            cycle_count = cycle_count + 1
                            print "NEW CYCLE"
#8
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
            GPIO.output(input_valve,GPIO.LOW)
            GPIO.output(output_valve,GPIO.LOW)
            GPIO.cleanup()
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
        GPIO.output(input_valve,GPIO.LOW)
        GPIO.output(output_valve,GPIO.LOW)
        GPIO.cleanup()
        print "Experiment Finished"
#9
        plt.plot(T_axis, P_meausred)
        plt.show()



        




















    
    

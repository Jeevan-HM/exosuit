"""
Test of connection with an actual autopilot (Pixhawk)
"""

from dronekit import connect, VehicleMode
import time




#Connection Port:  #-for USB use /dev/ttyACM0/  - Check ubs ports with: ls /dev/tty*
connection_string = "/dev/ttyACM0" #--for a serial port connection, use /dev/ttyAMA0. Otherwise for USB use /dev/ttyACM0/
baud_rate = 115200

#Connect to the pixhawk, through the specified port and baud rate
print(">>>> Connecting with the UAV <<<")
vehicle = connect(connection_string, baud=baud_rate, wait_ready=False)     #- wait_ready flag hold the program untill all the parameters are been read (=, not .)

try:

    while 1:


        @vehicle.on_message('ATTITUDE_QUATERNION')
        def listener(self, name, message):
            #    print 'message: %s' % message.q1
            # print message.q1
            print 'sending message'

            Q1 = message.q1
            Q2 = message.q2
            Q3 = message.q3
            Q4 = message.q4

            print Q1,Q2,Q3,Q4



except KeyboardInterrupt:
    vehicle.close()
    exit()
#--- Now we close the simulation




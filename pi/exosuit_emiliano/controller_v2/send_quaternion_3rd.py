"""
Test of connection with an actual autopilot (Pixhawk)
"""

from dronekit import connect, VehicleMode
import zmq
import zlib
import pickle
from time import time,sleep,gmtime, strftime
import numpy as np


#Function: Send message to socket for recording
def send_zipped_socket0(obj, flags=0, protocol=-1):
    """pack and compress an object with pickle and zlib."""
    pobj = pickle.dumps(obj, protocol)
    zobj = zlib.compress(pobj)
    socket0.send(zobj, flags=flags)


#Socket Connection:
#Socket0 =  Local Socket on this PC
context = zmq.Context()
socket0 = context.socket(zmq.PUB)
socket0.setsockopt(zmq.CONFLATE,1)
socket0.bind("tcp://127.0.0.1:3333")


#Pixhawk Connection:
#Connection Port:  #-for USB use /dev/ttyACM0/  - Check ubs ports with: ls /dev/tty*
connection_string = "/dev/ttyACM2" #--for a serial port connection, use /dev/ttyAMA0. Otherwise for USB use /dev/ttyACM0/
baud_rate = 115200

#Connect to the pixhawk, through the specified port and baud rate
print(">>>> Connecting with the UAV <<<")
vehicle = connect(connection_string, baud=baud_rate, wait_ready=False)     #- wait_ready flag hold the program untill all the parameters are been read (=, not .)


#Time to continously run data collection
total_time = 100 #[sec]


try:

    # while 1:


    @vehicle.on_message('ATTITUDE_QUATERNION')
    def listener(self, name, message):
        #    print 'message: %s' % message.q1
        # print message.q1
        print 'sending message'

        Qw = message.q1
        Qx = message.q2
        Qy = message.q3
        Qz = message.q4
        speed_roll = message.rollspeed
        speed_pitch = message.pitchspeed
        speed_yaw = message.yawspeed

        exportArray = np.array([Qw, Qx, Qy, Qz, speed_roll, speed_pitch, speed_yaw]) #array to export for data structure

        send_zipped_socket0(exportArray)

        print exportArray


    sleep(30000000) #use sleep to run data stream for a long time




except KeyboardInterrupt:
    vehicle.close()
    exit()
#--- Now we close the simulation




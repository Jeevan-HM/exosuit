"""
Test of connection with an actual autopilot (Pixhawk)
"""

from dronekit import connect, VehicleMode
import time

from pyquaternion import Quaternion


def euler_to_quaternion(yaw, pitch, roll):

    qx = np.sin(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) - np.cos(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)
    qy = np.cos(roll/2) * np.sin(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.cos(pitch/2) * np.sin(yaw/2)
    qz = np.cos(roll/2) * np.cos(pitch/2) * np.sin(yaw/2) - np.sin(roll/2) * np.sin(pitch/2) * np.cos(yaw/2)
    qw = np.cos(roll/2) * np.cos(pitch/2) * np.cos(yaw/2) + np.sin(roll/2) * np.sin(pitch/2) * np.sin(yaw/2)

    return [qx, qy, qz, qw]





connection_string = "/dev/ttyACM0" #--for a serial port connection, use /dev/ttyAMA0. Otherwise for USB use /dev/ttyACM0/
baud_rate = 115200

#--- Now that we have started the SITL and we have the connection string (basically the ip and udp port)...

print(">>>> Connecting with the UAV <<<")
vehicle = connect(connection_string, baud=baud_rate, wait_ready=False)     #- wait_ready flag hold the program untill all the parameters are been read (=, not .)

for i in range(0,30):

#    roll = vehicle.attitude.roll
#    pitch = vehicle.attitude.pitch
#    yaw = vehicle.attitude.yaw
    
#    roll = round( roll*180/3.14, 2)
#    pitch = round( pitch*180/3.14, 2)
#    yaw = round( yaw*180/3.14, 2)
    
#    print 'Roll = ',roll, '  Pitch =', pitch, '  Yaw = ',yaw

    print 'Value new = ', vehicle.attitude.roll
    
    time.sleep(0.1)



#--- Now we close the simulation
vehicle.close()
#sitl.stop()

print("done")



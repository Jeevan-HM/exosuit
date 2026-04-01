#### IMU Edison Code
#### This code runs on the Edison Stack
#### Sample Code Provided by George, September 8, 2020
#### Note: Sept 8: It seems that only angle data is being sent. Angular speed doesn't seem to be read/updated. Check lines 33-35 where only roll,pitch,yaw are updated.

import zmq
import time
import math
import capnp
import numpy
import cali_capnp
from upm import pyupm_bno055 as sensorObj
import pickle

if __name__ == '__main__':
    imu=sensorObj.BNO055()
    imu.setAccelerometerUnits(False) # to set the units to m/s^2
    byteData = pickle.load(open('calibRelative.dump' , 'rb'))
    imu.writeCalibrationData(byteData)
    print("IMU ready for measurements...")
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.setsockopt(zmq.CONFLATE,1)
    socket.bind("tcp://192.168.42.10:1000") #IP address of the Edison running this code.
    i=0
    ini=time.time()
    while True:
        try:
            imu.update()
            angle=imu.getEulerAngles()
            msg=cali_capnp.Message.new_message()
#            msg.roll=float(roll)
            msg.yaw=angle[0]
            msg.pitch=angle[1]
            msg.roll=angle[2]
            enc_msg=msg.to_bytes()
            socket.send(enc_msg)
            print "Timer",str(time.time()-ini),"Yaw:",round(str(angle[0]),2),"Pitch:",round(str(angle[1]),2),"Roll:",round(str(angle[2]),2)
            if i<=50:
                i+=1
            else:
                # print roll
                #print "Yaw:",str(angle[0]),"Pitch:",str(angle[1]),"Roll:",str(angle[2])
                i=0
#            sleep(0.005)
        except KeyboardInterrupt:
            print "Stop by User"
            exit()



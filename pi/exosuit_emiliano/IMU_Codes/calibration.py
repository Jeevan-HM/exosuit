#IMU Calibration Sample Code
#Provided by George, September 8, 2020
#Modified:
#Seems to be written for python3

import numpy as np
from upm import pyupm_bno055 as sensorObj
import time, sys,signal, atexit
import pickle


def main():
    sensor = sensorObj.BNO055()
    def SIGINTHandler(signum, frame):
        raise SystemExit
    def exitHandler():
        print("Exiting...")
        sys.exit(0)
    atexit.register(exitHandler)
    signal.signal(signal.SIGINT, SIGINTHandler)

    print("First we need to calibrate.  4 numbers will be output every")
    print("second for each sensor.  0 means uncalibrated, and 3 means")
    print("fully calibrated.")
    print("See the UPM documentation on this sensor for instructions on")
    print("what actions are required to calibrate.")
    print()

    while (not sensor.isFullyCalibrated()):
        intData = sensor.getCalibrationStatus()
#        print("Magnetometer:", intData[0], end=' ')   #print syntax for Raspi3: ( ,end=' ') prevents creating a new line and separates the prints with a blank space: ' '.
#        print(" Accelerometer:", intData[1], end=' ')
#        print(" Gyroscope:", intData[2], end=' ')
        print("Magnetometer:", intData[0]),   #print syntax for Raspi2:
        print(" Accelerometer:", intData[1]),
        print(" Gyroscope:", intData[2]),
        print(" System:", intData[3])
        time.sleep(1)

    print()
    print("Calibration complete.")
    print()
    
    print("Reading calibration data....")
    byteData = sensor.readCalibrationData() 
    print("Read data successfully.")
    time.sleep(1)
    
    print("Writing calibration data...")
    pickle.dump(byteData, open('calibRelative.dump', 'wb'))
    
    print("Success!")
    time.sleep(5)   
if __name__ == '__main__':
    main()
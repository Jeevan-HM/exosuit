##This code runs on the edison of the smart shoes
## Read smart shoe data and stream/send

#Import Libraries:
import numpy as np
#ZMQ Communication Libraries:
import zmq
import zlib
import pickle


#Function: Send Data message using ZMQ
def send_data_socket0(obj, flags=0, protocol=-1):
    """pack and compress an object with pickle and zlib."""
    pobj = pickle.dumps(obj, protocol)
    zobj = zlib.compress(pobj)
    socket0.send(zobj, flags=flags)


## Setup ZMQ Connection to send data to Raspberry Pi
context = zmq.Context()
#Socket0 = Destination to SEND data:
socket0 = context.socket(zmq.PUB)
socket0.setsockopt(zmq.CONFLATE,True)
socket0.connect("tcp://192.168.42.220:6000")  #chech "IP:Port" matches receiver.
#NOTE: It seems the smartshoes CANNOT send data to a remote IP:Port. Therefore, the data will be populated to a local IP:port. As such, the smartshoes will use ".bind()" to stream data into local IP, and the reciever should use ".connect()" to request data from the smartshoes which is a remote IP:port for the receiver.
#note: Use ".bind()" command to connect to a local IP:port (e.g. this PC). Use ".connect" to connect to a remote IP:port (e.g. another PC, Raspberry Pi)
print("Connected")



while True:
    try:

        #Read Sensors in Smart Shoe:
        sensor1 = 1001.01
        sensor2 = 2002.02
        sensor3 = 3003.03
        sensor4 = 4004.04

        #Set data structure  to send:
        data_array = np.array([sensor1, sensor2, sensor3, sensor4])

        #Send the data array:
        send_data_socket0(data_array)

        print(data_array)


    except KeyboardInterrupt:
        socket0.close()
        print('Connection to Socket Closed.')
        exit()


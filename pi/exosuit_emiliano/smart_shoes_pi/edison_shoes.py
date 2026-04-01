#This code runs on the edison of the smart shoes
import zmq
from time import time,sleep
#import time, signal, sys
from SF_ADC import ADS1x15
import capnp
import sendp_capnp

if __name__ == '__main__':
    i=0
    gain = 4096
    sps = 3300# 128 250 490 920 1600 2400 3300
    adc = ADS1x15()
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.setsockopt(zmq.CONFLATE,1)
    socket.bind("tcp://192.168.42.10:1000")  #This Smart Shoe IP address
    print("Connected")
    while True:
        try:
# socket.recv()
                msg = sendp_capnp.Message2.new_message()
#   msg.index = 0
                msg.sensor1 = int(adc.readADCSingleEnded(0, gain, sps))
                msg.sensor2 = int(adc.readADCSingleEnded(1, gain, sps))
                msg.sensor3 = int(adc.readADCSingleEnded(2, gain, sps))
                msg.sensor4 = int(adc.readADCSingleEnded(3, gain, sps))
                enc_msg = msg.to_bytes()
                socket.send(enc_msg)
                if i <50:
                         i+=1
                else:
                         i=0
#            print msg.index
                         print 'Right '+ str(msg.sensor1)+' '+str(msg.sensor2)+' '+str(msg.sensor3)+' '+str(msg.sensor4)+' '+' \n'
#        sleep(0.1)
        except KeyboardInterrupt:
                socket.close()
                exit()



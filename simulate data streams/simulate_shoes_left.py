import zmq
import time
import numpy as np


## Remove All Variables in Spyder Console:
from sys import exit #for debug: adds exit() function to spyder
try:
    from IPython import get_ipython
    get_ipython().magic('reset -f') #clear memory/variables
    # get_ipython().magic('clear')  #clear screen
except:
    pass


def main_function():

    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.setsockopt(zmq.CONFLATE,True)
    # socket.bind("tcp://192.168.42.3:3000")  # Replace with the appropriate address and port
    socket.bind("tcp://*:3000")  # Replace with the appropriate address and port


    while True:
        
        try: 

            grf_swing = 100 #value for swing
            grf_stance = 1000 #value for stance

            # value = np.random.rand()  # Generate a random float value
            # value = np.array([10, grf_swing, 20, 30])
            value = np.array([10, grf_stance, 20, 30])
            
            # Simulate sending the data
            # socket.send_pyobj(value.tolist(), zmq.SNDMORE)  # Send with SNDMORE flag to clear the buffer
            socket.send_pyobj(value.tolist())
            print("Sending data (Shoes Left):", value)
            
            freq = 100
            time.sleep(1 / freq)  # Sampling rate of "freq" Hz
            
        except KeyboardInterrupt:
            print('Stopping Data Stream Simulation')
            socket.close()
            exit()



if __name__ == '__main__':
       
    main_function()
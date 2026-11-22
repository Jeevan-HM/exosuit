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
    
    #Setup ZMQ Communication
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.setsockopt(zmq.CONFLATE,True)
    socket.bind("tcp://*:4444")  # Replace with the appropriate address and port
    
    #Main Loop for sending simulated data:
    while True:
        
        try: 
            # value = np.random.rand()  # Generate a random float value
            # value = np.array([10, 5, 20, 5])
            value = np.array([0.24515936, 0.5475967, 0.85723377, 0.43931271])
            # 0.24515936 0.5475967  0.85723377 0.43931271
            
            # Simulate sending the data
            socket.send_pyobj(value)
            print("Sending data (RL Timings):", value)
            
            freq = 2
            time.sleep(1 / freq)  # Sampling rate of "freq" Hz
            
        except KeyboardInterrupt:
            print('Stopping Data Stream Simulation')
            socket.close()
            exit()


if __name__ == '__main__':
       
    main_function()
    
    

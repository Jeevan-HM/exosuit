import zmq
from time import time,sleep

# Create a NumPy array
list_to_send = [1.513465, 2, 3.14, 4, 5]

# ZeroMQ socket setup
context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.setsockopt(zmq.CONFLATE,True) #keep latest sent msg only
socket.bind("tcp://*:9999")  # Set the socket address to match the one used in the Python 3 receiver script

while True:
    
    # Send NumPy array
    socket.send_pyobj( list_to_send )  # Send the LIST as a Python object
    
    print("sent data =",list_to_send)
    
    sleep(0.1)
    
    # # Wait for response (optional)
    # response = socket.recv_string()
    # print("Response from Python 3 receiver:", response)

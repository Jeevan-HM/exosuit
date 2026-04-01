import zmq
import numpy as np

# ZeroMQ context
context = zmq.Context()

# Create a socket to subscribe to the data
socket = context.socket(zmq.SUB)
# Set the subscription filter to an empty byte string to receive all messages
socket.setsockopt(zmq.SUBSCRIBE, b'')

# socket.connect("tcp://localhost:6699")
socket.connect("tcp://192.168.42.101:6699")

# socket.connect("tcp://localhost:6699")
#socket.bind("tcp://192.168.42.220:6699")



while True:
    # Wait for incoming data
    message = socket.recv()

    # Convert the received message to a NumPy array
    array = np.frombuffer(message, dtype=np.float64)

    # Reshape the array if needed
    # array = array.reshape((rows, columns))

    # Print the received array
    print("Received array:")
    print(array)

# Close the socket and context (this will never be reached in this example)
socket.close()
context.term()

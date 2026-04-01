import zmq

# Create a ZMQ context and socket
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.setsockopt_string(zmq.SUBSCRIBE, b"")
socket.setsockopt(zmq.CONFLATE,True) #read latest rcvd msg only 
socket.connet("tcp://192.168.42.101:6699")

# # Connect to the ZMQ socket on the sender's IP address and port
# # sender_ip = "192.168.42.184"  #IP edison network
# sender_ip = "10.203.53.113" #IP ASU network
# port = 7000  # Port number on the sender PC
# socket.connect(f"tcp://{sender_ip}:{port}")


while True:
    
    print('receiving data ...')
    
    
    # Receive the NumPy array
    arr = socket.recv_pyobj()

    # Print the received array
    print("Length received array:",len(arr))
    # print("Received array:", arr)
    
    print("-----------------------")
    
    
    # sleep(0.05)

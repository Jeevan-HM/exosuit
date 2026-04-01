#record_data.py    October 15, 2020
""" 
This code reads data from the local socket in this PC and exports the data into a structured txt file.
template tomado de: pc_record_0_2.py provided by George

"""

import zmq
from time import time,sleep,gmtime, strftime
import zlib
import pickle
import numpy as np


class recordFromLocalHost(object):
    """docstring for recordFromLocalHost"""
    def __init__(self):
        context = zmq.Context()
        self.socket0=context.socket(zmq.SUB) ### sub to PC socket0
        self.socket0.setsockopt(zmq.SUBSCRIBE,'')
        self.socket0.setsockopt(zmq.CONFLATE,True)
        self.socket0.connect("tcp://127.0.0.1:1111")

    #Receive Message Data    
    def recv_zipped_pickle(self,flags=0):
        """reconstruct a Python object sent with zipped_pickle"""
        zobj = self.socket0.recv(flags)
        pobj = zlib.decompress(zobj)
        return pickle.loads(pobj)


def main():
    try:
        file_name='OUTPUT_prueba.txt'
#         msg=np.array([0.]*39)
        lines=""
        print file_name
        raw_input("Press Enter to Start")
        pc_record=recordFromLocalHost()  #this is the variable to call the main object with functions
        
        # #test receive first message
        # msg=pc_record.recv_zipped_pickle()
        # print np.array2string(msg)

        with open(file_name,'w+') as data_file:
            msg=pc_record.recv_zipped_pickle()
            t0=time()
            told=t0
            while True:
                msg=pc_record.recv_zipped_pickle() #receive message

                #Set Structure
                lines=str(time()-t0)+"|"+np.array2string(msg,separator='|').replace('[','').replace(']','').replace('\n','')+"|"+"\n"
                data_file.write(lines)
                data_file.flush()
                print lines
                # sleep(0.01)
                # print time()-t0,'at',1.0/(time()-told)
                told=time()
    except KeyboardInterrupt:
        exit()


if __name__ == '__main__':
    main()



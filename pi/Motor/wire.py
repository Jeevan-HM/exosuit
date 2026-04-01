import zmq
from time import time,sleep
import capnp
import record_capnp

if __name__ == '__main__':
    lines=''
    file_name='pressure_test1.txt'
    # context = zmq.Context()
    # socket1 = context.socket(zmq.SUB)
    # socket1.setsockopt(zmq.CONFLATE,1)
    # socket1.setsockopt(zmq.SUBSCRIBE,'')
    # socket2 = context.socket(zmq.PUB)
    # socket1.connect("tcp://10.42.0.2:2000")
    # socket2.bind("tcp://10.42.0.1:1000")
    # i=0
    print file_name
    raw_input("Press Enter to Start")
    with open(file_name,'w+') as data_file:
        print "Done"
        told=-0.01
        ini=time()
        while True:
            try:
                t=time()-ini
                # print 1
                # en_msg1=socket1.recv()
                # print 2
                # msg1=record_capnp.Message.from_bytes(en_msg1)
                lines=(str(round(time()-ini,4))+'|'+str(pressure)+'|'+'\n')
                # lines=(str(round(time()-ini,4))+'|'+str(pressure)+'|'+str(m45+m12+heel+toe)+'|'+'\n')
                    # +'|'+str(msg1.pm)+'|'+str(msg1.km)+'|'+str(msg1.heel)+'|'+str(msg1.toe)+'|'+str(msg1.m12)+'|'+str(msg1.m45)+'|'+str(msg1.lheel)+'|'+str(msg1.ltoe)+'|'+str(msg1.lm12)+'|'+str(msg1.lm45)+'|'+'\n')
                data_file.write(lines)
                data_file.flush()
                # print "PD", round(msg1.pd,2),"PM:", abs(round(msg1.pm,2)),"Freq",round(1./(t-told),0),"Gait",msg1.st,"Delay",msg1.sw,'\n'
                told=t
                # socket2.send(en_msg1)
            except KeyboardInterrupt:
                exit()


#### This version calculates the parameters in raspi3 while the recording and ploting
#### is done on the laptop
import zmq
from time import time,sleep
import capnp
import cali_capnp
import numpy as np


def Rz(k,alpha):
    kx=k[0]
    ky=k[1]
    kz=k[2]
    va=1-np.cos(alpha)
    ca=np.cos(alpha)
    sa=np.sin(alpha)
    R=np.zeros((3,3))
    R[0][0]=kx*kx*va+ca
    R[0][1]=kx*ky*va-kz*sa
    R[0][2]=kx*kz*va+ky*sa

    R[1][0]=kx*ky*va+kz*sa
    R[1][1]=ky*ky*va+ca
    R[1][2]=ky*kz*va-kx*sa

    R[2][0]=kx*kz*va-ky*sa
    R[2][1]=ky*kz*va+kx*sa
    R[2][2]=kz*kz*va+ca
    return R
def rk(Rz,roll,pitch):
    r_t=np.zeros((3,1))
    rk=np.zeros((3,1))
    r_t[0]=np.sin(pitch)
    r_t[1]=-np.sin(roll)*np.cos(pitch)
    r_t[2]=np.cos(pitch)*np.cos(roll)
    rk[0]=Rz[0][0]*r_t[0]+Rz[0][1]*r_t[1]+Rz[0][2]*r_t[2]
    rk[1]=Rz[1][0]*r_t[0]+Rz[1][1]*r_t[1]+Rz[1][2]*r_t[2]
    rk[2]=Rz[2][0]*r_t[0]+Rz[2][1]*r_t[1]+Rz[2][2]*r_t[2]
    return rk
def knee(thigh_y,thigh_z,shank_y,shank_z):
    n1=[thigh_y,thigh_z]
    n2=[shank_y,shank_z]
    sig=np.sign(shank_y*thigh_z-shank_z*thigh_y)
    angle=np.arccos((thigh_y*shank_y+thigh_z*shank_z)/(np.linalg.norm(n1)*np.linalg.norm(n2)))
    kneeAngle=sig*angle
    return kneeAngle
def theta_t(w1,w2):#w1 is thigh , w2 is shank
    wx1=w1[0]
    wy1=w1[1]
    wx2=w2[0]
    wy2=w2[1]
    theta_t=np.sign(wx1*wy2-wy1*wx1)*np.arccos((wx1*wx2+wy1*wy2)/(np.linalg.norm([wx1,wy1])*np.linalg.norm([wx2,wy2])))
    num=np.linalg.norm([wx1,wy1])*theta_t
    den=np.linalg.norm([wx1,wy1])
    return num,den
def Rxy_shank(beta):
    ###### Uncomment following lines for AA motion calibratoin
    # Rxy=np.zeros((3,3))
    # Rxy[0][0]=np.cos(beta)
    # Rxy[0][1]=-np.sin(beta)

    # Rxy[1][0]=np.sin(beta)
    # Rxy[1][1]=np.cos(beta)

    # Rxy[2][2]=1
    ######## End #####
    Rxy=np.zeros((3,3))
    Rxy[0][0]=1
    Rxy[1][1]=1
    Rxy[2][2]=1
    return Rxy

if __name__ == '__main__':
    #####
    samples=1
    g1=[0.0]*3
    g2=[0.0]*3
    w1=[0.0]*3
    w2=[0.0]*3
    num=0.
    den=0.
    told=0.

    context = zmq.Context()

    socket1 = context.socket(zmq.SUB)
    socket1.setsockopt(zmq.CONFLATE,1)
    socket1.setsockopt(zmq.SUBSCRIBE,'')

    socket2 = context.socket(zmq.SUB)
    socket2.setsockopt(zmq.CONFLATE,1)
    socket2.setsockopt(zmq.SUBSCRIBE,'')

    socket1.connect("tcp://192.168.42.5:5000")#Shank
    socket2.connect("tcp://192.168.42.4:4000")#Thigh

    ini=time()
    print "Ini Done"
    while True:
        try:
            en_msg1=socket1.recv()
            en_msg2=socket2.recv()

            msg1=cali_capnp.Message.from_bytes(en_msg1)
            msg2=cali_capnp.Message.from_bytes(en_msg2)

            t=round((time()-ini),4)
            if i <=samples:
                if i==0:
                    raw_input("Press Enter to Start Stand Calibration")
                g1=np.add(g1,[msg1.gx,msg1.gy,msg1.gz])
                g2=np.add(g2,[msg2.gx,msg2.gy,msg2.gz])
                i+=1

            elif i==samples+1:
                g1=np.dot(g1,1.0/samples)
                g2=np.dot(g2,1.0/samples)

                alpha=np.arccos(g1[2]/np.linalg.norm(g1))
                k=[g1[1],-g1[0],0]
                k=k/np.linalg.norm(k)
                R=Rz(k,alpha)

                alpha2=np.arccos(g2[2]/np.linalg.norm(g2))
                k2=[g2[1],-g2[0],0]
                k2=k2/np.linalg.norm(k2)
                R2=Rz(k2,alpha2)
                i+=1
                print"Stand Calibration is Done"
                ##### Optional AA motion calibration swing leg sideway
                # raw_input("Press Enter to Start AA Calibration")
            # elif i>samples+1 and i<= samples*2+2:
            #     # w1=[msg1.wx,msg1.wy,msg1.wz]
            #     # w2=[msg2.wx,msg2.wy,msg2.wz]
            #     # num_t,den_t=theta_t(w1,w2)
            #     # num+=num_t
            #     # den+=den_t
            #     i+=1
            # elif i == samples*2+3:
            #     # beta=num/den
            #     beta=0.0
            #     Rxy=Rxy_shank(beta)
            #     print"AA Calibration is Done"
                raw_input("Press Enter to Continue")
                i+=1
            else:
                thigh=rk(R,msg1.roll,msg1.pitch)
                shank=np.matmul(Rxy,rk(R2,msg2.roll,msg2.pitch))
                phase_thigh=knee(thigh[0][0],thigh[2][0],0,1)
                phase_shank=knee(shank[0][0],shank[2][0],0,1)
                angle_rad=(phase_thigh-phase_shank)
                angle_deg=np.rad2deg(angle_rad)

        except KeyboardInterrupt:
                print " Stopped by User"
                exit()
                                

#### This version calculates the parameters in raspi3 while the recording and ploting
#### is done on the laptop
import zmq
from time import time,sleep
import capnp
# import cali_capnp
import sendp_capnp
import record_capnp
import Adafruit_ADS1x15 as ADC
import RPi.GPIO as GPIO
import numpy as np
# import keyboard
import threading

def readrightshoe(msg1,ratio):
	#### Red Shoe ####
	rm45=(msg1.sensor1/1000.-0.180)*2200.6*ratio
	rtoe=(msg1.sensor2/1000.-0.160)*2100.6*ratio
	rheel=(msg1.sensor3/1000.-0.150)*2100.6*ratio
	rm12=(msg1.sensor4/1000.-0.140)*2100.6*ratio
	##### Blue Shoe ######## male 8
	# rheel=(msg1.sensor1/1000.-0.216)*1000*ratio
	# rm45=(msg1.sensor2/1000.-0.194)*1000*ratio
	# rm12=(msg1.sensor3/1000.-0.192)*1000*ratio
	# rtoe=(msg1.sensor4/1000.-0.182)*1000*ratio
	return rm45,rtoe,rheel,rm12

def readleftshoe(msg2,ratio):
	#### Red Shoe ####
	lheel=(msg2.sensor1/1000.-0.228)*2100.6*ratio
	lm12=(msg2.sensor2/1000.-0.190)*2100.6*ratio
	lm45=(msg2.sensor3/1000.-0.212)*2200.6*ratio
	ltoe=(msg2.sensor4/1000.-0.220)*2100.6*ratio
	##### Blue Shoe ######## male 8
	# lheel=(msg2.sensor1/1000.-0.210)*1200*ratio
	# lm12=(msg2.sensor2/1000.-0.180)*1100*ratio
	# ltoe=(msg2.sensor3/1000.-0.182)*1100*ratio
	# lm45=(msg2.sensor4/1000.-0.204)*1100*ratio
	return lheel,lm12,lm45,ltoe

def send_message(socket0,pressure,psi,heel,toe,m12,m45,lheel,ltoe,lm12,lm45,swing_delay,gait):
	msg0=record_capnp.Message.new_message()
	msg0.pd=float(pressure)
	msg0.pm=psi
	#msg0.gait=gait_send
	# # msg0.valve=s1_send
	msg0.heel=heel
	msg0.toe=toe
	msg0.m12=m12
	msg0.m45=m45
	msg0.lheel=lheel
	msg0.ltoe=ltoe
	msg0.lm12=lm12
	msg0.lm45=lm45
	msg0.st=float(gait)
	msg0.sw=float(swing_delay)
	enc_msg0=msg0.to_bytes()
			# print"4"
	socket0.send(enc_msg0)
# class send_message(threading.Thread):
#     """docstring for myThread"""
#     def __init__(self):
#         threading.Thread.__init__(self)
#         self.context = zmq.Context()

#         self.socket0 = self.context.socket(zmq.PUB)
#         self.socket0.setsockopt(zmq.CONFLATE,1)
#         self.socket0.bind("tcp://10.42.0.3:3000")# rasipi local
#     def run(self):
#         print "Done"

if __name__ == '__main__':
	first_swing=0
	# thread_send= send_message()
	# thread_send.start()
	weight=9.8*70 #kg
	# weight=9.8*0.45392*141#lbs
	##########################
	maxpressure_swing=30.0
	maxpressure_stance=0.0
	error_max=np.maximum(maxpressure_stance,maxpressure_swing)
	weight_measured=0.
	weight_sum=0.
	ratio=1.0
	# pin1=19
	# pin2=26
	dr1Pin = 7
	limit1 = 11
	limit2 = 10
	valve1 = 18
	valve2 = 9
	speedPin = 12
	k = True
	mode = False
	limitstate = False
	GAIN=1

	#GPIO.cleanup()
	#print("CLEAN")
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(dr1Pin,GPIO.OUT)
	GPIO.setup(valve1,GPIO.OUT)
	GPIO.setup(valve2,GPIO.OUT)
	GPIO.setup(limit1,GPIO.IN,pull_up_down=GPIO.PUD_UP)
	GPIO.setup(limit2,GPIO.IN,pull_up_down=GPIO.PUD_UP)
	GPIO.setup(speedPin,GPIO.OUT)

	pwm = GPIO.PWM(speedPin,100000)
	pwm.start(0)
	# GPIO.setup(pin1,GPIO.OUT,initial=GPIO.LOW)  # pin1 and pin2 are the same as valve1 & valve2
	# GPIO.setup(pin2,GPIO.OUT,initial=GPIO.HIGH)
	#####
	gait=0
	swing_delay_start=0.
	maxdelay=0.3 #sec
	ini1=0.
	dt=1.0/190
	sum1=0.
	threshold_swing=weight*0.05# change by subject 100kg
	k_stance=1
	k_swing=15
	mode_hold=10/100.0*error_max ##valve thread hold   
	# ghold=0.11 ##gait thread hold
	s1=''
	i1=0
	samples=100
	pressure=0.
	state_stance=0
	state_swing=0
	state_delay=0
	pset_sw=np.linspace(0.0,1.0,num=10)*maxpressure_swing #psi
	pset_ic=np.linspace(0.0,1.0,num=10)*maxpressure_stance
	delayset=np.linspace(0.0,1.0,num=10)*maxdelay
	pressure_SW=0. ##psi
	pressure_IC=0. ## psi
	pressure_TST=0. ## psi
	swing_delay=0.
	ftheta=0.
	lines=''
	context = zmq.Context()

	socket3 = context.socket(zmq.SUB)
	socket3.setsockopt(zmq.CONFLATE,1)
	socket3.setsockopt(zmq.SUBSCRIBE, '')

	socket4 = context.socket(zmq.SUB)
	socket4.setsockopt(zmq.CONFLATE,1)
	socket4.setsockopt(zmq.SUBSCRIBE, '')

	socket0 = context.socket(zmq.PUB)
	socket0.setsockopt(zmq.CONFLATE,1)

	socket3.connect("tcp://192.168.42.8:8000")# Blue R
	# socket4.connect("tcp://192.168.42.8:8000")# Blue L

	# socket3.connect("tcp://192.168.42.1:1000")# Blue R
	# socket4.connect("tcp://192.168.42.2:2000")# Blue L

	socket0.bind("tcp://192.168.42.220:2400")
	socket0.bind("tcp://10.42.0.84:2000")# rasipi local
	adc = ADC.ADS1115()
	for i1 in range(100):
		val2= adc.read_adc(2,gain=1,data_rate=860)*4.096/(2.0**15-1)

 ###### Pressure Sensor Selection####
		# psi=val[2]*25.345-12.809 ##old 5V
		#psi=val[2]*7.911278701-18.1444525 ##3.3V
		psi=val2*14.25-7.1525 ##5v 58 psi
		sum1+=psi
	ini1=sum1/100.
	raw_input("Pressure Sensor Calibration Done, Press Enter to Start Shoe Calibration") 
	for i2 in range(1000):    
		en_msg1=socket3.recv()
		# en_msg2=socket4.recv()
		msg1=sendp_capnp.Message2.from_bytes(en_msg1)
		# msg2=sendp_capnp.Message2.from_bytes(en_msg2)
		rm45,rtoe,rheel,rm12=readrightshoe(msg1,ratio)
		# lheel,lm12,lm45,ltoe=readleftshoe(msg2,ratio)
		weight_measured=(rm45+rtoe+rheel+rm12)*2
		# weight_measured=rm45+rtoe+rheel+rm12+lheel+lm12+lm45+ltoe

		weight_sum=weight_sum+weight_measured
		print rm45,rtoe,rheel,rm12
	ratio=abs(weight/(weight_sum/1000.))
	print ratio
	# ratio=1
	raw_input("press enter to conti.")
	ini_time=time()
	told=-0.1
	i=0
	# GPIO.output(pin1,GPIO.LOW)
	# GPIO.output(pin2,GPIO.LOW)
	ini=time()
	lines=''
	file_name='act_walk_kashyap.txt'
	print file_name
	raw_input("Press Enter to Start")
	with open(file_name,'w+') as data_file:
		while True:
			try:
				en_msg1=socket3.recv()
				# en_msg2=socket4.recv()
				msg1=sendp_capnp.Message2.from_bytes(en_msg1)
				# msg2=sendp_capnp.Message2.from_bytes(en_msg2)
				m45,toe,heel,m12=readrightshoe(msg1,ratio)
				# print m45,toe,heel,m12
				# lheel,lm12,lm45,ltoe=readleftshoe(msg2,ratio)
				t=round((time()-ini_time),4)
				# print('Hello')
				# Gait mode detection
				si=val2*14.25-7.1525-ini1
				print(t, psi, (m45+m12+heel+toe))
				lines=(str(round(time()-ini,4))+'|'+str(psi)+'|'+str(m45+m12+heel+toe)+'|'+'\n')
				data_file.write(lines)
				data_file.flush()
				while ((m45+m12+heel+toe)<weight/5):
					en_msg1=socket3.recv()
					msg1=sendp_capnp.Message2.from_bytes(en_msg1)
					m45,toe,heel,m12=readrightshoe(msg1,ratio)
					t=round((time()-ini_time),4)
					psi=adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
					print(t, psi, (m45+m12+heel+toe))
					lines=(str(round(time()-ini,4))+'|'+str(psi)+'|'+str(m45+m12+heel+toe)+'|'+'\n')
					data_file.write(lines)
					data_file.flush()
					GPIO.output(valve1,False)

				while ((m45+m12+heel+toe)>weight/5):
					# print('Inflating')
					"""
					Inflation
					"""
					if (GPIO.input(limit1)==True and GPIO.input(limit2)==False)and k==True:
						mode = True
						limitstate = True
						k=False
					elif (GPIO.input(limit2)==True and GPIO.input(limit1)==False)and k==True:
						limitstate = False
						mode = False
						k=False

					while mode==True and limitstate==True and ((m45+m12+heel+toe)>weight/5):
					# while mode==True and limitstate==True:
						en_msg1=socket3.recv()
						msg1=sendp_capnp.Message2.from_bytes(en_msg1)
						m45,toe,heel,m12=readrightshoe(msg1,ratio)
						GPIO.output(valve1,limitstate)
						GPIO.output(valve2,not limitstate)
						GPIO.output(dr1Pin,limitstate)
						pwm.ChangeDutyCycle(100)
				#        time.sleep(0.5)
						if (GPIO.input(limit2)==True and GPIO.input(limit1)==False):
							mode=False
							limitstate=False
						# print("Limit state TRUE")
						psi=adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
						en_msg1=socket3.recv()
						msg1=sendp_capnp.Message2.from_bytes(en_msg1)
						# m45,toe,heel,m12=readrightshoe(msg1,ratio)
						m45,toe,heel,m12=readrightshoe(msg1,ratio)
						t=round((time()-ini_time),4)
						print(t, psi, (m45+m12+heel+toe))
						lines=(str(round(time()-ini,4))+'|'+str(psi)+'|'+str(m45+m12+heel+toe)+'|'+'\n')
						data_file.write(lines)
						data_file.flush()					# print(weight)

					while mode==False and limitstate==False and ((m45+m12+heel+toe)>weight/5):
					# while mode==False and limitstate==False:
						en_msg1=socket3.recv()
						msg1=sendp_capnp.Message2.from_bytes(en_msg1)
						m45,toe,heel,m12=readrightshoe(msg1,ratio)
						m45,toe,heel,m12=readrightshoe(msg1,ratio)
						GPIO.output(valve1,not limitstate)
						GPIO.output(valve2,not limitstate)
						GPIO.output(dr1Pin,limitstate)
						pwm.ChangeDutyCycle(100)
				#        time.sleep(0.5)
						if (GPIO.input(limit1)==True and GPIO.input(limit2)==False):
							mode=True
							limitstate=True
						# print("Limit state FALSE")
						en_msg1=socket3.recv()
						msg1=sendp_capnp.Message2.from_bytes(en_msg1)
						# m45,toe,heel,m12=readrightshoe(msg1,ratio)
						m45,toe,heel,m12=readrightshoe(msg1,ratio)
						t=round((time()-ini_time),4)
						psi=adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
						print(t, psi, (m45+m12+heel+toe))
						lines=(str(round(time()-ini,4))+'|'+str(psi)+'|'+str(m45+m12+heel+toe)+'|'+'\n')
						data_file.write(lines)
						data_file.flush()
						# print("Direction 2",weight,m45+m12+heel+toe)
						# print(weight)
								# inflate()
					# print('Inflating')
				# else
				# 	deflate()
			except KeyboardInterrupt:
					GPIO.output(valve1,GPIO.LOW)
					GPIO.output(valve2,GPIO.LOW)
					print " Stopped by User"
					exit()

import zmq
import capnp
import numpy as np
import sendp_capnp
import record_capnp
import Adafruit_ADS1x15 as ADC
import RPi.GPIO as GPIO


class motorControl(object):
	"""docstring for motorControl"""
	def __init__(self):
		self.ratio=1.0
		self.pin1=19
		self.pin2=26
		self.dr1Pin = 7
		self.limit1 = 10
		self.limit2 = 11
		self.valve1 = 8
		self.valve2 = 9
		self.speedPin = 12
		self.k = True
		self.mode = False
		self.limitstate = False
		self.ini1=0.

		GPIO.cleanup()
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(self.dr1Pin,GPIO.OUT)
		GPIO.setup(self.valve1,GPIO.OUT)
		GPIO.setup(self.valve2,GPIO.OUT)
		GPIO.setup(self.limit1,GPIO.IN,pull_up_down=GPIO.PUD_UP)
		GPIO.setup(self.limit2,GPIO.IN,pull_up_down=GPIO.PUD_UP)
		GPIO.setup(self.speedPin,GPIO.OUT)

		self.pwm = GPIO.PWM(self.speedPin,1000)
		self.pwm.start(0)
		GPIO.setup(self.pin1,GPIO.OUT,initial=GPIO.LOW)  # pin1 and pin2 are the same as valve1 & valve2
		GPIO.setup(self.pin2,GPIO.OUT,initial=GPIO.HIGH)
		print("GPIO Done")

		context = zmq.Context()

		self.socket3 = context.socket(zmq.SUB)
		self.socket3.setsockopt(zmq.CONFLATE,1)
		self.socket3.setsockopt(zmq.SUBSCRIBE, '')

		self.socket4 = context.socket(zmq.SUB)
		self.socket4.setsockopt(zmq.CONFLATE,1)
		self.socket4.setsockopt(zmq.SUBSCRIBE, '')

		self.socket0 = context.socket(zmq.PUB)
		self.socket0.setsockopt(zmq.CONFLATE,1)

		self.socket3.connect("tcp://192.168.42.6:6000")# Blue R
		# socket4.connect("tcp://192.168.42.8:8000")# Blue L

		# socket3.connect("tcp://192.168.42.1:1000")# Blue R
		# socket4.connect("tcp://192.168.42.2:2000")# Blue L

		self.socket0.bind("tcp://192.168.42.220:2400")
		self.socket0.bind("tcp://10.42.0.84:2000")# rasipi local
		self.adc = ADC.ADS1115()

		print("ZMQ AND ADC done")

	def readrightshoe(self,msg1):
		#### Red Shoe ####
		rm45=(msg1.sensor1/1000.-0.204)*2200.6*self.ratio
		rtoe=(msg1.sensor2/1000.-0.202)*2100.6*self.ratio
		rheel=(msg1.sensor3/1000.-0.210)*2100.6*self.ratio
		rm12=(msg1.sensor4/1000.-0.174)*2100.6*self.ratio
		##### Blue Shoe ######## male 8
		# rheel=(msg1.sensor1/1000.-0.216)*1000*ratio
		# rm45=(msg1.sensor2/1000.-0.194)*1000*ratio
		# rm12=(msg1.sensor3/1000.-0.192)*1000*ratio
		# rtoe=(msg1.sensor4/1000.-0.182)*1000*ratio
		return rm45,rtoe,rheel,rm12

	def pressureSensorCali(self):
		sum1=0.
		for i1 in range(100):
			val2= self.adc.read_adc(2,gain=1,data_rate=860)*4.096/(2.0**15-1)

 ###### Pressure Sensor Selection####
		# psi=val[2]*25.345-12.809 ##old 5V
		#psi=val[2]*7.911278701-18.1444525 ##3.3V
			psi=val2*14.25-7.1525 ##5v 58 psi
			sum1+=psi
		self.ini1=sum1/100.
		print("Pressrue Sensor Cali Done")
	def rightShoeCali(self):
		weight_sum=0.
		# for i2 in range(1000):
		while 1:    
			en_msg1=self.socket3.recv()
			# en_msg2=socket4.recv()
			msg1=sendp_capnp.Message2.from_bytes(en_msg1)
			# msg2=sendp_capnp.Message2.from_bytes(en_msg2)
			rm45,rtoe,rheel,rm12=self.readrightshoe(msg1)
			# lheel,lm12,lm45,ltoe=readleftshoe(msg2,ratio)
			weight_measured=(rm45+rtoe+rheel+rm12)*2
			# weight_measured=rm45+rtoe+rheel+rm12+lheel+lm12+lm45+ltoe

			# weight_sum=weight_sum+weight_measured
			print msg1.sensor1,msg1.sensor2,msg1.sensor3,msg1.sensor4



		


def main():
	m=motorControl()
	m.pressureSensorCali()
	m.rightShoeCali()


if __name__ == '__main__':
	main()

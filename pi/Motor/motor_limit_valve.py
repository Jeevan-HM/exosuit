from time import time,sleep
import RPi.GPIO as GPIO
import Adafruit_ADS1x15

adc = Adafruit_ADS1x15.ADS1115()
GAIN = 1


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

GPIO.setmode(GPIO.BCM)
GPIO.setup(dr1Pin,GPIO.OUT)
GPIO.setup(valve1,GPIO.OUT)
GPIO.setup(valve2,GPIO.OUT)
GPIO.setup(limit1,GPIO.IN,pull_up_down=GPIO.PUD_UP)
GPIO.setup(limit2,GPIO.IN,pull_up_down=GPIO.PUD_UP)
GPIO.	setup(speedPin,GPIO.OUT)
pwm = GPIO.PWM(speedPin,10)
pwm.start(0)
# GPIO.setup(pin1,GPIO.OUT,initial=GPIO.LOW)  # pin1 and pin2 are the same as valve1 & valve2
# GPIO.setup(pin2,GPIO.OUT,initial=GPIO.HIGH)
ini=time()


while True:
	try:
				t=time()-ini
				if (GPIO.input(limit1)==True and GPIO.input(limit2)==False)and k==True:
					mode = True
					limitstate = True
					k=False
				elif (GPIO.input(limit2)==True and GPIO.input(limit1)==False)and k==True:
					limitstate = False
					mode = False
					k=False

				pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
				print(float(round(time()-ini,6)),pressure)

				while mode==True and limitstate==True:
					GPIO.output(valve1,limitstate)
					GPIO.output(valve2,not limitstate)
					GPIO.output(dr1Pin,limitstate)
					pwm.ChangeDutyCycle(100)
					pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
					print(float(round(time()-ini,6)),pressure)
			#        time.sleep(0.5)
					if (GPIO.input(limit2)==True and GPIO.input(limit1)==False):
						mode=False
						limitstate=False
					# print("Limit state TRUE")
					# print(weight)

				while mode==False and limitstate==False:
					GPIO.output(valve1,not limitstate)
					GPIO.output(valve2,not limitstate)
					GPIO.output(dr1Pin,limitstate)
					pwm.ChangeDutyCycle(100)
					pressure = adc.read_adc(0, gain=GAIN)*0.0018-7.3134+0.1
					print(float(round(time()-ini,6)),pressure)
			#        time.sleep(0.5)
					if (GPIO.input(limit1)==True and GPIO.input(limit2)==False):
						mode=True
						limitstate=True
					# print("Limit state FALSE")

	except KeyboardInterrupt:
			GPIO.output(valve1,GPIO.LOW)
			GPIO.output(valve2,GPIO.LOW)
			print " Stopped by User"
			exit()
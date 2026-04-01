import time
import RPi.GPIO as GPIO

valve1 = 18
# valve2 = 9

GPIO.setmode(GPIO.BCM)
GPIO.setup(valve1,GPIO.OUT)
# GPIO.setup(valve2,GPIO.OUT)

while True:
	try:
		GPIO.output(valve1,True)
		time.sleep(5)
		GPIO.output(valve1,False)

	except KeyboardInterrupt:
		GPIO.output(valve1,False)
		print("Stopped")
		exit()
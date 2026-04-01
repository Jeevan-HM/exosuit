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
		print("ON")
		time.sleep(1)
		GPIO.output(valve1,False)
		print("OFF")
                time.sleep(1)

	except KeyboardInterrupt:
		GPIO.output(valve1,False)
		print("Stopped")
		exit()
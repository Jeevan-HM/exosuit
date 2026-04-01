import RPi.GPIO as GPIO
import time

GPIO.setwarnings(False)

dr1Pin = 7
limit1 = 10
limit2 = 11
speedPin = 12
i=0
mode=False
limitstate=False

GPIO.setmode(GPIO.BCM)
GPIO.setup(dr1Pin,GPIO.OUT)
GPIO.setup(speedPin,GPIO.OUT)
GPIO.setup(limit1,GPIO.IN,pull_up_down=GPIO.PUD_UP)
GPIO.setup(limit2,GPIO.IN,pull_up_down=GPIO.PUD_UP)

pwm = GPIO.PWM(speedPin,1000)
pwm.start(0)

try:
    while True:
        if (GPIO.input(limit1)==True and GPIO.input(limit2)==False):
            mode = True
            limitstate = True
        elif (GPIO.input(limit2)==True and GPIO.input(limit1)==False):
            limitstate = False
            mode = False
        print(mode)
#    while True:
#        for i in range(0,10):
#            GPIO.output(dr1Pin,True)
#            pwm.ChangeDutyCycle(20)
#            print("CW")
#            i=i+1
#            time.sleep(0.1)
#        
#        for i in range(11,20):
#            GPIO.output(dr1Pin,False)
#            pwm.ChangeDutyCycle(20)
#            print("CCW")
#            i=i+1
#            time.sleep(0.1)
#            
#        if i>20:
#            i=0
            
except KeyboardInterrupt:
    GPIO.cleanup()
            
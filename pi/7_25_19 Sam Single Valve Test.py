from time import sleep
import RPi.GPIO as GPIO
import Adafruit_ADS1x15 as ADC
import threading

class ValveControl():
    def __init__(self):
        self.pin1 = 19
        self.pin2 = 26
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin1,GPIO.OUT,initial = GPIO.LOW)
        GPIO.output(self.pin1,GPIO.LOW)
        GPIO.setup(self.pin2,GPIO.OUT,initial = GPIO.LOW)
        GPIO.output(self.pin2,GPIO.LOW)
        #self.th1_flag = True
        self.th2_flag = True
        self.th3_flag = True
        self.run_event = threading.Event()
        self.run_event.set()
        #self.th1 = threading.Thread(name = 'Control',target = self.PressureLoop)
        self.th2 = threading.Thread(name = 'PressureSensor',target = self.ADC_board)
        self.th3 = threading.Thread(name = 'PWM',target = self.PWM_Control)
        self.adc = ADC.ADS1115()
        self.p_desired = 2.0
        self.error_max = 0.3
        self.dt = 1.0/190
        self.mode_hold = 0.3
      
#    def PressureLoop(self):
#        try:
#            while self.run_event.is_set() and self.th1_flag:
#                sleep(1)
#                GPIO.output(self.pin1,GPIO.HIGH)
#                sleep(3)
#                GPIO.output(self.pin1,GPIO.LOW)
#                sleep(2)
#                GPIO.output(self.pin2,GPIO.HIGH)
#                sleep(3)
#                GPIO.output(self.pin2,GPIO.LOW)
#                sleep(1)
#        except:
#            self.th1_flag = False 
        
    def ADC_board(self):
        try:
            while self.run_event.is_set() and self.th2_flag:
                self.val2 = self.adc.read_adc(1,gain = 1,data_rate = 860)*4.096/(2.0**15-1)
                psi = (self.val2*25.345-12.809)-.6 ##old 5V
#                sleep(self.dt)
#                print(psi)
        except:
            self.th2_flag = False
            
    def PWM_Control(self):
        try:
            print(1)
            while self.run_event.is_set() and self.th3_flag:
                psi = (self.val2*25.345-12.809)-.6
                #pm_pwm = self.val2*14.25-7.1525 ##5v 58 psi
                e = self.p_desired-psi
                #check valve configuration
                print(e)
                if e > self.mode_hold: #inflate
                    GPIO.output(self.pin1,GPIO.HIGH)
                    GPIO.output(self.pin2,GPIO.HIGH)
                elif abs(e) <= self.mode_hold:
                    pwm = int(round((e/self.error_max),1)*10)
                    if pwm > 0 and pwm <= 10:# Inflate
                        HH = pwm
                        for i2 in range(HH): #inflate
                            GPIO.output(self.pin1,GPIO.HIGH)
                            GPIO.output(self.pin2,GPIO.HIGH)
                            sleep(self.dt)
                        for i2 in range(10-HH): #hold
                            GPIO.output(self.pin1,GPIO.LOW)
                            GPIO.output(self.pin2,GPIO.HIGH)
                            sleep(self.dt)
                elif pwm < 0 and pwm >= -10:
                    LL = 10 #pure deflation
                    for i2 in range(LL): #deflate
                        GPIO.output(self.pin1,GPIO.LOW)
                        GPIO.output(self.pin2,GPIO.LOW)
                        sleep(self.dt)
                    for i2 in range(10-LL): #hold
                        GPIO.output(self.pin1,GPIO.LOW)
                        GPIO.output(self.pin2,GPIO.HIGH)
                        sleep(self.dt)
                elif e < -self.mode_hold: #deflate
                    GPIO.output(self.pin1,GPIO.LOW)
                    GPIO.output(self.pin2,GPIO.LOW)
                    sleep(self.dt)
                else:
                    print(2)
        except:
            self.th3_flag = False
            
    def RunThread(self):
        #self.th1.start()
        self.th2.start()
#        print(1)
        self.th3.start()
        #print(1)
        try:
            while 1:
                pass
        except KeyboardInterrupt:
            self.run_event.clear()   
            print("Closed by User")
        
def main():
    v1 = ValveControl()
    v1.RunThread()

if __name__ == '__main__':
    main()
    

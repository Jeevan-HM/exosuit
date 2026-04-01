#Test Pressure Sensor

#Import ADC library:
import Adafruit_ADS1x15 as ADC


#Intialize ADC for Pressure Sensor:
adc_pressure = ADC.ADS1115()


#Function to read Pressure Sensor in actuator
def pressure_read():
    adc_channel = 1  #adc channel to read from (see ADC board)
    GAIN = 1  #setting for ADC
    adc_val =adc_pressure.read_adc(adc_channel, gain=GAIN)
    psi = adc_val*0.0018-7.3134 -0.20 #original pressure sensor equation (experiments w/ Sai)
    # psi = (adc_val*(4.096/65535.0) - 0.1*3.3)*(100)/(0.8*3.3);  #testing w/ honeywell sensor equation
    return psi



while True:

	#Measure Pressure in Actuator:
    P_meas = pressure_read()

    print(P_meas)

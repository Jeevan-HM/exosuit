# Simple demo of reading each analog input from the ADS1x15 and printing it to
# the screen.
# Author: Tony DiCola
# License: Public Domain
import time
import Adafruit_ADS1x15

# Create an ADS1115 ADC (16-bit) instance.
adc = Adafruit_ADS1x15.ADS1115()
GAIN = 1

#print('Reading ADS1x15 values, press Ctrl-C to quit...')
# Print nice channel column headers.
#print(' {0:>6} '.format(*range(4)))
#print('-' * 37)
# Main loop.
while True:
    # Read all the ADC channel values in a list.
    values = [0]*4
    for i in range(4):
        # Read the specified ADC channel using the previously set gain value.
        values[i] = adc.read_adc(i, gain=GAIN)*0.0018-7.3134+0.1
#        values[i] = adc.read_adc(i, gain=GAIN)
        print(' {0:>6}  '.format(*values))
    # Pause for half a second.
    # time.sleep(0.5)
    
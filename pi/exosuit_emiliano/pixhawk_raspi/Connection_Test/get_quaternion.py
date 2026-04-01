"""
Test of connection with an actual autopilot (Pixhawk)
"""

from dronekit import connect, VehicleMode
import time




#----- Adding a listener
#-- dronekit updates the variables as soon as it receives an update from the UAV
#-- you can define a callback function for predefined messages or define one for
#-- any mavlink message 

# def attitude_callback(self, attr_name, value):
#     print(vehicle.attitude)

# #Get and Print Data:
# print("")
# print("Adding an attitude listener")
# vehicle.add_attribute_listener('attitude', attitude_callback) #-- message type, callback function. This function prints the data
# time.sleep(0.3) #time to continously print data

# #--- Now we print the attitude from the callback for 5 seconds, then we remove the callback
# vehicle.remove_attribute_listener('attitude', attitude_callback) #(.remove)



class pixhawk_get_quaternion(object):
    """docstring for ClassName"""
    def __init__(self):

        #Connection Port:  #-for USB use /dev/ttyACM0/  - Check ubs ports with: ls /dev/tty*
        connection_string = "/dev/ttyACM0" #--for a serial port connection, use /dev/ttyAMA0. Otherwise for USB use /dev/ttyACM0/
        baud_rate = 115200

        #Connect to the pixhawk, through the specified port and baud rate
        print(">>>> Connecting with the UAV <<<")
        vehicle = connect(connection_string, baud=baud_rate, wait_ready=False)     #- wait_ready flag hold the program untill all the parameters are been read (=, not .)


        @vehicle.on_message('ATTITUDE_QUATERNION')
        def listener(self, name, message):
        #    print 'message: %s' % message.q1
            # print message.q1
            self.Q1 = message.q1
            self.Q2 = message.q2
            self.Q3 = message.q3
            self.Q4 = message.q4


    def update_values(self):

        q1 = self.Q1
        q2 = self.Q2
        q3 = self.Q3
        q4 = self.Q4

        return q1, q2, q3, q4

    #--- You can create a callback even with decorators, check the documentation out for more details

        #Create a message listener for all messages. This will continously update the values



            # return q1, q2, q3, q4    

    

            

        # time.sleep(1)



print '---- New Section Here -------'



""" ----- MAIN FUNCTION ----- """                     
def main():
    try:
        controls=pixhawk_get_quaternion()

        time.sleep(1)

        """ ------  Main Loop  ------ """
        while 1:
            print '---- New Section 2 Here -------'

            [q1,q2,q3,q4] = controls.update_values()

            print q1

            # for ii in range(0,10000):
            #     x = self.q1
            #     print 'value x = ', x


            #--- Now we close the simulation
            vehicle.close()


            print("done")



    except KeyboardInterrupt:
        exit()

if __name__ == '__main__':
    main()


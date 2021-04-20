"""
miniMSA-Version 2 | By Zachary Kennedy | Last Updated 3/8/2021

This is the python code for collecting and storing data on the miniMSA version 2. It collects data of green house gases using a Winsen ZPHS01B
sensor board. In addition to the sensor board, this code is equiped for use with a ublox-CAM-M8Q GPS to get longitude and latitiude readings.

This code collects data every 7 seconds and stores it in a file with the name and date of when the sensor began collecting data.

The text files stores each data point seperated by commas. This allows for easy data analysis using python or excel.

Data is written to the file in the following order:

Time in MST, Mission Elapsed Time, latitude, longitude, gps heading, pm1.0, pm2.5, pm10, CO2, VOC, Temp, rh, CH2O, CO, O3, NO2

"""

# Import serial and time for reading Wisen Board
import serial
import time
import datetime
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import os
import sys
stop = True
MT = 0

def run():
    global running
    
    # Import the sleep function from the time module
    GPIO.setwarnings(False) # Ignore warning for now
    GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
    GPIO.setup(16, GPIO.OUT, initial=GPIO.LOW)

    # Import spidev and Ublox library for GPS
    #import spidev
    #from ublox_gps import UbloxGps

    # Setting a port for GPS
    #port = spidev.SpiDev()
    #gps = UbloxGps(port)
    #gps_day = gps.date_time()

    # Opening serial port on RPi at a baudrate of 9600
    ser = serial.Serial("/dev/ttyS0", baudrate = 9600) # adjust to your serial port; thats just a guess

    # Create a variable for the file name that is the time at which data begins getting collected
    #file_date = "{}-{}-{} {}:{}:{}".format(gps_day.month, gps_day.day, gps_day.year, gps_day.hour-7, gps_day.min, gps_day.sec)
    #file_date = datetime.datetime.now()
    
    
    i=0
    while os.path.exists(r"DATA/file%s.txt" % i):
        i += 1
    #file_name = file_date

    # Create for the winsen data and name it according to the file_name variable
    winsen_file = open(r"DATA/file%s.txt" % i, "w")


    # Close the newly created file
    winsen_file.close()


    # Define a function that collects data from the GPS and Winsen board
    def get_data():
        global data, MT
        
        
        # Set inital mission elapsed time to 0

        
        # Set two variables to store GPS location and time
        #geo = gps.geo_coords()
        #current_time= gps.date_time()
        
        # Set GPS location specfics to variables
       # gps_longitude = geo.lon
        #gps_latitude = geo.lat
      #  gps_heading = geo.headMot
        
        # Update the current time according to the GPS
        #Real_time = "{}:{}:{}".format(current_time.hour-7, current_time.min, current_time.sec)
        
        # Reads the serial data from the Winsen board and converts it to readable values
        ser.write(b"\xff\x01\x86\x00\x00\x00\x00\x00\x79")
        s=ser.read(26)
        pm_1_0 = s[2]*256 + s[3]
        pm_2_5 = s[4]*256 + s[5]
        pm_10 = s[6]*256 + s[7]
        CO2 = s[8]*256 + s[9]
        VOC = s[10]
        temp = ((s[11]*256 + s[12])-435)*0.1
        rh = s[13]*256 + s[14]
        CH2O = (s[15]*256 + s[16])*0.001
        CO = (s[17]*256 + s[18])*0.1
        O3 = (s[19]*256 + s[20])*0.01
        NO2 = (s[21]*256 + s[22])*0.01
        
     
        # Open our preivously created file, and begin writing to it
        winsen_file = open(r"DATA/file%s.txt" % i, "a+")
        
        # Write data seperated by commas to the file
       # winsen_file.write(str(Real_time))
       # winsen_file.write(",")
        winsen_file.write(str(MT))
        winsen_file.write(",")
       # winsen_file.write(str(gps_latitude))
       # winsen_file.write(",")
        #winsen_file.write(str(gps_longitude))
       # winsen_file.write(",")
       # winsen_file.write(str(gps_heading))
       # winsen_file.write(",")
        winsen_file.write(str(pm_1_0))
        winsen_file.write(",")
        winsen_file.write(str(pm_2_5))
        winsen_file.write(",")
        winsen_file.write(str(pm_10))
        winsen_file.write(",")
        winsen_file.write(str(CO2))
        winsen_file.write(",")
        winsen_file.write(str(VOC))
        winsen_file.write(",")
        winsen_file.write(str(temp))
        winsen_file.write(",")
        winsen_file.write(str(rh))
        winsen_file.write(",")
        winsen_file.write(str(CH2O))
        winsen_file.write(",")
        winsen_file.write(str(CO))
        winsen_file.write(",")
        winsen_file.write(str(O3))
        winsen_file.write(",")
        winsen_file.write(str(NO2))
        winsen_file.write('\n')
        
        # Add 7 seconds to mission elapsed time
        MT += 7
        
        # Close the file
        winsen_file.close()
        
        # Print the winsen_data list to the console. This is only used for testing and is commneted out by default
        #print(winsen_data)
        

    # runs the get data function while the python script is running
    while True:
        if stop == False:
                print("Collecting Data...")
                

                
                GPIO.output(16, GPIO.HIGH) # Turn on
                time.sleep(1) # Sleep for 1 second

                print()
                print()
                 
                get_data()
                GPIO.output(16, GPIO.LOW) # Turn off
                time.sleep(1) # Sleep for 1 second
                
                time.sleep(5)
        else:
               break







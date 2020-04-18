import subprocess
import time, json
from datetime import datetime
#import paho.mqtt.publish as publish
import psutil
from sds011 import *
#import aqi

import adafruit_ssd1306, board, busio

# Create the I2C interface.
i2c = busio.I2C(board.SCL, board.SDA)

# 128x64 OLED Display
display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

# Clear the display.
display.fill(0)
display.show()
width = display.width
height = display.height

# JSON
JSON_FILE = '/var/www/html/aqi.json'

# TinyLora
from digitalio import DigitalInOut, Direction, Pull
from adafruit_tinylora.adafruit_tinylora import TTN, TinyLoRa

# TinyLoRa Configuration
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = DigitalInOut(board.CE1)
irq = DigitalInOut(board.D22)
rst = DigitalInOut(board.D25)

# TTN Device Address, 4 Bytes, MSB
devaddr = bytearray([0x00, 0x00, 0x00, 0x00])
# TTN Network Key, 16 Bytes, MSB
nwkey = bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
# TTN Application Key, 16 Bytess, MSB
app = bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
# Initialize ThingsNetwork configuration
ttn_config = TTN(devaddr, nwkey, app, country='EU')
lora = TinyLoRa(spi, cs, irq, rst, ttn_config)
# 2b array to store sensor data
data_pkt = bytearray(2)
# time to delay periodic packet sends (in seconds)
data_pkt_delay = 5.0

#sds011
sensor = SDS011("/dev/ttyUSB0", use_query_mode=True)
print("SDS011 sensor info:")
print(sensor)
"""
print("Device ID: ", sensor.device_id)
print("Device firmware: ", sensor.firmware)
print("Current device cycle (0 is permanent on): ", sensor.dutycycle)
print(sensor.workstate)
print(sensor.reportmode)
"""

def get_data(n=5):
        print('Measuring in 10sec')
        sensor.sleep(sleep=False)
        pmt_2_5 = 0
        pmt_10 = 0
        time.sleep(10)
        print('Measuring ' + str(n) + ' times')
        for i in range (n):
            x = sensor.query()
            pmt_2_5 = pmt_2_5 + x[0]
            pmt_10 = pmt_10 + x[1]
            print(str(i) + '. pm2.5: ' + str(pmt_2_5) + ' µg/m3  pm10:' + str(pmt_10) + ' µg/m3')
            time.sleep(2)
        pmt_2_5 = round(pmt_2_5/n, 1)
        pmt_10 = round(pmt_10/n, 1)
        sensor.sleep(sleep=True)
        time.sleep(2)
        return pmt_2_5, pmt_10

def conv_aqi(pmt_2_5, pmt_10):
    aqi_2_5 = aqi.to_iaqi(aqi.POLLUTANT_PM25, str(pmt_2_5))
    aqi_10 = aqi.to_iaqi(aqi.POLLUTANT_PM10, str(pmt_10))
    return aqi_2_5, aqi_10

"""
# NOT USED
def save_log():
    with open("/YOUR PATH/air_quality.csv", "a") as log:
        dt = datetime.now()
        log.write("{},{},{},{},{}\n".format(dt, pmt_2_5, aqi_2_5, pmt_10, aqi_10))
    log.close()
"""

def send_pi_data(data):
    # Encode float as int
    data = int(data * 100)
    # Encode payload as bytes
    data_pkt[0] = (data >> 8) & 0xff
    data_pkt[1] = data & 0xff
    # Send data packet
    lora.send_data(data_pkt, len(data_pkt), lora.frame_counter)
    lora.frame_counter += 1

    display.fill(0)
    display.text('Sent Data to TTN!',0 , 50, 1)

    print('Data sent to TTN!')
    display.show()
    time.sleep(0.5)

"""
# NOT USED
channelID = "YOUR CHANNEL ID"
apiKey = "YOUR WRITE KEY"
topic = "channels/" + channelID + "/publish/" + apiKey
mqttHost = "mqtt.thingspeak.com"

tTransport = "tcp"
tPort = 1883
tTLS = None
"""

while True:
    display.fill(0)
    display.show()
    display.text('ECO-SENSORS.CH', 0, 0, 1)
    display.text('Measuring Air Quality', 0, 10, 1)
    display.show()

    # read the raspberry pi cpu load
    cmd = "top -bn1 | grep load | awk '{printf \"%.1f\", $(NF-2)}'"
    CPU = subprocess.check_output(cmd, shell = True )
    CPU = float(CPU)
    print('CPU load %' + CPU)

    # get SDS011 measures
    pmt_2_5, pmt_10 = get_data()
    #aqi_2_5, aqi_10 = conv_aqi(pmt_2_5, pmt_10)
    print('------------------------------------')
    print('PM2.5: ' + str(pmt_2_5) + 'µg/m3')
    print('PM10: ' + str(pmt_10) + 'µg/m3')
    display.text(str(pmt_2_5) + 'µg/m3', 0, 25, 1)
    display.text(str(pmt_10) + 'µg/m3', 0, 35, 1)
    display.show()
    #print(aqi_2_5)
    #print(aqi_10))
    #tPayload = "field1=" + str(pmt_2_5)+ "&field2=" + str(aqi_2_5)+ "&field3=" + str(pmt_10)+ "&field4=" + str(aqi_10)

    # open stored data
    try:
        with open(JSON_FILE) as json_data:
            data = json.load(json_data)
    except IOError as e:
       data = []
       print('except')

    # check if length is more than 100 and delete first element
    if len(data) > 100:
        data.pop(0)

    # append new values
    jsonrow = {'pm25': pmt_2_5, 'pm10': pmt_10, 'time': time.strftime("%d.%m.%Y %H:%M:%S")}
    print(jsonrow)
    data.append(jsonrow)

    # save it
    with open(JSON_FILE, 'w') as outfile:
        json.dump(data, outfile)

    # Sent to TTN

    try:
        send_pi_data('pm25:' + str(pmt_2_5) + ',pm10:' + str(pmt_10) + ',t:' + time.strftime("%d.%m.%Y %H:%M:%S"))
    except:
        print ("[INFO] Failure in sending data to TTN")
        time.sleep(1)

    print('Sleep for 20sec')
    print(' ')
    display.text('Sleep for 60sec', 0, 60, 1)
    display.show()
    time.sleep(20)

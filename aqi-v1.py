#!/usr/bin/env python
import ttnkey
import subprocess
import time, json
from datetime import datetime
#import paho.mqtt.publish as publish
import psutil

# SDS011
from sds011 import SDS011
import aqi

# OLED LCD
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

# GPS
lat = 46.45343000
lon = 6.21918400

# JSON
JSON_FILE = '/var/www/html/aqi.json'

# MQTT
MQTT_HOST = ''
MQTT_TOPIC = '/weather/particulatematter'

# TinyLora
from digitalio import DigitalInOut, Direction, Pull
from adafruit_tinylora.adafruit_tinylora import TTN, TinyLoRa

# TinyLoRa Configuration
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = DigitalInOut(board.CE1)
irq = DigitalInOut(board.D5)
rst = DigitalInOut(board.D25)

# TTN Device Address, 4 Bytes, MSB
devaddr = bytearray(ttnkey.devaddr)
# TTN Network Key, 16 Bytes, MSB
nwkey = bytearray(ttnkey.nwkey)
# TTN Application Key, 16 Bytess, MSB
app = bytearray(ttnkey.app)

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
#print(sensor.device_id)

"""
print("Device ID: ", sensor.device_id)
print("Device firmware: ", sensor.firmware)
print("Current device cycle (0 is permanent on): ", sensor.dutycycle)
print(sensor.workstate)
print(sensor.reportmode)
"""

def get_data(n=5):
        print(' ')
        print('[INFO] Measuring in 10sec')
        print('[INFO] Waking up SDS011')
        sensor.sleep(sleep=False)
        pmt_2_5 = 0
        pmt_10 = 0
        time.sleep(10)
        print('[INFO] Measuring ' + str(n) + ' times')
        for i in range (n):
            x = sensor.query()
            pmt_2_5 = pmt_2_5 + x[0]
            pmt_10 = pmt_10 + x[1]
            print(str(i) + '. pm2.5: ' + str(pmt_2_5) + ' µg/m3  pm10:' + str(pmt_10) + ' µg/m3')
            time.sleep(2)
        pmt_2_5 = round(pmt_2_5/n, 1)
        pmt_10 = round(pmt_10/n, 1)
        print('[INFO] SDS011 go to sleep')
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
    print('data',data)
    data = int(data)
    #data.encode(ascii)
    print('data len',data)
    # Encode payload as bytes
    data_pkt[0] = (data >> 8) & 0xff
    data_pkt[1] = data & 0xff
    # Send data packet
    lora.send_data(data_pkt, len(data_pkt), lora.frame_counter)
    lora.frame_counter += 1
    display.text('Sent Data to TTN!',0 , 50, 1)
    display.show()
    time.sleep(0.5)

def send_data(data):
    print('[INFO] Sending data')
    data_pkt = bytearray(data, 'utf-8')
    lora.send_data(data_pkt, len(data_pkt),lora.frame_counter)
    lora.frame_counter += 1
    time.sleep(0.5)

def pub_mqtt(jsonrow):
    cmd = ['mosquitto_pub', '-h', MQTT_HOST, '-t', MQTT_TOPIC, '-s']
    print('Publishing using:', cmd)
    with subprocess.Popen(cmd, shell=False, bufsize=0, stdin=subprocess.PIPE).stdin as f:
        json.dump(jsonrow, f)

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
    display.text('Smart Air Quality', 0, 8, 1)
    display.show()

    """
    # read the raspberry pi cpu load
    cmd = "top -bn1 | grep load | awk '{printf \"%.1f\", $(NF-2)}'"
    CPU = subprocess.check_output(cmd, shell = True )
    CPU = float(CPU)
    print('[INFO] CPU load %' + str(CPU))
    """

    # get SDS011 measures

    # Get GPS
    #lat,lon = get_gps()
    pmt_2_5, pmt_10 = get_data()

    # aqi_2_5 = 0
    #aqi_10 = 0
    aqi_2_5, aqi_10 = conv_aqi(pmt_2_5, pmt_10)
    # bat = get_bat()
    bat = 0

    print('---------------------------------------')
    print(time.strftime("%Y-%m-%d (%H:%M:%S)"), end='')
    print(f"    PM2.5: {pmt_2_5} µg/m3    ", end='')
    print(f"PM10: {pmt_10} µg/m3")
    print(time.strftime("%Y-%m-%d (%H:%M:%S)"), end='')
    print(f"    AQI (PMT2.5): {aqi_2_5}    ", end='')
    print(f"AQI(PMT10): {aqi_10}")

    # a => pm2.5
    # b => pm10
    # c => aqi2.5
    # d => aqi10
    # e => lat
    # f => lon
    # g => time
    # h => bat

    # get date and time
    tnow = datetime.now()
    timestamp_now = datetime.timestamp(tnow)

    # Build payload
    payload = 'a' + str(int(pmt_2_5 * 100)) + 'b' + str(int(pmt_10 * 100)) + 'c' + str(int(aqi_2_5 * 100)) + 'd' + str(int(aqi_10 * 100)) + 'e' + str(int(lat * 10000)) + 'f' + str(int(lon * 10000)) + 'g' + str(timestamp_now) + 'h' + str(int(bat * 100))
    print('[DEBUG] payload:' + payload)

    display.text(str(pmt_2_5) + 'µg/m3', 0, 20, 1)
    display.text(str(pmt_10) + 'µg/m3', 0, 30, 1)
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
    jsonrow = {'pm25': pmt_2_5, 'pm10': pmt_10, 'time': timestamp_now}
    data.append(jsonrow)

    # save it
    with open(JSON_FILE, 'w') as outfile:
        json.dump(data, outfile)

    #if MQTT_HOST != '':
    #    pub_mqtt(jsonrow)

    # Sent to TTN
    try:
        send_data(payload)
        print('[INFO] Data sent to TTN')
        display.text('Data sent to TTN!',0 , 45, 1)
    except NameError:
        print ("[ERROR] Failure in sending data to TTN")
        display.text('[ERROR] Failure in sending data to TTN')
        time.sleep(1)

    print('[INFO] Sleep for 20sec')
    print(' ')
    display.text('Sleep for 20sec', 0, 55, 1)
    display.show()
    time.sleep(20)

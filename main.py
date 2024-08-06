# main.py -- put your code here!

import machine
import network
import config
import utime
import ntptime
import dht
import json
from umqtt.robust import MQTTClient
from machine import UART


_tz_sec = const(10*60 * 60)
_unix_epoch_sec = const(946684800)

def tz_shift(dt):
    return utime.localtime(
        utime.mktime(dt) + _tz_sec
    )

def unix_now_ms():
    return (utime.time_ns() + _unix_epoch_sec*10**9)//10**6

def format_datetime_string(dt_obj):
    dt_year, dt_month, dt_day, dt_hour, dt_min, dt_sec, dt_weekday, dt_yearday = (dt_obj)
    return "{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format( dt_year, dt_month, dt_day, dt_hour, dt_min, dt_sec)

def sync_time():
    try:
        print("NTP time sync")
        print("Local time before synchronization：%s" %format_datetime_string(utime.localtime()))
        #if needed, overwrite default time server
        # ntptime.host = "0.au.pool.ntp.org" 
        ntptime.settime()
        print("Local time after TZ shift：%s" %format_datetime_string(tz_shift(utime.localtime())), utime.time_ns())
    except:
        print("Error syncing time")

def connect_network(eth=False):
  
  if eth:

    print('Trying Ethernet...')
    lan = network.LAN(mdc=machine.Pin(23), mdio=machine.Pin(18), power=None,  phy_type=network.PHY_LAN8720, phy_addr=1, ref_clk_mode=False)
    lan.active(True)
    # by default (no parameters), ifconfig() will request DHCP
    #set fixed IP (address, netmask, gateway, dns)
    lan.ifconfig(('192.168.0.106', '255.255.255.0', '192.168.0.1', '1.1.1.1'))
    while not lan.isconnected():
        machine.idle()
    print('Ethernet connected! network config:', lan.ifconfig())

  else:
    print('Trying Wifi...')
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=network.WLAN.PM_NONE) # don't save power with wifi, max performance

    while True:
        try:
            wlan.connect(config.WIFI_NAME, config.WIFI_PASS)
            while not wlan.isconnected():
                machine.idle()
        except OSError as e:
            print(e)
            utime.sleep(2)
        if wlan.isconnected():
            print('Wifi connected! Network config:', wlan.ifconfig())
            print('Signal Strength:', wlan.status('rssi'))
            break
    
    return wlan




def connect_MQTT(client_name=b"esp32_client"):
    client = MQTTClient(
        client_id=client_name, 
        server=config.MQTT_SERVER_URL,
        port=config.MQTT_SERVER_PORT,
        user=config.MQTT_SERVER_USER,
        password=config.MQTT_SERVER_PASS,
        keepalive=7200,
        ssl=False,
        )
    client.connect()
    return client

def publish_MQTT(topic, value):
    print(topic)
    print(value)
    c.publish(topic, value)
    print("published")


values_dict = {}
lat = None
long = None
recording = None

wlan = connect_network(eth=False)
sync_time()


while True:

    if recording == False:
        c.disconnect()
        uart.deinit()
        wlan.active(False)
        print('Disconnected MQTT, UART and WLAN')
        utime.sleep(5)
        print('Restart Attempt')
        wlan = connect_network(eth=False)
        utime.sleep(5)
    
    c = connect_MQTT()
    
    net_led = machine.Pin(13, machine.Pin.OUT)
    uart = UART(2, tx=33, rx=32) #cts=12, rts=13)
    uart.init(38400, bits=8, parity=None, stop=1) #flow=UART.RTS | UART.CTS)

    recording = True

    while recording:

        try:
            net_led.value(0)

            if uart.any():

                net_led.value(1)

                data = uart.read()
                values = data.decode('utf-8').rstrip('\x00').split(None, 8)[1:]

                if int(values[2])%100 == 0:
                    if int(values[3]) == 1:
                        lat = float(values[4])
                    elif int(values[3]) == 2:
                        long = float(values[4])
                    # print(lat,long)

                values_dict.update({
                    'UID': int(values[0]),
                    'REGIONID': 'TAS1',
                    'LAT': lat,
                    'LONG': long,
                    'TIME': unix_now_ms(), #(int(values[3])-1)*100,
                    'FIRST_FREQ': float(values[4]),
                    'FINAL_FREQ': float(values[5]),
                    'VOLTAGE': float(values[6]),
                    'ANGLE': float(values[7])
                })

                json_values = json.dumps(values_dict)
                print(json_values)
                publish_MQTT('esp32/FDR_100MS', json_values)
            
        except Exception as e:
            print(e)
            recording = False
            



    



    # d = dht.DHT11(machine.Pin(4))
    # d.measure()
    # data['temperature'] = d.temperature()
    # data['humidity'] = d.humidity()
    # data['location'] = 'TAS'
    # data['time'] = unix_now_ms()
    # json_data = json.dumps(data)
    # publish_MQTT('esp32/dht', json_data)
    # # publish_MQTT('/esp32/tas/hum', str(d.humidity()))
    # utime.sleep_ms(100)

    


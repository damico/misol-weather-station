# !/usr/bin/env python3
#
# disp.py - read from Fine Offset RS495 weather station.
# Take RS485 via USB message from a Fine Offset WH2950 and interpret.
# See https://wordpress.com/post/doughall.me/1683
#
# Copyright (C) 2018, Doug Hall
# Licensed under MIT license, see included file LICENSE or http://opensource.org/licenses/MIT

#/weatherstation/updateweatherstation.php?ID=S20220038&PASSWORD=S20220038&tempf=90.7&humidity=57&dewptf=73.4&windchillf=90.7&winddir=88&windspeedmph=2.46&windgustmph=4.92&rainin=0.00&dailyrainin=0.00&weeklyrainin=0.00&monthlyrainin=0.15&yearlyrainin=0.15&solarradiation=7.18&UV=0&indoortempf=91.6&indoorhumidity=49&baromin=29.80&dateutc=2022-10-30%2021:48:24&softwaretype=WH2600%20V2.2.8&action=updateraw&realtime=1&rtfreq=5 HTTP/1.0" 200 341 "-" "-"


import logging
import math
import time
import datetime
import urllib.request
import urllib.parse
import sys

from serial import Serial

from wdata import RawWeatherData, wdata




logging.basicConfig(
    level=logging.DEBUG, filename='/tmp/misol.log', filemode='w',
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger(__name__)

BASE = '/devices/misol/controls'
TOPICS = ['temperature', 'humidity', 'light', 'wind_direction', 'wind_speed',
          'wind_gust', 'rain', 'uvi', 'bar', 'battery_low', 'last_update']
UVI = [432, 851, 1210, 1570, 2017, 2761, 3100, 3512, 3918, 4277, 4650, 5029,
       5230]


def main(args):
    counter = 0
    memory_rain = 0
    daily_rain = 0
    try:

        s = Serial('/dev/ttyUSB0', 9600, timeout=60)

        log.debug("Connected to serial")

        while True:
            h = datetime.datetime.now().hour
            m = datetime.datetime.now().minute
            if h == 0 and m == 0:
                daily_rain = 0

            raw = s.read(21)
            checksum = sum(i for i in raw[:16]) & 0xFF
            assert checksum == raw[16], "Wrong checksum"

            wd = wdata.from_buffer_copy(raw)
            rwd: RawWeatherData = wd.rawdata

            wind = ((wd.rawdata.WSP8 << 8) + wd.rawdata.WIND) / 8 * 1.12
            uvi = next((i for i, v in enumerate(UVI) if rwd.UVI <= v), 13)

            if memory_rain > rwd.RAIN:
                pre_rain = rwd.RAIN - memory_rain
                daily_rain = daily_rain + pre_rain

            payload = {
                'wind_direction': (wd.rawdata.DIR8 << 8) + wd.rawdata.DIR,
                'battery_low': rwd.BAT,
                'temperature': (rwd.TMP - 400) / 10.0,
                'humidity': rwd.HM,
                'wind_speed': round(wind),
                'wind_gust': round(rwd.GUST * 1.12),
                'memory_rain': memory_rain,
                'daily_rain': daily_rain,
                'uvi': uvi,
                'light': round(rwd.LIGHT / 10.0),
                'bar': round(rwd.BAR / 100.0, 2),
                'last_update': int(time.time())
            }

            memory_rain = rwd.RAIN

            send(payload, args[1])
            time.sleep(30)
            #print(payload)

    except AssertionError as e:
        log.error(e)

    except:
        log.exception("Exception")


def c_to_f(c):
    return (c * 9 / 5) + 32


def kmh_to_mph(kmh):
    return kmh * 0.621371


def pascal_to_inhg(pascal):
    return pascal / 0.029529983071445 / 1000


def get_dew_point_c(t_air_c, rel_humidity):
    A = 17.27
    B = 237.7
    alpha = ((A * t_air_c) / (B + t_air_c)) + math.log(rel_humidity/100.0)
    return c_to_f((B * alpha) / (A - alpha))


def get_wci(t, v):
    wci = 13.12 + 0.6215 * t - 11.37 * math.pow(v, 0.16) + 0.3965 * t * math.pow(v, 0.16)
    return round(c_to_f(wci))


def mm_to_in(mm):
    return mm / 25.4;


def send(payload, station_name):
    url = "http://dashboard.scicrop.com/weatherstation/updateweatherstation.php?" \
          "ID="+station_name+"" \
          "&tempf="+str(c_to_f(payload['temperature']))+"" \
          "&humidity="+str(payload['humidity'])+""  \
          "&dewptf="+str(get_dew_point_c(payload['temperature'], payload['humidity']))+""  \
          "&windchillf="+str(get_wci(payload['temperature'], payload['wind_speed']))+""  \
          "&winddir="+str(payload['wind_direction'])+""  \
          "&windspeedmph="+str(kmh_to_mph(payload['wind_speed']))+"" \
          "&windgustmph="+str(kmh_to_mph(payload['wind_gust']))+"" \
          "&rainin=0"  \
          "&dailyrainin="+str(mm_to_in(payload['daily_rain']))+""  \
          "&solarradiation="+str(payload['light'])+""  \
          "&UV="+str(payload['uvi'])+""  \
          "&indoortempf="+str(c_to_f(payload['temperature']))+""  \
          "&indoorhumidity="+str(payload['humidity'])+""  \
          "&baromin="+str(pascal_to_inhg(payload['bar']))+""  \
          "&weeklyrainin=0"  \
          "&monthlyrainin=0"  \
          "&yearlyrainin=0"  \
          "&dateutc="+urllib.parse.quote_plus(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))+""  \
          "&lowbatt="+str(payload['battery_low'])

    contents = urllib.request.urlopen(url).read()
    print(url)
    print(contents)


if __name__ == '__main__':
    main(sys.argv)


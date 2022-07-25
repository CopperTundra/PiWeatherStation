# =====================================================
#  Copyright (C) 2021 Schuwer Olivier <o.schuwer@gmail.com>
# =====================================================
#
# This file is part of PiWeatherStation.
# PiWeatherStation is free software: you can redistribute it and/or 
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3
#  of the License, or (at your option) any later version.
#
# PiWeatherStation is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the 
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with PiWeatherStation. If not, see <https://www.gnu.org/licenses/>.

# -*- coding: utf-8 -*-                 # NOQA

import sys
import os
import platform
import signal
import datetime
from threading import Event
import dateutil.parser
import tzlocal
import time
import json
import locale
import random
import math 
import paho.mqtt.client as mqtt
from metar import Metar

from PyQt5 import QtGui, QtCore, QtNetwork, QtWidgets
from PyQt5.QtGui import QPixmap, QBrush, QColor
from PyQt5.QtGui import QPainter, QImage, QFont
from PyQt5.QtCore import QEventLoop, QUrl, pyqtSignal
from PyQt5.QtCore import Qt
from PyQt5.QtNetwork import QNetworkReply
from PyQt5.QtNetwork import QNetworkRequest
from subprocess import Popen

sys.dont_write_bytecode = True
from GoogleMercatorProjection import getCorners, getPoint, getTileXY, LatLng  # NOQA
import ApiKeys                                              # NOQA


class tzutc(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(hours=0, minutes=0)


class suntimes:
    def __init__(self, lat, long):
        self.lat = lat
        self.long = long

    def sunrise(self, when=None):
        if when is None:
            when = datetime.datetime.now(tz=tzlocal.get_localzone())
        self.__preptime(when)
        self.__calc()
        return suntimes.__timefromdecimalday(self.sunrise_t)

    def sunset(self, when=None):
        if when is None:
            when = datetime.datetime.now(tz=tzlocal.get_localzone())
        self.__preptime(when)
        self.__calc()
        return suntimes.__timefromdecimalday(self.sunset_t)

    @staticmethod
    def __timefromdecimalday(day):
        hours = 24.0*day
        h = int(hours)
        minutes = (hours-h)*60
        m = int(minutes)
        seconds = (minutes-m)*60
        s = int(seconds)
        return datetime.time(hour=h, minute=m, second=s)

    def __preptime(self, when):
        # datetime days are numbered in the Gregorian calendar
        # while the calculations from NOAA are distibuted as
        # OpenOffice spreadsheets with days numbered from
        # 1/1/1900. The difference are those numbers taken for
        # 18/12/2010
        self.day = when.toordinal()-(734124-40529)
        t = when.time()
        self.time = (t.hour + t.minute/60.0 + t.second/3600.0) / 24.0

        self.timezone = 0
        offset = when.utcoffset()
        if offset is not None:
            self.timezone = offset.seconds / 3600.0 + (offset.days * 24)

    def __calc(self):
        timezone = self.timezone  # in hours, east is positive
        longitude = self.long     # in decimal degrees, east is positive
        latitude = self.lat       # in decimal degrees, north is positive

        time = self.time  # percentage past midnight, i.e. noon  is 0.5
        day = self.day     # daynumber 1=1/1/1900

        Jday = day+2415018.5 + time - timezone / 24  # Julian day
        Jcent = (Jday - 2451545) / 36525    # Julian century

        Manom = 357.52911 + Jcent * (35999.05029 - 0.0001537 * Jcent)
        Mlong = 280.46646 + Jcent * (36000.76983 + Jcent * 0.0003032) % 360
        Eccent = 0.016708634 - Jcent * (0.000042037 + 0.0001537 * Jcent)
        Mobliq = (23 + (26 + ((21.448 - Jcent * (46.815 + Jcent *
                  (0.00059 - Jcent * 0.001813)))) / 60) / 60)
        obliq = (Mobliq + 0.00256 *
                 math.cos(math.radians(125.04-1934.136 * Jcent)))
        vary = (math.tan(math.radians(obliq / 2)) *
                math.tan(math.radians(obliq / 2)))
        Seqcent = (math.sin(math.radians(Manom)) *
                   (1.914602 - Jcent*(0.004817 + 0.000014 * Jcent)) +
                   math.sin(math.radians(2 * Manom))
                   * (0.019993 - 0.000101 * Jcent) +
                   math.sin(math.radians(3 * Manom)) * 0.000289)
        Struelong = Mlong + Seqcent
        Sapplong = (Struelong - 0.00569 - 0.00478 *
                    math.sin(math.radians(125.04-1934.136*Jcent)))
        declination = (math.degrees(math.asin(math.sin(math.radians(obliq)) *
                       math.sin(math.radians(Sapplong)))))

        eqtime = (4 * math.degrees(vary * math.sin(2 * math.radians(Mlong)) -
                  2 * Eccent*math.sin(math.radians(Manom)) + 4 * Eccent *
                  vary * math.sin(math.radians(Manom)) *
                  math.cos(2 * math.radians(Mlong)) - 0.5 * vary * vary *
                  math.sin(4 * math.radians(Mlong)) - 1.25 * Eccent * Eccent *
                  math.sin(2*math.radians(Manom))))

        hourangle0 = (math.cos(math.radians(90.833)) /
                      (math.cos(math.radians(latitude)) *
                      math.cos(math.radians(declination))) -
                      math.tan(math.radians(latitude)) *
                      math.tan(math.radians(declination)))

        self.solarnoon_t = (720-4 * longitude - eqtime + timezone * 60) / 1440
        # sun never sets
        if hourangle0 > 1.0:
            self.sunrise_t = 0.0
            self.sunset_t = 1.0 - 1.0/86400.0
            return
        if hourangle0 < -1.0:
            self.sunrise_t = 0.0
            self.sunset_t = 0.0
            return

        hourangle = math.degrees(math.acos(hourangle0))

        self.sunrise_t = self.solarnoon_t - hourangle * 4 / 1440
        self.sunset_t = self.solarnoon_t + hourangle * 4 / 1440



# https://gist.github.com/miklb/ed145757971096565723
def moon_phase(dt=None):
    if dt is None:
        dt = datetime.datetime.now()
    diff = dt - datetime.datetime(2001, 1, 1)
    days = float(diff.days) + (float(diff.seconds) / 86400.0)
    lunations = 0.20439731 + float(days) * 0.03386319269
    return lunations % 1.0

#TODO: fix bug crash with clock ticking 
def tick():
    global hourpixmap, minpixmap, secpixmap
    global hourpixmap2, minpixmap2, secpixmap2
    global lastmin, lastday, lasttimestr
    global clockrect
    global datex, datex2, datey2, pdy
    global sun, daytime, sunrise, sunset
    global bottom

    if Config.DateLocale != "":
        try:
            locale.setlocale(locale.LC_TIME, Config.DateLocale)
        except:
            pass

    now = datetime.datetime.now()
    if Config.digital:
        timestr = Config.digitalformat.format(now)
        if Config.digitalformat.find("%I") > -1:
            if timestr[0] == '0':
                timestr = timestr[1:99]
        if lasttimestr != timestr:
            clockface.setText(timestr.lower())
        lasttimestr = timestr
    else:
        angle = now.second * 6
        ts = secpixmap.size()
        secpixmap2 = secpixmap.transformed(
            QtGui.QTransform().scale(
                float(clockrect.width()) / ts.height(),
                float(clockrect.height()) / ts.height()
            ).rotate(angle),
            Qt.SmoothTransformation
        )
        sechand.setPixmap(secpixmap2)
        ts = secpixmap2.size()
        sechand.setGeometry(
            clockrect.center().x() - ts.width() / 2,
            clockrect.center().y() - ts.height() / 2,
            ts.width(),
            ts.height()
        )
        if now.minute != lastmin:
            angle = now.minute * 6
            ts = minpixmap.size()
            minpixmap2 = minpixmap.transformed(
                QtGui.QTransform().scale(
                    float(clockrect.width()) / ts.height(),
                    float(clockrect.height()) / ts.height()
                ).rotate(angle),
                Qt.SmoothTransformation
            )
            minhand.setPixmap(minpixmap2)
            ts = minpixmap2.size()
            minhand.setGeometry(
                clockrect.center().x() - ts.width() / 2,
                clockrect.center().y() - ts.height() / 2,
                ts.width(),
                ts.height()
            )

            angle = ((now.hour % 12) + now.minute / 60.0) * 30.0
            ts = hourpixmap.size()
            hourpixmap2 = hourpixmap.transformed(
                QtGui.QTransform().scale(
                    float(clockrect.width()) / ts.height(),
                    float(clockrect.height()) / ts.height()
                ).rotate(angle),
                Qt.SmoothTransformation
            )
            hourhand.setPixmap(hourpixmap2)
            ts = hourpixmap2.size()
            hourhand.setGeometry(
                clockrect.center().x() - ts.width() / 2,
                clockrect.center().y() - ts.height() / 2,
                ts.width(),
                ts.height()
            )

    dy = Config.digitalformat2.format(now)
    if Config.digitalformat2.find("%I") > -1:
        if dy[0] == '0':
            dy = dy[1:99]
    if dy != pdy:
        pdy = dy
        datey2.setText(dy)

    if now.minute != lastmin:
        lastmin = now.minute
        if now.time() >= sunrise and now.time() <= sunset:
            daytime = True
        else:
            daytime = False

    if now.day != lastday:
        lastday = now.day
        # date
        sup = 'th'
        if (now.day == 1 or now.day == 21 or now.day == 31):
            sup = 'st'
        if (now.day == 2 or now.day == 22):
            sup = 'nd'
        if (now.day == 3 or now.day == 23):
            sup = 'rd'
        if Config.DateLocale != "":
            sup = ""
        ds = now.strftime("%A %d %B %Y").capitalize()
        ds2 = now.strftime("%a %d %b %Y").capitalize()
        # ds = "{0:%A %B} {0.day}<sup>{1}</sup> {0.year}".format(now, sup)
        # ds2 = "{0:%a %b} {0.day}<sup>{1}</sup> {0.year}".format(now, sup)
        print(ds)
        datex.setText(ds)
        datex2.setText(ds2)
        dt = tzlocal.get_localzone().localize(now)
        sunrise = sun.sunrise(dt)
        sunset = sun.sunset(dt)
        bottomText = ""
        bottomText += (Config.LSunRise +
                       "{0:%H:%M}".format(sunrise) +
                       Config.LSet +
                       "{0:%H:%M}".format(sunset))
        bottomText += (Config.LMoonPhase + phase(moon_phase()))
        bottom.setText(bottomText)


def tempfinished(msg):
    tempdata = json.loads(msg)
    if tempdata['temperature'] == '':
        return
    sensorStruct = {}
    sensorStruct["sensor"] = tempdata['topic']
    sensorStruct["temperature"] = round(tempdata['temperature'],1)
    sensorStruct["pressure"] = round(tempdata['pressure'])
    sensorStruct["humidity"] = round(tempdata['humidity'])
    try:
        sensorStruct["quality"] = tempdata['linkquality']
    except:
        print("Info : no quality information available in the MQTT message")
        pass
    try:
        sensorStruct["voltage"] = tempdata['voltage']
    except:
        print("Info : no voltage information available in the MQTT message")
        pass    
    try:
        sensorStruct["battery"] = tempdata['battery']
        sensorStruct["iconbat"] = getBatteryIcon(float(tempdata['battery']))
    except:
        print("Info : no battery information available in the MQTT message")
        pass

    if sensorStruct["sensor"] == "zigbee/Sensor1" :
        sensor1.setText(f'Salon :\n{sensorStruct["temperature"]:.1f}°C \nHumidité : {sensorStruct["humidity"]:.0f}% \nPression : {sensorStruct["pressure"]:.0f}hPa \n')
        sensor1Date.setText("{0:%H:%M}".format(datetime.datetime.now()))
        if sensorStruct["iconbat"] != '':
            resIcon = QPixmap('icons/' + sensorStruct["iconbat"] + '.png')
            sensor1Battery.setPixmap(resIcon.scaled(
                sensor1Battery.width(),sensor1Battery.height(), Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
    elif sensorStruct["sensor"] == "zigbee/Sensor2" :
        sensor2.setText(f'Chambre :\n{sensorStruct["temperature"]:.1f}°C \nHumidité : {sensorStruct["humidity"]:.0f}% \nPression : {sensorStruct["pressure"]:.0f}hPa \n')
        sensor2Date.setText("{0:%H:%M}".format(datetime.datetime.now()))
        if sensorStruct["iconbat"] != '':
            resIcon = QPixmap('icons/' + sensorStruct["iconbat"] + '.png')
            sensor2Battery.setPixmap(resIcon.scaled(
                sensor1Battery.width(),sensor1Battery.height(), Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
    else :
        print("tempfinished() error : Could not find the corresponding MQTT topic " + sensorStruct["sensor"] + " in the configuration !")
        return

def getBatteryIcon(f):
    if f > 80:
        return 'fullbattery'
    elif f > 30:
        return 'halfbattery'
    else:
        return 'lowbattery'


def tempToImp(f):
    return f * 1.8 - 32


def speedMph(f):
    return f / 0.621371192


def pressi(f):
    return f * 0.029530


def heightImp(f):
    return f / 25.4


def barom(f):
    return f * 25.4


def phase(f):
    pp = Config.Lmoon1          # 'New Moon'
    if (f > 0.9375):
            pp = Config.Lmoon1  # 'New Moon'
    elif (f > 0.8125):
            pp = Config.Lmoon8  # 'Waning Crecent'
    elif (f > 0.6875):
            pp = Config.Lmoon7  # 'Third Quarter'
    elif (f > 0.5625):
            pp = Config.Lmoon6  # 'Waning Gibbous'
    elif (f > 0.4375):
            pp = Config.Lmoon5  # 'Full Moon'
    elif (f > 0.3125):
            pp = Config.Lmoon4  # 'Waxing Gibbous'
    elif (f > 0.1875):
            pp = Config.Lmoon3  # 'First Quarter'
    elif (f > 0.0625):
            pp = Config.Lmoon2  # 'Waxing Crescent'
    return pp


def bearing(f):
    wd = 'N'
    if (f > 22.5):
        wd = 'NE'
    if (f > 67.5):
        wd = 'E'
    if (f > 112.5):
        wd = 'SE'
    if (f > 157.5):
        wd = 'S'
    if (f > 202.5):
        wd = 'SO'
    if (f > 247.5):
        wd = 'O'
    if (f > 292.5):
        wd = 'NO'
    if (f > 337.5):
        wd = 'N'
    return wd

def wxfinished_owm():
    global wxreply, wxdata, supress_current
    global wxicon, temper, wxdesc, press, humidity
    global wind, wind2, wdate, bottom, forecast
    global wxicon2, temper2, wxdesc2, attribution
    global daytime
    owmicons = {
        '01d': 'clear-day',
        '02d': 'partly-cloudy-day',
        '03d': 'partly-cloudy-day',
        '04d': 'partly-cloudy-day',
        '09d': 'rain',
        '10d': 'rain',
        '11d': 'thunderstorm',
        '13d': 'snow',
        '50d': 'fog',
        '01n': 'clear-night',
        '02n': 'partly-cloudy-night',
        '03n': 'partly-cloudy-night',
        '04n': 'partly-cloudy-night',
        '09n': 'rain',
        '10n': 'rain',
        '11n': 'thunderstorm',
        '13n': 'snow',
        '50n': 'fog'
    }

    wxstr = str(wxreply.readAll(),'utf-8')
    wxdata = json.loads(wxstr)
    f = wxdata['current']
    icon = f['weather'][0]['icon']
    icon = owmicons[icon]
    if not Config.use_metar:
        attribution.setText("openweathermap")
        attribution2.setText("openweathermap")
        wxiconpixmap = QtGui.QPixmap(Config.icons + "/" + icon + ".png")
        wxicon.setPixmap(wxiconpixmap.scaled(
            wxicon.width(), wxicon.height(), Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wxicon2.setPixmap(wxiconpixmap.scaled(
            wxicon.width(),
            wxicon.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wxdesc.setText(f['weather'][0]['description'])
        wxdesc2.setText(f['weather'][0]['description'])

        if Config.metric:
            temper.setText(f'{round(f["temp"]*2/2):.1f}°C')
            temper2.setText(f'{round(f["temp"]*2/2):.1f}°C')
            press.setText(Config.LPressure + f'{round(f["pressure"]):.0f}mb')
            humidity.setText(Config.LHumidity + f'{round(f["humidity"]):.0f}%')
            wd = bearing(f['wind_deg'])
            if Config.wind_degrees:
                wd = str(f['wind_deg']) + u'°'
            w = (Config.LWind +
                 wd + ' ' +
                 '%.1f' % (speedMph(f['wind_speed'])) + 'kmh')
            if 'wind_gust' in f:
                w += (Config.Lgusting +
                      '%.1f' % (speedMph(f['wind_gust'])) + 'kmh')
            wind.setText(w)
            wind2.setText(Config.LFeelslike + f'{round(f["feels_like"]):.0f}°C')
            wdate.setText("{0:%H:%M}".format(datetime.datetime.fromtimestamp(
                int(f['dt']))))
    # Config.LPrecip1hr + f['precip_1hr_metric'] + 'mm ' +
    # Config.LToday + f['precip_today_metric'] + 'mm')
        else:
            temper.setText(f'{round(tempToImp(f["temp"])*2/2):.1f}°F')
            temper2.setText(f'{round(tempToImp(f["temp"])*2/2):.1f}°F')
            press.setText(Config.LPressure + f'{round(pressi(f["pressure"])):.0f}in')
            humidity.setText(Config.LHumidity + f'{round(f["humidity"]):.0f}%')
            wd = bearing(f['wind_deg'])
            if Config.wind_degrees:
                wd = str(f['wind_deg']) + u'°'
            w = (Config.LWind +
                 wd + ' ' +
                 '%.1f' % ((f['wind_speed'])) + 'mph')
            if 'wind_gust' in f:
                w += (Config.Lgusting +
                      '%.1f' % ((f['wind_gust'])) + 'kph')
            wind.setText(w)
            wind2.setText(Config.LFeelslike + f'{round(tempToImp(f["feels_like"])):.0f}°F')
            wdate.setText("{0:%H:%M}".format(datetime.datetime.fromtimestamp(
                int(f['dt']))))
    # Config.LPrecip1hr + f['precip_1hr_in'] + 'in ' +
    # Config.LToday + f['precip_today_in'] + 'in')
    for i in range(0, 3):
        f = wxdata['hourly'][i * 3 + 2]
        fl = forecast[i]
        wicon = f['weather'][0]['icon']
        wicon = owmicons[wicon]
        icon = fl.findChild(QtWidgets.QLabel, "icon")
        wxiconpixmap = QtGui.QPixmap(
            Config.icons + "/" + wicon + ".png")
        icon.setPixmap(wxiconpixmap.scaled(
            icon.width(),
            icon.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wx = fl.findChild(QtWidgets.QLabel, "wx")
        day = fl.findChild(QtWidgets.QLabel, "day")
        day.setText("{0:%A %I:%M%p}".format(datetime.datetime.fromtimestamp(
            int(f['dt']))))
        s = ''
        pop = 0
        ptype = ''
        paccum = 0
        if ('pop' in f):
            pop = float(f['pop']) * 100.0
        if ('snow' in f):
            ptype = 'snow'
            paccum = float(f['snow']['1h'])
        if ('rain' in f):
            ptype = 'rain'
            paccum = float(f['rain']['1h'])

        if (pop > 0.0 or ptype != ''):
            s += '%.0f' % pop + '% '
        if Config.metric:
            if (ptype == 'snow'):
                if (paccum > 0.05):
                    s += Config.LSnow + '%.0f' % paccum + 'mm '
            else:
                if (paccum > 0.05):
                    s += Config.LRain + '%.0f' % paccum + 'mm '
            s += '%.0f' % round(f['temp']) + u'°C'
        else:
            if (ptype == 'snow'):
                if (paccum > 0.05):
                    s += Config.LSnow + '%.0f' % heightImp(paccum) + 'in '
            else:
                if (paccum > 0.05):
                    s += Config.LRain + '%.0f' % heightImp(paccum) + 'in '
            s += '%.0f' % round(tempToImp(f['temp'])) + u'°F'

        wx.setStyleSheet(
            "#wx { font-size: " +
            str(int(25 * xscale * Config.fontmult)) + "px; }")
        wx.setText(f['weather'][0]['description'] + "\n" + s)

    for i in range(3, 9):
        f = wxdata['daily'][i - 3]
        wicon = f['weather'][0]['icon']
        wicon = owmicons[wicon]
        fl = forecast[i]
        icon = fl.findChild(QtWidgets.QLabel, "icon")
        wxiconpixmap = QtGui.QPixmap(Config.icons + "/" + wicon + ".png")
        icon.setPixmap(wxiconpixmap.scaled(
            icon.width(),
            icon.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wx = fl.findChild(QtWidgets.QLabel, "wx")
        day = fl.findChild(QtWidgets.QLabel, "day")
        day.setText("{0:%A}".format(datetime.datetime.fromtimestamp(
            int(f['dt']))))
        s = ''
        pop = 0
        ptype = ''
        paccum = 0
        if ('pop' in f):
            pop = float(f['pop']) * 100.0
        if ('rain' in f):
            ptype = 'rain'
            paccum = float(f['rain'])
        if ('snow' in f):
            ptype = 'snow'
            paccum = float(f['snow'])

        if (pop > 0.05 or ptype != ''):
            s += '%.0f' % pop + '% '
        if Config.metric:
            if (ptype == 'snow'):
                if (paccum > 0.05):
                    s += Config.LSnow + '%.0f' % paccum + 'mm '
            else:
                if (paccum > 0.05):
                    s += Config.LRain + '%.0f' % paccum + 'mm '
            s += '%.0f' % round(f['temp']['max']) + '/' + \
                 '%.0f' % round(f['temp']['min'])
        else:
            if (ptype == 'snow'):
                if (paccum > 0.05):
                    s += Config.LSnow + '%.1f' % heightImp(paccum) + 'in '
            else:
                if (paccum > 0.05):
                    s += Config.LRain + '%.1f' % heightImp(paccum) + 'in '
            s += '%.0f' % round(tempToImp(f['temp']['max'])) + '/' + \
                 '%.0f' % round(tempToImp(f['temp']['min']))

        wx.setStyleSheet(
            "#wx { font-size: "
            + str(int(19 * xscale * Config.fontmult)) + "px; }")
        wx.setText(f['weather'][0]['description'] + "\n" + s)


def wxfinished_ds():
    global wxreply, wxdata, supress_current
    global wxicon, temper, wxdesc, press, humidity
    global wind, wind2, wdate, bottom, forecast
    global wxicon2, temper2, wxdesc2, attribution
    global daytime

    attribution.setText("DarkSky.net")
    attribution2.setText("DarkSky.net")

    wxstr = str(wxreply.readAll())
    wxdata = json.loads(wxstr)
    f = wxdata['currently']
    if not supress_current:
        wxiconpixmap = QtGui.QPixmap(Config.icons + "/" + f['icon'] + ".png")
        wxicon.setPixmap(wxiconpixmap.scaled(
            wxicon.width(), wxicon.height(), Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wxicon2.setPixmap(wxiconpixmap.scaled(
            wxicon.width(),
            wxicon.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wxdesc.setText(f['summary'])
        wxdesc2.setText(f['summary'])

        if Config.metric:
            temper.setText('%.1f' % (tempm(f['temperature'])) + u'°C')
            temper2.setText('%.1f' % (tempm(f['temperature'])) + u'°C')
            press.setText(Config.LPressure + '%.1f' % f['pressure'] + 'mb')
            humidity.setText(
                Config.LHumidity + '%.0f%%' % (f['humidity']*100.0))
            wd = bearing(f['windBearing'])
            if Config.wind_degrees:
                wd = str(f['windBearing']) + u'°'
            wind.setText(Config.LWind +
                         wd + ' ' +
                         '%.1f' % (speedm(f['windSpeed'])) + 'kmh' +
                         Config.Lgusting +
                         '%.1f' % (speedm(f['windGust'])) + 'kmh')
            wind2.setText(Config.LFeelslike +
                          '%.1f' % (tempm(f['apparentTemperature'])) + u'°C')
            wdate.setText("{0:%H:%M}".format(datetime.datetime.fromtimestamp(
                int(f['time']))))
    # Config.LPrecip1hr + f['precip_1hr_metric'] + 'mm ' +
    # Config.LToday + f['precip_today_metric'] + 'mm')
        else:
            temper.setText('%.1f' % (f['temperature']) + u'°F')
            temper2.setText('%.1f' % (f['temperature']) + u'°F')
            press.setText(
                Config.LPressure + '%.2f' % pressi(f['pressure']) + 'in')
            humidity.setText(
                Config.LHumidity + '%.0f%%' % (f['humidity']*100.0))
            wd = bearing(f['windBearing'])
            if Config.wind_degrees:
                wd = str(f['windBearing']) + u'°'
            wind.setText(Config.LWind +
                         wd + ' ' +
                         '%.1f' % (f['windSpeed']) + 'mph' +
                         Config.Lgusting +
                         '%.1f' % (f['windGust']) + 'mph')
            wind2.setText(Config.LFeelslike +
                          '%.1f' % (f['apparentTemperature']) + u'°F')
            wdate.setText("{0:%H:%M}".format(datetime.datetime.fromtimestamp(
                int(f['time']))))
    # Config.LPrecip1hr + f['precip_1hr_in'] + 'in ' +
    # Config.LToday + f['precip_today_in'] + 'in')

    for i in range(0, 3):
        f = wxdata['hourly']['data'][i * 3 + 2]
        fl = forecast[i]
        icon = fl.findChild(QtWidgets.QLabel, "icon")
        wxiconpixmap = QtGui.QPixmap(
            Config.icons + "/" + f['icon'] + ".png")
        icon.setPixmap(wxiconpixmap.scaled(
            icon.width(),
            icon.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wx = fl.findChild(QtWidgets.QLabel, "wx")
        day = fl.findChild(QtWidgets.QLabel, "day")
        day.setText("{0:%A %I:%M%p}".format(datetime.datetime.fromtimestamp(
            int(f['time']))))
        s = ''
        pop = 0
        ptype = ''
        paccum = 0
        if ('precipProbability' in f):
            pop = float(f['precipProbability']) * 100.0
        if ('precipAccumulation' in f):
            paccum = float(f['precipAccumulation'])
        if ('precipType' in f):
            ptype = f['precipType']

        if (pop > 0.0 or ptype != ''):
            s += '%.0f' % pop + '% '
        if Config.metric:
            if (ptype == 'snow'):
                if (paccum > 0.05):
                    s += Config.LSnow + '%.0f' % heightm(paccum) + 'mm '
            else:
                if (paccum > 0.05):
                    s += Config.LRain + '%.0f' % heightm(paccum) + 'mm '
            s += '%.0f' % tempm(f['temperature']) + u'°C'
        else:
            if (ptype == 'snow'):
                if (paccum > 0.05):
                    s += Config.LSnow + '%.0f' % paccum + 'in '
            else:
                if (paccum > 0.05):
                    s += Config.LRain + '%.0f' % paccum + 'in '
            s += '%.0f' % (f['temperature']) + u'°F'

        wx.setStyleSheet("#wx { font-size: " + str(int(25 * xscale)) + "px; }")
        wx.setText(f['summary'] + "\n" + s)

    for i in range(3, 9):
        f = wxdata['daily']['data'][i - 3]
        fl = forecast[i]
        icon = fl.findChild(QtWidgets.QLabel, "icon")
        wxiconpixmap = QtGui.QPixmap(Config.icons + "/" + f['icon'] + ".png")
        icon.setPixmap(wxiconpixmap.scaled(
            icon.width(),
            icon.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wx = fl.findChild(QtWidgets.QLabel, "wx")
        day = fl.findChild(QtWidgets.QLabel, "day")
        day.setText("{0:%A}".format(datetime.datetime.fromtimestamp(
            int(f['time']))))
        s = ''
        pop = 0
        ptype = ''
        paccum = 0
        if ('precipProbability' in f):
            pop = float(f['precipProbability']) * 100.0
        if ('precipAccumulation' in f):
            paccum = float(f['precipAccumulation'])
        if ('precipType' in f):
            ptype = f['precipType']

        if (pop > 0.05 or ptype != ''):
            s += '%.0f' % pop + '% '
        if Config.metric:
            if (ptype == 'snow'):
                if (paccum > 0.05):
                    s += Config.LSnow + '%.0f' % heightm(paccum) + 'mm '
            else:
                if (paccum > 0.05):
                    s += Config.LRain + '%.0f' % heightm(paccum) + 'mm '
            s += '%.0f' % tempm(f['temperatureHigh']) + '/' + \
                 '%.0f' % tempm(f['temperatureLow'])
        else:
            if (ptype == 'snow'):
                if (paccum > 0.05):
                    s += Config.LSnow + '%.1f' % paccum + 'in '
            else:
                if (paccum > 0.05):
                    s += Config.LRain + '%.1f' % paccum + 'in '
            s += '%.0f' % f['temperatureHigh'] + '/' + \
                 '%.0f' % f['temperatureLow']

        wx.setStyleSheet("#wx { font-size: " + str(int(19 * xscale)) + "px; }")
        wx.setText(f['summary'] + "\n" + s)


cc_code_map = {
            "freezing_rain_heavy": "Freezing Rain",
            "freezing_rain": "Freezing Rain",
            "freezing_rain_light": "Freezing Rain",
            "freezing_drizzle": "Freezing Drizzle",
            "ice_pellets_heavy": "Ice Pellets",
            "ice_pellets": "Ice Pellets",
            "ice_pellets_light": "Ice Pellets",
            "snow_heavy": "Heavy Snow",
            "snow": "Snow",
            "snow_light": "Light Snow",
            "flurries": "Flurries",
            "tstorm": "Thunder Storm",
            "rain_heavy": "Heavy Rain",
            "rain": "Rain",
            "rain_light": "Light Rain",
            "drizzle": "Drizzle",
            "fog_light": "Light Fog",
            "fog": "Fog",
            "cloudy": "Cloudy",
            "mostly_cloudy": "Mostly Cloudy",
            "partly_cloudy": "Partly Cloudy",
            "mostly_clear": "Mostly Clear",
            "clear": "Clear"
}
cc_code_metar = {
            "Clear": u"Clair",
            "Few Clouds": u"Quelques nuages",
            "Scattered Clouds": u"Nuages épars",
            "Mostly Cloudy": u"Plutôt nuageux",
            "Cloudy": u"Nuageux",
            "Drizzle": u"Bruine",
            "Heavy Freezing Rain": u"Forte pluie verglaçante",
            "Light Freezing Rain": u"Légère pluie verglaçante",
            "Heavy Rain Showers": u"Fortes averses",
            "Light Rain Showers": u"Légères averses",
            "Heavy Blowing Rain": u"Forte pluie et vent",
            "Light Blowing Rain": u"Légère pluie et vent",
            "Freezing Rain": u"Pluie verglaçante",
            "Rain Showers": u"Averses",
            "Blowing Rain": u"Pluie et vent",
            "Heavy Rain": u"Forte pluie",
            "Light Rain": u"Légère pluie",
            "Rain": u"Pluie",
            "Heavy Freezing Snow": u"Forte neige verglaçante",
            "Light Freezing Snow": u"Légère neige verglaçante",
            "Heavy Snow Showers": u"Fortes chutes de neige",
            "Light Snow Showers": u"Faibles chutes de neige",
            "Heavy Blowing Snow": u"Forte neige et vent",
            "Light Blowing Snow": u"Faible neige et vent",
            "Freezing Snow": u"Neige verglaçante",
            "Snow Showers": u"Chute de neige",
            "Blowing Snow": u"Neige et vent",
            "Heavy Snow": u"Forte neige",
            "Light Snow": u"Légère neige",
            "Snow": u"Neige",
            "Blowing Snow Pellets": u"Grésil et vent",
            "Snow Pellets": u"Grésil",
            "Ice Crystals": u"Poudrin de glace",
            "Ice Pellets": u"Faible grêle",
            "Heavy Hail": u"Forte grêle",
            "Hail": u"Grêle"
}


cc_code_icons = {
            "freezing_rain_heavy": "sleet",
            "freezing_rain": "sleet",
            "freezing_rain_light": "sleet",
            "freezing_drizzle": "sleet",
            "ice_pellets_heavy": "sleet",
            "ice_pellets": "sleet",
            "ice_pellets_light": "sleet",
            "snow_heavy": "snow",
            "snow": "snow",
            "snow_light": "snow",
            "flurries": "snow",
            "tstorm": "thunderstorm",
            "rain_heavy": "rain",
            "rain": "rain",
            "rain_light": "rain",
            "drizzle": "rain",
            "fog_light": "fog",
            "fog": "fog",
            "cloudy": "cloudy",
            "partly_cloudy": "partly-cloudy-day",
            "mostly_cloudy": "partly-cloudy-day",
            "mostly_clear": "partly-cloudy-day",
            "clear": "clear-day"
}


def wxfinished_cc():
    global wxreply, wxdata, supress_current
    global wxicon, temper, wxdesc, press, humidity
    global wind, wind2, wdate, bottom, forecast
    global wxicon2, temper2, wxdesc2, attribution
    global daytime
    attribution.setText("climacell.co")
    attribution2.setText("climacell.co")

    wxstr = str(wxreply.readAll())
    wxdata = json.loads(wxstr)
    f = wxdata
    dt = dateutil.parser.parse(f['observation_time']['value'])\
        .astimezone(tzlocal.get_localzone())
    icon = f['weather_code']['value']
    icon = cc_code_icons[icon]
    if not daytime:
        icon = icon.replace('-day', '-night')
    if not supress_current:
        wxiconpixmap = QtGui.QPixmap(Config.icons + "/" + icon + ".png")
        wxicon.setPixmap(wxiconpixmap.scaled(
            wxicon.width(), wxicon.height(), Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wxicon2.setPixmap(wxiconpixmap.scaled(
            wxicon.width(),
            wxicon.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wxdesc.setText(cc_code_map[f['weather_code']['value']])
        wxdesc2.setText(cc_code_map[f['weather_code']['value']])

        if Config.metric:
            temper.setText('%.1f' % (tempm(f['temp']['value'])) + u'°C')
            temper2.setText('%.1f' % (tempm(f['temp']['value'])) + u'°C')
            press.setText(
                Config.LPressure +
                '%.1f' % barom(f['baro_pressure']['value']) + 'mm')
            humidity.setText(
                Config.LHumidity + '%.0f%%' % (f['humidity']['value']))
            wd = bearing(f['wind_direction']['value'])
            if Config.wind_degrees:
                wd = str(f['wind_direction']['value']) + u'°'
            wind.setText(Config.LWind +
                         wd + ' ' +
                         '%.1f' % (speedm(f['wind_speed']['value'])) + 'kmh' +
                         Config.Lgusting +
                         '%.1f' % (speedm(f['wind_gust']['value'])) + 'kmh')
            wind2.setText(Config.LFeelslike +
                          '%.1f' % (tempm(f['feels_like']['value'])) + u'°C')
            wdate.setText("{0:%H:%M}".format(dt))
    # Config.LPrecip1hr + f['precip_1hr_metric'] + 'mm ' +
    # Config.LToday + f['precip_today_metric'] + 'mm')
        else:
            temper.setText('%.1f' % (f['temp']['value']) + u'°F')
            temper2.setText('%.1f' % (f['temp']['value']) + u'°F')
            press.setText(
                Config.LPressure +
                '%.2f' % (f['baro_pressure']['value']) + 'in')
            humidity.setText(
                Config.LHumidity + '%.0f%%' % (f['humidity']['value']))
            wd = bearing(f['wind_direction']['value'])
            if Config.wind_degrees:
                wd = str(f['wind_direction']['value']) + u'°'
            wind.setText(Config.LWind +
                         wd + ' ' +
                         '%.1f' % (f['wind_speed']['value']) + 'mph' +
                         Config.Lgusting +
                         '%.1f' % (f['wind_gust']['value']) + 'mph')
            wind2.setText(Config.LFeelslike +
                          '%.1f' % (f['feels_like']['value']) + u'°F')
            wdate.setText("{0:%H:%M}".format(dt))
    # Config.LPrecip1hr + f['precip_1hr_in'] + 'in ' +
    # Config.LToday + f['precip_today_in'] + 'in')


def wxfinished_cc2():
    global wxreply, forecast
    global daytime
    wxstr2 = str(wxreply2.readAll())
    # print('cc2', wxstr2)
    wxdata2 = json.loads(wxstr2)

    for i in range(0, 3):
        f = wxdata2[i * 3 + 2]
        # print(i, i*3+2, f)
        fl = forecast[i]
        wicon = f['weather_code']['value']
        wicon = cc_code_icons[wicon]

        dt = dateutil.parser.parse(f['observation_time']['value']) \
            .astimezone(tzlocal.get_localzone())
        if dt.day == datetime.datetime.now().day:
            fdaytime = daytime
        else:
            fsunrise = sun.sunrise(dt)
            fsunset = sun.sunset(dt)
            print('calc daytime', fdaytime, dt, fsunrise, fsunset)
            if dt.time() >= fsunrise and dt.time() <= fsunset:
                fdaytime = True
            else:
                fdaytime = False

        if not fdaytime:
            wicon = wicon.replace('-day', '-night')
        icon = fl.findChild(QtWidgets.QLabel, "icon")
        wxiconpixmap = QtGui.QPixmap(
            Config.icons + "/" + wicon + ".png")
        icon.setPixmap(wxiconpixmap.scaled(
            icon.width(),
            icon.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wx = fl.findChild(QtWidgets.QLabel, "wx")
        day = fl.findChild(QtWidgets.QLabel, "day")
        day.setText("{0:%A %I:%M%p}".format(
            dateutil.parser.parse(f['observation_time']['value'])
            .astimezone(tzlocal.get_localzone())))
        s = ''
        pop = float(f['precipitation_probability']['value'])
        ptype = f['precipitation_type']['value']
        if ptype == 'none':
            ptype = ''
        paccum = f['precipitation']['value']

        if (pop > 0.0 or ptype != ''):
            s += '%.0f' % pop + '% '
        if Config.metric:
            if (ptype == 'snow'):
                if (paccum > 0.01):
                    s += Config.LSnow + '%.0f' % heightm(paccum) + 'mm '
            else:
                if (paccum > 0.01):
                    s += Config.LRain + '%.0f' % heightm(paccum) + 'mm '
            s += '%.0f' % tempm(f['temp']['value']) + u'°C'
        else:
            if (ptype == 'snow'):
                if (paccum > 0.01):
                    s += Config.LSnow + '%.0f' % paccum + 'in '
            else:
                if (paccum > 0.01):
                    s += Config.LRain + '%.0f' % paccum + 'in '
            s += '%.0f' % (f['temp']['value']) + u'°F'

        wx.setStyleSheet(
            "#wx { font-size: " +
            str(int(25 * xscale * Config.fontmult)) + "px; }")
        wx.setText(cc_code_map[f['weather_code']['value']] + "\n" + s)


def wxfinished_cc3():
    global wxreply3, forecast
    global daytime
    wxstr3 = str(wxreply3.readAll())
    # print('cc2', wxstr2)
    wxdata3 = json.loads(wxstr3)
    ioff = 0
    dt = dateutil.parser.parse(
        wxdata3[0]['observation_time']['value']+"T00:00:00")
    if datetime.datetime.now().day != dt.day:
        ioff += 1
    for i in range(3, 9):
        f = wxdata3[i - 3 + ioff]
        wicon = f['weather_code']['value']
        wicon = cc_code_icons[wicon]
        fl = forecast[i]
        icon = fl.findChild(QtWidgets.QLabel, "icon")
        wxiconpixmap = QtGui.QPixmap(Config.icons + "/" + wicon + ".png")
        icon.setPixmap(wxiconpixmap.scaled(
            icon.width(),
            icon.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation))
        wx = fl.findChild(QtWidgets.QLabel, "wx")
        day = fl.findChild(QtWidgets.QLabel, "day")
        day.setText("{0:%A}".format(
            dateutil.parser.parse(
                f['observation_time']['value']+"T00:00:00"
            )
            ))
        s = ''
        pop = float(f['precipitation_probability']['value'])
        ptype = ''
        paccum = float(f['precipitation_accumulation']['value'])
        wc = f['weather_code']['value']
        if 'rain' in wc:
            ptype = 'rain'
        if 'drizzle' in wc:
            ptype = 'rain'
        if 'ice' in wc:
            ptype = 'snow'
        if 'flurries' in wc:
            ptype = 'snow'
        if 'snow' in wc:
            ptype = 'snow'
        if 'tstorm' in wc:
            ptype = 'rain'

        # if (pop > 0.05 and ptype == ''):
        #     if f['temp'][1]['max']['value'] > 28:
        #         ptype = 'rain'
        #     else:
        #         ptype = 'snow'
        if (pop > 0.05 or ptype != ''):
            s += '%.0f' % pop + '% '
        if Config.metric:
            if (ptype == 'snow'):
                if (paccum > 0.01):
                    s += Config.LSnow + '%.0f' % heightm(paccum*15) + 'mm '
            else:
                if (paccum > 0.01):
                    s += Config.LRain + '%.0f' % heightm(paccum) + 'mm '
            s += '%.0f' % tempm(f['temp'][1]['max']['value']) + '/' + \
                 '%.0f' % tempm(f['temp'][0]['min']['value'])
        else:
            if (ptype == 'snow'):
                if (paccum > 0.01):
                    s += Config.LSnow + '%.1f' % (paccum*15) + 'in '
            else:
                if (paccum > 0.01):
                    s += Config.LRain + '%.1f' % paccum + 'in '
            s += '%.0f' % f['temp'][1]['max']['value'] + '/' + \
                 '%.0f' % f['temp'][0]['min']['value']

        wx.setStyleSheet(
            "#wx { font-size: "
            + str(int(19 * xscale * Config.fontmult)) + "px; }")
        wx.setText(cc_code_map[f['weather_code']['value']] + "\n" + s)
        print("cc_code_map2[f['weather_code']['value']]", cc_code_map[f['weather_code']['value']])


metar_cond = [
    ('CLR', '', '', 'Clear', 'clear-day', 0),
    ('NSC', '', '', 'Clear', 'clear-day', 0),
    ('SKC', '', '', 'Clear', 'clear-day', 0),
    ('FEW', '', '', 'Few Clouds', 'partly-cloudy-day', 1),
    ('NCD', '', '', 'Clear', 'clear-day', 0),
    ('SCT', '', '', 'Scattered Clouds', 'partly-cloudy-day', 2),
    ('BKN', '', '', 'Mostly Cloudy', 'partly-cloudy-day', 3),
    ('OVC', '', '', 'Cloudy', 'cloudy', 4),

    ('///', '', '', '', 'cloudy', 0),
    ('UP', '', '', '', 'cloudy', 0),
    ('VV', '', '', '', 'cloudy', 0),
    ('//', '', '', '', 'cloudy', 0),

    ('DZ', '', '', 'Drizzle', 'rain', 10),

    ('RA', 'FZ', '+', 'Heavy Freezing Rain', 'sleet', 11),
    ('RA', 'FZ', '-', 'Light Freezing Rain', 'sleet', 11),
    ('RA', 'SH', '+', 'Heavy Rain Showers', 'sleet', 11),
    ('RA', 'SH', '-', 'Light Rain Showers', 'rain', 11),
    ('RA', 'BL', '+', 'Heavy Blowing Rain', 'rain', 11),
    ('RA', 'BL', '-', 'Light Blowing Rain', 'rain', 11),
    ('RA', 'FZ', '', 'Freezing Rain', 'sleet', 11),
    ('RA', 'SH', '', 'Rain Showers', 'rain', 11),
    ('RA', 'BL', '', 'Blowing Rain', 'rain', 11),
    ('RA', '', '+', 'Heavy Rain', 'rain', 11),
    ('RA', '', '-', 'Light Rain', 'rain', 11),
    ('RA', '', '', 'Rain', 'rain', 11),

    ('SN', 'FZ', '+', 'Heavy Freezing Snow', 'snow', 12),
    ('SN', 'FZ', '-', 'Light Freezing Snow', 'snow', 12),
    ('SN', 'SH', '+', 'Heavy Snow Showers', 'snow', 12),
    ('SN', 'SH', '-', 'Light Snow Showers', 'snow', 12),
    ('SN', 'BL', '+', 'Heavy Blowing Snow', 'snow', 12),
    ('SN', 'BL', '-', 'Light Blowing Snow', 'snow', 12),
    ('SN', 'FZ', '', 'Freezing Snow', 'snow', 12),
    ('SN', 'SH', '', 'Snow Showers', 'snow', 12),
    ('SN', 'BL', '', 'Blowing Snow', 'snow', 12),
    ('SN', '', '+', 'Heavy Snow', 'snow', 12),
    ('SN', '', '-', 'Light Snow', 'snow', 12),
    ('SN', '', '', 'Rain', 'snow', 12),

    ('SG', 'BL', '', 'Blowing Snow', 'snow', 12),
    ('SG', '', '', 'Snow', 'snow', 12),
    ('GS', 'BL', '', 'Blowing Snow Pellets', 'snow', 12),
    ('GS', '', '', 'Snow Pellets', 'snow', 12),

    ('IC', '', '', 'Ice Crystals', 'snow', 13),
    ('PL', '', '', 'Ice Pellets', 'snow', 13),

    ('GR', '', '+', 'Heavy Hail', 'thuderstorm', 14),
    ('GR', '', '', 'Hail', 'thuderstorm', 14),
]


def feels_like(f):
    t = f.temp.value('C')
    d = f.dewpt.value('C')
    h = (math.exp((17.625*d)/(243.04+d)) /
         math.exp((17.625*t)/(243.04+t)))
    t = f.temp.value('F')
    w = f.wind_speed.value('MPH')
    if t > 80 and h >= 0.40:
        hi = (-42.379 + 2.04901523 * t + 10.14333127 * h - .22475541 * t * h -
              .00683783 * t * t - .05481717 * h * h + .00122874 * t * t * h +
              .00085282 * t * h * h - .00000199 * t * t * h * h)
        if h < 0.13 and t >= 80.0 and t <= 112.0:
            hi -= ((13 - h) / 4) * math.sqrt((17 - math.abs(t-95)) / 17)
        if h > 0.85 and t >= 80.0 and t <= 112.0:
            hi += ((h - 85)/10) * ((87 - t)/5)
        return hi
    if t < 50 and w >= 3:
        wc = 35.74 + 0.6215 * t - 35.75 * \
         (w ** 0.16) + 0.4275 * t * (w ** 0.16)
        return wc
    return t

compass_french = {
            "N": "N",
            "S": "S",
            "W": "O",
            "E": "E",
            "NW": "NO",
            "SW": "SO",
            "NE": "NE",
            "SE": "SE",
            "NNW": "NNO",
            "SSW": "SSO",
            "NNE": "NNE",
            "SSE": "SSE",
            "WNW": "ONO",
            "WSW": "OSO",
            "ENE": "ENE",
            "ESE": "ESE"
}

def wxfinished_metar():
    global metarreply
    global wxicon, temper, wxdesc, press, humidity
    global wind, wind2, wdate, bottom
    global wxicon2, temper2, wxdesc2
    global daytime
    global attribution, attribution2

    attribution.setText("METAR " + Config.METAR)
    attribution2.setText("METAR " + Config.METAR)


    try:
        wxstr = str(metarreply.readAll(),'utf-8')
    except:
        print("Error : Could not extract METAR data from URL")
        return
    # print("[DEBUG] : ", wxstr)
    for wxline in wxstr.splitlines():
        if wxline.startswith(Config.METAR):
            wxstr = wxline
    f = Metar.Metar(wxstr,strict=False)
    try:
        dt = f.time.replace(tzinfo=tzutc()).astimezone(tzlocal.get_localzone())
    except:
        print("Error: METAR string is not valid")
        print("METAR string : ", wxstr)
        return
    pri = -1
    weather = ''
    icon = ''
    print(f.string())
    for s in f.sky:
        print("f.sky : ", s)
        for c in metar_cond:
            if s[0] == c[0]:
                if c[5] > pri:
                    pri = c[5]
                    weather = c[3]
                    icon = c[4]
    for w in f.weather:
        print("f.weather : ", w)
        for c in metar_cond:
            if w[2] == c[0]:
                if c[1] > '':
                    if w[1] == c[1]:
                        if c[2] > '':
                            if w[0][0:1] == c[2]:
                                if c[5] > pri:
                                    pri = c[5]
                                    weather = c[3]
                                    icon = c[4]
                else:
                    if c[2] > '':
                        if w[0][0:1] == c[2]:
                            if c[5] > pri:
                                pri = c[5]
                                weather = c[3]
                                icon = c[4]
                    else:
                        if c[5] > pri:
                            pri = c[5]
                            weather = c[3]
                            icon = c[4]
    if weather == '':
        weather = cc_code_metar['Clear']
        for c in metar_cond:
            icon = 'clear-day'
            pri = c[5]
    else:
        weather = cc_code_metar[weather]
    if not daytime:
        icon = icon.replace('-day', '-night')

    print("weather values :",icon, weather, pri)

    wxiconpixmap = QtGui.QPixmap(Config.icons + "/" + icon + ".png")
    wxicon.setPixmap(wxiconpixmap.scaled(
        wxicon.width(), wxicon.height(), Qt.IgnoreAspectRatio,
        Qt.SmoothTransformation))
    wxicon2.setPixmap(wxiconpixmap.scaled(
        wxicon.width(),
        wxicon.height(),
        Qt.IgnoreAspectRatio,
        Qt.SmoothTransformation))
    wxdesc.setText(weather)
    wxdesc2.setText(weather)
    if Config.metric:
        temper.setText('%.1f' % round((f.temp.value('C'))) + u'°C')
        temper2.setText('%.1f' % round((f.temp.value('C'))) + u'°C')
        press.setText(
            Config.LPressure +
            '%.1f' % f.press.value('MB') + 'mb')
        t = f.temp.value('C')
        d = f.dewpt.value('C')
        h = 100.0 * (math.exp((17.625*d)/(243.04+d)) /
                     math.exp((17.625*t)/(243.04+t)))
        humidity.setText(
            Config.LHumidity + '%.0f%%' % (h))
        if f.wind_dir != None:
            wd = f.wind_dir.compass()
            wd = compass_french[wd]
        else:
            wd = 'variable'
        if Config.wind_degrees:
            wd = str(f.wind_dir.value) + u'°'
        ws = (Config.LWind +
              wd + ' ' +
              '%.1f' % (f.wind_speed.value('KMH')) + 'kmh')
        if f.wind_gust:
            ws += (Config.Lgusting +
                   '%.1f' % (f.wind_gust.value('KMH')) + 'kmh')
        wind.setText(ws)
        wind2.setText(Config.LFeelslike +
                      ('%.0f' % (round(feels_like(f))) + u'°C'))
        wdate.setText("{0:%H:%M}".format(dt))
# Config.LPrecip1hr + f['precip_1hr_metric'] + 'mm ' +
# Config.LToday + f['precip_today_metric'] + 'mm')
    else:
        temper.setText('%.1f' % (f.temp.value('F')) + u'°F')
        temper2.setText('%.1f' % (f.temp.value('F')) + u'°F')
        press.setText(
            Config.LPressure +
            '%.2f' % f.press.value('IN') + 'in')
        t = f.temp.value('C')
        d = f.dewpt.value('C')
        h = 100.0 * (math.exp((17.625*d)/(243.04+d)) /
                     math.exp((17.625*t)/(243.04+t)))
        humidity.setText(
            Config.LHumidity + '%.0f%%' % (h))
        wd = f.wind_dir.compass()
        if Config.wind_degrees:
            wd = str(f.wind_dir.value) + u'°'
        ws = (Config.LWind +
              wd + ' ' +
              '%.1f' % (f.wind_speed.value('MPH')) + 'mph')
        if f.wind_gust:
            ws += (Config.Lgusting +
                   '%.1f' % (f.wind_gust.value('MPH')) + 'mph')
        wind.setText(ws)
        wind2.setText(Config.LFeelslike +
                      '%.1f' % (feels_like(f)) + u'°F')
        wdate.setText("{0:%H:%M} {1}".format(dt, Config.METAR))
# Config.LPrecip1hr + f['precip_1hr_in'] + 'in ' +
# Config.LToday + f['precip_today_in'] + 'in')


def getwx():
    global supress_current
    supress_current = False
    try:
        if Config.use_metar :
            supress_current = True
            getwx_metar()
    except:
        pass

    try:
        ApiKeys.dsapi
        getwx_ds()
        return
    except:
        pass

    try:
        ApiKeys.ccapi
        global cc_code_map, cc_code_metar
        try:
            cc_code_map = Config.Lcc_code_map
            cc_code_metar = Config.Lcc_code_metar
        except:
            pass
        getwx_cc()
        return
    except:
        pass

    try:
        ApiKeys.owmapi
        getwx_owm()
        return
    except:
        pass


def getwx_ds():
    global wxurl
    global wxreply
    print ("getting current and forecast:" + time.ctime())
    wxurl = 'https://api.darksky.net/forecast/' + \
        ApiKeys.dsapi + \
        '/'
    wxurl += str(Config.location.lat) + ',' + \
        str(Config.location.lng)
    wxurl += '?units=us&lang=' + Config.Language.lower()
    wxurl += '&r=' + str(random.random())
    print (wxurl)
    r = QUrl(wxurl)
    r = QNetworkRequest(r)
    wxreply = manager.get(r)
    wxreply.finished.connect(wxfinished_ds)


def getwx_owm():
    global wxurl
    global wxreply
    print("getting current and forecast:" + time.ctime())
    wxurl = 'https://api.openweathermap.org/data/2.5/onecall?appid=' + \
        ApiKeys.owmapi
    wxurl += "&lat=" + str(Config.location.lat) + '&lon=' + \
        str(Config.location.lng)
    wxurl += '&units=metric&lang=' + Config.Language.lower()
    wxurl += '&r=' + str(random.random())
    print(wxurl)
    r = QUrl(wxurl)
    r = QNetworkRequest(r)
    wxreply = manager.get(r)
    event = QEventLoop()
    wxreply.finished.connect(event.quit)
    wxreply.finished.connect(wxfinished_owm)
    event.exec()
    # print("wxreply ", str(wxreply.readAll()))


def getwx_cc():
    global wxurl
    global wxurl2
    global wxurl3
    global wxreply
    global wxreply2
    global wxreply3
    print("getting current:" + time.ctime())
    wxurl = 'https://api.climacell.co/v3/weather/realtime?apikey=' + \
        ApiKeys.ccapi
    wxurl += "&lat=" + str(Config.location.lat) + '&lon=' + \
        str(Config.location.lng)
    wxurl += '&unit_system=us'
    wxurl += '&fields=temp,weather_code,feels_like,humidity,'
    wxurl += 'wind_speed,wind_direction,wind_gust,baro_pressure'
    print(wxurl)
    r = QUrl(wxurl)
    r = QNetworkRequest(r)
    wxreply = manager.get(r)
    wxreply.finished.connect(wxfinished_cc)

    print("getting hourly:" + time.ctime())
    wxurl2 = 'https://api.climacell.co/v3/weather/forecast/hourly?apikey=' + \
        ApiKeys.ccapi
    wxurl2 += "&lat=" + str(Config.location.lat) + '&lon=' + \
        str(Config.location.lng)
    wxurl2 += '&unit_system=us'
    wxurl2 += '&fields=temp,precipitation,precipitation_type,'
    wxurl2 += 'precipitation_probability,weather_code'
    print(wxurl2)
    r2 = QUrl(wxurl2)
    r2 = QNetworkRequest(r2)
    wxreply2 = manager.get(r2)
    wxreply2.finished.connect(wxfinished_cc2)

    print("getting daily:" + time.ctime())
    wxurl3 = 'https://api.climacell.co/v3/weather/forecast/daily?apikey=' + \
        ApiKeys.ccapi
    wxurl3 += "&lat=" + str(Config.location.lat) + '&lon=' + \
        str(Config.location.lng)
    wxurl3 += '&unit_system=us'
    wxurl3 += '&fields=temp,precipitation_accumulation,'
    wxurl3 += 'precipitation_probability,weather_code'
    print(wxurl3)
    r3 = QUrl(wxurl3)
    r3 = QNetworkRequest(r3)
    wxreply3 = manager.get(r3)
    wxreply3.finished.connect(wxfinished_cc3)


def getwx_metar():
    global metarurl
    global metarreply
    metarurl = \
        "https://tgftp.nws.noaa.gov/data/observations/metar/stations/" + \
        Config.METAR + ".TXT"
    print(metarurl)
    r = QUrl(metarurl)
    r = QNetworkRequest(r)
    metarreply = manager.get(r)
    event = QEventLoop()
    metarreply.finished.connect(event.quit)
    metarreply.finished.connect(wxfinished_metar)
    event.exec()

def getallwx():
    getwx()
   
@QtCore.pyqtSlot(int)
def on_stateChanged(state):
        if state == MqttClient.Connected:
            print(state)
            client.subscribe("zigbee/Sensor1")
            client.subscribe("zigbee/Sensor2")

@QtCore.pyqtSlot(str)
def on_messageSignal(msg):
        try:
            print("read from " + msg)
            tempfinished(msg)

        except ValueError:
            print("error: Not is number")

def qtstart():
    global ctimer, wxtimer, temptimer
    global manager
    global objradar1
    global objradar2
    global objradar3
    global objradar4
    global sun, daytime, sunrise, sunset

    dt = datetime.datetime.now().replace(tzinfo=tzlocal.get_localzone())
    sun = suntimes(Config.location.lat, Config.location.lng)
    dt = tzlocal.get_localzone().localize(datetime.datetime.now())
    sunrise = sun.sunrise(dt)
    sunset = sun.sunset(dt)
    if dt.time() >= sunrise and dt.time() <= sunset:
            daytime = True
    else:
            daytime = False
    getallwx()

    # gettemp()

    objradar1.start(Config.radar_refresh * 60)
    objradar1.wxstart()
    objradar2.start(Config.radar_refresh * 60)
    objradar2.wxstart()
    objradar3.start(Config.radar_refresh * 60)
    objradar4.start(Config.radar_refresh * 60)

    ctimer = QtCore.QTimer()
    ctimer.timeout.connect(tick)
    ctimer.start(1000)

    wxtimer = QtCore.QTimer()
    wxtimer.timeout.connect(getallwx)
    wxtimer.start(1000 * Config.weather_refresh *
                  60 + random.uniform(1000, 10000))

    # temptimer = QtCore.QTimer()
    # temptimer.timeout.connect(gettemp)
    # temptimer.start(1000 * 10 * 60 + random.uniform(1000, 10000))

    if Config.useslideshow:
        objimage1.start(Config.slide_time)


class SS(QtWidgets.QLabel):
    def __init__(self, parent, rect, myname):
        self.myname = myname
        self.rect = rect
        QtWidgets.QLabel.__init__(self, parent)

        self.pause = False
        self.count = 0
        self.img_list = []
        self.img_inc = 1

        self.get_images()

        self.setObjectName("slideShow")
        self.setGeometry(rect)
        self.setStyleSheet("#slideShow { background-color: " +
                           Config.slide_bg_color + "; }")
        self.setAlignment(Qt.AlignHCenter | Qt.AlignCenter)

    def start(self, interval):
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.run_ss)
        self.timer.start(1000 * interval + random.uniform(1, 10))
        self.run_ss()

    def stop(self):
        try:
            self.timer.stop()
            self.timer = None
        except Exception:
            pass

    def run_ss(self):
        self.get_images()
        self.switch_image()

    def switch_image(self):
        if self.img_list:
            if not self.pause:
                self.count += self.img_inc
                if self.count >= len(self.img_list):
                    self.count = 0
                self.show_image(self.img_list[self.count])
                self.img_inc = 1

    def show_image(self, image):
        image = QtWidgets.QImage(image)

        bg = QtGui.QPixmap.fromImage(image)
        self.setPixmap(bg.scaled(
                self.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation))

    def get_images(self):
        self.get_local(Config.slides)

    def play_pause(self):
        if not self.pause:
            self.pause = True
        else:
            self.pause = False

    def prev_next(self, direction):
        self.img_inc = direction
        self.timer.stop()
        self.switch_image()
        self.timer.start()

    def get_local(self, path):
        try:
            dirContent = os.listdir(path)
        except OSError:
            print("path '%s' doesn't exists." % path)

        for each in dirContent:
            fullFile = os.path.join(path, each)
            if os.path.isfile(fullFile) and (fullFile.lower().endswith('png')
               or fullFile.lower().endswith('jpg')):
                    self.img_list.append(fullFile)


class Radar(QtWidgets.QLabel):
    def __init__(self, parent, radar, rect, myname):
        global xscale, yscale
        self.myname = myname
        self.rect = rect
        self.anim = 5
        self.zoom = radar["zoom"]
        self.point = radar["center"]
        self.radar = radar
        self.baseurl = self.mapurl(radar, rect)
        print ("map base url: " + self.baseurl)
        QtWidgets.QLabel.__init__(self, parent)
        self.interval = Config.radar_refresh * 60
        self.lastwx = 0
        self.retries = 0
        self.corners = getCorners(self.point, self.zoom,
                                  rect.width(), rect.height())
        self.baseTime = 0
        self.cornerTiles = {
         "NW": getTileXY(LatLng(self.corners["N"],
                                self.corners["W"]), self.zoom),
         "NE": getTileXY(LatLng(self.corners["N"],
                                self.corners["E"]), self.zoom),
         "SE": getTileXY(LatLng(self.corners["S"],
                                self.corners["E"]), self.zoom),
         "SW": getTileXY(LatLng(self.corners["S"],
                                self.corners["W"]), self.zoom)
        }
        self.tiles = []
        self.tiletails = []
        self.totalWidth = 0
        self.totalHeight = 0
        self.tilesWidth = 0
        self.tilesHeight = 0

        self.setObjectName("radar")
        self.setGeometry(rect)
        self.setStyleSheet("#radar { background-color: grey; }")
        self.setAlignment(Qt.AlignCenter)

        self.wwx = QtWidgets.QLabel(self)
        self.wwx.setObjectName("wx")
        self.wwx.setStyleSheet("#wx { background-color: transparent; }")
        self.wwx.setGeometry(0, 0, rect.width(), rect.height())

        self.wmk = QtWidgets.QLabel(self)
        self.wmk.setObjectName("mk")
        self.wmk.setStyleSheet("#mk { background-color: transparent; }")
        self.wmk.setGeometry(0, 0, rect.width(), rect.height())

        for y in range(int(self.cornerTiles["NW"]["Y"]),
                       int(self.cornerTiles["SW"]["Y"])+1):
            self.totalHeight += 256
            self.tilesHeight += 1
            for x in range(int(self.cornerTiles["NW"]["X"]),
                           int(self.cornerTiles["NE"]["X"])+1):
                tile = {"X": x, "Y": y}
                self.tiles.append(tile)
                if 'color' not in radar:
                    radar['color'] = 6
                if 'smooth' not in radar:
                    radar['smooth'] = 1
                if 'snow' not in radar:
                    radar['snow'] = 1
                tail = "/256/%d/%d/%d/%d/%d_%d.png" % (self.zoom, x, y,
                                                       radar['color'],
                                                       radar['smooth'],
                                                       radar['snow'])
                if 'oldcolor' in radar:
                    tail = "/256/%d/%d/%d.png?color=%d" % (self.zoom, x, y,
                                                           radar['color']
                                                           )
                self.tiletails.append(tail)
        for x in range(int(self.cornerTiles["NW"]["X"]),
                       int(self.cornerTiles["NE"]["X"])+1):
            self.totalWidth += 256
            self.tilesWidth += 1
        self.frameImages = []
        self.frameIndex = 0
        self.displayedFrame = 0
        self.ticker = 0
        self.lastget = 0

    def rtick(self):
        if time.time() > (self.lastget + self.interval):
            self.get(time.time())
            self.lastget = time.time()
        if len(self.frameImages) < 1:
            return
        if self.displayedFrame == 0:
            self.ticker += 1
            if self.ticker < 5:
                return
        self.ticker = 0
        # print("len frameImages :", len(self.frameImages), "self.displayedFrame : ", self.displayedFrame)
        if self.displayedFrame >= len(self.frameImages):
            self.displayedFrame = 0
        f = self.frameImages[self.displayedFrame]
        self.wwx.setPixmap(f["image"])
        self.displayedFrame += 1

    def get(self, t=0):
        t = int(t / 600)*600
        if t > 0 and self.baseTime == t:
            return
        if t == 0:
            t = self.baseTime
        else:
            self.baseTime = t
        newf = []
        for f in self.frameImages:
            if f["time"] >= (t - self.anim * 600):
                newf.append(f)
        self.frameImages = newf
        firstt = t - self.anim * 600
        for tt in range(firstt, t+1, 600):
            print ("get... " + str(tt) + " " + self.myname)
            gotit = False
            for f in self.frameImages:
                if f["time"] == tt:
                    gotit = True
            if not gotit:
                self.getTiles(tt)
                break

    def getTiles(self, t, i=0):
        t = int(t / 600)*600
        self.getTime = t
        self.getIndex = i
        if i == 0:
            self.tileurls = []
            self.tileQimages = []
            for tt in self.tiletails:
                tileurl = "https://tilecache.rainviewer.com/v2/radar/%d/%s" \
                    % (t, tt)
                self.tileurls.append(tileurl)
        print (self.myname + " " + str(self.getIndex) + " " + self.tileurls[i])
        self.tilereq = QNetworkRequest(QUrl(self.tileurls[i]))
        self.tilereply = manager.get(self.tilereq)
        self.tilereply.finished.connect(self.getTilesReply)
        # QtCore.QObject.connect(self.tilereply, QtCore.SIGNAL(
        #         "finished()"), self.getTilesReply)

        # self.basereply.finished.connect(self.basefinished)
        # QtCore.QObject.connect(self.basereply, QtCore.SIGNAL(
        #     "finished()"), self.basefinished)

    def getTilesReply(self):
        print ("getTilesReply " + str(self.getIndex))
        if self.tilereply.error() != QNetworkReply.NoError:
                return
        self.tileQimages.append(QImage())
        self.tileQimages[self.getIndex].loadFromData(self.tilereply.readAll())
        self.getIndex = self.getIndex + 1
        if self.getIndex < len(self.tileurls):
            self.getTiles(self.getTime, self.getIndex)
        else:
            self.combineTiles()
            self.get()

    def combineTiles(self):
        global radar1
        ii = QImage(self.tilesWidth*256, self.tilesHeight*256,
                    QImage.Format_ARGB32)
        painter = QPainter()
        painter.begin(ii)
        painter.setPen(QColor(255, 255, 255, 255))
        painter.setFont(QFont("Arial", 10))
        i = 0
        xo = self.cornerTiles["NW"]["X"]
        xo = int((int(xo) - xo)*256)
        yo = self.cornerTiles["NW"]["Y"]
        yo = int((int(yo) - yo)*256)
        for y in range(0, self.totalHeight, 256):
            for x in range(0, self.totalWidth, 256):
                if self.tileQimages[i].format() == 5:
                    painter.drawImage(x, y, self.tileQimages[i])
                # painter.drawRect(x, y, 255, 255)
                # painter.drawText(x+3, y+12, self.tiletails[i])
                i += 1
        painter.end()
        painter = None
        self.tileQimages = []
        ii2 = ii.copy(-xo, -yo, self.rect.width(), self.rect.height())
        ii = None
        painter2 = QPainter()
        painter2.begin(ii2)
        timestamp = "{0:%H:%M} rainvewer.com".format(
                    datetime.datetime.fromtimestamp(self.getTime))
        painter2.setPen(QColor(63, 63, 63, 255))
        painter2.setFont(QFont("Arial", 8))
        painter2.setRenderHint(QPainter.TextAntialiasing)
        painter2.drawText(3-1, 12-1, timestamp)
        painter2.drawText(3+2, 12+1, timestamp)
        painter2.setPen(QColor(255, 255, 255, 255))
        painter2.drawText(3, 12, timestamp)
        painter2.drawText(3+1, 12, timestamp)
        painter2.end()
        painter2 = None
        ii3 = QPixmap(ii2)
        ii2 = None
        self.frameImages.append({"time": self.getTime, "image": ii3})
        ii3 = None

    def mapurl(self, radar, rect):
        mb = 0
        try:
            mb = Config.usemapbox
        except:
            pass
        if mb:
            return self.mapboxurl(radar, rect)
        else:
            return self.googlemapurl(radar, rect)

    def mapboxurl(self, radar, rect):
        #  note we're using google maps zoom factor.
        #  Mapbox equivilant zoom is one less
        #  They seem to be using 512x512 tiles instead of 256x256
        style = 'mapbox/satellite-streets-v10'
        if 'style' in radar:
            style = radar['style']
        return 'https://api.mapbox.com/styles/v1/' + \
               style + \
               '/static/' + \
               str(radar['center'].lng) + ',' + \
               str(radar['center'].lat) + ',' + \
               str(radar['zoom']-1) + ',0,0/' + \
               str(rect.width()) + 'x' + str(rect.height()) + \
               '?access_token=' + ApiKeys.mbapi

    def googlemapurl(self, radar, rect):
        urlp = []
        if len(ApiKeys.googleapi) > 0:
            urlp.append('key=' + ApiKeys.googleapi)
        urlp.append(
            'center=' + str(radar['center'].lat) +
            ',' + str(radar['center'].lng))
        zoom = radar['zoom']
        rsize = rect.size()
        if rsize.width() > 640 or rsize.height() > 640:
            rsize = QtCore.QSize(rsize.width() / 2, rsize.height() / 2)
            zoom -= 1
        urlp.append('zoom=' + str(zoom))
        urlp.append('size=' + str(rsize.width()) + 'x' + str(rsize.height()))
        urlp.append('maptype=hybrid')

        return 'http://maps.googleapis.com/maps/api/staticmap?' + \
            '&'.join(urlp)

    def basefinished(self):
        if self.basereply.error() != QNetworkReply.NoError:
            return
        self.basepixmap = QPixmap()
        self.basepixmap.loadFromData(self.basereply.readAll())
        if self.basepixmap.size() != self.rect.size():
            self.basepixmap = self.basepixmap.scaled(self.rect.size(),
                                                     Qt.KeepAspectRatio,
                                                     Qt.SmoothTransformation)
        self.setPixmap(self.basepixmap)

        # make marker pixmap
        self.mkpixmap = QPixmap(self.basepixmap.size())
        self.mkpixmap.fill(Qt.transparent)
        br = QBrush(QColor(Config.dimcolor))
        painter = QPainter()
        painter.begin(self.mkpixmap)
        painter.fillRect(0, 0, self.mkpixmap.width(),
                         self.mkpixmap.height(), br)
        for marker in self.radar['markers']:
            if 'visible' not in marker or marker['visible'] == 1:
                pt = getPoint(marker["location"], self.point, self.zoom,
                              self.rect.width(), self.rect.height())
                mk2 = QImage()
                mkfile = 'teardrop'
                if 'image' in marker:
                    mkfile = marker['image']
                if os.path.dirname(mkfile) == '':
                    mkfile = os.path.join('markers', mkfile)
                if os.path.splitext(mkfile)[1] == '':
                    mkfile += '.png'
                mk2.load(mkfile)
                if mk2.format != QImage.Format_ARGB32:
                    mk2 = mk2.convertToFormat(QImage.Format_ARGB32)
                mkh = 80  # self.rect.height() / 5
                if 'size' in marker:
                    if marker['size'] == 'small':
                        mkh = 64
                    if marker['size'] == 'mid':
                        mkh = 70
                    if marker['size'] == 'tiny':
                        mkh = 40
                if 'color' in marker:
                    c = QColor(marker['color'])
                    (cr, cg, cb, ca) = c.getRgbF()
                    for x in range(0, mk2.width()):
                        for y in range(0, mk2.height()):
                            (r, g, b, a) = QColor.fromRgba(
                                           mk2.pixel(x, y)).getRgbF()
                            r = r * cr
                            g = g * cg
                            b = b * cb
                            mk2.setPixel(x, y, QColor.fromRgbF(r, g, b, a)
                                         .rgba())
                mk2 = mk2.scaledToHeight(mkh, 1)
                painter.drawImage(pt.x-mkh/2, pt.y-mkh/2, mk2)

        painter.end()

        self.wmk.setPixmap(self.mkpixmap)


    def getbase(self):
        global manager
        self.basereq = QNetworkRequest(QUrl(self.baseurl))
        self.basereply = manager.get(self.basereq)
        self.basereply.finished.connect(self.basefinished)
        # QtCore.QObject.connect(self.basereply, QtCore.SIGNAL(
        #     "finished()"), self.basefinished)

    def start(self, interval=0):
        if interval > 0:
            self.interval = interval
        self.getbase()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.rtick)
        self.lastget = time.time() - self.interval + random.uniform(3, 10)

    def wxstart(self):
        print ("wxstart for " + self.myname)
        self.timer.start(200)

    def wxstop(self):
        print ("wxstop for " + self.myname)
        self.timer.stop()

    def stop(self):
        try:
            self.timer.stop()
            self.timer = None
        except Exception:
            pass


def realquit():
    QtWidgets.QApplication.exit(0)


def myquit(a=0, b=0):
    global objradar1, objradar2, objradar3, objradar4
    global ctimer, wtimer, temptimer

    objradar1.stop()
    objradar2.stop()
    objradar3.stop()
    objradar4.stop()
    ctimer.stop()
    wxtimer.stop()
    # temptimer.stop()
    if Config.useslideshow:
        objimage1.stop()

    QtCore.QTimer.singleShot(30, realquit)


def fixupframe(frame, onoff):
    for child in frame.children():
        if isinstance(child, Radar):
            if onoff:
                # print "calling wxstart on radar on ",frame.objectName()
                child.wxstart()
            else:
                # print "calling wxstop on radar on ",frame.objectName()
                child.wxstop()


def nextframe(plusminus):
    global frames, framep
    frames[framep].setVisible(False)
    fixupframe(frames[framep], False)
    framep += plusminus
    if framep >= len(frames):
        framep = 0
    if framep < 0:
        framep = len(frames) - 1
    frames[framep].setVisible(True)
    fixupframe(frames[framep], True)


class myMain(QtWidgets.QWidget):

    def keyPressEvent(self, event):
        global weatherplayer, lastkeytime
        if isinstance(event, QtWidgets.QKeyEvent):
            # print event.key(), format(event.key(), '08x')
            if event.key() == Qt.Key_F4:
                myquit()
            if event.key() == Qt.Key_F2:
                if time.time() > lastkeytime:
                    if weatherplayer is None:
                        weatherplayer = Popen(
                            ["mpg123", "-q", Config.noaastream])
                    else:
                        weatherplayer.kill()
                        weatherplayer = None
                lastkeytime = time.time() + 2
            if event.key() == Qt.Key_Space:
                nextframe(1)
            if event.key() == Qt.Key_Left:
                nextframe(-1)
            if event.key() == Qt.Key_Right:
                nextframe(1)
            if event.key() == Qt.Key_F6:  # Previous Image
                objimage1.prev_next(-1)
            if event.key() == Qt.Key_F7:  # Next Image
                objimage1.prev_next(1)
            if event.key() == Qt.Key_F8:  # Play/Pause
                objimage1.play_pause()
            if event.key() == Qt.Key_F9:  # Foreground Toggle
                if foreGround.isVisible():
                    foreGround.hide()
                else:
                    foreGround.show()

    def mousePressEvent(self, event):
        if type(event) == QtGui.QMouseEvent:
            nextframe(1)

class MqttClient(QtCore.QObject):
    Disconnected = 0
    Connecting = 1
    Connected = 2

    MQTT_3_1 = mqtt.MQTTv31
    MQTT_3_1_1 = mqtt.MQTTv311
    connected = QtCore.pyqtSignal()
    disconnected = QtCore.pyqtSignal()

    stateChanged = QtCore.pyqtSignal(int)
    hostnameChanged = QtCore.pyqtSignal(str)
    portChanged = QtCore.pyqtSignal(int)
    keepAliveChanged = QtCore.pyqtSignal(int)
    cleanSessionChanged = QtCore.pyqtSignal(bool)
    protocolVersionChanged = QtCore.pyqtSignal(int)

    messageSignal = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super(MqttClient, self).__init__(parent)

        self.m_hostname = "localhost"
        self.m_port = 1883
        self.m_keepAlive = 60
        self.m_cleanSession = True
        self.m_protocolVersion = MqttClient.MQTT_3_1

        self.m_state = MqttClient.Disconnected

        self.m_client =  mqtt.Client(clean_session=self.m_cleanSession,
            protocol=self.protocolVersion)

        self.m_client.on_connect = self.on_connect
        self.m_client.on_message = self.on_message
        self.m_client.on_disconnect = self.on_disconnect
    
    @QtCore.pyqtProperty(int, notify=stateChanged)
    def state(self):
        return self.m_state

    @state.setter
    def state(self, state):
        if self.m_state == state: return
        self.m_state = state
        self.stateChanged.emit(state) 

    @QtCore.pyqtProperty(str, notify=hostnameChanged)
    def hostname(self):
        return self.m_hostname

    @hostname.setter
    def hostname(self, hostname):
        if self.m_hostname == hostname: return
        self.m_hostname = hostname
        self.hostnameChanged.emit(hostname)

    @QtCore.pyqtProperty(int, notify=portChanged)
    def port(self):
        return self.m_port

    @port.setter
    def port(self, port):
        if self.m_port == port: return
        self.m_port = port
        self.portChanged.emit(port)

    @QtCore.pyqtProperty(int, notify=keepAliveChanged)
    def keepAlive(self):
        return self.m_keepAlive

    @keepAlive.setter
    def keepAlive(self, keepAlive):
        if self.m_keepAlive == keepAlive: return
        self.m_keepAlive = keepAlive
        self.keepAliveChanged.emit(keepAlive)

    @QtCore.pyqtProperty(bool, notify=cleanSessionChanged)
    def cleanSession(self):
        return self.m_cleanSession

    @cleanSession.setter
    def cleanSession(self, cleanSession):
        if self.m_cleanSession == cleanSession: return
        self.m_cleanSession = cleanSession
        self.cleanSessionChanged.emit(cleanSession)

    @QtCore.pyqtProperty(int, notify=protocolVersionChanged)
    def protocolVersion(self):
        return self.m_protocolVersion

    @protocolVersion.setter
    def protocolVersion(self, protocolVersion):
        if self.m_protocolVersion == protocolVersion: return
        if protocolVersion in (MqttClient.MQTT_3_1, MQTT_3_1_1):
            self.m_protocolVersion = protocolVersion
            self.protocolVersionChanged.emit(protocolVersion)

    #################################################################
    @QtCore.pyqtSlot()
    def connectToHost(self):
        if self.m_hostname:
            self.m_client.connect(self.m_hostname, 
                port=self.port, 
                keepalive=self.keepAlive)

            self.state = MqttClient.Connecting
            self.m_client.loop_start()

    @QtCore.pyqtSlot()
    def disconnectFromHost(self):
        self.m_client.disconnect()

    def subscribe(self, path):
        if self.state == MqttClient.Connected:
            self.m_client.subscribe(path)

    #################################################################
    # callbacks
    def on_message(self, mqttc, obj, msg):
        topic = msg.topic
        mstr = msg.payload.decode("ascii")
        idx = mstr.index("}")
        mstr = mstr[:idx] + ",\"topic\":\"" + topic + "\"" + mstr[idx:]
        # print("on message() : ", mstr)
        # print("on_message", mstr, obj, mqttc)
        self.messageSignal.emit(mstr)

    def on_connect(self, *args):
        # print("on_connect", args)
        self.state = MqttClient.Connected
        self.connected.emit()

    def on_disconnect(self, *args):
        # print("on_disconnect", args)
        self.state = MqttClient.Disconnected
        self.disconnected.emit()

configname = 'Config'

if len(sys.argv) > 1:
    configname = sys.argv[1]

if not os.path.isfile(configname + ".py"):
    print ("Config file not found %s" % configname + ".py")
    exit(1)

Config = __import__(configname)

# define default values for new/optional config variables.

try:
    Config.location
except AttributeError:
    Config.location = Config.wulocation

try:
    Config.metric
except AttributeError:
    Config.metric = 0

try:
    Config.weather_refresh
except AttributeError:
    Config.weather_refresh = 30   # minutes

try:
    Config.radar_refresh
except AttributeError:
    Config.radar_refresh = 10    # minutes

try:
    Config.fontattr
except AttributeError:
    Config.fontattr = ''

try:
    Config.dimcolor
except AttributeError:
    Config.dimcolor = QColor('#000000')
    Config.dimcolor.setAlpha(0)

try:
    Config.DateLocale
except AttributeError:
    Config.DateLocale = ''

try:
    Config.wind_degrees
except AttributeError:
    Config.wind_degrees = 0

try:
    Config.digital
except AttributeError:
    Config.digital = 0

try:
    Config.Language
except AttributeError:
    try:
        Config.Language = Config.wuLanguage
    except AttributeError:
        Config.Language = "en"

try:
    Config.fontmult
except AttributeError:
    Config.fontmult = 1.0

try:
    Config.LPressure
except AttributeError:
    Config.LPressure = "Pressure "
    Config.LHumidity = "Humidity "
    Config.LWind = "Wind "
    Config.Lgusting = " gusting "
    Config.LFeelslike = "Feels like "
    Config.LPrecip1hr = " Precip 1hr:"
    Config.LToday = "Today: "
    Config.LSunRise = "Sun Rise:"
    Config.LSet = " Set: "
    Config.LMoonPhase = " Moon Phase:"
    Config.LInsideTemp = "Inside Temp "
    Config.LRain = " Rain: "
    Config.LSnow = " Snow: "

try:
    Config.Lmoon1
    Config.Lmoon2
    Config.Lmoon3
    Config.Lmoon4
    Config.Lmoon5
    Config.Lmoon6
    Config.Lmoon7
    Config.Lmoon8
except AttributeError:
    Config.Lmoon1 = 'New Moon'
    Config.Lmoon2 = 'Waxing Crescent'
    Config.Lmoon3 = 'First Quarter'
    Config.Lmoon4 = 'Waxing Gibbous'
    Config.Lmoon5 = 'Full Moon'
    Config.Lmoon6 = 'Waning Gibbous'
    Config.Lmoon7 = 'Third Quarter'
    Config.Lmoon8 = 'Waning Crecent'

try:
    Config.digitalformat2
except AttributeError:
    Config.digitalformat2 = "{0:%H:%M:%S}"

try:
    Config.useslideshow
except AttributeError:
    Config.useslideshow = 0


#
# Check if Mapbox API key is set, and use mapbox if so
try:
    if ApiKeys.mbapi[:3].lower() == "pk.":
        Config.usemapbox = 1
except AttributeError:
    pass


try:
    if Config.METAR != '':
        from metar import Metar
except AttributeError:
    pass

lastmin = -1
lastday = -1
pdy = ""
lasttimestr = ""
weatherplayer = None
lastkeytime = 0
lastapiget = time.time()

app = QtWidgets.QApplication(sys.argv)
desktop = app.desktop()
rec = desktop.screenGeometry()
height = rec.height()
width = rec.width()

signal.signal(signal.SIGINT, myquit)

w = myMain()
w.setWindowTitle(os.path.basename(__file__))

w.setStyleSheet("QWidget { background-color: black;}")

# connectMqtt()
global client
client = MqttClient()
client.stateChanged.connect(on_stateChanged)
client.messageSignal.connect(on_messageSignal)

client.connectToHost()

# fullbgpixmap = QtGui.QPixmap(Config.background)
# fullbgrect = fullbgpixmap.rect()
# xscale = float(width)/fullbgpixmap.width()
# yscale = float(height)/fullbgpixmap.height()

xscale = float(width) / 1440.0
yscale = float(height) / 900.0

frames = []
framep = 0

frame1 = QtWidgets.QFrame(w)
frame1.setObjectName("frame1")
frame1.setGeometry(0, 0, width, height)
frame1.setStyleSheet("#frame1 { background-color: black; border-image: url(" +
                     Config.background + ") 0 0 0 0 stretch stretch;}")
frames.append(frame1)

if Config.useslideshow:
    imgRect = QtCore.QRect(0, 0, width, height)
    objimage1 = SS(frame1, imgRect, "image1")

frame2 = QtWidgets.QFrame(w)
frame2.setObjectName("frame2")
frame2.setGeometry(0, 0, width, height)
frame2.setStyleSheet("#frame2 { background-color: blue; border-image: url(" +
                     Config.background + ") 0 0 0 0 stretch stretch;}")
frame2.setVisible(False)
frames.append(frame2)

# frame3 = QtGui.QFrame(w)
# frame3.setObjectName("frame3")
# frame3.setGeometry(0,0,width,height)
# frame3.setStyleSheet("#frame3 { background-color: blue; border-image:
#       url("+Config.background+") 0 0 0 0 stretch stretch;}")
# frame3.setVisible(False)
# frames.append(frame3)

foreGround = QtWidgets.QFrame(frame1)
foreGround.setObjectName("foreGround")
foreGround.setStyleSheet("#foreGround { background-color: transparent; }")
foreGround.setGeometry(0, 0, width, height)

squares1 = QtWidgets.QFrame(foreGround)
squares1.setObjectName("squares1")
squares1.setGeometry(0, height - yscale * 600, xscale * 340, yscale * 600)
squares1.setStyleSheet(
    "#squares1 { background-color: transparent; border-image: url(" +
    Config.squares1 +
    ") 0 0 0 0 stretch stretch;}")

squares2 = QtWidgets.QFrame(foreGround)
squares2.setObjectName("squares2")
squares2.setGeometry(width - xscale * 340, 0, xscale * 340, yscale * 900)
squares2.setStyleSheet(
    "#squares2 { background-color: transparent; border-image: url(" +
    Config.squares2 +
    ") 0 0 0 0 stretch stretch;}")

if not Config.digital:
    clockface = QtWidgets.QFrame(foreGround)
    clockface.setObjectName("clockface")
    clockrect = QtCore.QRect(
        width / 2 - height * .325,
        height * .45 - height * .4,
        height * .65,
        height * .65)
    clockface.setGeometry(clockrect)
    clockface.setStyleSheet(
        "#clockface { background-color: transparent; border-image: url(" +
        Config.clockface +
        ") 0 0 0 0 stretch stretch;}")

    hourhand = QtWidgets.QLabel(foreGround)
    hourhand.setObjectName("hourhand")
    hourhand.setStyleSheet("#hourhand { background-color: transparent; }")

    minhand = QtWidgets.QLabel(foreGround)
    minhand.setObjectName("minhand")
    minhand.setStyleSheet("#minhand { background-color: transparent; }")

    sechand = QtWidgets.QLabel(foreGround)
    sechand.setObjectName("sechand")
    sechand.setStyleSheet("#sechand { background-color: transparent; }")

    hourpixmap = QtGui.QPixmap(Config.hourhand)
    hourpixmap2 = QtGui.QPixmap(Config.hourhand)
    minpixmap = QtGui.QPixmap(Config.minhand)
    minpixmap2 = QtGui.QPixmap(Config.minhand)
    secpixmap = QtGui.QPixmap(Config.sechand)
    secpixmap2 = QtGui.QPixmap(Config.sechand)
else:
    clockface = QtWidgets.QLabel(foreGround)
    clockface.setObjectName("clockface")
    clockrect = QtCore.QRect(
        width / 2 - height * .325,
        height * .45 - height * .4,
        height * .65,
        height * .65)
    clockface.setGeometry(clockrect)
    dcolor = QColor(Config.digitalcolor).darker(0).name()
    lcolor = QColor(Config.digitalcolor).lighter(120).name()
    clockface.setStyleSheet(
        "#clockface { background-color: transparent; font-family:sans-serif;" +
        " font-weight: light; color: " +
        lcolor +
        "; background-color: transparent; font-size: " +
        str(int(Config.digitalsize * xscale)) +
        "px; " +
        Config.fontattr +
        "}")
    clockface.setAlignment(Qt.AlignCenter)
    clockface.setGeometry(clockrect)
    glow = QtWidgets.QGraphicsDropShadowEffect()
    glow.setOffset(0)
    glow.setBlurRadius(50)
    glow.setColor(QColor(dcolor))
    clockface.setGraphicsEffect(glow)


radar1rect = QtCore.QRect(3 * xscale, 344 * yscale, 300 * xscale, 275 * yscale)
objradar1 = Radar(foreGround, Config.radar1, radar1rect, "radar1")

radar2rect = QtCore.QRect(3 * xscale, 622 * yscale, 300 * xscale, 275 * yscale)
objradar2 = Radar(foreGround, Config.radar2, radar2rect, "radar2")

radar3rect = QtCore.QRect(13 * xscale, 50 * yscale, 700 * xscale, 700 * yscale)
objradar3 = Radar(frame2, Config.radar3, radar3rect, "radar3")

radar4rect = QtCore.QRect(726 * xscale, 50 * yscale,
                          700 * xscale, 700 * yscale)
objradar4 = Radar(frame2, Config.radar4, radar4rect, "radar4")


datex = QtWidgets.QLabel(foreGround)
datex.setObjectName("datex")
datex.setStyleSheet("#datex { font-family:sans-serif; color: " +
                    Config.textcolor +
                    "; background-color: transparent; font-size: " +
                    str(int(50 * xscale * Config.fontmult)) +
                    "px; " +
                    Config.fontattr +
                    "}")
datex.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
datex.setGeometry(0, 0, width, 100 * yscale)

datex2 = QtWidgets.QLabel(frame2)
datex2.setObjectName("datex2")
datex2.setStyleSheet("#datex2 { font-family:sans-serif; color: " +
                     Config.textcolor +
                     "; background-color: transparent; font-size: " +
                     str(int(50 * xscale * Config.fontmult)) + "px; " +
                     Config.fontattr +
                     "}")
datex2.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
datex2.setGeometry(800 * xscale, 780 * yscale, 640 * xscale, 100)
datey2 = QtWidgets.QLabel(frame2)
datey2.setObjectName("datey2")
datey2.setStyleSheet("#datey2 { font-family:sans-serif; color: " +
                     Config.textcolor +
                     "; background-color: transparent; font-size: " +
                     str(int(50 * xscale * Config.fontmult)) +
                     "px; " +
                     Config.fontattr +
                     "}")
datey2.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
datey2.setGeometry(800 * xscale, 840 * yscale, 640 * xscale, 100)

attribution = QtWidgets.QLabel(foreGround)
attribution.setObjectName("attribution")
attribution.setStyleSheet("#attribution { " +
                          " background-color: transparent; color: " +
                          Config.textcolor +
                          "; font-size: " +
                          str(int(12 * xscale)) +
                          "px; " +
                          Config.fontattr +
                          "}")
attribution.setAlignment(Qt.AlignTop)
attribution.setGeometry(6 * xscale, 3 * yscale, 100 * xscale, 100)

ypos = -25
wxicon = QtWidgets.QLabel(foreGround)
wxicon.setObjectName("wxicon")
wxicon.setStyleSheet("#wxicon { background-color: transparent; }")
wxicon.setGeometry(75 * xscale, ypos * yscale, 150 * xscale, 150 * yscale)

attribution2 = QtWidgets.QLabel(frame2)
attribution2.setObjectName("attribution2")
attribution2.setStyleSheet("#attribution2 { " +
                           "background-color: transparent; color: " +
                           Config.textcolor +
                           "; font-size: " +
                           str(int(12 * xscale * Config.fontmult)) +
                           "px; " +
                           Config.fontattr +
                           "}")
attribution2.setAlignment(Qt.AlignTop)
attribution2.setGeometry(6 * xscale, 880 * yscale, 100 * xscale, 100)

wxicon2 = QtWidgets.QLabel(frame2)
wxicon2.setObjectName("wxicon2")
wxicon2.setStyleSheet("#wxicon2 { background-color: transparent; }")
wxicon2.setGeometry(0 * xscale, 750 * yscale, 150 * xscale, 150 * yscale)

ypos += 130
wxdesc = QtWidgets.QLabel(foreGround)
wxdesc.setObjectName("wxdesc")
wxdesc.setStyleSheet("#wxdesc { background-color: transparent; color: " +
                     Config.textcolor +
                     "; font-size: " +
                     str(int(30 * xscale)) +
                     "px; " +
                     Config.fontattr +
                     "}")
wxdesc.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
wxdesc.setGeometry(3 * xscale, ypos * yscale, 300 * xscale, 100)

wxdesc2 = QtWidgets.QLabel(frame2)
wxdesc2.setObjectName("wxdesc2")
wxdesc2.setStyleSheet("#wxdesc2 { background-color: transparent; color: " +
                      Config.textcolor +
                      "; font-size: " +
                      str(int(50 * xscale * Config.fontmult)) +
                      "px; " +
                      Config.fontattr +
                      "}")
wxdesc2.setAlignment(Qt.AlignLeft | Qt.AlignTop)
wxdesc2.setGeometry(400 * xscale, 800 * yscale, 400 * xscale, 100)

ypos += 25
temper = QtWidgets.QLabel(foreGround)
temper.setObjectName("temper")
temper.setStyleSheet("#temper { background-color: transparent; color: " +
                     Config.textcolor +
                     "; font-size: " +
                     str(int(70 * xscale * Config.fontmult)) +
                     "px; " +
                     Config.fontattr +
                     "}")
temper.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
temper.setGeometry(3 * xscale, ypos * yscale,
                   300 * xscale, 100 * yscale)

temper2 = QtWidgets.QLabel(frame2)
temper2.setObjectName("temper2")
temper2.setStyleSheet("#temper2 { background-color: transparent; color: " +
                      Config.textcolor +
                      "; font-size: " +
                      str(int(70 * xscale * Config.fontmult)) +
                      "px; " +
                      Config.fontattr +
                      "}")
temper2.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
temper2.setGeometry(125 * xscale, 780 * yscale, 300 * xscale, 100)

ypos += 80
press = QtWidgets.QLabel(foreGround)
press.setObjectName("press")
press.setStyleSheet("#press { background-color: transparent; color: " +
                    Config.textcolor +
                    "; font-size: " +
                    str(int(25 * xscale * Config.fontmult)) +
                    "px; " +
                    Config.fontattr +
                    "}")
press.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
press.setGeometry(3 * xscale, ypos * yscale, 300 * xscale, 100)

ypos += 30
humidity = QtWidgets.QLabel(foreGround)
humidity.setObjectName("humidity")
humidity.setStyleSheet("#humidity { background-color: transparent; color: " +
                       Config.textcolor +
                       "; font-size: " +
                       str(int(25 * xscale * Config.fontmult)) +
                       "px; " +
                       Config.fontattr +
                       "}")
humidity.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
humidity.setGeometry(3 * xscale, ypos * yscale, 300 * xscale, 100)

ypos += 30
wind = QtWidgets.QLabel(foreGround)
wind.setObjectName("wind")
wind.setStyleSheet("#wind { background-color: transparent; color: " +
                   Config.textcolor +
                   "; font-size: " +
                   str(int(20 * xscale * Config.fontmult)) +
                   "px; " +
                   Config.fontattr +
                   "}")
wind.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
wind.setGeometry(3 * xscale, ypos * yscale, 300 * xscale, 100)

ypos += 20
wind2 = QtWidgets.QLabel(foreGround)
wind2.setObjectName("wind2")
wind2.setStyleSheet("#wind2 { background-color: transparent; color: " +
                    Config.textcolor +
                    "; font-size: " +
                    str(int(20 * xscale * Config.fontmult)) +
                    "px; " +
                    Config.fontattr +
                    "}")
wind2.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
wind2.setGeometry(3 * xscale, ypos * yscale, 300 * xscale, 100)

ypos += 20
wdate = QtWidgets.QLabel(foreGround)
wdate.setObjectName("wdate")
wdate.setStyleSheet("#wdate { background-color: transparent; color: " +
                    Config.textcolor +
                    "; font-size: " +
                    str(int(15 * xscale * Config.fontmult)) +
                    "px; " +
                    Config.fontattr +
                    "}")
wdate.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
wdate.setGeometry(3 * xscale, ypos * yscale, 300 * xscale, 100)

bottom = QtWidgets.QLabel(foreGround)
bottom.setObjectName("bottom")
bottom.setStyleSheet("#bottom { font-family:sans-serif; color: " +
                     Config.textcolor +
                     "; background-color: transparent; font-size: " +
                     str(int(30 * xscale * Config.fontmult)) +
                     "px; " +
                     Config.fontattr +
                     "}")
bottom.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
bottom.setGeometry(0, height - 50 * yscale, width, 50 * yscale)

temp = QtWidgets.QLabel(foreGround)
temp.setObjectName("temp")
temp.setStyleSheet("#temp { font-family:sans-serif; color: " +
                   Config.textcolor +
                   "; background-color: transparent; font-size: " +
                   str(int(30 * xscale * Config.fontmult)) +
                   "px; " +
                   Config.fontattr +
                   "}")
temp.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
temp.setGeometry(0, height - 100 * yscale, width, 50 * yscale)


forecast = []
for i in range(0, 9):
    lab = QtWidgets.QLabel(foreGround)
    lab.setObjectName("forecast" + str(i))
    lab.setStyleSheet("QWidget { background-color: transparent; color: " +
                      Config.textcolor +
                      "; font-size: " +
                      str(int(20 * xscale * Config.fontmult)) +
                      "px; " +
                      Config.fontattr +
                      "}")
    lab.setGeometry(1137 * xscale, i * 100 * yscale,
                    300 * xscale, 100 * yscale)

    icon = QtWidgets.QLabel(lab)
    icon.setStyleSheet("#icon { background-color: transparent; }")
    icon.setGeometry(0, 0, 100 * xscale, 100 * yscale)
    icon.setObjectName("icon")

    wx = QtWidgets.QLabel(lab)
    wx.setStyleSheet("#wx { background-color: transparent; }")
    wx.setGeometry(100 * xscale, 5 * yscale, 200 * xscale, 120 * yscale)
    wx.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    wx.setWordWrap(True)
    wx.setObjectName("wx")

    day = QtWidgets.QLabel(lab)
    day.setStyleSheet("#day { background-color: transparent; }")
    day.setGeometry(100 * xscale, 75 * yscale, 200 * xscale, 25 * yscale)
    day.setAlignment(Qt.AlignRight | Qt.AlignBottom)
    day.setObjectName("day")

    forecast.append(lab)

sensor1 = QtWidgets.QLabel(foreGround)
sensor1.setObjectName("sensor1")
sensor1.setStyleSheet("#sensor1 { font-family:sans-serif; color: " +
                     Config.textcolor +
                     "; background-color: transparent; font-size: " +
                     str(int(30 * xscale * Config.fontmult)) +
                     "px; " +
                     Config.fontattr +
                     "}")
sensor1.setGeometry(width / 2 - 400 * xscale , height - 280 * yscale, 400 * xscale, 200 * yscale)
sensor1.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

sensor1Battery = QtWidgets.QLabel(foreGround)
sensor1Battery.setStyleSheet("#sensor1Battery { background-color: transparent; }")
sensor1Battery.setObjectName("sensor1Battery")
sensor1Battery.setGeometry(width / 2 - 135 * xscale , height - 250 * yscale, 40 * xscale, 40 * yscale)

sensor1Date = QtWidgets.QLabel(foreGround)
sensor1Date.setObjectName("sensor1Date")
sensor1Date.setStyleSheet("#sensor1Date { background-color: transparent; color: " +
                    Config.textcolor +
                    "; font-size: " +
                    str(int(15 * xscale * Config.fontmult)) +
                    "px; " +
                    Config.fontattr +
                    "}")
sensor1Date.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
sensor1Date.setGeometry(width / 2 - 400 * xscale , height - 140 * yscale, 400 * xscale, 20 * yscale)

sensor2 = QtWidgets.QLabel(foreGround)
sensor2.setObjectName("sensor2")
sensor2.setStyleSheet("#sensor2 { font-family:sans-serif; color: " +
                     Config.textcolor +
                     "; background-color: transparent; font-size: " +
                     str(int(30 * xscale * Config.fontmult)) +
                     "px; " +
                     Config.fontattr +
                     "}")
sensor2.setGeometry(width / 2 , height - 280 * yscale, 400 * xscale, 200 * yscale)
sensor2.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

sensor2Battery = QtWidgets.QLabel(foreGround)
sensor2Battery.setStyleSheet("#sensor2Battery { background-color: transparent; }")
sensor2Battery.setObjectName("sensor2Battery")
sensor2Battery.setGeometry(width / 2 + 90 * xscale , height - 250 * yscale, 40 * xscale, 40 * yscale)

sensor2Date = QtWidgets.QLabel(foreGround)
sensor2Date.setObjectName("sensor2Date")
sensor2Date.setStyleSheet("#sensor2Date { background-color: transparent; color: " +
                    Config.textcolor +
                    "; font-size: " +
                    str(int(15 * xscale * Config.fontmult)) +
                    "px; " +
                    Config.fontattr +
                    "}")
sensor2Date.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
sensor2Date.setGeometry(width / 2 , height - 140 * yscale, 400 * xscale, 20 * yscale)

manager = QtNetwork.QNetworkAccessManager()

# proxy = QNetworkProxy()
# proxy.setType(QNetworkProxy.HttpProxy)
# proxy.setHostName("localhost")
# proxy.setPort(8888)
# QNetworkProxy.setApplicationProxy(proxy)

stimer = QtCore.QTimer()
stimer.singleShot(10, qtstart)

# print radarurl(Config.radar1,radar1rect)

w.show()
w.showFullScreen()

sys.exit(app.exec_())

# -*- coding: utf-8 -*-
from GoogleMercatorProjection import LatLng
from PyQt4.QtGui import QColor

# LOCATION(S)
# Further radar configuration (zoom, marker location) can be
# completed under the RADAR section
primary_coordinates = 48.58162487353572, 7.7504504491828845  # Change to your Lat/Lon

location = LatLng(primary_coordinates[0], primary_coordinates[1])
primary_location = LatLng(primary_coordinates[0], primary_coordinates[1])
noaastream = ''
background = 'images/berlin-at-night-mrwallpaper.jpg'
squares1 = 'images/squares1-kevin.png'
squares2 = 'images/squares2-kevin.png'
icons = 'icons-lightblue'
textcolor = '#bef'
clockface = 'images/clockface3.png'
hourhand = 'images/hourhand.png'
minhand = 'images/minhand.png'
sechand = 'images/sechand.png'


digital = 0             # 1 = Digital Clock, 0 = Analog Clock

# Goes with light blue config (like the default one)
digitalcolor = "#50CBEB"
digitalformat = "{0:%I:%M\n%S %p}"  # The format of the time
digitalsize = 200

metric = 1  # 0 = English, 1 = Metric
radar_refresh = 10      # minutes
weather_refresh = 30    # minutes
# Wind in degrees instead of cardinal 0 = cardinal, 1 = degrees
wind_degrees = 0


# gives all text additional attributes using QT style notation
# example: fontattr = 'font-weight: bold; '
fontattr = ''

# These are to dim the radar images, if needed.
# see and try Config-Example-Bedside.py
dimcolor = QColor('#000000')
dimcolor.setAlpha(0)

use_metar = 0   # set use_metar to 1 if you live near an airport
                # if set to 0, PiWeatherStation will use openweathermap data to get the actual weather conditions
METAR="LFST"  # Strasbourg-Entzheim Airport (SXB)

# Language Specific wording
# DarkSky Language code
#  (https://darksky.net/dev/docs under lang=)
Language = "FR"

# The Python Locale for date/time (locale.setlocale)
#  '' for default Pi Setting
# Locales must be installed in your Pi.. to check what is installed
# locale -a
# to install locales
# sudo dpkg-reconfigure locales
DateLocale = 'fr_FR.utf-8'

# Language specific wording
# thanks to colonia27 for the language work
LPressure = "Pression "
LHumidity = u"Humidité "
LWind = "Vent "
Lgusting = u" Raf "
LFeelslike = u"Ressenti "
LPrecip1hr = " Pluie 1h:"
LToday = "Aujd: "
LSunRise = "Soleil:"
LSet = u" à "
LMoonPhase = " Phase lune:"
LInsideTemp = "Temp int: "
LRain = "Pluie: "
LSnow = "Neige: "
Lmoon1 = 'Nouvelle lune'
Lmoon2 = 'Premier quart. croissant'
Lmoon3 = 'Demi-lune croissant'
Lmoon4 = 'Dernier quart. croissant'
Lmoon5 = 'Pleine lune'
Lmoon6 = u'Dernier quart. décr.'
Lmoon7 = u'Demi-lune décr.'
Lmoon8 = u'Premier quart. décr.'
# Language Specific terms for weather conditions
Lcc_code_map = {
            "freezing_rain_heavy": u"Pluie forte verglaçante",
            "freezing_rain": u"Pluie verglaçante",
            "freezing_rain_light": u"Pluie légère verglaçante",
            "freezing_drizzle": u"Bruine verglaçante",
            "ice_pellets_heavy": u"Grêle forte",
            "ice_pellets": u"Grêle",
            "ice_pellets_light": u"Grêle légère",
            "snow_heavy": "Forte neige",
            "snow": "Neige",
            "snow_light": u"Neige légère",
            "flurries": "Rafales",
            "tstorm": "Orage",
            "rain_heavy": "Pluie forte",
            "rain": "Pluie",
            "rain_light": u"Pluie légère",
            "drizzle": "Bruine",
            "fog_light": u"Léger brouillard",
            "fog": "Brouillard",
            "cloudy": "Nuageux",
            "mostly_cloudy": u"Très nuageux",
            "partly_cloudy": u"Plutôt nuageux",
            "mostly_clear": "Eclaircies",
            "clear": u"Dégagé"
}

# RADAR
# By default, primary_location entered will be the
#  center and marker of all radar images.
# To update centers/markers, change radar sections
# below the desired lat/lon as:
# -FROM-
# primary_location,
# -TO-
# LatLng(44.9764016,-93.2486732),
radar1 = {
    'center': primary_location,  # the center of your radar block
    'zoom': 7,  # this is a google maps zoom factor, bigger = smaller area
    'markers': (   # google maps markers can be overlayed
        {
            'location': primary_location,
            'color': 'red',
            'size': 'small',
        },          # dangling comma is on purpose.
    )
}


radar2 = {
    'center': primary_location,
    'zoom': 11,
    'markers': (
        {
            'location': primary_location,
            'color': 'red',
            'size': 'small',
        },
    )
}


radar3 = {
    'center': primary_location,
    'zoom': 7,
    'markers': (
        {
            'location': primary_location,
            'color': 'red',
            'size': 'small',
        },
    )
}

radar4 = {
    'center': primary_location,
    'zoom': 11,
    'markers': (
        {
            'location': primary_location,
            'color': 'red',
            'size': 'small',
        },
    )
}

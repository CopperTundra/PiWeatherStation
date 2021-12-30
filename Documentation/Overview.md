# Overview of the PiWeatherStation

## Introduction

The PiWeatherStation is a weather station which includes weather forecast, rain radar map display, an analog clock, and inside temperature. It's originally a fork from the code from [n0bel](https://github.com/n0bel/PiClock/) (cheers 🍻), but many parts have been rewritten to suits the requirements of the weather station. 

Hardware is simply composed of a Raspberry Pi and his official 7" touchscreen display, two Xiaomi Aqara temperature sensors, and a compatible Zigbee adapter.
For more informations on the hardware, see https://github.com/CopperTundra/PiWeatherStation/blob/master/Documentation/Hardware.md

The weather data is taken out from [OpenWeatherMap.org](https://openweathermap.org/), the maps from [Mapbox](https://mapbox.com/).
**You must get API Keys from OpenWeatherMap.org and Mapbox in order to make this work.** It's free for low usage such as this application.

The real-time weather comes from the international weather reports from the nearest airport (METAR). These reports are issued one or two times an hour from every airfield in the world and brings a lot of weather data for aircrafts, this is free and publicly accessible for everyone.

## List of materials

So what do you need to build a PiWeatherStation?

  * A Raspberry Pi 3 Model B or newer
  * An official 7" touchscreen display (other touchscreens may also work but will maybe not be as good integrated in the case)
  * A nice case to protect both the touchscreen and the Pi
  * One or two Xiaomi Aqara Zigbee temperature sensors
  * An USB Zigbee Adapter
  * A good power supply. I highly recommend to use the official one, I personally experienced voltage unstability with other models (even though they were designed to support more than 3A)
  * A USB or bluetooth keyboard to initially setup the board
  * Wifi (or Ethernet) internet connection

## What else?

The Hardware guide ( https://github.com/CopperTundra/PiWeatherStation/blob/master/Documentation/Hardware.md )
gives more details about the material needed and how to assemble everything.

The Install guide ( https://github.com/CopperTundra/PiWeatherStation/blob/master/Documentation/Install.md )
steps through all the things that you need to do from a stock Raspbian image to make the PiWeatherStation work.

## History

This project is inspired from a Clock project, but I've adapted it to my needs.
The base project was based on a HDMI 19" screen and was using Python 2.7, Qt4, and DarkSky.
I've updated it to make it work with the touchscreen display, with OpenWeatherMap data and with the latest Python 3.X and Qt5.
I also decided to add some temperature sensors to the weather station, in order to display some indoor informations as well. Xiaomi Aqara were my choice because they are compatible with Zigbee2MQTT, which allow us to process the data out from the sensors without the need of a proprietary gateway.

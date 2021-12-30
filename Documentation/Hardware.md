# PiWeatherStation Hardware Guide

## Introduction

This guide specify and explains how to connect the different parts needed in order to build your own PiWeatherStation.

## Raspberry Pi Models

All models from Raspberry Pi 1 Model A supports officially the touchscreen. However, since the first models doesn't have mouting holes, I advice to use at least a Raspberry Pi Model 2 A or a later version.

Don't forget to use a good power supply for this project. I highly recommend to use the official one, I personally experienced voltage unstability with other models (even though they were designed to support more than 3A).

## Touchscreen display and case

I recommend the official touchscreen display from Raspberry, because it fits well with the official cases.
I'm personnaly using this [case](https://thepihut.com/collections/oneninedesign/products/raspberry-pi-7-touchscreen-display-case-clear) with my Raspberry Pi 3B, but you may find the proper case for your Pi model (or build your own).

## Zigbee sensors and Zigbee adapter

I'm using Xiaomi Aqara temperature sensors for this project. These are Zigbee sensors and capable of measuring pressure, temperature and humidity of an indoor location. However it's also possible to use other sensors, as long as they are compatible with Zigbee2MQTT. You can check the complete list of compatible devices here :
https://www.zigbee2mqtt.io/supported-devices/

In order to use these sensors with our Raspberry Pi, we need an USB adapter.
A Zigbee Adapter is the interface between the Computer (or Server) where you run Zigbee2MQTT and the Zigbee radio communication. Zigbee2MQTT supports a variety of adapters with different kind of connections like USB, GPIO or remote via WIFI or Ethernet. Complete list of compatible adapters :
https://www.zigbee2mqtt.io/guide/adapters/#recommended

I'm using Slaesh's CC2652RB stick, they are delivered already flashed and ready to work.

## Assembly
If you are not familiar with Raspberry Pi, I recommend reading the documentation on their website first.

Start with a fresh install of Raspbian (other distributions may as well work, but everything here is written for Raspbian), stick the SD card in the port and connect the touchscreen display to your Raspberry Pi using the [documentation](https://www.raspberrypi.com/documentation/accessories/display.html).

Insert the Zigbee adapter in one of the USB port and you can proceed with the software documentation :
https://github.com/CopperTundra/PiWeatherStation/master/Documentation/Install.md


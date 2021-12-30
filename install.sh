#!/bin/bash
# Install script for the PiWeatherStation
# This script needs superuser privileges in order to install all the necessary software on your Pi
#

# Installing required packages
apt-get update -y && apt-get upgrade -y
apt-get install -y git make g++ gcc python-dev unclutter mosquitto mosquitto-clients nodejs 
pip install tzlocal
pip install python-dateutil
pip install PyQt5
git clone https://github.com/python-metar/python-metar.git
cd python-metar
python setup.py install
cd ..
rm -rf python-metar

# Start Mosquitto broker along with the system
sudo systemctl enable mosquitto.service

# Install Zigbee2MQTT
# Setup Node.js repository
curl -sL https://deb.nodesource.com/setup_14.x | sudo -E bash -

# NOTE 1: If you see the message below please follow: https://gist.github.com/Koenkk/11fe6d4845f5275a2a8791d04ea223cb.
# ## You appear to be running on ARMv6 hardware. Unfortunately this is not currently supported by the NodeSource Linux distributions. Please use the 'linux-armv6l' binary tarballs available directly from nodejs.org for Node.js 4 and later.
# IMPORTANT: In this case instead of the apt-get install mentioned below; do: sudo apt-get install -y git make g++ gcc

# NOTE 2: On x86, Node.js 10 may not work. It's recommended to install an unofficial Node.js 14 build which can be found here: https://unofficial-builds.nodejs.org/download/release/ (e.g. v14.16.0)

# Clone Zigbee2MQTT repository
git clone https://github.com/Koenkk/zigbee2mqtt.git /opt/zigbee2mqtt
chown -R pi:pi /opt/zigbee2mqtt

# Install dependencies (as user "pi")
cd /opt/zigbee2mqtt
npm ci
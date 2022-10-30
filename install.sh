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

#!/bin/bash
# Install script for the PiWeatherStation
# This script needs superuser privileges in order to install all the necessary software on your Pi
#

# Installing required packages
echo     "#####################################################################"
echo     "# Installing necessary parts for PiWeatherStation to run...         #"
echo     "#####################################################################"
echo -ne "# Updating the system...                                    (0%)\r"
apt-get update -y && apt-get upgrade -y
echo -ne "# Installing necessary packages...   ##                    (10%)\r"
apt-get install -y git make g++ gcc python-dev unclutter mosquitto mosquitto-clients nodejs unattended-upgrades
echo -ne "# Installing python dependancies...  ######                (30%)\r"
pip install tzlocal
pip install python-dateutil
pip install PyQt5
echo -ne "# Installing METAR libraries...      ########              (40%)\r"
git clone https://github.com/python-metar/python-metar.git
cd python-metar
python setup.py install
cd ..
rm -rf python-metar
echo -ne "# Configuring Mosquitto broker...    ##########            (50%)\r"
# Start Mosquitto broker along with the system
sudo systemctl enable mosquitto.service

# Install Zigbee2MQTT
# Setup Node.js repository
echo -ne "# Installing Zigbee2MQTT...          ############          (60%)\r"
curl -sL https://deb.nodesource.com/setup_14.x | sudo -E bash -

# NOTE 1: If you see the message below please follow: https://gist.github.com/Koenkk/11fe6d4845f5275a2a8791d04ea223cb.
# ## You appear to be running on ARMv6 hardware. Unfortunately this is not currently supported by the NodeSource Linux distributions. Please use the 'linux-armv6l' binary tarballs available directly from nodejs.org for Node.js 4 and later.
# IMPORTANT: In this case instead of the apt-get install mentioned below; do: sudo apt-get install -y git make g++ gcc

# NOTE 2: On x86, Node.js 10 may not work. It's recommended to install an unofficial Node.js 14 build which can be found here: https://unofficial-builds.nodejs.org/download/release/ (e.g. v14.16.0)

# Clone Zigbee2MQTT repository
echo -ne "# Installing Zigbee2MQTT...          ################       (80%)\r"
git clone https://github.com/Koenkk/zigbee2mqtt.git /opt/zigbee2mqtt
chown -R 1001:1001 /opt/zigbee2mqtt

# Install dependencies (as user "pi")
cd /opt/zigbee2mqtt
npm ci
echo -ne "# Configuring system updates...      ##################     (90%)\r"

echo "Unattended-Upgrade::Origins-Pattern {
        \"origin=Debian,codename=${distro_codename}-updates\";
        \"origin=Debian,codename=${distro_codename},label=Debian\";
        \"origin=Debian,codename=${distro_codename},label=Debian-Security\";
        \"origin=Raspbian,codename=${distro_codename},label=Raspbian\";
        \"origin=Raspberry Pi Foundation,codename=${distro_codename},label=Raspberry Pi Foundation\";
};
Unattended-Upgrade::Remove-Unused-Dependencies \"true\";
Unattended-Upgrade::Automatic-Reboot \"true\";
Unattended-Upgrade::Automatic-Reboot-Time \"05:00\";
Unattended-Upgrade::SyslogEnable \"true\";
" >> /etc/apt/apt.conf.d/50unattended-upgrades
echo -ne "# Installation complete.             ####################  (100%)\r"
echo -ne '\n'
echo     "#####################################################################"
echo     "# Done.                                                             #"
echo     "#####################################################################"
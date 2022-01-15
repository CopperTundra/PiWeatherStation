#!/bin/bash

echo "Disabling services and saving power for the night..."
systemctl stop piclock
cp /home/pi/PiClock/off /sys/class/backlight/rpi_backlight/bl_power
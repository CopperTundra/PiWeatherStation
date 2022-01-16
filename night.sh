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

echo "Disabling services and saving power for the night..."
systemctl stop piclock
cp /home/pi/PiClock/off /sys/class/backlight/rpi_backlight/bl_power
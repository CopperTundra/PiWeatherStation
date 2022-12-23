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
# Startup script for the PiWeatherStation
#

#
cd $HOME/PiWeatherStation
#
if [ "$DISPLAY" = "" ]
then
	export DISPLAY=:0
fi

COPYRIGHT="<span size='xx-small'>PiWeatherStation  Copyright (C) 2021  Olivier Schuwer \n This program comes with ABSOLUTELY NO WARRANTY. \n This is free software, and you are welcome to redistribute it under certain conditions.</span>"
# wait for Xwindows and the desktop to start up
MSG="echo Waiting 45 seconds before starting"
DELAY="sleep 45"
if [ "$1" = "-n" -o "$1" = "--no-sleep" -o "$1" = "--no-delay" ]
then
	MSG=""
	DELAY=""
	shift
fi
if [ "$1" = "-d" -o "$1" = "--delay" ]
then
	MSG="echo Waiting $2 seconds before starting"
	DELAY="sleep $2"
	shift
	shift
fi
if [ "$1" = "-m" -o "$1" = "--message-delay" ]
then
	MSG="echo Waiting $2 seconds for response before starting"
	DELAY='zenity --no-wrap --question --title PiWeatherStation --ok-label=Now --cancel-label=Cancel --timeout '$2' --text "Starting PiWeatherStation in '$2' seconds\n '$COPYRIGHT'" >/dev/null 2>&1'
	shift
	shift
fi

$MSG
eval $DELAY
if [ $? -eq 1 ]
then

	echo "PiClock Cancelled"
	exit 0
fi

#xmessage -timeout 5 Starting PiClock....... &
zenity --no-wrap --info --timeout 3 --text "${COPYRIGHT}" >/dev/null 2>&1 &

# stop screen blanking
echo "Disabling screen blanking...."
xset s off
xset -dpms
xset s noblank

# get rid of mouse cursor
pgrep unclutter >/dev/null 2>&1
if [ $? -eq 1 ]
then
	unclutter >/dev/null 2>&1 &
fi

# the main app
cd Clock
if [ "$1" = "-s" -o "$1" = "--screen-log" ]
then
  echo "PiWeatherStation  Copyright (C) 2021  Olivier Schuwer \n This program comes with ABSOLUTELY NO WARRANTY. \n This is free software, and you are welcome to redistribute it under certain conditions."
  echo "Starting PiWeatherStation... logging to screen."
  python3 -u PyQtPiClock.py
else
  # create a new log file name, max of 7 log files
  echo "Rotating log files...."
  rm PyQtPiClock.7.log >/dev/null 2>&1
  mv PyQtPiClock.6.log PyQtPiClock.7.log >/dev/null 2>&1
  mv PyQtPiClock.5.log PyQtPiClock.6.log >/dev/null 2>&1
  mv PyQtPiClock.4.log PyQtPiClock.5.log >/dev/null 2>&1
  mv PyQtPiClock.3.log PyQtPiClock.4.log >/dev/null 2>&1
  mv PyQtPiClock.2.log PyQtPiClock.3.log >/dev/null 2>&1
  mv PyQtPiClock.1.log PyQtPiClock.2.log >/dev/null 2>&1
  echo "Starting PiClock.... logging to Clock/PyQtPiClock.1.log "
  python3 -u PyQtPiClock.py >PyQtPiClock.1.log 2>&1
fi

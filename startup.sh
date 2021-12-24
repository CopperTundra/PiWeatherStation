#!/bin/bash
# Startup script for the PiClock
#
# Designed to be started from PiClock.desktop (autostart)
#
# or alternatively from crontab as follows
#@reboot sh /home/pi/PiClock/startup.sh

#
cd $HOME/PiClock
#
if [ "$DISPLAY" = "" ]
then
	export DISPLAY=:0
fi

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
	#DELAY="xmessage -buttons Now:0,Cancel:1 -default Now -timeout $2 Starting PiClock in $2 seconds"
	DELAY='zenity --question --title PiClock --ok-label=Now --cancel-label=Cancel --timeout '$2' --text "Starting PiClock in '$2' seconds" >/dev/null 2>&1'
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
zenity --info --timeout 3 --text "Starting PiClock......." >/dev/null 2>&1 &

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
  echo "Starting PiClock.... logging to screen."
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

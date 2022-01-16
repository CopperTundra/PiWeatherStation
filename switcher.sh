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

cd $HOME/PiClock
pkill -INT -f PyQtPiClock.py
cd Clock
if [ "$DISPLAY" = "" ]
then
	export DISPLAY=:0
fi
# the main app
# create a new log file name, max of 7 log files
echo "Rotating log files...."
rm PyQtPiClock.7.log >/dev/null 2>&1
mv PyQtPiClock.6.log PyQtPiClock.7.log >/dev/null 2>&1
mv PyQtPiClock.5.log PyQtPiClock.6.log >/dev/null 2>&1
mv PyQtPiClock.4.log PyQtPiClock.5.log >/dev/null 2>&1
mv PyQtPiClock.3.log PyQtPiClock.4.log >/dev/null 2>&1
mv PyQtPiClock.2.log PyQtPiClock.3.log >/dev/null 2>&1
mv PyQtPiClock.1.log PyQtPiClock.2.log >/dev/null 2>&1
# start the clock
echo "Starting PiClock...."
python -u PyQtPiClock.py $1 >PyQtPiClock.1.log 2>&1 &

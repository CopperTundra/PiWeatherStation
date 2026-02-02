# Install Instructions for PiWeatherStation

PiWeatherStation and this install guide are based on Raspian. I suggest using a Raspbian version with a desktop.

## Download Raspbian and put it on an SD Card

The instructions for doing this are on the following page:
https://www.raspberrypi.com/documentation/computers/getting-started.html#installing-the-operating-system
### First boot and configure
A keyboard and mouse are really handy at this point.
When you first boot your Pi, you'll be presented with the desktop.
Following this there will be several prompts to set things up, follow
those prompts and set things as they make sense for you.  Of course
setting the proper timezone for a clock is key.

Eventually the Pi will reboot, and you'll be back to the desktop.
We need to configure a few more things.

Navigate to Menu->Preferences->Raspberry Pi Configuration.
Just change the Items below.
- System Tab
  - Hostname: Change it to the name that you want
  - Boot: To Desktop
  - Auto Login: Checked
- Interfaces
  - enable SSH

Click ok, and allow it to reboot.
Check the IP of your Raspberry Pi by typing
```
sudo ifconfig
```
From this point, you're free to get rid of your mouse/keyboard and you may proceed over SSH. It will allow you to open a bash connection to your Raspberry Pi over your PC.
To open a SSH connection, from your PC :
- Open a Powershell window (Windows 10/11) or a Terminal (MacOSX, Linux)
- Type :
```
ssh hostname@ipaddress
```

## Get all the software that PiWeatherStation needs
### Install everything

Clone this repository and use the install script :

~~~
git clone https://github.com/CopperTundra/PiWeatherStation.git
chmod +x install.sh
sudo ./install.sh
~~~

If you get no error, you're good to proceed to the configuration !

### reboot
To get some things running, and ensure the final config is right, we'll do
a reboot
```
reboot
```
### Configure your PiWeatherStation

#### Configure the PiWeatherStation API keys

First things first, you need to get an API key for Mapbox and for OpenWeatherMap.org. It's totally free for low data usage !

- Mapbox : https://www.mapbox.com/
  - Register and login, you'll get an API key in your account under the section "Default public token"
- OpenWeatherMap.org : https://openweathermap.org/
  - Register and login, you'll get an API key in the section "_YourName_/My API keys"
 
The PiWeatherStation usage is well below the maximums imposed by the no cost API keys.

**Protect your API keys.**  You'd be surprised how many pastebin's are out
there with valid API keys, because of people not being careful. _If you post
your keys somewhere, your usage will skyrocket, and your bill as well._ 
An API key is like a password, nobody has to know it except you !

Now that you have your API keys...

```
cd PiClock/Clock
cp ApiKeys-example.py ApiKeys.py
nano ApiKeys.py
```
Put your API keys in the file as indicated.

### Configure your PiWeatherStation
here's were you tell PiWeatherStation where your weather should come from, and the
radar map centers and markers.

```
cd PiWeatherStation
cd Clock
cp Config-Example.py Config.py
nano Config.py
```

This file is a python script, subject to python rules and syntax.
The configuration is a set of variables, objects and arrays,
set up in python syntax.  The positioning of the {} and () and ','
are not arbitrary.  If you're not familiar with python, use extra
care not to disturb the format while changing the data.

The first thing is to change the primary_coordinates to yours. That is really all that is manditory. Easiest way to get them is to use Google Maps and right click on your location, by clicking on your coordinates you will copy them. 

![How to : Google Maps Coordinates](https://raw.githubusercontent.com/CopperTundra/PiWeatherStation/master/Pictures/GoogleMapsCoordinates.png)

At this point, I'd not recommend many other changes until you have tested
and gotten it running.

### Run it!
Just run it :
```
cd PiWeatherStation
sh startup.sh -n -s
```
Your screen should be covered by the PiClock  YAY!

There will be some output on the terminal screen as startup.sh executes.
If everything works, it can be ignored.  If for some reason the clock
doesn't work, or maps are missing, etc the output may give a reason
or reasons, which usually reference something to do with the config
file (Config.py)

If everything works you should be able to zoom in/out the radars by touching the display.

### Logs
The -s option causes no log files to be created, but
instead logs to your terminal screen.  If -s is omitted, logs are
created in PiWeatherStation/Clock as PyQtPiClock.[1-7].log, which can also help
you find issues.  -s is normally omitted when started from autostart.  Logs are then created for debugging auto starts.

### setting the clock to auto start
At this point the clock will only start when you manually start it, as described in the Run It section.
## Autostart
We will gonna use systemd standard list. To do this, just use the given PiWeatherStation.service file :

~~~
cd PiWeatherStation/Clock
sudo cp PiWeatherStation.service /etc/systemd/system/
sudo systemctl enable PiWeatherStation
~~~


## Some notes about startup.sh
startup.sh has a few options:
* -n or --no-delay			Don't delay on starting the clock right away (default is 45 seconds delay)
* -d X or --delay X			Delay X seconds before starting the clock
* -m X or --message-delay X 	Delay X seconds while displaying a message on the desktop

Startup also looks at the various optional PiClock items (Buttons, Temperature, NeoPixel, etc)
and only starts those things that are configured to run.   It also checks if they are already
running, and refrains from starting them again if they are.

### Switching skins at certain times of the day
This is optional, but if its just too bright at night, a switcher script will kill and restart
PyQtPiClock with an alternate config.

First you need to set up an alternate config.   Config.py is the normal name, so perhaps Config-Night.py
might be appropriate.  For a dimmer display use Config-Example-Bedside.py as a guide.

First we must make switcher.sh executable (git removes the x flags)
```
cd PiClock
chmod +x switcher.sh
```
Now we'll tell our friend cron to run the switcher script (switcher.sh) on day/night cycles.
Run the cron editor: (should *not* be roor)
```
crontab -e
```
Add lines similar to this:
```
0 8 * * * sh /home/pi/PiClock/switcher.sh Config
0 21 * * * sh /home/pi/PiClock/switcher.sh Config-Night
```
The 8 there means 8am, to switch to the normal config, and the 21 means switch to Config-Night at 9pm.
More info on crontab can be found here: https://en.wikipedia.org/wiki/Cron

### Setting the Pi to auto reboot every day
This is optional but some may want their PiClock to reboot every day.  I do this with mine,
but it is probably not needed.
```
sudo crontab -e
```
For exeample, add the following lines :
```
30 22 * * 0-4 /home/pi/PiClock/night.sh
00 00 * * 6,7 /home/pi/PiClock/night.sh
00 09 * * 6,7 /usr/sbin/shutdown -r 0
00 06 * * 1-5 /usr/sbin/shutdown -r 0

```
save the file

This will disable the screen and stop the app at 22:30 and reboot at 06:00 every monday-friday.
And it will do the same on week-ends between 00:00 and 09:00.

### Updating to newer/updated versions
Since we pulled the software from github originally, it can be updated
using git and github.
```
cd PiClock
git pull
python update.py
```
This will automatically update any part(s) of the software that has changed.
The update.py program will then convert any config files as needed.

You'll want to reboot after the update.

Note: If you get errors because you've made changes to the base code you might need
```
git diff
```
To see your changes, so you can back them up

Then this will update to the current version
```
git reset --hard
```
(This won't bother your Config.py nor ApiKeys.py because they are not tracked in git.

Also, if you're using gpio-keys, you may need to remake it:
```
cd PiClock/Button
rm gpio-keys
make gpio-keys
```

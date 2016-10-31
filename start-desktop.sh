#!/usr/bin/env bash

# Start TightVNC Server
echo 'Starting display...'

# Remove existing X lock
rm /tmp/.X1-lock
rm /tmp/.X11-unix/X1
unset SESSION_MANAGER

# Create predefined vnc password
mkdir ~/.vnc
echo 'password' | /usr/bin/vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# Start VNC server
su -c 'tightvncserver :1 -geometry 1024x768 -depth 24' root
export 'DISPLAY=:1'
/usr/bin/lxsession -s LXDE &

# Autologin session
echo 'password' | vncviewer -autopass :1 &

echo 'Display started'

bash

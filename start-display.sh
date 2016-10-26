#!/usr/bin/env bash

# Start TightVNC Server
echo 'Starting display...'

su -c 'tightvncserver :1 -geometry 1024x768 -depth 24' root
export 'DISPLAY=:1'
/usr/bin/lxsession -s LXDE &

echo 'Display started'

bash

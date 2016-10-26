#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE}")" ; pwd -P )
cd "$parent_path"
xvfb-run -a --server-args='-screen 0 1024x768x16 -ac +extension RANDR' python start.py $1 $2

read -p "Press [Enter] key to exit..."

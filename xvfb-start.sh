#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE}")" ; pwd -P )
cd "$parent_path"
xvfb-run python start.py $1

read -p "Press [Enter] key to exit..."

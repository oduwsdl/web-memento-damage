#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE}")" ; pwd -P )
cd "$parent_path"
env-linux/bin/python start.py

read -p "Press [Enter] key to exit..."

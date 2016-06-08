#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE}")" ; pwd -P )
cd "$parent_path"
python start.py

read -p "Press [Enter] key to exit..."

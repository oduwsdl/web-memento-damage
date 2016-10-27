#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE}")" ; pwd -P )
cd "$parent_path"

python server.py $1 $2

read -p "Press [Enter] key to exit..."

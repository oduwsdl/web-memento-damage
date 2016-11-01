#!/usr/bin/env bash

nohup /display/desktop.sh
nohup /server/configure-nginx.sh &
nohup /server/start-server.sh & 

bash

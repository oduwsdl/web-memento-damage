#!/usr/bin/env bash

# Start 4 tornado servers with different ports
echo 'Starting tornado servers...'
nohup /app/server.sh 8880 &
nohup /app/server.sh 8881 &
nohup /app/server.sh 8882 &
nohup /app/server.sh 8883 &
echo 'Tornado started'


# Enter bash console
bash

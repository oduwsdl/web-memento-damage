#!/usr/bin/env bash

# Start 4 tornado servers with different ports
echo 'Starting tornado servers...'
nohup /app/server.sh 8880 &
nohup /app/server.sh 8881 &
nohup /app/server.sh 8882 &
nohup /app/server.sh 8883 &
echo 'Tornado started'


# Create nginx load balancer
echo 'Starting nginx load balancer...'
rm /etc/nginx/sites-enabled/default
cp /app/nginx.conf /etc/nginx/sites-available

ln -s /etc/nginx/sites-available/nginx.conf \
    /etc/nginx/sites-enabled/nginx.conf

service nginx restart
echo 'Nginx started'


# Enter bash console
bash
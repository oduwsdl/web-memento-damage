#!/usr/bin/env bash

# Start 4 tornado servers with different ports
echo 'Starting tornado servers...'

nohup /app/start.sh 8880 &
nohup /app/start.sh 8881 &
nohup /app/start.sh 8882 &
nohup /app/start.sh 8883 &

echo 'Tornado started'

# Create nginx load balancer
echo 'Starting nginx load balancer...'

rm /etc/nginx/sites-enabled/default
cp /app/web-memento-damage.conf /etc/nginx/sites-available

ln -s /etc/nginx/sites-available/web-memento-damage.conf \
    /etc/nginx/sites-enabled/web-memento-damage.conf

service nginx restart

echo 'Nginx started'

# Enter bash console
bash
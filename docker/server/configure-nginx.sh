#!/usr/bin/env bash

# Create nginx load balancer
echo 'Starting nginx load balancer...'
rm /etc/nginx/sites-enabled/default
cp /server/nginx.conf /etc/nginx/sites-available

ln -s /etc/nginx/sites-available/nginx.conf \
    /etc/nginx/sites-enabled/nginx.conf

service nginx restart
echo 'Nginx started'

bash

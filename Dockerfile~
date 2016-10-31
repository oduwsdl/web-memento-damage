FROM erikaris/memento-damage:latest
MAINTAINER Erika Siregar <erikaris87@gmail.com>

# Install nginx
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y nginx

# Copy necessary files
COPY start-desktop-server.sh /app

# Start desktop dan server
ENTRYPOINT /app/start-desktop-server.sh

# Expose variables
EXPOSE 80
VOLUME /app/cache

CMD /bin/bash

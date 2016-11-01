FROM erikaris/memento-damage:latest
MAINTAINER Erika Siregar <erikaris87@gmail.com>

# Install nginx
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y nginx

# Clean apt cache
RUN DEBIAN_FRONTEND=noninteractive apt-get clean

# Copy necessary files
COPY . /server
RUN chmod +x /server/*
RUN chmod +x /app/*.sh

# Start desktop dan server
ENTRYPOINT /server/start-all.sh

# Expose variables
EXPOSE 80
VOLUME /app/cache

CMD /bin/bash

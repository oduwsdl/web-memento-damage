FROM ubuntu:xenial
MAINTAINER Sawood Alam <ibnesayeed@gmail.com>

# Set workdir
RUN mkdir -p /app
WORKDIR /app

RUN apt-get update

# Install python pio phantomjs xvfb and nginx
RUN apt-get install -y python python-pip
RUN pip install --upgrade pip

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y phantomjs
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y xvfb
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y nginx

# Install desktop and vncserver
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y lxde-core tightvncserver

# Install application
COPY . /app
RUN pip install -r requirements.txt

# Create startup
RUN mkdir ~/.config
RUN mkdir ~/.config/autostart
RUN echo '[Desktop Entry]' >> ~/.config/autostart/start-nginx.desktop
RUN echo 'Type=Application' >> ~/.config/autostart/start-nginx.desktop
RUN echo 'Exec=/app/start-server.sh' >> ~/.config/autostart/start-nginx.desktop

# Expose variables
EXPOSE 80
VOLUME /app/cli
VOLUME /app/cache
VOLUME /app/test

CMD /app/start-display.sh

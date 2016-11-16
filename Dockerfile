FROM soedomoto/docker:ubuntu-lxde
MAINTAINER Erika Siregar <erikaris1515@gmail.com>

# Change ubuntu mirror
RUN sed -i 's|http://|http://us.|g' /etc/apt/sources.list
RUN apt-get update -y

# Install python pio phantomjs xvfb and nginx
RUN apt-get install -y python python-pip
RUN pip install --upgrade pip --no-cache-dir

# Install phantomjs
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y phantomjs

# Clean apt cache
RUN DEBIAN_FRONTEND=noninteractive apt-get clean


# Set workdir
RUN mkdir -p /app
WORKDIR /app

# Copy files
COPY . /app
RUN pip install -r requirements.txt --no-cache-dir

# Expose directory
VOLUME /app/cache


CMD /bin/bash

FROM soedomoto/docker:ubuntu-lxde
MAINTAINER Erika Siregar <erikaris1515@gmail.com>

# Change ubuntu mirror
RUN sed -i 's|http://archive.ubuntu.com/ubuntu/|mirror://mirrors.ubuntu.com/mirrors.txt|g' /etc/apt/sources.list
RUN apt-get update -y

# Install python pip
RUN apt-get install -y python python-pip
RUN pip install --upgrade pip --no-cache-dir

# Install phantomjs
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y phantomjs

# Install nginx
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y nginx

# Clean apt cache
RUN DEBIAN_FRONTEND=noninteractive apt-get clean

# Set workdir
RUN mkdir -p /app
WORKDIR /app

# Copy files
COPY . /app
RUN chmod +x /app/*.sh

# Install required phython libraries
RUN pip install -r /app/requirements.txt --no-cache-dir

# Set workspace
ENV WORKSPACE /app/cache
# RUN mkdir "$WORKSPACE"

# Expose directory
VOLUME "$WORKSPACE"



# CLI SETTINGS ====================================================

# Copy necessary files
RUN mv /app/docker/cli/damage /app/cli/damage
RUN chmod +x -R /app/cli

# Add project cli directory to PATH
env PATH /app/cli:$PATH

# Set workdir
WORKDIR "$WORKSPACE"



# SERVER SETTINGS =================================================

# Locate necessary files
RUN mv /app/docker/server /server
RUN chmod +x /server/*

# Expose variables
EXPOSE 80



# Wrap all
RUN mv /app/docker/entrypoint /entrypoint
RUN chmod +x /entrypoint/*

ENTRYPOINT /entrypoint/start.sh

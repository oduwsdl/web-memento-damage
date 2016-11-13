FROM soedomoto/docker:ubuntu-lxde
MAINTAINER Erika Siregar <erikaris151@gmail.com>

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

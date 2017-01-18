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

# Clean apt cache
RUN DEBIAN_FRONTEND=noninteractive apt-get clean

# Make temporary dir to put library file
RUN mkdir -p /tmp/app
COPY . /tmp/app

RUN pip install -U setuptools
RUN pip install /tmp/app

# Copy entrypoint to /server
RUN mkdir -p /app
COPY ./entrypoint.sh /app

# Run entrypoint at startup
ENTRYPOINT /app/entrypoint.sh

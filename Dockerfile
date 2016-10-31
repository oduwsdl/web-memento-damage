FROM soedomoto/docker:ubuntu-lxde
MAINTAINER Erika Siregar <erikaris87@gmail.com>

# Install phantomjs, perl, and perlmagick
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y phantomjs
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y perl
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y perlmagick

# Install perl module
RUN PERL_MM_USE_DEFAULT=1 perl -MCPAN -e 'install HTML::Strip'
RUN PERL_MM_USE_DEFAULT=1 perl -MCPAN -e 'install HTML::TokeParser::Simple'
RUN PERL_MM_USE_DEFAULT=1 perl -MCPAN -e 'install Color::Rgb'

# Set workdir and copy all files
RUN mkdir -p /app
COPY . /app

WORKDIR /app

# Expose variables
VOLUME /app/testing


CMD /bin/bash

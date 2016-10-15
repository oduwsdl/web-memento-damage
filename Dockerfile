FROM python:2-onbuild
MAINTAINER Sawood Alam <ibnesayeed@gmail.com>

RUN apt-get update && apt-get install -y xvfb

# Using NPM because PhantomJS binaries are returning 403 when downloaded by wget
RUN curl -sL https://deb.nodesource.com/setup | bash - && \
    apt-get install -y nodejs && \
    npm install -g phantomjs-prebuilt

ENV MDPORT=8880 MDHOST=0.0.0.0
EXPOSE $MDPORT

CMD xvfb-run --server-args='-screen 0, 1024x768x16' python start.py $MDPORT $MDHOST

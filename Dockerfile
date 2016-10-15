FROM python:2-onbuild
MAINTAINER Sawood Alam <ibnesayeed@gmail.com>

RUN apt-get update && apt-get install -y xvfb

ENV MDPORT=8880 MDHOST=0.0.0.0
EXPOSE $MDPORT

CMD xvfb-run --server-args='-screen 0, 1024x768x16' python start.py $MDPORT $MDHOST

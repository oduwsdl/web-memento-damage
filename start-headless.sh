#!/usr/bin/env bash

xvfb-run -a --server-args='-screen 0 1024x768x16 -ac +extension RANDR' /app/start-server.sh

bash

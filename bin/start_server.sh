#!/bin/bash

# TODO: Run script to handle replay server load if needed before triggering memento damage crawl and analysis
#!/usr/bin/env bash

nohup /display/desktop.sh
memento-damage-server -p $PORT -o "$WORKSPACE"
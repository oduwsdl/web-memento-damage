FROM erikaris/memento-damage:latest
MAINTAINER Erika Siregar <erikaris87@gmail.com>

# Copy necessary files
COPY start-desktop.sh /app
COPY damage /app/cli

# Add project cli directory to PATH
env PATH /app/cli:$PATH

# Set workdir
RUN mkdir -p /app/cli/workspace
WORKDIR /app/cli/workspace

# Start desktop
ENTRYPOINT /bin/sh -c /app/start-desktop.sh

# Expose variables
VOLUME /app/cli/workspace

CMD /bin/bash

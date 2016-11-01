FROM erikaris/memento-damage:latest
MAINTAINER Erika Siregar <erikaris87@gmail.com>

# Copy necessary files
COPY damage /app/cli
RUN chmod +x -R /app/cli

# Add project cli directory to PATH
env PATH /app/cli:$PATH

# Set workspace
ENV WORKSPACE /app/cache

# Set workdir
RUN mkdir -p "$WORKSPACE"
WORKDIR "$WORKSPACE"

# Expose "$WORKSPACE"
VOLUME "$WORKSPACE"

CMD /bin/bash

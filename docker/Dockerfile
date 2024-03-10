ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim as base

ARG UID=1000
ARG GID=1000
ARG PORT=80
ARG NODE_MAJOR=20

EXPOSE $PORT

# ENV PATH="/venv/bin:$PATH"

RUN set -ex \
    # Install NodeJS
    && apt-get update && apt-get install -yq --no-install-recommends \
    ca-certificates curl gnupg \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -yq --no-install-recommends nodejs \
    # Puppeteer system dependencies
    gconf-service lsb-release xdg-utils wget dbus dbus-x11 \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libc6 libcairo2 libcups2 libdbus-1-3 libdrm2 libexpat1 libgbm1 libgcc1 libglib2.0-0 \
    libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libuuid1 libx11-6 libx11-xcb1 libxcb-dri3-0 libxcb1 libxcomposite1 \
    libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxkbcommon0 libxrandr2 libxrender1 libxshmfence1 libxss1 libxtst6 \
    fonts-liberation fonts-ipafont-gothic fonts-wqy-zenhei fonts-khmeros fonts-thai-tlwg fonts-kacst fonts-freefont-ttf \
    # Post-install cleanups
    && service dbus start \
    && rm -rf /var/lib/apt/lists/*

ENV WORKSPACE /app/cache
RUN mkdir -p "$WORKSPACE"
WORKDIR "$WORKSPACE"
VOLUME "$WORKSPACE"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=100
ENV PUPPETEER_CACHE_DIR=/app/.cache
ENV PUPPETEER_DOWNLOAD_PATH=/app/.cache

COPY . .
COPY ./docker/run.sh /app/bin/run.sh

RUN npm i . \
    && pip install --no-cache-dir . \
    && groupadd -g ${GID} wsdl && useradd -rm -u ${UID} -g ${GID} -G audio,video wsdl \
    && mkdir -p /app/downloads \
    && chown -R wsdl:wsdl /app

USER wsdl

# Make temporary dir to put library file --> install it
RUN mkdir -p /tmp/app
COPY . /tmp/app

RUN pip install -U setuptools --no-cache-dir
RUN pip install /tmp/app --no-cache-dir

# Copy entrypoint to /server
RUN mkdir -p /app
COPY ./entrypoint.sh /app
RUN chmod +x -R /app/entrypoint.sh

# Run entrypoint at startup
ENV PORT 80
EXPOSE $PORT
ENTRYPOINT ["/bin/sh", "-c"]

CMD ["/app/bin/start_server.sh"]
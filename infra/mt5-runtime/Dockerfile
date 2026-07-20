FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV WINEPREFIX=/data/mt5-prefix
ENV WINEARCH=win64

RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      wget \
      xvfb \
      xauth \
      xdotool \
      x11vnc \
      openbox \
      novnc \
      websockify \
      cabextract \
      unzip \
    && mkdir -p /etc/apt/keyrings \
    && wget -qO /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -qO /etc/apt/sources.list.d/winehq-noble.sources https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources \
    && apt-get update \
    && apt-get install -y --install-recommends winehq-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/2lotus

COPY infra/mt5-runtime/verify-runtime.sh /usr/local/bin/verify-runtime
COPY infra/mt5-runtime/bootstrap-mt5.sh /usr/local/bin/bootstrap-mt5
COPY infra/mt5-runtime/start-remote-desktop.sh /usr/local/bin/start-remote-desktop

RUN chmod +x /usr/local/bin/verify-runtime /usr/local/bin/bootstrap-mt5 /usr/local/bin/start-remote-desktop \
    && mkdir -p /data/downloads /data/mt5-prefix

CMD ["bash"]

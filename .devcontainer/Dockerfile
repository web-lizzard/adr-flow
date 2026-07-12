FROM mcr.microsoft.com/devcontainers/base:ubuntu

# Virtual display for headed Playwright / browser debugging via noVNC (port 6080).
RUN apt-get update \
	&& DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
		dbus-x11 \
		fluxbox \
		novnc \
		websockify \
		x11vnc \
		xvfb \
	&& rm -rf /var/lib/apt/lists/*

# Match workspaceFolder / compose bind mount target in devcontainer.json.
ENV DISPLAY=:99

COPY profile.d/display.sh /etc/profile.d/devcontainer-display.sh

RUN mkdir -p /workspace /home/vscode/.cursor /tmp/.X11-unix \
	&& chown -R vscode:vscode /workspace /home/vscode/.cursor \
	&& chmod 1777 /tmp/.X11-unix

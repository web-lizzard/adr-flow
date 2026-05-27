FROM mcr.microsoft.com/devcontainers/base:ubuntu

# Match workspaceFolder / compose bind mount target in devcontainer.json.
RUN mkdir -p /workspace /home/vscode/.cursor \
	&& chown -R vscode:vscode /workspace /home/vscode/.cursor

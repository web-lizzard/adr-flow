FROM mcr.microsoft.com/devcontainers/base:ubuntu

# Required so permissions.json can be bind-mounted at /home/vscode/.cursor/permissions.json.
RUN mkdir -p /home/vscode/.cursor && chown -R vscode:vscode /home/vscode/.cursor

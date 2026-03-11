#!/bin/bash
# Runs on the HOST before container start.

# Clean stale VS Code Server installs from Docker Desktop WSL root (tiny 135MB FS).
wsl -d docker-desktop -- rm -rf /root/.vscode-remote-containers /root/.vscode-server /root/.vscode 2>/dev/null

# Capture git identity for post-create.sh to apply inside the container.
git config --global user.name > .devcontainer/.gituser.tmp 2>/dev/null
git config --global user.email >> .devcontainer/.gituser.tmp 2>/dev/null

exit 0

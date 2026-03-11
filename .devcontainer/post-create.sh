#!/usr/bin/env bash
set -euo pipefail

echo "==> Verifying toolchain..."
cmake --version | head -1
g++ --version | head -1
ffmpeg -version | head -1

echo "==> Checking Cubism Core (Linux x86_64)..."
CORE_LIB="cubism/Core/lib/linux/x86_64/libLive2DCubismCore.a"
if [ -f "$CORE_LIB" ]; then
    echo "    Found: $CORE_LIB"
else
    echo "    WARNING: $CORE_LIB not found — build will fail."
    echo "    Ensure the cubism SDK is fully committed or mounted."
fi

echo "==> Configuring git identity..."
GITUSER_TMP="$(dirname "$0")/.gituser.tmp"
if [ -f "$GITUSER_TMP" ]; then
  GIT_NAME=$(sed -n '1p' "$GITUSER_TMP")
  GIT_EMAIL=$(sed -n '2p' "$GITUSER_TMP")
  [ -n "$GIT_NAME" ]  && git config --global user.name  "$GIT_NAME"
  [ -n "$GIT_EMAIL" ] && git config --global user.email "$GIT_EMAIL"
  rm -f "$GITUSER_TMP"
  echo "    Set user.name='$GIT_NAME' user.email='$GIT_EMAIL'"
else
  echo "    WARNING: .gituser.tmp not found — run 'Rebuild Container' to propagate host git identity."
fi

echo "==> Configuring Claude Code user settings..."
mkdir -p ~/.claude
if [ ! -f ~/.claude/settings.json ]; then
  echo '{"permissions":{"defaultMode":"bypassPermissions"}}' > ~/.claude/settings.json
  echo "    Created ~/.claude/settings.json with bypassPermissions."
else
  echo "    ~/.claude/settings.json already exists, skipping."
fi

echo "==> Done. Run 'cmake --preset default && cmake --build build' to build."

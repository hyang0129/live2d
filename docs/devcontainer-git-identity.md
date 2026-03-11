# Git Identity in the Devcontainer

## The Problem

VS Code Dev Containers automatically propagates the host's git credentials (via a socket-based credential helper) but does **not** reliably copy `user.name` / `user.email` when using Docker Desktop on Windows. The result is that git commits made inside the container have no author identity, causing `git commit` to fail or fall back to a system default.

Verified: inside the container, `~/.gitconfig` does not exist and `git config user.name` returns nothing — even when the host has both values set globally.

## The Fix

`initializeCommand` in `devcontainer.json` runs on the **host** before the container starts. The workspace folder is the only location guaranteed to be shared between host and container, so we use it as a relay:

1. **`initializeCommand`** writes the two values from the host gitconfig into `.devcontainer/.gituser.tmp`.
2. **`post-create.sh`** reads them, applies them with `git config --global`, and deletes the temp file.
3. **`.gitignore`** ensures `.gituser.tmp` is never committed.

## Applying the Fix

**Rebuild the container** (one-time, after pulling these changes):

> Ctrl+Shift+P → "Dev Containers: Rebuild Container"

After that, every subsequent container start will have the correct identity automatically.

FROM mcr.microsoft.com/devcontainers/cpp:1-ubuntu-22.04

# Install build tools and runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
        cmake \
        ninja-build \
        pkg-config \
        # OpenGL / EGL for headless rendering
        libgl1-mesa-dev \
        libegl1-mesa-dev \
        libgles2-mesa-dev \
        mesa-utils \
        # GLEW and GLFW for Live2D OpenGL backend
        libglew-dev \
        libglfw3-dev \
        # X11 (needed by GLFW even in offscreen mode)
        libx11-dev \
        libxrandr-dev \
        libxinerama-dev \
        libxcursor-dev \
        libxi-dev \
        # FFmpeg for video encoding
        ffmpeg \
        libavcodec-dev \
        libavformat-dev \
        libavutil-dev \
        libswscale-dev \
        # Audio processing
        libsndfile1-dev \
        # Utilities
        git \
        curl \
        unzip \
    && apt-get autoremove -y && apt-get clean -y

# Upgrade Mesa to 24.x via kisak-mesa PPA — enables hardware EGL/DRI
# (requires /dev/dri passthrough in devcontainer.json + WSLg or DRI nodes on host)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get -y install --no-install-recommends software-properties-common \
    && add-apt-repository --yes ppa:kisak/kisak-mesa \
    && apt-get update && apt-get -y install --no-install-recommends \
        libgl1-mesa-dri \
        libegl-mesa0 \
        libgles2-mesa

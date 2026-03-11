FROM mcr.microsoft.com/devcontainers/cpp:1-ubuntu-22.04

# Install build tools and runtime dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
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
    && apt-get autoremove -y && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

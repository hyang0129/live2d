# Claude Code Configuration

## Permissions

Claude has full permissions for this directory. Proceed autonomously without asking for confirmation on:
- Reading, editing, creating, and deleting files
- Running build commands, scripts, and tests
- Installing dependencies
- Any git operations within this repository

## Project Overview

**Live2D Cubism Native SDK** — C++ SDK for displaying Live2D models in native applications.

- SDK version: 5-r.4.1
- Root: `cubism/`

### Directory Structure

```
cubism/
├── Core/         # Live2D Cubism Core library (prebuilt binaries)
├── Framework/    # Source code for rendering and animation (submodule)
└── Samples/
    ├── D3D9/     # DirectX 9.0c sample
    ├── D3D11/    # DirectX 11 sample
    ├── Metal/    # Metal sample (macOS/iOS)
    ├── OpenGL/   # OpenGL sample
    ├── Vulkan/   # Vulkan sample
    └── Resources/# Model files and assets
```

### Build System

- CMake (3.31.7+)
- Visual Studio 2019/2022 on Windows
- Each sample has its own `README.md` with build instructions
- Build output goes to `bin/` inside each sample's cmake build directory

### Key Source Files

- `Framework/` — Cubism Native Framework (rendering, animation, model loading)
- `Samples/OpenGL/Demo/proj.*/` — OpenGL sample projects per platform
- `Samples/D3D11/Demo/proj.*/` — D3D11 sample projects per platform

### Development Environment (Windows)

- Visual Studio 2022 (17.14.2)
- CMake 3.31.7
- Target: Windows 10/11

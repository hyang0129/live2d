# Vulkan Build & GPU Passthrough Guide

## Build

### Prerequisites (container already provides these)

| Package | Purpose |
|---|---|
| `libvulkan-dev` | Vulkan headers and loader (`libvulkan.so`) |
| `mesa-vulkan-drivers` | ICDs: llvmpipe (software), virtio (GPU passthrough), intel, radeon |
| `glslc` / `glslangValidator` | GLSL → SPIR-V shader compilation |
| `cmake ≥ 3.16`, `ninja` | Build system |
| `libLive2DCubismCore.a` | Prebuilt Cubism Core for `linux/x86_64` (ships in `cubism/Core/lib/linux/`) |

### Configure & Build

```bash
cd /workspaces/hub_2/live2d

# Configure (writes build/ with RENDERER_BACKEND=Vulkan)
cmake --preset linux-vulkan

# Build
cmake --build --preset linux-vulkan
```

The preset sets `RENDERER_BACKEND=Vulkan` and `CMAKE_BUILD_TYPE=Release`.
A successful build produces:

- `build/live2d-render` — renderer binary linked to `libvulkan.so.1`
- `FrameworkShaders/*.spv` — SPIR-V shaders copied from build output to repo root

The build is idempotent (`ninja: no work to do` if nothing changed).

### What the Vulkan branch compiles

`CMakeLists.txt` selects the Vulkan path when `RENDERER_BACKEND=Vulkan`:

```
cubism/Framework/src/Rendering/Vulkan/  — Cubism Vulkan renderer
cubism/Framework/src/Rendering/Vulkan/Shaders/  — GLSL shaders compiled to SPIR-V
```

The `FrameworkShaders/` subdirectory at the repo root is the runtime shader search
path (the binary looks for `FrameworkShaders/*.spv` relative to its working directory,
which must be the repo root).

---

## Runtime GPU Selection

### How the device is chosen

The renderer calls `vkEnumeratePhysicalDevices` and picks the **first non-llvmpipe
discrete or integrated GPU** it finds. If no real GPU is available it falls back to
llvmpipe (Mesa's software rasterizer). The selected device is logged at startup:

```
[INFO ] Vulkan: using device "..." (Vulkan 1.x.y)
```

### ICD files on this system

The Vulkan loader reads ICDs from `/usr/share/vulkan/icd.d/`:

| ICD file | Driver | Notes |
|---|---|---|
| `virtio_icd.x86_64.json` | `libvulkan_virtio.so` | WSL2 VirtIO-GPU passthrough |
| `lvp_icd.x86_64.json` | `libvulkan_lvp.so` | llvmpipe — software fallback |
| `intel_icd.x86_64.json` | `libvulkan_intel.so` | Intel ANV |
| `radeon_icd.x86_64.json` | `libvulkan_radeon.so` | AMD RADV |

---

## Current Status: llvmpipe (Software Renderer)

The renderer currently selects **llvmpipe** because the VirtIO-GPU path fails:

```
[INFO ] Vulkan: using device "llvmpipe (LLVM 15.0.7, 256 bits)" (Vulkan 1.3.255)
```

Testing `VK_ICD_FILENAMES=virtio_icd.x86_64.json` alone returns:

```
[ERROR] Vulkan: vkCreateInstance failed
```

### Root cause

This is a **dev container isolation problem**, not a missing GPU on the host.

The WSL2 host has a real GPU accessible via `/dev/dxg` (the Windows DXCore bridge
device). Real Vulkan GPU access inside a Docker container requires two things that
are not currently configured:

1. **`/dev/dxg` device forwarded into the container**
   ```json
   // devcontainer.json
   "runArgs": ["--device=/dev/dxg"]
   ```

2. **Microsoft's D3D12 translation layer mounted from the WSL2 host**
   The host provides `libd3d12.so` at `/usr/lib/wsl/lib/` — this is Microsoft's
   DirectX-over-Linux shim. It is **not** an apt package; it is installed automatically
   by the WSL2 kernel into the host filesystem. Inside the container it is absent:
   ```
   /usr/lib/wsl/lib/   ← does NOT exist in container
   ```
   It must be bind-mounted:
   ```json
   "mounts": ["source=/usr/lib/wsl,target=/usr/lib/wsl,type=bind,readonly"]
   ```
   And the library path must include it:
   ```json
   "containerEnv": {
     "LD_LIBRARY_PATH": "/usr/lib/wsl/lib:${containerEnv:LD_LIBRARY_PATH}"
   }
   ```

   With `libd3d12.so` available, Mesa's `d3d12_dri.so` (already installed) acts as
   the Gallium backend, and Mesa's **DZN** (Dozen) Vulkan driver translates Vulkan
   calls to D3D12, exposing the Windows GPU as a Vulkan device.

   Alternatively, if the GPU has a native Linux Vulkan driver (e.g. NVIDIA with
   `--gpus all` or native Mesa radeon/intel in a bare-metal WSL2 passthrough), the
   corresponding ICD (radeon, intel, or an NVIDIA ICD) would be used directly.

### To enable real GPU rendering: devcontainer changes (applied)

`/dev/dxg` is **already forwarded** into the container automatically by WSL2 —
no `--device` flag needed.

The only missing piece was `libd3d12.so`. The following changes have been made
to `.devcontainer/devcontainer.json`:

```json
"mounts": [
  // ... existing mounts ...
  "source=/usr/lib/wsl/lib,target=/usr/lib/wsl/lib,type=bind,readonly"
],
"containerEnv": {
  "LD_LIBRARY_PATH": "/usr/lib/wsl/lib",
  // ... existing env vars ...
}
```

After **rebuilding the container**, Mesa's DZN driver will find `libd3d12.so` via
`LD_LIBRARY_PATH` and the virtio ICD should enumerate the real Windows GPU instead
of falling back to llvmpipe.

### Performance impact of llvmpipe

llvmpipe is a CPU-based software rasterizer. For the current use case
(offscreen rendering to MP4, no realtime requirement) it is functional:

- 110s behaviour review (1080×1920 @ 30fps, 22 segments) completes in reasonable time
- No rendering artefacts — output is correct

The primary motivation for real GPU is **render speed** on long-form videos, not
correctness.

---

## Forcing a Specific ICD (debugging)

```bash
# Use only the virtio ICD (test GPU passthrough)
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/virtio_icd.x86_64.json ./build/live2d-render --scene ...

# Use only llvmpipe (guaranteed software, reproducible)
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.x86_64.json ./build/live2d-render --scene ...
```

## Switching to OpenGL

If Vulkan causes problems, the OpenGL build is also available:

```bash
cmake --preset linux          # RENDERER_BACKEND=OpenGL
cmake --build --preset linux
```

The OpenGL build uses EGL (headless) with Mesa's software rasterizer. It is
slightly slower than Vulkan/llvmpipe and does not support GPU passthrough.

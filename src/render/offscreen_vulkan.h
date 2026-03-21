#pragma once
#if !defined(_WIN32) && defined(USE_VULKAN_RENDERER)

#include <vulkan/vulkan.h>
#include <vector>

// Headless offscreen renderer using Vulkan (Mesa DZN / D3D12 backend on WSL2).
// Mirrors the public interface of OffscreenOpenGL so render_loop can use either.
//
// Lifecycle:
//   Init(w, h)           — create Vulkan context + color image + staging buffer
//   BeginFrame()         — signal the Cubism renderer which image to target
//   Clear(r, g, b, a)    — store background colour for compositing in ReadPixels
//   model.Draw(vp)       — Cubism renderer records + submits its own commands
//   ReadPixels(out)      — wait for GPU, copy image → CPU, composite background
//   Release()            — destroy all Vulkan objects
//
// The Cubism Vulkan renderer (CubismRenderer_Vulkan) manages its own command
// buffers internally; this class only owns the Vulkan context and the offscreen
// image.  The depth buffer is created by the Cubism renderer itself.
class OffscreenVulkan {
public:
    ~OffscreenVulkan();

    bool Init(int width, int height);

    // Called once per frame, before model.Draw().
    void BeginFrame();

    // Store background colour.  For transparent output pass (0,0,0,0).
    // For solid background pass (r,g,b,1) — composited in ReadPixels since the
    // Cubism renderer always clears to transparent black internally.
    void Clear(float r, float g, float b, float a);

    // Wait for the previous Draw() to complete, copy the colour image to CPU
    // memory, optionally composite over the stored background colour, and store
    // the result (top-to-bottom, straight RGBA) into `out`.
    bool ReadPixels(std::vector<unsigned char>& out);

    void Release();

    int Width()  const { return _width; }
    int Height() const { return _height; }

    // Exposed to Live2DModel so it can upload textures via the same device.
    VkDevice         Device()         const { return _device; }
    VkPhysicalDevice PhysicalDevice() const { return _physicalDevice; }
    VkCommandPool    CommandPool()    const { return _commandPool; }
    VkQueue          GraphicsQueue()  const { return _graphicsQueue; }

    // Format used for the colour render target (R8G8B8A8_UNORM).
    VkFormat         ColorFormat()    const { return _colorFormat; }
    // Depth/stencil format chosen from device capabilities.
    VkFormat         DepthFormat()    const { return _depthFormat; }

private:
    bool CreateInstance();
    bool PickPhysicalDevice();
    bool CreateDevice();
    bool CreateCommandPool();
    bool CreateColorImage();
    bool CreateStagingBuffer();

    // Find the best supported depth format from a list of candidates.
    VkFormat FindSupportedDepthFormat() const;
    // Find a memory type index matching typeFilter and properties.
    uint32_t FindMemoryType(uint32_t typeFilter, VkMemoryPropertyFlags props) const;

    // Submit a one-shot command buffer and wait for completion.
    bool SubmitAndWait(VkCommandBuffer cmd) const;
    // Allocate a primary command buffer from _commandPool.
    VkCommandBuffer AllocCommandBuffer() const;

    VkInstance       _instance        = VK_NULL_HANDLE;
    VkPhysicalDevice _physicalDevice  = VK_NULL_HANDLE;
    VkDevice         _device          = VK_NULL_HANDLE;
    uint32_t         _graphicsFamily  = 0;
    VkQueue          _graphicsQueue   = VK_NULL_HANDLE;
    VkCommandPool    _commandPool     = VK_NULL_HANDLE;

    // Colour render target (R8G8B8A8_UNORM, device-local).
    VkImage          _colorImage      = VK_NULL_HANDLE;
    VkDeviceMemory   _colorMemory     = VK_NULL_HANDLE;
    VkImageView      _colorView       = VK_NULL_HANDLE;
    VkFormat         _colorFormat     = VK_FORMAT_R8G8B8A8_UNORM;

    // Depth/stencil format (D32_SFLOAT_S8_UINT or D24_UNORM_S8_UINT).
    VkFormat         _depthFormat     = VK_FORMAT_UNDEFINED;

    // Host-visible staging buffer for pixel readback.
    VkBuffer         _stagingBuf      = VK_NULL_HANDLE;
    VkDeviceMemory   _stagingMem      = VK_NULL_HANDLE;

    int   _width  = 0;
    int   _height = 0;

    // Background colour stored by Clear(); used for solid-background compositing.
    float _clearR = 0.f, _clearG = 0.f, _clearB = 0.f, _clearA = 0.f;
};

#endif // !_WIN32 && USE_VULKAN_RENDERER

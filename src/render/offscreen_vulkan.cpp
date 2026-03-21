#if !defined(_WIN32) && defined(USE_VULKAN_RENDERER)

#include "offscreen_vulkan.h"
#include "../cli/logger.h"

#include <Rendering/Vulkan/CubismRenderer_Vulkan.hpp>

#include <cstring>
#include <algorithm>
#include <vector>

using namespace Live2D::Cubism::Framework::Rendering;

// ── Helpers ───────────────────────────────────────────────────────────────────

uint32_t OffscreenVulkan::FindMemoryType(uint32_t typeFilter,
                                         VkMemoryPropertyFlags props) const
{
    VkPhysicalDeviceMemoryProperties memProps;
    vkGetPhysicalDeviceMemoryProperties(_physicalDevice, &memProps);
    for (uint32_t i = 0; i < memProps.memoryTypeCount; ++i) {
        if ((typeFilter & (1u << i)) &&
            (memProps.memoryTypes[i].propertyFlags & props) == props)
            return i;
    }
    Logger::Error("Vulkan: no suitable memory type");
    return UINT32_MAX;
}

VkFormat OffscreenVulkan::FindSupportedDepthFormat() const
{
    const VkFormat candidates[] = {
        VK_FORMAT_D32_SFLOAT_S8_UINT,
        VK_FORMAT_D24_UNORM_S8_UINT,
        VK_FORMAT_D32_SFLOAT,
    };
    for (VkFormat fmt : candidates) {
        VkFormatProperties props;
        vkGetPhysicalDeviceFormatProperties(_physicalDevice, fmt, &props);
        if (props.optimalTilingFeatures & VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT)
            return fmt;
    }
    Logger::Error("Vulkan: no supported depth format");
    return VK_FORMAT_UNDEFINED;
}

VkCommandBuffer OffscreenVulkan::AllocCommandBuffer() const
{
    VkCommandBufferAllocateInfo ai{};
    ai.sType              = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    ai.commandPool        = _commandPool;
    ai.level              = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    ai.commandBufferCount = 1;
    VkCommandBuffer cmd = VK_NULL_HANDLE;
    vkAllocateCommandBuffers(_device, &ai, &cmd);
    return cmd;
}

bool OffscreenVulkan::SubmitAndWait(VkCommandBuffer cmd) const
{
    VkSubmitInfo si{};
    si.sType              = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    si.commandBufferCount = 1;
    si.pCommandBuffers    = &cmd;

    VkFenceCreateInfo fi{};
    fi.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
    VkFence fence = VK_NULL_HANDLE;
    vkCreateFence(_device, &fi, nullptr, &fence);

    vkQueueSubmit(_graphicsQueue, 1, &si, fence);
    vkWaitForFences(_device, 1, &fence, VK_TRUE, UINT64_MAX);
    vkDestroyFence(_device, fence, nullptr);
    vkFreeCommandBuffers(_device, _commandPool, 1, &cmd);
    return true;
}

// ── Init steps ────────────────────────────────────────────────────────────────

bool OffscreenVulkan::CreateInstance()
{
    VkApplicationInfo app{};
    app.sType            = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app.pApplicationName = "live2d-render";
    app.apiVersion       = VK_API_VERSION_1_3;

    // No surface extensions needed for headless rendering.
    VkInstanceCreateInfo ci{};
    ci.sType            = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    ci.pApplicationInfo = &app;

    if (vkCreateInstance(&ci, nullptr, &_instance) != VK_SUCCESS) {
        Logger::Error("Vulkan: vkCreateInstance failed");
        return false;
    }
    return true;
}

bool OffscreenVulkan::PickPhysicalDevice()
{
    uint32_t count = 0;
    vkEnumeratePhysicalDevices(_instance, &count, nullptr);
    if (count == 0) {
        Logger::Error("Vulkan: no physical devices found");
        return false;
    }
    std::vector<VkPhysicalDevice> devices(count);
    vkEnumeratePhysicalDevices(_instance, &count, devices.data());

    // Prefer discrete GPU; otherwise take the first available device.
    _physicalDevice = devices[0];
    for (VkPhysicalDevice d : devices) {
        VkPhysicalDeviceProperties props;
        vkGetPhysicalDeviceProperties(d, &props);
        if (props.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) {
            _physicalDevice = d;
            break;
        }
    }

    VkPhysicalDeviceProperties p;
    vkGetPhysicalDeviceProperties(_physicalDevice, &p);
    Logger::Info("Vulkan: using device \"%s\" (Vulkan %d.%d.%d)",
        p.deviceName,
        VK_VERSION_MAJOR(p.apiVersion),
        VK_VERSION_MINOR(p.apiVersion),
        VK_VERSION_PATCH(p.apiVersion));
    return true;
}

bool OffscreenVulkan::CreateDevice()
{
    // Find a graphics queue family.
    uint32_t qfCount = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(_physicalDevice, &qfCount, nullptr);
    std::vector<VkQueueFamilyProperties> qfs(qfCount);
    vkGetPhysicalDeviceQueueFamilyProperties(_physicalDevice, &qfCount, qfs.data());

    _graphicsFamily = UINT32_MAX;
    for (uint32_t i = 0; i < qfCount; ++i) {
        if (qfs[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) {
            _graphicsFamily = i;
            break;
        }
    }
    if (_graphicsFamily == UINT32_MAX) {
        Logger::Error("Vulkan: no graphics queue family");
        return false;
    }

    const float priority = 1.0f;
    VkDeviceQueueCreateInfo qci{};
    qci.sType            = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
    qci.queueFamilyIndex = _graphicsFamily;
    qci.queueCount       = 1;
    qci.pQueuePriorities = &priority;

    // Required device extensions for CubismRenderer_Vulkan.
    const char* exts[] = {
        VK_KHR_DYNAMIC_RENDERING_EXTENSION_NAME,
        VK_EXT_EXTENDED_DYNAMIC_STATE_EXTENSION_NAME,
    };

    // Enable dynamic rendering and extended dynamic state features.
    VkPhysicalDeviceDynamicRenderingFeaturesKHR dynRendering{};
    dynRendering.sType            = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DYNAMIC_RENDERING_FEATURES_KHR;
    dynRendering.dynamicRendering = VK_TRUE;

    VkPhysicalDeviceExtendedDynamicStateFeaturesEXT extDynState{};
    extDynState.sType                = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTENDED_DYNAMIC_STATE_FEATURES_EXT;
    extDynState.extendedDynamicState = VK_TRUE;
    extDynState.pNext                = &dynRendering;

    VkDeviceCreateInfo dci{};
    dci.sType                   = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
    dci.pNext                   = &extDynState;
    dci.queueCreateInfoCount    = 1;
    dci.pQueueCreateInfos       = &qci;
    dci.enabledExtensionCount   = 2;
    dci.ppEnabledExtensionNames = exts;

    if (vkCreateDevice(_physicalDevice, &dci, nullptr, &_device) != VK_SUCCESS) {
        Logger::Error("Vulkan: vkCreateDevice failed");
        return false;
    }

    vkGetDeviceQueue(_device, _graphicsFamily, 0, &_graphicsQueue);
    return true;
}

bool OffscreenVulkan::CreateCommandPool()
{
    VkCommandPoolCreateInfo ci{};
    ci.sType            = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    ci.flags            = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
    ci.queueFamilyIndex = _graphicsFamily;

    if (vkCreateCommandPool(_device, &ci, nullptr, &_commandPool) != VK_SUCCESS) {
        Logger::Error("Vulkan: vkCreateCommandPool failed");
        return false;
    }
    return true;
}

bool OffscreenVulkan::CreateColorImage()
{
    // Device-local RGBA8 image used as the colour render target.
    VkImageCreateInfo ici{};
    ici.sType         = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    ici.imageType     = VK_IMAGE_TYPE_2D;
    ici.format        = _colorFormat;
    ici.extent        = { (uint32_t)_width, (uint32_t)_height, 1 };
    ici.mipLevels     = 1;
    ici.arrayLayers   = 1;
    ici.samples       = VK_SAMPLE_COUNT_1_BIT;
    ici.tiling        = VK_IMAGE_TILING_OPTIMAL;
    ici.usage         = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT
                      | VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
    ici.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;

    if (vkCreateImage(_device, &ici, nullptr, &_colorImage) != VK_SUCCESS) {
        Logger::Error("Vulkan: vkCreateImage (color) failed");
        return false;
    }

    VkMemoryRequirements mr;
    vkGetImageMemoryRequirements(_device, _colorImage, &mr);

    VkMemoryAllocateInfo mai{};
    mai.sType           = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    mai.allocationSize  = mr.size;
    mai.memoryTypeIndex = FindMemoryType(mr.memoryTypeBits,
                                         VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    if (mai.memoryTypeIndex == UINT32_MAX) return false;

    vkAllocateMemory(_device, &mai, nullptr, &_colorMemory);
    vkBindImageMemory(_device, _colorImage, _colorMemory, 0);

    VkImageViewCreateInfo vci{};
    vci.sType                           = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    vci.image                           = _colorImage;
    vci.viewType                        = VK_IMAGE_VIEW_TYPE_2D;
    vci.format                          = _colorFormat;
    vci.subresourceRange.aspectMask     = VK_IMAGE_ASPECT_COLOR_BIT;
    vci.subresourceRange.levelCount     = 1;
    vci.subresourceRange.layerCount     = 1;

    if (vkCreateImageView(_device, &vci, nullptr, &_colorView) != VK_SUCCESS) {
        Logger::Error("Vulkan: vkCreateImageView (color) failed");
        return false;
    }
    return true;
}

bool OffscreenVulkan::CreateStagingBuffer()
{
    VkDeviceSize size = (VkDeviceSize)_width * _height * 4; // RGBA8

    VkBufferCreateInfo bci{};
    bci.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    bci.size  = size;
    bci.usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT;

    if (vkCreateBuffer(_device, &bci, nullptr, &_stagingBuf) != VK_SUCCESS) {
        Logger::Error("Vulkan: vkCreateBuffer (staging) failed");
        return false;
    }

    VkMemoryRequirements mr;
    vkGetBufferMemoryRequirements(_device, _stagingBuf, &mr);

    VkMemoryAllocateInfo mai{};
    mai.sType           = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    mai.allocationSize  = mr.size;
    mai.memoryTypeIndex = FindMemoryType(mr.memoryTypeBits,
                                         VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                                         VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    if (mai.memoryTypeIndex == UINT32_MAX) return false;

    vkAllocateMemory(_device, &mai, nullptr, &_stagingMem);
    vkBindBufferMemory(_device, _stagingBuf, _stagingMem, 0);
    return true;
}

// ── Public API ────────────────────────────────────────────────────────────────

bool OffscreenVulkan::Init(int width, int height)
{
    _width  = width;
    _height = height;

    if (!CreateInstance())     return false;
    if (!PickPhysicalDevice()) return false;
    if (!CreateDevice())       return false;
    if (!CreateCommandPool())  return false;

    _depthFormat = FindSupportedDepthFormat();
    if (_depthFormat == VK_FORMAT_UNDEFINED) return false;

    if (!CreateColorImage())   return false;
    if (!CreateStagingBuffer()) return false;

    // Tell the Cubism Vulkan renderer about our device and static render target.
    // swapchainImageCount=1 for single-buffered offscreen rendering.
    VkExtent2D extent{ (uint32_t)_width, (uint32_t)_height };
    CubismRenderer_Vulkan::InitializeConstantSettings(
        _device, _physicalDevice, _commandPool, _graphicsQueue,
        /*swapchainImageCount=*/1,
        extent, _colorView, _colorFormat, _depthFormat);

    Logger::Info("Vulkan offscreen: %dx%d RGBA, color=%d depth=%d",
                 width, height, (int)_colorFormat, (int)_depthFormat);
    return true;
}

void OffscreenVulkan::BeginFrame()
{
    // Update the Cubism renderer's static render target reference.
    // Required each frame so s_renderImage/s_imageView/s_renderExtent stay current.
    VkExtent2D extent{ (uint32_t)_width, (uint32_t)_height };
    CubismRenderer_Vulkan::SetRenderTarget(
        _colorImage, _colorView, _colorFormat, extent);
}

void OffscreenVulkan::Clear(float r, float g, float b, float a)
{
    // The Cubism Vulkan renderer always clears to transparent black internally
    // (its _clearColor is private and defaults to {0,0,0,0}).
    // We store the caller's background colour and composite it in ReadPixels.
    _clearR = r;
    _clearG = g;
    _clearB = b;
    _clearA = a;
}

bool OffscreenVulkan::ReadPixels(std::vector<unsigned char>& out)
{
    // Ensure the Cubism renderer's submitted draw commands have finished.
    vkQueueWaitIdle(_graphicsQueue);

    // Transition: GENERAL → TRANSFER_SRC_OPTIMAL, copy image to staging buffer.
    VkCommandBuffer cmd = AllocCommandBuffer();

    VkCommandBufferBeginInfo bi{};
    bi.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    bi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    vkBeginCommandBuffer(cmd, &bi);

    // After EndRendering, the image is in VK_IMAGE_LAYOUT_GENERAL.
    VkImageMemoryBarrier barrier{};
    barrier.sType               = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.srcAccessMask       = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
    barrier.dstAccessMask       = VK_ACCESS_TRANSFER_READ_BIT;
    barrier.oldLayout           = VK_IMAGE_LAYOUT_GENERAL;
    barrier.newLayout           = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    barrier.image               = _colorImage;
    barrier.subresourceRange    = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
    vkCmdPipelineBarrier(cmd,
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
        VK_PIPELINE_STAGE_TRANSFER_BIT,
        0, 0, nullptr, 0, nullptr, 1, &barrier);

    VkBufferImageCopy region{};
    region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    region.imageSubresource.layerCount = 1;
    region.imageExtent                 = { (uint32_t)_width, (uint32_t)_height, 1 };
    vkCmdCopyImageToBuffer(cmd,
        _colorImage, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
        _stagingBuf, 1, &region);

    vkEndCommandBuffer(cmd);
    SubmitAndWait(cmd);

    // Map staging buffer and copy to output.
    const size_t byteCount = (size_t)_width * _height * 4;
    out.resize(byteCount);

    void* mapped = nullptr;
    vkMapMemory(_device, _stagingMem, 0, byteCount, 0, &mapped);
    memcpy(out.data(), mapped, byteCount);
    vkUnmapMemory(_device, _stagingMem);

    // The Cubism renderer outputs premultiplied alpha over a transparent black
    // clear.  For solid backgrounds, composite the stored background colour.
    // (For transparent output the render_loop un-premultiplies after this call.)
    if (_clearA > 0.f) {
        for (size_t i = 0; i < byteCount; i += 4) {
            const float alpha = out[i + 3] / 255.f;
            // src is premultiplied: result = src + bg*(1-alpha)
            out[i + 0] = (unsigned char)std::min(255.f,
                out[i + 0] + _clearR * 255.f * (1.f - alpha));
            out[i + 1] = (unsigned char)std::min(255.f,
                out[i + 1] + _clearG * 255.f * (1.f - alpha));
            out[i + 2] = (unsigned char)std::min(255.f,
                out[i + 2] + _clearB * 255.f * (1.f - alpha));
            out[i + 3] = 255;
        }
    }

    return true;
}

void OffscreenVulkan::Release()
{
    if (_device == VK_NULL_HANDLE) return;

    vkDeviceWaitIdle(_device);

    if (_stagingBuf  != VK_NULL_HANDLE) { vkDestroyBuffer(_device, _stagingBuf, nullptr); _stagingBuf = VK_NULL_HANDLE; }
    if (_stagingMem  != VK_NULL_HANDLE) { vkFreeMemory(_device,   _stagingMem,  nullptr); _stagingMem = VK_NULL_HANDLE; }
    if (_colorView   != VK_NULL_HANDLE) { vkDestroyImageView(_device, _colorView, nullptr); _colorView = VK_NULL_HANDLE; }
    if (_colorImage  != VK_NULL_HANDLE) { vkDestroyImage(_device, _colorImage, nullptr); _colorImage = VK_NULL_HANDLE; }
    if (_colorMemory != VK_NULL_HANDLE) { vkFreeMemory(_device,   _colorMemory, nullptr); _colorMemory = VK_NULL_HANDLE; }
    if (_commandPool != VK_NULL_HANDLE) { vkDestroyCommandPool(_device, _commandPool, nullptr); _commandPool = VK_NULL_HANDLE; }
    if (_device      != VK_NULL_HANDLE) { vkDestroyDevice(_device, nullptr); _device = VK_NULL_HANDLE; }
    if (_instance    != VK_NULL_HANDLE) { vkDestroyInstance(_instance, nullptr); _instance = VK_NULL_HANDLE; }
}

OffscreenVulkan::~OffscreenVulkan()
{
    Release();
}

#endif // !_WIN32 && USE_VULKAN_RENDERER

#include "offscreen_d3d11.h"
#include "../cli/logger.h"
#include <d3dcompiler.h>
#include <dxgi.h>

#define SAFE_RELEASE(x) if (x) { (x)->Release(); (x) = nullptr; }

OffscreenD3D11::~OffscreenD3D11()
{
    Release();
}

bool OffscreenD3D11::Init(int width, int height)
{
    _width  = width;
    _height = height;

    // ── Create device (no window, no swapchain) ───────────────────────────────
    D3D_FEATURE_LEVEL featureLevel;
    UINT createFlags = D3D11_CREATE_DEVICE_BGRA_SUPPORT;  // required for WIC/DirectXTK
#ifdef _DEBUG
    createFlags |= D3D11_CREATE_DEVICE_DEBUG;
#endif

    HRESULT hr = D3D11CreateDevice(
        nullptr,                    // default adapter
        D3D_DRIVER_TYPE_HARDWARE,
        nullptr,
        createFlags,
        nullptr, 0,                 // default feature levels
        D3D11_SDK_VERSION,
        &_device,
        &featureLevel,
        &_context
    );
    if (FAILED(hr)) {
        Logger::Error("D3D11CreateDevice failed: 0x%08X", (unsigned)hr);
        return false;
    }

    // Query adapter name for the info log
    {
        IDXGIDevice*  dxgiDevice  = nullptr;
        IDXGIAdapter* dxgiAdapter = nullptr;
        if (SUCCEEDED(_device->QueryInterface(__uuidof(IDXGIDevice), (void**)&dxgiDevice)) &&
            SUCCEEDED(dxgiDevice->GetAdapter(&dxgiAdapter)))
        {
            DXGI_ADAPTER_DESC desc;
            if (SUCCEEDED(dxgiAdapter->GetDesc(&desc))) {
                char buf[256];
                WideCharToMultiByte(CP_UTF8, 0, desc.Description, -1, buf, sizeof(buf), nullptr, nullptr);
                Logger::Info("Graphics backend: D3D11 (adapter: \"%s\")", buf);
            }
            SAFE_RELEASE(dxgiAdapter);
            SAFE_RELEASE(dxgiDevice);
        }
    }

    // ── Render target texture (RGBA, bindable as RTV + SRV) ──────────────────
    D3D11_TEXTURE2D_DESC rtDesc = {};
    rtDesc.Width            = (UINT)width;
    rtDesc.Height           = (UINT)height;
    rtDesc.MipLevels        = 1;
    rtDesc.ArraySize        = 1;
    rtDesc.Format           = DXGI_FORMAT_R8G8B8A8_UNORM;
    rtDesc.SampleDesc.Count = 1;
    rtDesc.Usage            = D3D11_USAGE_DEFAULT;
    rtDesc.BindFlags        = D3D11_BIND_RENDER_TARGET | D3D11_BIND_SHADER_RESOURCE;

    hr = _device->CreateTexture2D(&rtDesc, nullptr, &_rtTex);
    if (FAILED(hr)) {
        Logger::Error("CreateTexture2D (render target) failed: 0x%08X", (unsigned)hr);
        return false;
    }

    hr = _device->CreateRenderTargetView(_rtTex, nullptr, &_rtv);
    if (FAILED(hr)) {
        Logger::Error("CreateRenderTargetView failed: 0x%08X", (unsigned)hr);
        return false;
    }

    // ── Depth/stencil ─────────────────────────────────────────────────────────
    D3D11_TEXTURE2D_DESC depthDesc = {};
    depthDesc.Width            = (UINT)width;
    depthDesc.Height           = (UINT)height;
    depthDesc.MipLevels        = 1;
    depthDesc.ArraySize        = 1;
    depthDesc.Format           = DXGI_FORMAT_D24_UNORM_S8_UINT;
    depthDesc.SampleDesc.Count = 1;
    depthDesc.Usage            = D3D11_USAGE_DEFAULT;
    depthDesc.BindFlags        = D3D11_BIND_DEPTH_STENCIL;

    hr = _device->CreateTexture2D(&depthDesc, nullptr, &_depthTex);
    if (FAILED(hr)) {
        Logger::Error("CreateTexture2D (depth) failed: 0x%08X", (unsigned)hr);
        return false;
    }

    hr = _device->CreateDepthStencilView(_depthTex, nullptr, &_dsv);
    if (FAILED(hr)) {
        Logger::Error("CreateDepthStencilView failed: 0x%08X", (unsigned)hr);
        return false;
    }

    // Depth disabled (matches the sample)
    D3D11_DEPTH_STENCIL_DESC dsDesc = {};
    dsDesc.DepthEnable    = FALSE;
    dsDesc.DepthWriteMask = D3D11_DEPTH_WRITE_MASK_ALL;
    dsDesc.DepthFunc      = D3D11_COMPARISON_LESS;
    dsDesc.StencilEnable  = FALSE;
    hr = _device->CreateDepthStencilState(&dsDesc, &_depthState);
    if (FAILED(hr)) {
        Logger::Error("CreateDepthStencilState failed: 0x%08X", (unsigned)hr);
        return false;
    }
    _context->OMSetDepthStencilState(_depthState, 0);

    // ── Staging texture for CPU readback ─────────────────────────────────────
    D3D11_TEXTURE2D_DESC stagingDesc = {};
    stagingDesc.Width            = (UINT)width;
    stagingDesc.Height           = (UINT)height;
    stagingDesc.MipLevels        = 1;
    stagingDesc.ArraySize        = 1;
    stagingDesc.Format           = DXGI_FORMAT_R8G8B8A8_UNORM;
    stagingDesc.SampleDesc.Count = 1;
    stagingDesc.Usage            = D3D11_USAGE_STAGING;
    stagingDesc.CPUAccessFlags   = D3D11_CPU_ACCESS_READ;

    hr = _device->CreateTexture2D(&stagingDesc, nullptr, &_staging);
    if (FAILED(hr)) {
        Logger::Error("CreateTexture2D (staging) failed: 0x%08X", (unsigned)hr);
        return false;
    }

    // ── Viewport ──────────────────────────────────────────────────────────────
    D3D11_VIEWPORT vp = {};
    vp.Width    = (FLOAT)width;
    vp.Height   = (FLOAT)height;
    vp.MaxDepth = 1.0f;
    _context->RSSetViewports(1, &vp);

    Logger::Info("Render target: %dx%d RGBA, offscreen", width, height);
    Logger::Debug("Offscreen framebuffer allocated: %dx%dx4 = %.1f MB",
                  width, height, (width * height * 4) / (1024.0 * 1024.0));

    return true;
}

void OffscreenD3D11::BeginFrame()
{
    _context->OMSetRenderTargets(1, &_rtv, _dsv);
}

void OffscreenD3D11::Clear(float r, float g, float b, float a)
{
    const FLOAT color[4] = { r, g, b, a };
    _context->ClearRenderTargetView(_rtv, color);
    _context->ClearDepthStencilView(_dsv, D3D11_CLEAR_DEPTH | D3D11_CLEAR_STENCIL, 1.0f, 0);
}

bool OffscreenD3D11::ReadPixels(std::vector<unsigned char>& out) const
{
    _context->CopyResource(_staging, _rtTex);

    D3D11_MAPPED_SUBRESOURCE mapped;
    HRESULT hr = _context->Map(_staging, 0, D3D11_MAP_READ, 0, &mapped);
    if (FAILED(hr)) {
        Logger::Error("Map staging texture failed: 0x%08X", (unsigned)hr);
        return false;
    }

    out.resize((size_t)_width * _height * 4);
    const UINT rowBytes = (UINT)_width * 4;
    const unsigned char* src = static_cast<const unsigned char*>(mapped.pData);
    unsigned char* dst = out.data();

    for (int y = 0; y < _height; ++y) {
        memcpy(dst + y * rowBytes, src + y * mapped.RowPitch, rowBytes);
    }

    _context->Unmap(_staging, 0);
    return true;
}

void OffscreenD3D11::Release()
{
    SAFE_RELEASE(_staging);
    SAFE_RELEASE(_depthState);
    SAFE_RELEASE(_dsv);
    SAFE_RELEASE(_depthTex);
    SAFE_RELEASE(_rtv);
    SAFE_RELEASE(_rtTex);
    SAFE_RELEASE(_context);
    SAFE_RELEASE(_device);
}

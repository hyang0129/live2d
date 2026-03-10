#pragma once
#include <d3d11.h>
#include <dxgi.h>
#include <string>
#include <vector>

class OffscreenD3D11 {
public:
    ~OffscreenD3D11();

    // Creates a D3D11 device (no window, no swapchain) and an offscreen RGBA
    // render target at the given dimensions.
    // Returns false on failure (error logged to stderr).
    bool Init(int width, int height);

    // Reads back the current render target contents to an RGBA byte buffer.
    // Buffer is resized to width * height * 4 bytes.
    bool ReadPixels(std::vector<unsigned char>& out) const;

    void Release();

    ID3D11Device*        Device()  const { return _device; }
    ID3D11DeviceContext* Context() const { return _context; }
    ID3D11RenderTargetView* RTV()  const { return _rtv; }
    int Width()  const { return _width; }
    int Height() const { return _height; }

    // Bind the offscreen RTV + depth as the active render target
    void BeginFrame();
    // Clear the render target (r,g,b,a = 0 for transparent)
    void Clear(float r, float g, float b, float a);

private:
    ID3D11Device*            _device   = nullptr;
    ID3D11DeviceContext*     _context  = nullptr;
    ID3D11Texture2D*         _rtTex    = nullptr;
    ID3D11RenderTargetView*  _rtv      = nullptr;
    ID3D11Texture2D*         _depthTex = nullptr;
    ID3D11DepthStencilView*  _dsv      = nullptr;
    ID3D11Texture2D*         _staging  = nullptr;  // CPU readback
    ID3D11DepthStencilState* _depthState = nullptr;
    int _width = 0, _height = 0;
};

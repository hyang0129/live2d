#pragma once
#ifndef _WIN32

#include <EGL/egl.h>
#include <GL/glew.h>
#include <vector>

// Headless offscreen renderer using EGL + OpenGL FBO.
// Mirrors the interface of OffscreenD3D11 so render_loop can use either.
class OffscreenOpenGL {
public:
    ~OffscreenOpenGL();

    // Creates a surfaceless EGL context (Mesa EGL_PLATFORM_SURFACELESS or
    // EGL_DEFAULT_DISPLAY fallback) and an RGBA FBO at the given dimensions.
    // Returns false on failure (error logged to stderr).
    bool Init(int width, int height);

    // Reads back the current FBO contents to an RGBA byte buffer (top-to-bottom).
    // OpenGL origin is bottom-left, so rows are flipped during readback.
    bool ReadPixels(std::vector<unsigned char>& out) const;

    void Release();

    int Width()  const { return _width; }
    int Height() const { return _height; }

    // Bind the FBO as the active render target and set the viewport.
    void BeginFrame();
    // Clear colour + depth + stencil.
    void Clear(float r, float g, float b, float a);

private:
    EGLDisplay _eglDisplay = EGL_NO_DISPLAY;
    EGLSurface _eglSurface = EGL_NO_SURFACE;
    EGLContext _eglContext = EGL_NO_CONTEXT;

    GLuint _fbo      = 0;
    GLuint _colorTex = 0;
    GLuint _depthRbo = 0;

    int _width  = 0;
    int _height = 0;
};

#endif // !_WIN32

#ifndef _WIN32

#include "offscreen_opengl.h"
#include "../cli/logger.h"

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GL/glew.h>
#include <cstring>

// ── EGL context helpers ───────────────────────────────────────────────────────

// Try Mesa's surfaceless platform first (works in containers / WSL with no
// display).  Fall back to EGL_DEFAULT_DISPLAY which works when a real display
// or software Mesa is available.
static EGLDisplay TryGetHeadlessDisplay()
{
    const char* client_exts = eglQueryString(EGL_NO_DISPLAY, EGL_EXTENSIONS);
    if (client_exts && strstr(client_exts, "EGL_MESA_platform_surfaceless")) {
        auto fn = reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(
            eglGetProcAddress("eglGetPlatformDisplayEXT"));
        if (fn) {
            EGLDisplay d = fn(EGL_PLATFORM_SURFACELESS_MESA,
                              EGL_DEFAULT_DISPLAY, nullptr);
            if (d != EGL_NO_DISPLAY) {
                Logger::Info("EGL: using surfaceless Mesa platform");
                return d;
            }
        }
    }
    return eglGetDisplay(EGL_DEFAULT_DISPLAY);
}

// ── OffscreenOpenGL ───────────────────────────────────────────────────────────

OffscreenOpenGL::~OffscreenOpenGL()
{
    Release();
}

bool OffscreenOpenGL::Init(int width, int height)
{
    _width  = width;
    _height = height;

    // ── EGL display ───────────────────────────────────────────────────────
    _eglDisplay = TryGetHeadlessDisplay();
    if (_eglDisplay == EGL_NO_DISPLAY) {
        Logger::Error("EGL: no display available (0x%x)", eglGetError());
        return false;
    }

    EGLint major = 0, minor = 0;
    if (!eglInitialize(_eglDisplay, &major, &minor)) {
        Logger::Error("EGL: eglInitialize failed (0x%x)", eglGetError());
        return false;
    }
    Logger::Info("EGL %d.%d initialized", major, minor);

    if (!eglBindAPI(EGL_OPENGL_API)) {
        Logger::Error("EGL: eglBindAPI(EGL_OPENGL_API) failed (0x%x)", eglGetError());
        return false;
    }

    // ── EGL config ────────────────────────────────────────────────────────
    const EGLint cfg_attrs[] = {
        EGL_SURFACE_TYPE,    EGL_PBUFFER_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT,
        EGL_RED_SIZE,        8,
        EGL_GREEN_SIZE,      8,
        EGL_BLUE_SIZE,       8,
        EGL_ALPHA_SIZE,      8,
        EGL_DEPTH_SIZE,      24,
        EGL_NONE
    };
    EGLConfig cfg;
    EGLint    num_cfg = 0;
    if (!eglChooseConfig(_eglDisplay, cfg_attrs, &cfg, 1, &num_cfg) || num_cfg == 0) {
        Logger::Error("EGL: no suitable config (0x%x)", eglGetError());
        return false;
    }

    // ── Minimal 1×1 pbuffer (rendering goes to our FBO, not the surface) ──
    const EGLint pb_attrs[] = { EGL_WIDTH, 1, EGL_HEIGHT, 1, EGL_NONE };
    _eglSurface = eglCreatePbufferSurface(_eglDisplay, cfg, pb_attrs);
    if (_eglSurface == EGL_NO_SURFACE) {
        Logger::Error("EGL: eglCreatePbufferSurface failed (0x%x)", eglGetError());
        return false;
    }

    // ── OpenGL 3.3 Compatibility profile context ──────────────────────────
    // The Cubism Framework shaders use GLSL 1.20 syntax (attribute, varying,
    // gl_FragColor) which is not available in the Core profile.
    // EGL_CONTEXT_OPENGL_PROFILE_MASK_KHR = 0x30FD
    // EGL_CONTEXT_OPENGL_COMPATIBILITY_PROFILE_BIT_KHR = 0x00000002
    const EGLint ctx_attrs[] = {
        EGL_CONTEXT_MAJOR_VERSION, 3,
        EGL_CONTEXT_MINOR_VERSION, 3,
        0x30FD, 0x00000002,  // KHR_create_context: compatibility profile
        EGL_NONE
    };
    _eglContext = eglCreateContext(_eglDisplay, cfg, EGL_NO_CONTEXT, ctx_attrs);
    if (_eglContext == EGL_NO_CONTEXT) {
        Logger::Error("EGL: eglCreateContext failed (0x%x)", eglGetError());
        return false;
    }

    if (!eglMakeCurrent(_eglDisplay, _eglSurface, _eglSurface, _eglContext)) {
        Logger::Error("EGL: eglMakeCurrent failed (0x%x)", eglGetError());
        return false;
    }

    // ── GLEW (required by Cubism Framework OpenGL renderer) ───────────────
    glewExperimental = GL_TRUE;
    GLenum glew_err = glewInit();
    if (glew_err != GLEW_OK) {
        Logger::Error("GLEW init failed: %s",
                      reinterpret_cast<const char*>(glewGetErrorString(glew_err)));
        return false;
    }
    Logger::Info("Graphics backend: OpenGL %s",
                 reinterpret_cast<const char*>(glGetString(GL_VERSION)));

    // ── Framebuffer object ────────────────────────────────────────────────
    glGenFramebuffers(1, &_fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, _fbo);

    // Color texture (RGBA8)
    glGenTextures(1, &_colorTex);
    glBindTexture(GL_TEXTURE_2D, _colorTex);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8,
                 width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                           GL_TEXTURE_2D, _colorTex, 0);

    // Depth + stencil renderbuffer
    glGenRenderbuffers(1, &_depthRbo);
    glBindRenderbuffer(GL_RENDERBUFFER, _depthRbo);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, width, height);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT,
                              GL_RENDERBUFFER, _depthRbo);

    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        Logger::Error("OpenGL: framebuffer incomplete");
        return false;
    }

    glViewport(0, 0, width, height);
    Logger::Info("Render target: %dx%d RGBA, offscreen (FBO)", width, height);
    Logger::Debug("Offscreen framebuffer allocated: %dx%dx4 = %.1f MB",
                  width, height, (width * height * 4) / (1024.0 * 1024.0));
    return true;
}

void OffscreenOpenGL::BeginFrame()
{
    glBindFramebuffer(GL_FRAMEBUFFER, _fbo);
    glViewport(0, 0, _width, _height);
}

void OffscreenOpenGL::Clear(float r, float g, float b, float a)
{
    glClearColor(r, g, b, a);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT | GL_STENCIL_BUFFER_BIT);
}

bool OffscreenOpenGL::ReadPixels(std::vector<unsigned char>& out) const
{
    const size_t rowBytes = static_cast<size_t>(_width) * 4;
    out.resize(rowBytes * static_cast<size_t>(_height));

    glBindFramebuffer(GL_FRAMEBUFFER, _fbo);
    // glReadPixels stores rows bottom-to-top; flip to top-to-bottom for FFmpeg
    glReadPixels(0, 0, _width, _height, GL_RGBA, GL_UNSIGNED_BYTE, out.data());

    std::vector<unsigned char> tmp(rowBytes);
    for (int y = 0; y < _height / 2; ++y) {
        unsigned char* top = out.data() + y * rowBytes;
        unsigned char* bot = out.data() + (_height - 1 - y) * rowBytes;
        memcpy(tmp.data(), top, rowBytes);
        memcpy(top,        bot, rowBytes);
        memcpy(bot,        tmp.data(), rowBytes);
    }
    return true;
}

void OffscreenOpenGL::Release()
{
    if (_fbo)      { glDeleteFramebuffers(1,  &_fbo);      _fbo = 0; }
    if (_colorTex) { glDeleteTextures(1,       &_colorTex); _colorTex = 0; }
    if (_depthRbo) { glDeleteRenderbuffers(1,  &_depthRbo); _depthRbo = 0; }

    if (_eglDisplay != EGL_NO_DISPLAY) {
        eglMakeCurrent(_eglDisplay,
                       EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (_eglContext != EGL_NO_CONTEXT) {
            eglDestroyContext(_eglDisplay, _eglContext);
            _eglContext = EGL_NO_CONTEXT;
        }
        if (_eglSurface != EGL_NO_SURFACE) {
            eglDestroySurface(_eglDisplay, _eglSurface);
            _eglSurface = EGL_NO_SURFACE;
        }
        eglTerminate(_eglDisplay);
        _eglDisplay = EGL_NO_DISPLAY;
    }
}

#endif // !_WIN32

#pragma once
// Minimal GLEW compatibility shim for EGL/Mesa headless builds.
//
// The system libGLEW is compiled for GLX only and fails to initialize when
// using an EGL context without a real X11 display.  On Mesa/Linux all
// OpenGL 3.3 core functions are exported directly from libGL.so, so no
// runtime extension loading is needed.  This shim provides the GLEW API
// surface the Cubism Framework expects while delegating to the standard
// OpenGL headers for function declarations.

#ifndef __glew_h__
#define __glew_h__

// Declare all GL 3.3+ prototypes directly from the OS headers.
#ifndef GL_GLEXT_PROTOTYPES
#  define GL_GLEXT_PROTOTYPES 1
#endif
#include <GL/gl.h>
#include <GL/glext.h>

// ── GLEW API compatibility surface ───────────────────────────────────────────

typedef unsigned int GLenum;  // may already be defined — that's fine

#define GLEW_OK 0

// glewInit() is a no-op: all functions are available via libGL.so directly.
inline unsigned int glewInit() { return GLEW_OK; }
inline const unsigned char* glewGetString(unsigned int)      { return (const unsigned char*)"2.2.0 (shim)"; }
inline const unsigned char* glewGetErrorString(unsigned int) { return (const unsigned char*)""; }

// glewExperimental — our code sets this; make it a mutable inline variable.
inline GLboolean glewExperimental = GL_FALSE;

// Version support flags expected by the Cubism Framework
#define GLEW_VERSION_1_1 1
#define GLEW_VERSION_1_2 1
#define GLEW_VERSION_1_3 1
#define GLEW_VERSION_1_4 1
#define GLEW_VERSION_1_5 1
#define GLEW_VERSION_2_0 1
#define GLEW_VERSION_2_1 1
#define GLEW_VERSION_3_0 1
#define GLEW_VERSION_3_1 1
#define GLEW_VERSION_3_2 1
#define GLEW_VERSION_3_3 1

#endif // __glew_h__

cmake_minimum_required(VERSION 3.16)
project(live2d-render CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── Paths ──────────────────────────────────────────────────────────────────────
set(SDK_ROOT       ${CMAKE_CURRENT_SOURCE_DIR}/cubism)
set(CORE_PATH      ${SDK_ROOT}/Core)
set(FRAMEWORK_PATH ${SDK_ROOT}/Framework)
set(COMMON_PATH    ${SDK_ROOT}/Samples/Common)

# ── nlohmann/json (FetchContent) ──────────────────────────────────────────────
include(FetchContent)
FetchContent_Declare(
  nlohmann_json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG        v3.11.3
)
FetchContent_MakeAvailable(nlohmann_json)

# ── Platform-specific setup ────────────────────────────────────────────────────
if(WIN32)

  # ── Windows / D3D11 ─────────────────────────────────────────────────────────
  set(DX_PATH ${SDK_ROOT}/Samples/D3D11/thirdParty/DirectXTK)

  if(CMAKE_EXE_LINKER_FLAGS STREQUAL "/machine:x64")
    set(ARCH x86_64)
    set(DX_ARCH x64)
  elseif(CMAKE_EXE_LINKER_FLAGS STREQUAL "/machine:X86")
    set(ARCH x86)
    set(DX_ARCH Win32)
  else()
    set(ARCH x86_64)
    set(DX_ARCH x64)
  endif()

  if(MSVC_VERSION MATCHES 1900)
    set(COMPILER 140)
    set(MSVC_YEAR 2015)
  elseif(MSVC_VERSION GREATER_EQUAL 1910 AND MSVC_VERSION LESS 1920)
    set(COMPILER 141)
    set(MSVC_YEAR 2017)
  elseif(MSVC_VERSION GREATER_EQUAL 1920 AND MSVC_VERSION LESS 1930)
    set(COMPILER 142)
    set(MSVC_YEAR 2019)
  elseif(MSVC_VERSION GREATER_EQUAL 1930 AND MSVC_VERSION LESS 1950)
    set(COMPILER 143)
    set(MSVC_YEAR 2022)
  else()
    set(COMPILER 143)
    set(MSVC_YEAR 2022)
  endif()

  option(CORE_CRL_MD "Use MD CRT variant of Cubism Core" OFF)
  if(CORE_CRL_MD)
    set(CRT MD)
  else()
    set(CRT MT)
  endif()

  add_library(Live2DCubismCore STATIC IMPORTED)
  set(CORE_LIB_SUFFIX ${CORE_PATH}/lib/windows/${ARCH}/${COMPILER})
  set_target_properties(Live2DCubismCore PROPERTIES
    IMPORTED_LOCATION_DEBUG   ${CORE_LIB_SUFFIX}/Live2DCubismCore_${CRT}d.lib
    IMPORTED_LOCATION_RELEASE ${CORE_LIB_SUFFIX}/Live2DCubismCore_${CRT}.lib
    INTERFACE_INCLUDE_DIRECTORIES ${CORE_PATH}/include
  )

  set(FRAMEWORK_SOURCE D3D11)
  add_subdirectory(${FRAMEWORK_PATH} ${CMAKE_CURRENT_BINARY_DIR}/Framework)
  target_include_directories(Framework PUBLIC ${DX_PATH}/Inc)
  target_link_libraries(Framework
    Live2DCubismCore
    ${DX_PATH}/Bin/Desktop_${MSVC_YEAR}/${DX_ARCH}/$<CONFIG>/DirectXTK.lib
    d3d11.lib
    d3dcompiler.lib
  )

elseif(RENDERER_BACKEND STREQUAL "Vulkan")

  # ── Linux / Vulkan (Mesa DZN headless) ───────────────────────────────────────
  add_library(Live2DCubismCore STATIC IMPORTED)
  set_target_properties(Live2DCubismCore PROPERTIES
    IMPORTED_LOCATION             ${CORE_PATH}/lib/linux/x86_64/libLive2DCubismCore.a
    INTERFACE_INCLUDE_DIRECTORIES ${CORE_PATH}/include
  )

  find_package(Vulkan REQUIRED)

  set(FRAMEWORK_SOURCE Vulkan)
  add_subdirectory(${FRAMEWORK_PATH} ${CMAKE_CURRENT_BINARY_DIR}/Framework)
  target_link_libraries(Framework Live2DCubismCore ${Vulkan_LIBRARIES})
  target_include_directories(Framework PUBLIC ${Vulkan_INCLUDE_DIRS})

  # Compile Vulkan GLSL shaders to SPIR-V (uses glslc wrapper → glslangValidator)
  add_subdirectory(
    ${FRAMEWORK_PATH}/src/Rendering/Vulkan/Shaders
    ${CMAKE_CURRENT_BINARY_DIR}/FrameworkShaders)
  add_dependencies(Framework FrameworkShaders)

  # Propagate backend flag to all translation units
  add_compile_definitions(USE_VULKAN_RENDERER)

else()

  # ── Linux / OpenGL ───────────────────────────────────────────────────────────
  add_library(Live2DCubismCore STATIC IMPORTED)
  set_target_properties(Live2DCubismCore PROPERTIES
    IMPORTED_LOCATION             ${CORE_PATH}/lib/linux/x86_64/libLive2DCubismCore.a
    INTERFACE_INCLUDE_DIRECTORIES ${CORE_PATH}/include
  )

  find_package(OpenGL REQUIRED)

  # Use a thin GLEW shim that maps to libGL.so directly.
  # The system libGLEW is compiled for GLX only and fails with EGL contexts.
  # On Mesa/Linux all GL 3.3 core functions are available in libGL.so without
  # any runtime extension loading, so the shim is sufficient.
  set(GL_COMPAT_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src/gl_compat)

  set(FRAMEWORK_SOURCE OpenGL)
  add_subdirectory(${FRAMEWORK_PATH} ${CMAKE_CURRENT_BINARY_DIR}/Framework)
  target_compile_definitions(Framework PUBLIC CSM_TARGET_LINUX_GL)
  # Shim directory must come before system include paths so our GL/glew.h
  # is found instead of the real one.
  target_include_directories(Framework BEFORE PUBLIC ${GL_COMPAT_DIR})
  target_link_libraries(Framework Live2DCubismCore OpenGL::GL)

endif()

# ── Common sample sources (allocator only) ─────────────────────────────────────
add_library(SampleCommon STATIC
  ${COMMON_PATH}/LAppAllocator_Common.cpp
)
target_include_directories(SampleCommon PUBLIC
  ${COMMON_PATH}
  ${FRAMEWORK_PATH}/src
  ${CORE_PATH}/include
)
target_link_libraries(SampleCommon PUBLIC Framework)

# ── Main executable ───────────────────────────────────────────────────────────
add_executable(live2d-render)
add_subdirectory(src)

if(WIN32)
  target_link_libraries(live2d-render PRIVATE
    Framework
    SampleCommon
    nlohmann_json::nlohmann_json
    d3d11.lib
    dxgi.lib
    d3dcompiler.lib
    winmm.lib
    windowscodecs.lib
    debug     -NODEFAULTLIB:libcmtd.lib
    optimized -NODEFAULTLIB:libcmt.lib
  )
  target_compile_options(live2d-render PRIVATE /MP)
  add_custom_command(TARGET live2d-render POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
      ${FRAMEWORK_PATH}/src/Rendering/D3D11/Shaders
      ${CMAKE_SOURCE_DIR}/FrameworkShaders
  )
  set_target_properties(live2d-render PROPERTIES
    VS_DEBUGGER_WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
  )
elseif(RENDERER_BACKEND STREQUAL "Vulkan")
  target_link_libraries(live2d-render PRIVATE
    Framework
    SampleCommon
    nlohmann_json::nlohmann_json
    ${Vulkan_LIBRARIES}
  )
  # Shader SPIRVs are copied at configure-time by the FrameworkShaders target.
  # The runtime binary looks for FrameworkShaders/ relative to its CWD (repo root).
  add_custom_command(TARGET live2d-render POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
      ${CMAKE_CURRENT_BINARY_DIR}/FrameworkShaders/compiledShaders
      ${CMAKE_SOURCE_DIR}/FrameworkShaders
  )
else()
  target_link_libraries(live2d-render PRIVATE
    Framework
    SampleCommon
    nlohmann_json::nlohmann_json
    OpenGL::GL
    EGL
  )
  add_custom_command(TARGET live2d-render POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
      ${FRAMEWORK_PATH}/src/Rendering/OpenGL/Shaders/Standard
      ${CMAKE_SOURCE_DIR}/FrameworkShaders
  )
endif()

# Suppress ZERO_CHECK
set(CMAKE_SUPPRESS_REGENERATION ON)
if(WIN32)
  set_property(DIRECTORY PROPERTY VS_STARTUP_PROJECT live2d-render)
endif()

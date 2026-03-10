cmake_minimum_required(VERSION 3.16)
project(live2d-render CXX)

option(CORE_CRL_MD "Use MD CRT variant of Cubism Core" OFF)
option(RENDERER_BACKEND "Graphics backend: D3D11" "D3D11")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── Paths ──────────────────────────────────────────────────────────────────────
set(SDK_ROOT       ${CMAKE_CURRENT_SOURCE_DIR}/cubism)
set(CORE_PATH      ${SDK_ROOT}/Core)
set(FRAMEWORK_PATH ${SDK_ROOT}/Framework)
set(COMMON_PATH    ${SDK_ROOT}/Samples/Common)
set(DX_PATH        ${SDK_ROOT}/Samples/D3D11/thirdParty/DirectXTK)
set(FRAMEWORK_SHADER_PATH ${FRAMEWORK_PATH}/src/Rendering/D3D11/Shaders)

# ── Detect compiler/arch (mirrors sample CMakeLists) ─────────────────────────
if(CMAKE_EXE_LINKER_FLAGS STREQUAL "/machine:x64")
  set(ARCH x86_64)
  set(DX_ARCH x64)
elseif(CMAKE_EXE_LINKER_FLAGS STREQUAL "/machine:X86")
  set(ARCH x86)
  set(DX_ARCH Win32)
else()
  # Default to x64 when cmake-gui or VS generator sets it automatically
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

if(CORE_CRL_MD)
  set(CRT MD)
else()
  set(CRT MT)
endif()

# ── Cubism Core (static import) ───────────────────────────────────────────────
add_library(Live2DCubismCore STATIC IMPORTED)
set(CORE_LIB_SUFFIX ${CORE_PATH}/lib/windows/${ARCH}/${COMPILER})
set_target_properties(Live2DCubismCore PROPERTIES
  IMPORTED_LOCATION_DEBUG   ${CORE_LIB_SUFFIX}/Live2DCubismCore_${CRT}d.lib
  IMPORTED_LOCATION_RELEASE ${CORE_LIB_SUFFIX}/Live2DCubismCore_${CRT}.lib
  INTERFACE_INCLUDE_DIRECTORIES ${CORE_PATH}/include
)

# ── Cubism Framework ──────────────────────────────────────────────────────────
set(FRAMEWORK_SOURCE D3D11)
add_subdirectory(${FRAMEWORK_PATH} ${CMAKE_CURRENT_BINARY_DIR}/Framework)
target_include_directories(Framework PUBLIC ${DX_PATH}/Inc)
target_link_libraries(Framework
  Live2DCubismCore
  ${DX_PATH}/Bin/Desktop_${MSVC_YEAR}/${DX_ARCH}/$<CONFIG>/DirectXTK.lib
  d3d11.lib
  d3dcompiler.lib
)

# ── nlohmann/json (FetchContent) ──────────────────────────────────────────────
include(FetchContent)
FetchContent_Declare(
  nlohmann_json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG        v3.11.3
)
FetchContent_MakeAvailable(nlohmann_json)

# ── Common sample sources (allocator only — we override model I/O directly) ───
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

target_link_libraries(live2d-render PRIVATE
  Framework
  SampleCommon
  nlohmann_json::nlohmann_json
  d3d11.lib
  dxgi.lib
  d3dcompiler.lib
  winmm.lib
  windowscodecs.lib
  debug   -NODEFAULTLIB:libcmtd.lib
  optimized -NODEFAULTLIB:libcmt.lib
)

target_compile_options(live2d-render PRIVATE /MP)

# ── Post-build: copy Framework shaders ───────────────────────────────────────
add_custom_command(TARGET live2d-render POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_directory
    ${FRAMEWORK_SHADER_PATH}
    ${CMAKE_SOURCE_DIR}/FrameworkShaders
)

set_target_properties(live2d-render PROPERTIES
  VS_DEBUGGER_WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)

# Suppress ZERO_CHECK
set(CMAKE_SUPPRESS_REGENERATION ON)
set_property(DIRECTORY PROPERTY VS_STARTUP_PROJECT live2d-render)

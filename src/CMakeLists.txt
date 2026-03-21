target_sources(live2d-render PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/main.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/allocator.cpp

  ${CMAKE_CURRENT_SOURCE_DIR}/cli/logger.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/cli/args.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/cli/manifest.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/cli/model_resolver.cpp

  ${CMAKE_CURRENT_SOURCE_DIR}/render/renderer_config.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/render/lipsync_sequencer.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/render/cue_sequencer.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/render/live2d_model.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/render/ffmpeg_encoder.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/render/render_loop.cpp
)

if(WIN32)
  target_sources(live2d-render PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/render/offscreen_d3d11.cpp
  )
  target_include_directories(live2d-render PRIVATE
    ${CMAKE_SOURCE_DIR}/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc
  )
elseif(RENDERER_BACKEND STREQUAL "Vulkan")
  target_sources(live2d-render PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/render/offscreen_vulkan.cpp
  )
  target_include_directories(live2d-render PRIVATE
    ${Vulkan_INCLUDE_DIRS}
    ${CMAKE_SOURCE_DIR}/cubism/Samples/Vulkan/thirdParty/stb
  )
else()
  target_sources(live2d-render PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/render/offscreen_opengl.cpp
  )
  target_include_directories(live2d-render BEFORE PRIVATE
    ${CMAKE_SOURCE_DIR}/src/gl_compat
  )
  target_include_directories(live2d-render PRIVATE
    ${CMAKE_SOURCE_DIR}/cubism/Samples/OpenGL/thirdParty/stb
  )
endif()

target_include_directories(live2d-render PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${CMAKE_SOURCE_DIR}/cubism/Framework/src
  ${CMAKE_SOURCE_DIR}/cubism/Core/include
  ${CMAKE_SOURCE_DIR}/cubism/Samples/Common
)

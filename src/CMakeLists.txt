target_sources(live2d-render PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/main.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/allocator.cpp

  ${CMAKE_CURRENT_SOURCE_DIR}/cli/logger.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/cli/args.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/cli/manifest.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/cli/model_resolver.cpp

  ${CMAKE_CURRENT_SOURCE_DIR}/render/lipsync_sequencer.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/render/cue_sequencer.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/render/live2d_model.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/render/offscreen_d3d11.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/render/ffmpeg_encoder.cpp
  ${CMAKE_CURRENT_SOURCE_DIR}/render/render_loop.cpp
)

target_include_directories(live2d-render PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${CMAKE_SOURCE_DIR}/cubism/Framework/src
  ${CMAKE_SOURCE_DIR}/cubism/Core/include
  ${CMAKE_SOURCE_DIR}/cubism/Samples/Common
  ${CMAKE_SOURCE_DIR}/cubism/Samples/D3D11/thirdParty/DirectXTK/Inc
)

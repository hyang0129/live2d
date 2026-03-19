#pragma once
#include "../cli/manifest.h"
#include "live2d_model.h"
#include "ffmpeg_encoder.h"
#include "lipsync_sequencer.h"
#include "cue_sequencer.h"

#ifdef _WIN32
#  include "offscreen_d3d11.h"
   using OffscreenRenderer = OffscreenD3D11;
#else
#  include "offscreen_opengl.h"
   using OffscreenRenderer = OffscreenOpenGL;
#endif

// Drives the deterministic frame loop and wires all rendering components together.
// scene_tail_duration: idle seconds appended after the last cue/lipsync event.
// Returns false on any render or encode failure.
bool RunRenderLoop(const SceneManifest& manifest,
                   Live2DModel&         model,
                   OffscreenRenderer&   offscreen,
                   FfmpegEncoder&       encoder,
                   LipsyncSequencer&    lipsync,
                   CueSequencer&        cues,
                   float                scene_tail_duration = 1.0f);

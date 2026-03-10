#pragma once
#include "../cli/manifest.h"
#include "live2d_model.h"
#include "offscreen_d3d11.h"
#include "ffmpeg_encoder.h"
#include "lipsync_sequencer.h"
#include "cue_sequencer.h"

// Drives the deterministic frame loop and wires all rendering components together.
// Returns false on any render or encode failure.
bool RunRenderLoop(const SceneManifest& manifest,
                   Live2DModel&         model,
                   OffscreenD3D11&      offscreen,
                   FfmpegEncoder&       encoder,
                   LipsyncSequencer&    lipsync,
                   CueSequencer&        cues);

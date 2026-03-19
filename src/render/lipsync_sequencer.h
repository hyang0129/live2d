#pragma once
#include <vector>
#include "../cli/manifest.h"
#include "renderer_config.h"

struct MouthState {
    float open = 0.0f;  // ParamMouthOpenY  [0,1]
    float form = 0.0f;  // ParamMouthForm   [-1,1]
};

class LipsyncSequencer {
public:
    // Apply lipsync config (shape map, smoothing). Call before Load().
    void SetLipsyncConfig(const LipsyncConfig& cfg);

    void Load(const std::vector<LipsyncKeyframe>& keyframes);
    MouthState Evaluate(float time_sec) const;

private:
    struct Frame {
        float     time;
        MouthState state;
    };
    std::vector<Frame> _frames;
    LipsyncConfig _lipsyncCfg;  // shape map used during Load()

    MouthState ShapeToState(char shape) const;
    static MouthState Lerp(const MouthState& a, const MouthState& b, float t);
};

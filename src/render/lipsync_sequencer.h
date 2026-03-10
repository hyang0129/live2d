#pragma once
#include <vector>
#include "../cli/manifest.h"

struct MouthState {
    float open = 0.0f;  // ParamMouthOpenY  [0,1]
    float form = 0.0f;  // ParamMouthForm   [-1,1]
};

class LipsyncSequencer {
public:
    void Load(const std::vector<LipsyncKeyframe>& keyframes);
    MouthState Evaluate(float time_sec) const;

private:
    struct Frame {
        float     time;
        MouthState state;
    };
    std::vector<Frame> _frames;

    static MouthState ShapeToState(char shape);
    static MouthState Lerp(const MouthState& a, const MouthState& b, float t);
};

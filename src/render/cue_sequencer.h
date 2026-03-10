#pragma once
#include <vector>
#include <map>
#include <functional>
#include "../cli/manifest.h"

// Per-frame state derived from dispatched cues
struct CueState {
    std::string emotion;          // last dispatched emotion alias
    float       gaze_x = 0.0f;
    float       gaze_y = 0.0f;
    float       head_yaw   = 0.0f;
    float       head_pitch = 0.0f;
    float       head_roll  = 0.0f;
};

class CueSequencer {
public:
    // emotion_aliases: director alias → raw model expression name
    // reaction_aliases: director alias → raw model motion name
    // Only aliases present in these maps are accepted; anything else is WARN+skip.
    void Load(const std::vector<Cue>& cues,
              const std::map<std::string, std::string>& emotion_aliases,
              const std::map<std::string, std::string>& reaction_aliases);

    void Advance(float time_sec,
                 std::function<void(const std::string&)> set_expression,
                 std::function<void(const std::string&)> trigger_motion,
                 CueState& state);

private:
    std::vector<Cue> _cues;
    std::map<std::string, std::string> _emotions;
    std::map<std::string, std::string> _reactions;
    int   _next = 0;
    float _prev_time = -1.0f;
};

#include "cue_sequencer.h"
#include "../cli/logger.h"
#include <algorithm>

void CueSequencer::Load(const std::vector<Cue>& cues,
                        const std::map<std::string, std::string>& emotion_aliases,
                        const std::map<std::string, std::string>& reaction_aliases)
{
    _cues      = cues;
    _emotions  = emotion_aliases;
    _reactions = reaction_aliases;
    _next      = 0;
    _prev_time = -1.0f;

    std::sort(_cues.begin(), _cues.end(),
              [](const Cue& a, const Cue& b){ return a.time < b.time; });
}

void CueSequencer::Advance(float time_sec,
                           std::function<void(const std::string&)> set_expression,
                           std::function<void(const std::string&, float)> trigger_motion,
                           CueState& state)
{
    while (_next < (int)_cues.size() && _cues[_next].time <= time_sec) {
        const Cue& c = _cues[_next];

        switch (c.type) {
        case CueType::Emotion: {
            auto it = _emotions.find(c.str_value);
            if (it == _emotions.end()) {
                Logger::Warn("Cue t=%.3fs: emotion \"%s\" not in model vocabulary — held at current expression",
                             c.time, c.str_value.c_str());
            } else {
                Logger::Info("Cue t=%.3fs: emotion → \"%s\" (raw: \"%s\")",
                             c.time, c.str_value.c_str(), it->second.c_str());
                state.emotion = c.str_value;
                set_expression(it->second);  // pass raw name to model
            }
            break;
        }
        case CueType::Reaction: {
            auto it = _reactions.find(c.str_value);
            if (it == _reactions.end()) {
                Logger::Warn("Cue t=%.3fs: reaction \"%s\" not in model vocabulary — skipped",
                             c.time, c.str_value.c_str());
            } else {
                Logger::Info("Cue t=%.3fs: reaction → \"%s\" (raw: \"%s\")",
                             c.time, c.str_value.c_str(), it->second.c_str());
                trigger_motion(it->second, c.time);  // pass raw name and cue time to model
            }
            break;
        }
        case CueType::Gaze:
            Logger::Debug("Cue t=%.3fs: gaze → (%.2f, %.2f)", c.time, c.gaze_x, c.gaze_y);
            state.gaze_x = c.gaze_x;
            state.gaze_y = c.gaze_y;
            break;

        case CueType::Head:
            Logger::Debug("Cue t=%.3fs: head → yaw=%.1f pitch=%.1f roll=%.1f",
                          c.time, c.head_yaw, c.head_pitch, c.head_roll);
            state.head_yaw   = c.head_yaw;
            state.head_pitch = c.head_pitch;
            state.head_roll  = c.head_roll;
            break;

        case CueType::Unknown:
            break; // already warned during manifest load
        }
        ++_next;
    }
}

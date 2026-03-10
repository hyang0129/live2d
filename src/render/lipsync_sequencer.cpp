#include "lipsync_sequencer.h"
#include <algorithm>
#include <cmath>

// Rhubarb → Live2D parameter mapping (from cli_design.md)
MouthState LipsyncSequencer::ShapeToState(char shape)
{
    switch (shape) {
        case 'X': return { 0.0f,  0.0f };
        case 'A': return { 0.1f, -1.0f };
        case 'B': return { 1.0f,  0.0f };
        case 'C': return { 0.8f,  0.5f };
        case 'D': return { 0.3f,  0.0f };
        case 'E': return { 0.6f,  0.5f };
        case 'F': return { 0.2f, -0.5f };
        case 'G': return { 0.4f,  0.0f };
        case 'H': return { 0.3f,  0.3f };
        default:  return { 0.0f,  0.0f };
    }
}

MouthState LipsyncSequencer::Lerp(const MouthState& a, const MouthState& b, float t)
{
    return { a.open + (b.open - a.open) * t,
             a.form + (b.form - a.form) * t };
}

void LipsyncSequencer::Load(const std::vector<LipsyncKeyframe>& keyframes)
{
    _frames.clear();
    for (const auto& kf : keyframes)
        _frames.push_back({ kf.time, ShapeToState(kf.shape) });

    std::sort(_frames.begin(), _frames.end(),
              [](const Frame& a, const Frame& b){ return a.time < b.time; });
}

MouthState LipsyncSequencer::Evaluate(float t) const
{
    if (_frames.empty()) return {};
    if (t <= _frames.front().time) return _frames.front().state;
    if (t >= _frames.back().time)  return _frames.back().state;

    // Binary search for bracketing frames
    auto it = std::lower_bound(_frames.begin(), _frames.end(), t,
        [](const Frame& f, float v){ return f.time < v; });

    const Frame& hi = *it;
    const Frame& lo = *(it - 1);

    const float span = hi.time - lo.time;
    const float frac = (span > 0.0f) ? (t - lo.time) / span : 0.0f;
    return Lerp(lo.state, hi.state, frac);
}

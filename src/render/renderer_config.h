#pragma once
#include <string>
#include <map>

// ── Per-parameter breath settings ────────────────────────────────────────────
struct BreathParamConfig {
    float offset = 0.0f;
    float peak   = 0.0f;
    float cycle  = 1.0f;
    float weight = 0.5f;
};

struct BreathConfig {
    BreathParamConfig angle_x      {0.0f,  7.2f,  6.5345f, 0.5f};  // post-#8 reduced values
    BreathParamConfig angle_y      {0.0f,  4.5f,  3.5345f, 0.5f};
    BreathParamConfig angle_z      {0.0f,  5.4f,  5.5345f, 0.5f};
    BreathParamConfig body_angle_x {0.0f, 2.25f, 15.5345f, 0.5f};
    BreathParamConfig breath_param {0.5f,  0.5f,  3.2345f, 0.5f};
};

// ── Lip-sync shape mappings ──────────────────────────────────────────────────
struct MouthShapeValues {
    float open = 0.0f;   // MouthOpenY  [0,1]
    float form = 0.0f;   // MouthForm   [-1,1]
};

struct LipsyncConfig {
    std::map<char, MouthShapeValues> shapes {
        {'X', {0.0f,  0.0f}},
        {'A', {0.1f, -1.0f}},
        {'B', {1.0f,  0.0f}},
        {'C', {0.8f,  0.5f}},
        {'D', {0.3f,  0.0f}},
        {'E', {0.6f,  0.5f}},
        {'F', {0.2f, -0.5f}},
        {'G', {0.4f,  0.0f}},
        {'H', {0.3f,  0.3f}}
    };
    float smoothing_open = 0.8f;  // MouthOpenY blend weight per frame
    float smoothing_form = 0.8f;  // MouthForm  blend weight per frame
};

// ── Breath guard / reaction animation ────────────────────────────────────────
struct AnimationConfig {
    // Time (seconds) to ramp _reactionFadeWeight from 0→1 when a reaction starts.
    // Fixes the entry snap (#5): breath transitions smoothly out instead of cutting.
    float breath_guard_entry_fade_duration = 0.15f;
    // Time (seconds) to ramp _reactionFadeWeight from 1→0 after reaction ends.
    float breath_guard_exit_fade_duration  = 0.5f;
    // Motion priority level that triggers the breath guard.
    int   motion_priority_threshold        = 2;
};

// ── Out-of-range normalisation ───────────────────────────────────────────────
struct NormalisationConfig {
    float minimum_duration    = 0.1f;   // seconds; prevents instant snap for tiny violations
    float auto_rate_multiplier = 2.0f;  // auto-rate = max_breath_speed * multiplier
    float fallback_rate        = 15.0f; // units/s when breath speed unavailable
};

// ── Render loop ───────────────────────────────────────────────────────────────
struct RenderConfig {
    float scene_tail_duration = 1.0f;  // idle seconds added after last cue/lipsync event
};

// ── FFmpeg codec quality ──────────────────────────────────────────────────────
struct FfmpegAv1Config    { int crf = 30; int bitrate = 0; };
struct FfmpegProresConfig  { int profile = 4; };
struct FfmpegH264Config    { int crf = 23; std::string preset = "medium"; };
struct FfmpegAacConfig     { std::string bitrate = "128k"; };

struct FfmpegCodecConfig {
    FfmpegAv1Config    av1;
    FfmpegProresConfig prores;
    FfmpegH264Config   h264;
    FfmpegAacConfig    aac;
};

// ── Top-level config ──────────────────────────────────────────────────────────
struct RendererConfig {
    BreathConfig        breath;
    LipsyncConfig       lipsync;
    AnimationConfig     animation;
    NormalisationConfig normalisation;
    RenderConfig        render;
    FfmpegCodecConfig   ffmpeg;
};

// Load from JSON file. Missing file or parse errors → returns all defaults (logged).
RendererConfig LoadRendererConfig(const std::string& path);

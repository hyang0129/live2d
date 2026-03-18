#pragma once
#include <string>
#include <vector>

// ── Background ────────────────────────────────────────────────────────────────
enum class BackgroundType { Transparent, Color, Image };

struct Background {
    BackgroundType type = BackgroundType::Transparent;
    float r = 0, g = 0, b = 0;  // used when type == Color
    std::string image_path;      // used when type == Image
};

// ── Lipsync ───────────────────────────────────────────────────────────────────
struct LipsyncKeyframe {
    float       time;
    char        shape; // X A B C D E F G H
};

// ── Cues ─────────────────────────────────────────────────────────────────────
enum class CueType { Emotion, Reaction, Gaze, Head, Unknown };

struct Cue {
    float    time;
    CueType  type  = CueType::Unknown;
    std::string str_value;     // emotion name or reaction name
    float    gaze_x = 0, gaze_y = 0;
    float    head_yaw = 0, head_pitch = 0, head_roll = 0;
};

// ── Model spec ────────────────────────────────────────────────────────────────
struct ModelSpec {
    std::string id;
    std::string path;
};

// ── Full manifest ─────────────────────────────────────────────────────────────
struct SceneManifest {
    std::string schema_version;
    ModelSpec   model;
    std::string audio_path;      // empty if null
    std::string output_path;
    int         width  = 1080;
    int         height = 1920;
    int         fps    = 30;
    Background  background;
    float       breath_speed = 1.0f;  // multiplier: 2.0 = twice as fast
    std::vector<LipsyncKeyframe> lipsync;
    std::vector<Cue>             cues;
};

// Returns false on validation failure; writes reason to stderr.
bool LoadManifest(const std::string& path,
                  const std::string& output_override,
                  bool transparent_override,
                  SceneManifest& out);

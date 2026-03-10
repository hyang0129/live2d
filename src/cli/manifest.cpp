#include "manifest.h"
#include "logger.h"

#include <fstream>
#include <nlohmann/json.hpp>
using json = nlohmann::json;

static const char* kSupportedVersion = "1.0";

static bool ParseBackground(const json& j, Background& bg)
{
    if (j.is_null() || !j.is_string()) {
        bg.type = BackgroundType::Transparent;
        return true;
    }
    const std::string s = j.get<std::string>();
    if (s == "transparent") {
        bg.type = BackgroundType::Transparent;
    }
    else if (!s.empty() && s[0] == '#') {
        bg.type = BackgroundType::Color;
        // parse hex #RRGGBB
        unsigned int hex = 0;
        if (sscanf(s.c_str() + 1, "%x", &hex) == 1) {
            bg.r = ((hex >> 16) & 0xFF) / 255.0f;
            bg.g = ((hex >>  8) & 0xFF) / 255.0f;
            bg.b = ((hex      ) & 0xFF) / 255.0f;
        }
    }
    else {
        bg.type = BackgroundType::Image;
        bg.image_path = s;
    }
    return true;
}

static char ParseMouthShape(const std::string& s)
{
    if (s.size() == 1) {
        char c = s[0];
        if (c >= 'A' && c <= 'H') return c;
        if (c == 'X') return 'X';
    }
    Logger::Warn("Unknown mouth_shape \"%s\" — treating as X", s.c_str());
    return 'X';
}

bool LoadManifest(const std::string& path,
                  const std::string& output_override,
                  bool transparent_override,
                  SceneManifest& out)
{
    std::ifstream f(path);
    if (!f.is_open()) {
        Logger::Error("Cannot open manifest file \"%s\"", path.c_str());
        return false;
    }

    json j;
    try {
        f >> j;
    }
    catch (const json::exception& e) {
        Logger::Error("Manifest JSON parse error: %s", e.what());
        return false;
    }

    // schema_version
    if (!j.contains("schema_version") || !j["schema_version"].is_string()) {
        Logger::Error("Manifest validation failed: missing required field \"schema_version\"");
        return false;
    }
    out.schema_version = j["schema_version"].get<std::string>();
    if (out.schema_version != kSupportedVersion) {
        Logger::Error("Unrecognized schema_version \"%s\" — supported versions: [\"%s\"]",
                      out.schema_version.c_str(), kSupportedVersion);
        return false;
    }

    // model
    if (!j.contains("model") || !j["model"].is_object()) {
        Logger::Error("Manifest validation failed: missing required field \"model\"");
        return false;
    }
    {
        const auto& m = j["model"];
        if (!m.contains("id") || !m["id"].is_string()) {
            Logger::Error("Manifest validation failed: model.id is required");
            return false;
        }
        out.model.id = m["id"].get<std::string>();
        if (m.contains("path") && m["path"].is_string())
            out.model.path = m["path"].get<std::string>();
    }

    // audio (nullable)
    if (j.contains("audio") && j["audio"].is_string())
        out.audio_path = j["audio"].get<std::string>();

    // output
    if (!j.contains("output") || !j["output"].is_string()) {
        Logger::Error("Manifest validation failed: missing required field \"output\"");
        return false;
    }
    out.output_path = j["output"].get<std::string>();

    // resolution
    if (!j.contains("resolution") || !j["resolution"].is_array() || j["resolution"].size() != 2) {
        Logger::Error("Manifest validation failed: missing or malformed \"resolution\" — expected [width, height]");
        return false;
    }
    out.width  = j["resolution"][0].get<int>();
    out.height = j["resolution"][1].get<int>();

    // fps
    if (!j.contains("fps") || !j["fps"].is_number_integer()) {
        Logger::Error("Manifest validation failed: missing required field \"fps\"");
        return false;
    }
    out.fps = j["fps"].get<int>();

    // background
    ParseBackground(j.value("background", json(nullptr)), out.background);

    // lipsync
    if (j.contains("lipsync") && j["lipsync"].is_array()) {
        for (const auto& kf : j["lipsync"]) {
            LipsyncKeyframe k;
            k.time  = kf.value("time", 0.0f);
            k.shape = ParseMouthShape(kf.value("mouth_shape", std::string("X")));
            out.lipsync.push_back(k);
        }
    }

    if (out.lipsync.empty()) {
        Logger::Warn("Lipsync array is empty — mouth will remain closed for the full scene");
    }

    // cues
    if (j.contains("cues") && j["cues"].is_array()) {
        for (const auto& jc : j["cues"]) {
            Cue c;
            c.time = jc.value("time", 0.0f);

            bool recognised = false;
            if (jc.contains("emotion") && jc["emotion"].is_string()) {
                c.type = CueType::Emotion;
                c.str_value = jc["emotion"].get<std::string>();
                recognised = true;
            }
            else if (jc.contains("reaction") && jc["reaction"].is_string()) {
                c.type = CueType::Reaction;
                c.str_value = jc["reaction"].get<std::string>();
                recognised = true;
            }
            else if (jc.contains("gaze") && jc["gaze"].is_object()) {
                c.type   = CueType::Gaze;
                c.gaze_x = jc["gaze"].value("x", 0.0f);
                c.gaze_y = jc["gaze"].value("y", 0.0f);
                recognised = true;
            }
            else if (jc.contains("head") && jc["head"].is_object()) {
                c.type       = CueType::Head;
                c.head_yaw   = jc["head"].value("yaw",   0.0f);
                c.head_pitch = jc["head"].value("pitch", 0.0f);
                c.head_roll  = jc["head"].value("roll",  0.0f);
                recognised = true;
            }

            if (!recognised) {
                // find the first unknown key (skip "time")
                for (auto& [key, val] : jc.items()) {
                    if (key != "time") {
                        Logger::Warn("Cue t=%.3fs: unknown key \"%s\" — ignored", c.time, key.c_str());
                        break;
                    }
                }
                c.type = CueType::Unknown;
            }

            out.cues.push_back(c);
        }
    }

    // Apply CLI overrides
    if (!output_override.empty())
        out.output_path = output_override;

    if (transparent_override) {
        if (out.background.type != BackgroundType::Transparent) {
            // check for .mp4 mismatch handled later in ffmpeg encoder
        }
        out.background.type = BackgroundType::Transparent;
    }

    const int total_frames = static_cast<int>(
        out.lipsync.empty() && out.cues.empty() ? out.fps * 3
        : (out.cues.empty() ? out.lipsync.back().time * out.fps + 1
                            : out.cues.back().time  * out.fps + out.fps));

    Logger::Info("Manifest loaded: schema_version=%s, model=%s, fps=%d, resolution=%dx%d, cues=%d, lipsync_keyframes=%d",
        out.schema_version.c_str(),
        out.model.id.c_str(),
        out.fps,
        out.width, out.height,
        (int)out.cues.size(),
        (int)out.lipsync.size());

    return true;
}

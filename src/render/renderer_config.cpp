#include "renderer_config.h"
#include "../cli/logger.h"

#include <fstream>
#include <nlohmann/json.hpp>
using json = nlohmann::json;

static BreathParamConfig ParseBreathParam(const json& j, const BreathParamConfig& def)
{
    if (!j.is_object()) return def;
    return {
        j.value("offset", def.offset),
        j.value("peak",   def.peak),
        j.value("cycle",  def.cycle),
        j.value("weight", def.weight)
    };
}

RendererConfig LoadRendererConfig(const std::string& path)
{
    RendererConfig cfg;  // all defaults

    std::ifstream f(path);
    if (!f.is_open()) {
        Logger::Info("renderer_config.json not found at \"%s\" — using built-in defaults",
                     path.c_str());
        return cfg;
    }

    json j;
    try { f >> j; }
    catch (const json::exception& e) {
        Logger::Warn("renderer_config.json parse error: %s — using built-in defaults", e.what());
        return cfg;
    }

    // ── breath ────────────────────────────────────────────────────────────────
    if (j.contains("breath") && j["breath"].is_object()) {
        const auto& b = j["breath"];
        if (b.contains("parameters") && b["parameters"].is_object()) {
            const auto& p = b["parameters"];
            cfg.breath.angle_x      = ParseBreathParam(p.value("angle_x",      json{}), cfg.breath.angle_x);
            cfg.breath.angle_y      = ParseBreathParam(p.value("angle_y",      json{}), cfg.breath.angle_y);
            cfg.breath.angle_z      = ParseBreathParam(p.value("angle_z",      json{}), cfg.breath.angle_z);
            cfg.breath.body_angle_x = ParseBreathParam(p.value("body_angle_x", json{}), cfg.breath.body_angle_x);
            cfg.breath.breath_param = ParseBreathParam(p.value("breath",       json{}), cfg.breath.breath_param);
        }
    }

    // ── lipsync ───────────────────────────────────────────────────────────────
    if (j.contains("lipsync") && j["lipsync"].is_object()) {
        const auto& ls = j["lipsync"];
        if (ls.contains("shapes") && ls["shapes"].is_object()) {
            for (const auto& [key, val] : ls["shapes"].items()) {
                if (key.size() == 1 && val.is_object()) {
                    const char c = key[0];
                    cfg.lipsync.shapes[c] = {
                        val.value("open", 0.0f),
                        val.value("form", 0.0f)
                    };
                }
            }
        }
        if (ls.contains("smoothing") && ls["smoothing"].is_object()) {
            cfg.lipsync.smoothing_open = ls["smoothing"].value("open", cfg.lipsync.smoothing_open);
            cfg.lipsync.smoothing_form = ls["smoothing"].value("form", cfg.lipsync.smoothing_form);
        }
    }

    // ── animation ─────────────────────────────────────────────────────────────
    if (j.contains("animation") && j["animation"].is_object()) {
        const auto& a = j["animation"];
        cfg.animation.breath_guard_entry_fade_duration =
            a.value("breath_guard_entry_fade_duration", cfg.animation.breath_guard_entry_fade_duration);
        cfg.animation.breath_guard_exit_fade_duration =
            a.value("breath_guard_exit_fade_duration",  cfg.animation.breath_guard_exit_fade_duration);
        cfg.animation.motion_priority_threshold =
            a.value("motion_priority_threshold", cfg.animation.motion_priority_threshold);
        cfg.animation.fade_to_idle_duration =
            a.value("fade_to_idle_duration", cfg.animation.fade_to_idle_duration);
    }

    // ── normalisation ─────────────────────────────────────────────────────────
    if (j.contains("normalisation") && j["normalisation"].is_object()) {
        const auto& n = j["normalisation"];
        cfg.normalisation.minimum_duration     = n.value("minimum_duration",     cfg.normalisation.minimum_duration);
        cfg.normalisation.auto_rate_multiplier = n.value("auto_rate_multiplier", cfg.normalisation.auto_rate_multiplier);
        cfg.normalisation.fallback_rate        = n.value("fallback_rate",        cfg.normalisation.fallback_rate);
    }

    // ── render ────────────────────────────────────────────────────────────────
    if (j.contains("render") && j["render"].is_object())
        cfg.render.scene_tail_duration =
            j["render"].value("scene_tail_duration", cfg.render.scene_tail_duration);

    // ── ffmpeg ────────────────────────────────────────────────────────────────
    if (j.contains("ffmpeg") && j["ffmpeg"].is_object()) {
        const auto& ff = j["ffmpeg"];
        if (ff.contains("av1") && ff["av1"].is_object()) {
            cfg.ffmpeg.av1.crf     = ff["av1"].value("crf",     cfg.ffmpeg.av1.crf);
            cfg.ffmpeg.av1.bitrate = ff["av1"].value("bitrate", cfg.ffmpeg.av1.bitrate);
        }
        if (ff.contains("prores") && ff["prores"].is_object())
            cfg.ffmpeg.prores.profile = ff["prores"].value("profile", cfg.ffmpeg.prores.profile);
        if (ff.contains("h264") && ff["h264"].is_object()) {
            cfg.ffmpeg.h264.crf     = ff["h264"].value("crf",     cfg.ffmpeg.h264.crf);
            cfg.ffmpeg.h264.preset  = ff["h264"].value("preset",  cfg.ffmpeg.h264.preset);
            cfg.ffmpeg.h264.threads = ff["h264"].value("threads", cfg.ffmpeg.h264.threads);
        }
        if (ff.contains("aac") && ff["aac"].is_object())
            cfg.ffmpeg.aac.bitrate = ff["aac"].value("bitrate", cfg.ffmpeg.aac.bitrate);
    }

    Logger::Info("renderer_config.json loaded: entry_fade=%.2fs exit_fade=%.2fs tail=%.1fs",
                 cfg.animation.breath_guard_entry_fade_duration,
                 cfg.animation.breath_guard_exit_fade_duration,
                 cfg.render.scene_tail_duration);
    return cfg;
}

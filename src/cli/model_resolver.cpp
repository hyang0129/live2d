#include "model_resolver.h"
#include "logger.h"

#include <fstream>
#include <filesystem>
#include <nlohmann/json.hpp>
using json = nlohmann::json;
namespace fs = std::filesystem;

static const char* kRegistryPath = "assets/models/registry.json";

static ModelProfile ParseEntry(const json& entry)
{
    ModelProfile p;
    p.id   = entry.value("id",   "");
    p.path = entry.value("path", "");

    // Emotion values may be a plain string ("F01") or an object ({"id":"F01","note":"..."})
    if (entry.contains("emotions") && entry["emotions"].is_object())
        for (auto& [alias, raw] : entry["emotions"].items()) {
            if (raw.is_string())
                p.emotions[alias] = raw.get<std::string>();
            else if (raw.is_object() && raw.contains("id"))
                p.emotions[alias] = raw["id"].get<std::string>();
        }

    if (entry.contains("reactions") && entry["reactions"].is_object())
        for (auto& [alias, raw] : entry["reactions"].items()) {
            if (raw.is_string())
                p.reactions[alias] = raw.get<std::string>();
            else if (raw.is_object() && raw.contains("id"))
                p.reactions[alias] = raw["id"].get<std::string>();
        }

    return p;
}

std::vector<ModelProfile> LoadRegistry()
{
    std::vector<ModelProfile> profiles;
    std::ifstream f(kRegistryPath);
    if (!f.is_open()) return profiles;

    json reg;
    try { f >> reg; } catch (...) { return profiles; }

    if (!reg.is_array()) return profiles;
    for (const auto& entry : reg)
        if (entry.contains("id") && entry.contains("path"))
            profiles.push_back(ParseEntry(entry));

    return profiles;
}

ModelProfile ResolveModel(const ModelSpec& spec)
{
    // ── 1. Try registry ────────────────────────────────────────────────────────
    std::ifstream f(kRegistryPath);
    if (f.is_open()) {
        json reg;
        try { f >> reg; }
        catch (...) {
            Logger::Warn("Failed to parse registry \"%s\" — skipping registry lookup", kRegistryPath);
        }

        if (reg.is_array()) {
            Logger::Debug("Registry loaded: %d entries", (int)reg.size());
            for (const auto& entry : reg) {
                if (!entry.contains("id") || !entry.contains("path")) continue;
                if (entry["id"].get<std::string>() != spec.id) continue;

                ModelProfile p = ParseEntry(entry);
                if (fs::exists(fs::u8path(p.path))) {
                    Logger::Info("Model resolved: id=%s → \"%s\" (%d emotions, %d reactions)",
                                 p.id.c_str(), p.path.c_str(),
                                 (int)p.emotions.size(), (int)p.reactions.size());
                    return p;
                }
                Logger::Warn("Registry entry for id=\"%s\" points to non-existent path \"%s\"",
                             spec.id.c_str(), p.path.c_str());
            }
        }
    }

    // ── 2. No registry match — error; manifest.path is not trusted without a profile ──
    Logger::Error("Model id=\"%s\" not found in registry \"%s\" — no cue vocabulary available",
                  spec.id.c_str(), kRegistryPath);
    Logger::Error("Add an entry for \"%s\" to the registry with emotion and reaction aliases before rendering",
                  spec.id.c_str());
    return {};
}

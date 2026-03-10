#pragma once
#include <string>
#include <map>
#include "manifest.h"

struct ModelProfile {
    std::string id;
    std::string path;
    // Director-facing alias → raw model expression/motion name
    std::map<std::string, std::string> emotions;   // e.g. "neutral" → "F01"
    std::map<std::string, std::string> reactions;  // e.g. "tap" → "TapBody"

    bool valid() const { return !path.empty(); }
};

// Resolves the model profile from the manifest's ModelSpec.
// Resolution order: registry[model.id]  →  error
// Returns a profile with empty path on failure (error logged).
ModelProfile ResolveModel(const ModelSpec& spec);

// Loads the full registry and returns all profiles.
// Used by --inspect to enumerate available models.
std::vector<ModelProfile> LoadRegistry();

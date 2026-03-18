#pragma once
#include <string>
#include <map>
#include "manifest.h"

struct EntryBound {
    float min;
    float max;
};

enum class OutOfRangeMode {
    None,     // skip entry check entirely — play motion regardless of position
    Implicit, // normalise-then-play with warning (default)
    Explicit, // log structured error and do not play
};

enum class BreathGuardMode {
    Lerp, // default: lerp breath back in as reaction fades out
    None, // no guard — breath runs freely through and after the reaction
};

struct ReactionEntry {
    std::string raw_id;                           // raw motion group name (e.g. "Nod")
    bool entry_dependent = false;
    std::map<std::string, EntryBound> valid_entry; // param name → bounds
    float normalise_rate = 0.0f;                   // units/s; 0 = auto (2× breath max speed)
    OutOfRangeMode out_of_range_mode = OutOfRangeMode::Implicit;
    BreathGuardMode breath_guard = BreathGuardMode::Lerp;
};

struct ModelProfile {
    std::string id;
    std::string path;
    // Director-facing alias → raw model expression/motion name
    std::map<std::string, std::string> emotions;   // e.g. "neutral" → "F01"
    std::map<std::string, ReactionEntry> reactions;  // e.g. "tap" → ReactionEntry

    bool valid() const { return !path.empty(); }
};

// Resolves the model profile from the manifest's ModelSpec.
// Resolution order: registry[model.id]  →  error
// Returns a profile with empty path on failure (error logged).
ModelProfile ResolveModel(const ModelSpec& spec);

// Loads the full registry and returns all profiles.
// Used by --inspect to enumerate available models.
std::vector<ModelProfile> LoadRegistry();

#pragma once
#include <string>
#include "logger.h"

struct Args {
    std::string scene_path;
    std::string output_override;   // empty if not set
    bool        transparent_override = false;
    LogLevel    log_level = LogLevel::Info;

    // --inspect mode: print model vocabulary as JSON and exit
    bool        inspect = false;
    std::string inspect_model;     // model id to inspect
};

// Returns false and writes to stderr on error.
bool ParseArgs(int argc, char* argv[], Args& out);

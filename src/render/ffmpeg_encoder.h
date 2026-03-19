#pragma once
#include <string>
#include <vector>
#include "../cli/manifest.h"
#include "renderer_config.h"

class FfmpegEncoder {
public:
    ~FfmpegEncoder();

    // Spawns ffmpeg as a child process.
    // transparent=true → ProRes 4444 .mov (or AV1 .mp4); false → H.264 .mp4
    // codec_cfg controls quality/profile settings (defaults if not provided).
    // output_path: final destination (written only on success)
    // Returns false on failure.
    bool Open(const std::string& output_path,
              int width, int height, int fps,
              bool transparent,
              const std::string& audio_path,
              const FfmpegCodecConfig& codec_cfg = FfmpegCodecConfig{});

    // Send one RGBA frame (width * height * 4 bytes).
    bool WriteFrame(const std::vector<unsigned char>& rgba);

    // Finalize: close stdin pipe, wait for ffmpeg to exit.
    // Returns false if ffmpeg exited non-zero.
    bool Close();

    bool IsOpen() const { return _pipe != nullptr; }

private:
    FILE*       _pipe       = nullptr;
    std::string _tmp_path;   // .tmp output, renamed on success
    std::string _final_path;
    bool        _ok         = true;
};

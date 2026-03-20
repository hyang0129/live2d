#include "ffmpeg_encoder.h"
#include "../cli/logger.h"

#include <cstdio>
#include <filesystem>
#include <sstream>
#include <algorithm>
namespace fs = std::filesystem;

FfmpegEncoder::~FfmpegEncoder()
{
    if (_pipe) {
        pclose(_pipe);
        _pipe = nullptr;
    }
}

bool FfmpegEncoder::Open(const std::string& output_path,
                         int width, int height, int fps,
                         bool transparent,
                         const std::string& audio_path,
                         const FfmpegCodecConfig& codec_cfg)
{
    _final_path = output_path;

    // Determine effective path and codec
    std::string effective_path = output_path;
    bool is_mp4 = (output_path.size() >= 4 &&
                   output_path.substr(output_path.size() - 4) == ".mp4");

    // Transparent + .mov → ProRes 4444 (lossless, industry standard)
    // Transparent + .mp4 → AV1 with alpha (yuva420p, stays as .mp4)
    // Transparent + other → treat as .mov / ProRes
    bool use_prores = transparent && !is_mp4;
    bool use_av1    = transparent &&  is_mp4;

    _tmp_path = effective_path + ".tmp" + (is_mp4 ? ".mp4" : ".mov");

    // Ensure output directory exists
    {
        const fs::path dir = fs::path(effective_path).parent_path();
        if (!dir.empty() && !fs::exists(dir)) {
            std::error_code ec;
            fs::create_directories(dir, ec);
            if (ec) {
                Logger::Error("Cannot create output directory \"%s\": %s",
                              dir.string().c_str(), ec.message().c_str());
                return false;
            }
        }
    }

    // Build ffmpeg command
    std::ostringstream cmd;
    cmd << "ffmpeg -y"
        << " -f rawvideo -pix_fmt rgba"
        << " -s " << width << "x" << height
        << " -r " << fps
        << " -i pipe:0";

    if (!audio_path.empty())
        cmd << " -i \"" << audio_path << "\"";

    if (use_av1)
        cmd << " -c:v libvpx-vp9 -pix_fmt yuva420p"
            << " -crf " << codec_cfg.av1.crf
            << " -b:v " << codec_cfg.av1.bitrate;
    else if (use_prores)
        cmd << " -c:v prores_ks -profile:v " << codec_cfg.prores.profile
            << " -pix_fmt yuva444p10le";
    else {
        cmd << " -c:v libx264 -pix_fmt yuv420p"
            << " -crf " << codec_cfg.h264.crf
            << " -preset " << codec_cfg.h264.preset;
        if (codec_cfg.h264.threads > 0)
            cmd << " -threads " << codec_cfg.h264.threads;
    }

    if (!audio_path.empty())
        cmd << " -c:a aac -b:a " << codec_cfg.aac.bitrate;

    cmd << " \"" << _tmp_path << "\" 2>&1";

    const std::string cmdStr = cmd.str();
    Logger::Debug("FFmpeg command: %s", cmdStr.c_str());

#ifdef _WIN32
    _pipe = popen(cmdStr.c_str(), "wb");  // binary mode required on Windows
#else
    _pipe = popen(cmdStr.c_str(), "w");   // POSIX: only "r" or "w" are valid
#endif
    if (!_pipe) {
        Logger::Error("Failed to spawn ffmpeg — is ffmpeg in PATH?");
        return false;
    }

    const char* codec = use_av1 ? "libvpx-vp9 yuva420p" : use_prores ? "prores_ks yuva444p10le" : "libx264 yuv420p";
    Logger::Info("FFmpeg encoder started: %s %dfps → \"%s\"", codec, fps, _tmp_path.c_str());

    return true;
}

bool FfmpegEncoder::WriteFrame(const std::vector<unsigned char>& rgba)
{
    if (!_pipe || !_ok) return false;
    const size_t written = fwrite(rgba.data(), 1, rgba.size(), _pipe);
    if (written != rgba.size()) {
        Logger::Error("FFmpeg pipe write failed (wrote %zu of %zu bytes)", written, rgba.size());
        _ok = false;
    }
    return _ok;
}

bool FfmpegEncoder::Close()
{
    if (!_pipe) return false;
    const int exit_code = pclose(_pipe);
    _pipe = nullptr;

    if (exit_code != 0) {
        Logger::Error("FFmpeg exited with code %d — output not written", exit_code);
        fs::remove(_tmp_path);
        return false;
    }

    // Atomic rename: tmp → final
    std::error_code ec;
    fs::rename(_tmp_path, _final_path, ec);
    if (ec) {
        Logger::Error("Failed to move \"%s\" to \"%s\": %s",
                      _tmp_path.c_str(), _final_path.c_str(), ec.message().c_str());
        return false;
    }

    // Report file size
    const uintmax_t sz = fs::file_size(_final_path, ec);
    if (!ec)
        Logger::Info("FFmpeg finalized. Output: \"%s\" (%.1f MB)",
                     _final_path.c_str(), sz / (1024.0 * 1024.0));

    return true;
}

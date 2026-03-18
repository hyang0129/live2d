/**
 * live2d-render — headless Live2D avatar renderer
 *
 * Entry point. Parses args, loads manifest, drives the render pipeline,
 * and exits with an appropriate code.
 */

#ifdef _WIN32
#  define NOMINMAX
#  include <Windows.h>
#  include <objbase.h>  // CoInitializeEx / CoUninitialize
#endif

#include <fstream>
#include <filesystem>
#include <cstdio>
namespace fs = std::filesystem;

#include <CubismFramework.hpp>
#ifdef _WIN32
#  include <Rendering/D3D11/CubismRenderer_D3D11.hpp>
#endif

#include "allocator.h"
#include "cli/args.h"
#include "cli/logger.h"
#include "cli/manifest.h"
#include "cli/model_resolver.h"
#include "render/lipsync_sequencer.h"
#include "render/cue_sequencer.h"
#include "render/live2d_model.h"
#include "render/ffmpeg_encoder.h"
#include "render/render_loop.h"  // also pulls in OffscreenRenderer typedef

using namespace Csm;

// Exit codes per cli_design.md
enum ExitCode {
    EXIT_OK           = 0,
    EXIT_BAD_ARGS     = 1,
    EXIT_BAD_MANIFEST = 2,
    EXIT_ASSET_ERROR  = 3,
    EXIT_RENDER_ERROR = 4,
    EXIT_OUTPUT_ERROR = 5,
};

// Cubism log bridge → our logger
static void CubismLogFunc(const char* msg) {
    Logger::Debug("[Cubism] %s", msg);
}

// Cubism file loader — used by shader manager to load FrameworkShaders/
static Csm::csmByte* CubismLoadFile(const std::string filePath, Csm::csmSizeInt* outSize) {
    std::ifstream f(fs::u8path(filePath), std::ios::binary | std::ios::ate);
    if (!f.is_open()) { *outSize = 0; return nullptr; }
    *outSize = static_cast<Csm::csmSizeInt>(f.tellg());
    f.seekg(0);
    auto* buf = new Csm::csmByte[*outSize];
    f.read(reinterpret_cast<char*>(buf), *outSize);
    return buf;
}
static void CubismReleaseBytes(Csm::csmByte* bytes) { delete[] bytes; }

// ── Inspect mode ─────────────────────────────────────────────────────────────
static int RunInspect(const std::string& model_id)
{
    const auto profiles = LoadRegistry();

    for (const auto& p : profiles) {
        if (p.id != model_id) continue;

        printf("{\n");
        printf("  \"model\": \"%s\",\n", p.id.c_str());
        printf("  \"path\": \"%s\",\n", p.path.c_str());

        printf("  \"emotions\": [");
        bool first = true;
        for (const auto& [alias, _] : p.emotions) {
            printf("%s\"%s\"", first ? "" : ", ", alias.c_str());
            first = false;
        }
        printf("],\n");

        printf("  \"reactions\": [");
        first = true;
        for (const auto& [alias, entry] : p.reactions) {
            printf("%s\"%s\"", first ? "" : ", ", alias.c_str());
            first = false;
        }
        printf("]\n");
        printf("}\n");
        return EXIT_OK;
    }

    fprintf(stderr, "[ERROR] Model \"%s\" not found in registry\n", model_id.c_str());
    return EXIT_ASSET_ERROR;
}

int main(int argc, char* argv[])
{
    // ── 1. Parse arguments ────────────────────────────────────────────────────
    Args args;
    if (!ParseArgs(argc, argv, args))
        return EXIT_BAD_ARGS;

    Logger::SetLevel(args.log_level);

    // ── Inspect mode (no render) ──────────────────────────────────────────────
    if (args.inspect)
        return RunInspect(args.inspect_model);

    Logger::Info("live2d-render starting — scene: \"%s\"", args.scene_path.c_str());

    // ── 2. Load and validate manifest ─────────────────────────────────────────
    SceneManifest manifest;
    if (!LoadManifest(args.scene_path, args.output_override, args.transparent_override, manifest))
        return EXIT_BAD_MANIFEST;

    // Open log file alongside output (same stem, .log extension)
    {
        std::filesystem::path out(manifest.output_path);
        const std::string log_path = (out.parent_path() / out.stem()).string() + ".log";
        std::error_code ec;
        std::filesystem::create_directories(out.parent_path(), ec);
        Logger::OpenLogFile(log_path);
        Logger::Info("Log file: \"%s\"", log_path.c_str());
    }

    // Audio existence check
    if (!manifest.audio_path.empty()) {
        std::ifstream af(manifest.audio_path);
        if (!af.is_open()) {
            Logger::Error("Audio file not found: \"%s\"", manifest.audio_path.c_str());
            return EXIT_ASSET_ERROR;
        }
        Logger::Info("Audio: \"%s\"", manifest.audio_path.c_str());
    }

    Logger::Info("Output: \"%s\" (transparent=%s)",
        manifest.output_path.c_str(),
        manifest.background.type == BackgroundType::Transparent ? "true" : "false");

    // ── 3. Resolve model profile ──────────────────────────────────────────────
    const ModelProfile profile = ResolveModel(manifest.model);
    if (!profile.valid())
        return EXIT_ASSET_ERROR;

    // ── 4. Initialize graphics backend ───────────────────────────────────────
#ifdef _WIN32
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
#endif

    OffscreenRenderer offscreen;
    if (!offscreen.Init(manifest.width, manifest.height))
        return EXIT_RENDER_ERROR;

    // ── 5. Initialize Cubism framework ───────────────────────────────────────
    static Allocator allocator;
    CubismFramework::Option cubismOption;
    cubismOption.LogFunction          = CubismLogFunc;
    cubismOption.LoggingLevel         = CubismFramework::Option::LogLevel_Off;
    cubismOption.LoadFileFunction     = CubismLoadFile;
    cubismOption.ReleaseBytesFunction = CubismReleaseBytes;

    CubismFramework::StartUp(&allocator, &cubismOption);
    CubismFramework::Initialize();

#ifdef _WIN32
    // Tell the D3D11 renderer about our device (required before CreateRenderer)
    // bufferSetNum=1 → single buffered (no swap chain needed for offscreen)
    Rendering::CubismRenderer_D3D11::InitializeConstantSettings(1, offscreen.Device());
#endif

    // ── 6. Load Live2D model ──────────────────────────────────────────────────
    Live2DModel model;
#ifdef _WIN32
    if (!model.Load(profile.path, offscreen.Device(), offscreen.Context())) {
#else
    if (!model.Load(profile.path)) {
#endif
        CubismFramework::Dispose();
        return EXIT_RENDER_ERROR;
    }

    if (manifest.breath_speed != 1.0f)
        model.SetBreathSpeed(manifest.breath_speed);

    // ── 7. Prepare sequencers ─────────────────────────────────────────────────
    LipsyncSequencer lipsync;
    lipsync.Load(manifest.lipsync);

    // Build alias → raw_id string map for CueSequencer (unchanged interface)
    std::map<std::string, std::string> reactionAliases;
    for (const auto& [alias, entry] : profile.reactions)
        reactionAliases[alias] = entry.raw_id;

    // Build raw_id → ReactionEntry map for Live2DModel entry checking
    std::map<std::string, ReactionEntry> reactionEntries;
    for (const auto& [alias, entry] : profile.reactions)
        reactionEntries[entry.raw_id] = entry;
    model.SetReactionEntries(reactionEntries);

    CueSequencer cues;
    cues.Load(manifest.cues, profile.emotions, reactionAliases);

    // ── 8. Open FFmpeg encoder ────────────────────────────────────────────────
    const bool transparent = (manifest.background.type == BackgroundType::Transparent);
    FfmpegEncoder encoder;
    if (!encoder.Open(manifest.output_path,
                      manifest.width, manifest.height, manifest.fps,
                      transparent,
                      manifest.audio_path))
    {
        CubismFramework::Dispose();
        return EXIT_RENDER_ERROR;
    }

    // ── 9. Run render loop ────────────────────────────────────────────────────
    const bool render_ok = RunRenderLoop(manifest, model, offscreen, encoder, lipsync, cues);

    // ── 10. Finalize encoder ──────────────────────────────────────────────────
    const bool encode_ok = encoder.Close();

    CubismFramework::Dispose();

#ifdef _WIN32
    CoUninitialize();
#endif

    if (!render_ok) { Logger::CloseLogFile(); return EXIT_RENDER_ERROR; }
    if (!encode_ok) { Logger::CloseLogFile(); return EXIT_OUTPUT_ERROR; }

    Logger::CloseLogFile();
    return EXIT_OK;
}

#include "render_loop.h"
#include "../cli/logger.h"

#ifdef _WIN32
#  define NOMINMAX
#  include <Rendering/D3D11/CubismRenderer_D3D11.hpp>
#endif

#include <Math/CubismMatrix44.hpp>
#include <Math/CubismViewMatrix.hpp>

#include <chrono>

using namespace Csm;
using namespace Live2D::Cubism::Framework;

bool RunRenderLoop(const SceneManifest& manifest,
                   Live2DModel&         model,
                   OffscreenRenderer&   offscreen,
                   FfmpegEncoder&       encoder,
                   LipsyncSequencer&    lipsync,
                   CueSequencer&        cues)
{
    // Determine total frame count from the last cue/lipsync time + 1 second tail
    float scene_duration = 0.0f;
    for (const auto& c : manifest.cues)
        scene_duration = std::max(scene_duration, c.time);
    for (const auto& kf : manifest.lipsync)
        scene_duration = std::max(scene_duration, kf.time);
    scene_duration += 1.0f;  // 1-second tail

    const int   total_frames = static_cast<int>(scene_duration * manifest.fps);
    const float dt           = 1.0f / static_cast<float>(manifest.fps);

    // View-projection: orthographic to fill [-1,1] on both axes
    CubismMatrix44 projection;
    projection.Scale(
        static_cast<float>(manifest.height) / static_cast<float>(manifest.width),
        1.0f);

    // Clear colour
    float cr = 0.f, cg = 0.f, cb = 0.f, ca = 0.f;
    if (manifest.background.type == BackgroundType::Color) {
        cr = manifest.background.r;
        cg = manifest.background.g;
        cb = manifest.background.b;
        ca = 1.0f;
    }

    CueState cue_state;
    std::vector<unsigned char> pixels;

    const auto wall_start = std::chrono::steady_clock::now();

    Logger::Info("Rendering: frame 0/%d (0%%)", total_frames);

    for (int frame = 0; frame < total_frames; ++frame) {
        const float t = static_cast<float>(frame) * dt;

        // Progress log at 0 / 33 / 67 / 100 %
        const int pct = (frame * 100) / total_frames;
        if (frame > 0 && (pct == 33 || pct == 67)) {
            static int last_pct = 0;
            if (pct != last_pct) {
                Logger::Info("Rendering: frame %d/%d (%d%%)", frame, total_frames, pct);
                last_pct = pct;
            }
        }

        // ── Dispatch cues ───────────────────────────────────────────────────
        cues.Advance(t,
            [&](const std::string& name) { model.SetExpression(name); },
            [&](const std::string& name, float cue_time) { model.TriggerMotion(name, cue_time); },
            cue_state);

        // ── Evaluate lipsync ─────────────────────────────────────────────────
        const MouthState mouth = lipsync.Evaluate(t);

        // ── Update Live2D model ──────────────────────────────────────────────
        model.Update(dt, mouth, cue_state);

        // ── Render ───────────────────────────────────────────────────────────
#ifdef _WIN32
        Rendering::CubismRenderer_D3D11::StartFrame(
            offscreen.Device(), offscreen.Context(),
            static_cast<Csm::csmUint32>(manifest.width),
            static_cast<Csm::csmUint32>(manifest.height));
#endif

        offscreen.BeginFrame();
        offscreen.Clear(cr, cg, cb, ca);

        CubismMatrix44 vp = projection;
        model.Draw(vp);

#ifdef _WIN32
        Rendering::CubismRenderer_D3D11::EndFrame(offscreen.Device());
#endif

        // ── Readback + encode ────────────────────────────────────────────────
        if (!offscreen.ReadPixels(pixels)) return false;
        if (!encoder.WriteFrame(pixels))   return false;

        // ── Per-frame debug log ──────────────────────────────────────────────
        Logger::Debug("Frame %d: t=%.3fs mouth=(open=%.2f form=%.2f) emotion=%s gaze=(%.2f,%.2f) head=(yaw=%.1f pitch=%.1f roll=%.1f)",
            frame, t,
            mouth.open, mouth.form,
            cue_state.emotion.c_str(),
            cue_state.gaze_x, cue_state.gaze_y,
            cue_state.head_yaw, cue_state.head_pitch, cue_state.head_roll);
    }

    const auto wall_end = std::chrono::steady_clock::now();
    const double elapsed = std::chrono::duration<double>(wall_end - wall_start).count();
    const double render_fps = total_frames / elapsed;

    Logger::Info("Rendering: frame %d/%d (100%%)", total_frames, total_frames);
    Logger::Info("Render complete: %d frames in %.2fs (%.1f fps)", total_frames, elapsed, render_fps);

    return true;
}

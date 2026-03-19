#include "live2d_model.h"
#include "../cli/logger.h"

#include <CubismModelSettingJson.hpp>
#include <CubismDefaultParameterId.hpp>
#include <Id/CubismIdManager.hpp>
#include <Motion/CubismMotion.hpp>
#include <Effect/CubismBreath.hpp>
#include <Physics/CubismPhysics.hpp>
#include <Utils/CubismString.hpp>
#include <Motion/CubismMotionQueueEntry.hpp>

#include <filesystem>
#include <fstream>

#ifdef _WIN32
#  include <Rendering/D3D11/CubismRenderer_D3D11.hpp>
#  include <WICTextureLoader.h>  // DirectXTK
#else
#  include <Rendering/OpenGL/CubismRenderer_OpenGLES2.hpp>
#  define STB_IMAGE_IMPLEMENTATION
#  include <stb_image.h>
#endif

namespace fs = std::filesystem;
using namespace Csm;
using namespace Live2D::Cubism::Framework;
using namespace Live2D::Cubism::Framework::DefaultParameterId;

// ── File I/O helpers (from LAppModel_Common pattern) ────────────────────────
csmByte* Live2DModel::CreateBuffer(const csmChar* path, csmSizeInt* size)
{
    std::ifstream f(fs::u8path(path), std::ios::binary | std::ios::ate);
    if (!f.is_open()) {
        Logger::Error("Cannot read file \"%s\"", path);
        *size = 0;
        return nullptr;
    }
    *size = static_cast<csmSizeInt>(f.tellg());
    f.seekg(0);
    auto* buf = new csmByte[*size];
    f.read(reinterpret_cast<char*>(buf), *size);
    return buf;
}

void Live2DModel::DeleteBuffer(csmByte* buffer, const csmChar*)
{
    delete[] buffer;
}

// ── Constructor / Destructor ─────────────────────────────────────────────────
Live2DModel::Live2DModel()
    : CubismUserModel()
{}

Live2DModel::~Live2DModel()
{
    for (auto& t : _textures) {
#ifdef _WIN32
        if (t.srv) { t.srv->Release(); t.srv = nullptr; }
        if (t.res) { t.res->Release(); t.res = nullptr; }
#else
        if (t.id) { glDeleteTextures(1, &t.id); t.id = 0; }
#endif
    }
    _textures.clear();

    if (_motions.GetSize() > 0) {
        for (auto it = _motions.Begin(); it != _motions.End(); ++it)
            ACubismMotion::Delete(it->Second);
        _motions.Clear();
    }
    if (_expressions.GetSize() > 0) {
        for (auto it = _expressions.Begin(); it != _expressions.End(); ++it)
            ACubismMotion::Delete(it->Second);
        _expressions.Clear();
    }

    delete _setting;
}

// ── Load ─────────────────────────────────────────────────────────────────────
#ifdef _WIN32
bool Live2DModel::Load(const std::string& model3_json_path,
                       ID3D11Device*        device,
                       ID3D11DeviceContext* context)
#else
bool Live2DModel::Load(const std::string& model3_json_path)
#endif
{
    // Separate directory and filename
    fs::path p(model3_json_path);
    _modelDir = (p.parent_path().string() + "/").c_str();

    csmSizeInt size;
    csmByte* buf = CreateBuffer(model3_json_path.c_str(), &size);
    if (!buf) return false;

    auto* setting = new CubismModelSettingJson(buf, size);
    DeleteBuffer(buf);

    SetupModel(setting);

    if (!_model) {
        Logger::Error("Failed to load Live2D model from \"%s\"", model3_json_path.c_str());
        return false;
    }

    // Create renderer and upload textures
    CreateRenderer();
#ifdef _WIN32
    SetupTextures(device, context);
#else
    SetupTextures();
#endif

    Logger::Info("Live2D model loaded: %d parameters, %d expressions, %d motions, physics %s",
        _model->GetParameterCount(),
        (int)_expressionNames.size(),
        (int)_motionNames.size(),
        _physics ? "enabled" : "disabled");

    return true;
}

void Live2DModel::SetupModel(ICubismModelSetting* setting)
{
    _updating    = true;
    _initialized = false;
    _setting     = setting;

    csmByte* buf;
    csmSizeInt size;

    // Model
    if (strcmp(_setting->GetModelFileName(), "") != 0) {
        csmString path = csmString(_modelDir) + _setting->GetModelFileName();
        buf = CreateBuffer(path.GetRawString(), &size);
        if (buf) { LoadModel(buf, size, _mocConsistency); DeleteBuffer(buf); }
    }

    // Expressions
    for (int i = 0; i < _setting->GetExpressionCount(); ++i) {
        csmString name = _setting->GetExpressionName(i);
        csmString path = csmString(_modelDir) + _setting->GetExpressionFileName(i);
        buf = CreateBuffer(path.GetRawString(), &size);
        if (buf) {
            auto* motion = LoadExpression(buf, size, name.GetRawString());
            if (motion) {
                if (_expressions[name]) ACubismMotion::Delete(_expressions[name]);
                _expressions[name] = motion;
                _expressionNames.push_back(name.GetRawString());
            }
            DeleteBuffer(buf);
        }
    }

    // Physics
    if (strcmp(_setting->GetPhysicsFileName(), "") != 0) {
        csmString path = csmString(_modelDir) + _setting->GetPhysicsFileName();
        buf = CreateBuffer(path.GetRawString(), &size);
        if (buf) { LoadPhysics(buf, size); DeleteBuffer(buf); }
    }

    // Pose
    if (strcmp(_setting->GetPoseFileName(), "") != 0) {
        csmString path = csmString(_modelDir) + _setting->GetPoseFileName();
        buf = CreateBuffer(path.GetRawString(), &size);
        if (buf) { LoadPose(buf, size); DeleteBuffer(buf); }
    }

    // Eye blink
    if (_setting->GetEyeBlinkParameterCount() > 0)
        _eyeBlink = CubismEyeBlink::Create(_setting);

    // Breath — store base params so SetBreathSpeed can rescale later
    {
        _breath = CubismBreath::Create();
        auto* idMgr = CubismFramework::GetIdManager();

        const auto& bc = _cfg.breath;
        _breathBaseParams = {
            {idMgr->GetId(ParamAngleX),     bc.angle_x.offset,      bc.angle_x.peak,      bc.angle_x.cycle,      bc.angle_x.weight},
            {idMgr->GetId(ParamAngleY),     bc.angle_y.offset,      bc.angle_y.peak,      bc.angle_y.cycle,      bc.angle_y.weight},
            {idMgr->GetId(ParamAngleZ),     bc.angle_z.offset,      bc.angle_z.peak,      bc.angle_z.cycle,      bc.angle_z.weight},
            {idMgr->GetId(ParamBodyAngleX), bc.body_angle_x.offset, bc.body_angle_x.peak, bc.body_angle_x.cycle, bc.body_angle_x.weight},
            {idMgr->GetId(ParamBreath),     bc.breath_param.offset, bc.breath_param.peak, bc.breath_param.cycle, bc.breath_param.weight},
        };

        csmVector<CubismBreath::BreathParameterData> bp;
        for (const auto& p : _breathBaseParams)
            bp.PushBack({p.id, p.offset, p.peak, p.cycle, p.weight});
        _breath->SetParameters(bp);

        // Compute max speed (units/s) = peak * weight * (2π / cycle)
        _breathMaxSpeed.clear();
        constexpr float kTwoPi = 6.28318530718f;
        for (const auto& p : _breathBaseParams)
            _breathMaxSpeed[p.id] = p.peak * p.weight * (kTwoPi / p.cycle);
    }

    // Preload motions
    for (int g = 0; g < _setting->GetMotionGroupCount(); ++g) {
        const csmChar* group = _setting->GetMotionGroupName(g);
        const int count = _setting->GetMotionCount(group);
        for (int i = 0; i < count; ++i) {
            csmString name = Utils::CubismString::GetFormatedString("%s_%d", group, i);
            csmString path = csmString(_modelDir) + _setting->GetMotionFileName(group, i);
            buf = CreateBuffer(path.GetRawString(), &size);
            if (buf) {
                auto* motion = static_cast<CubismMotion*>(
                    LoadMotion(buf, size, name.GetRawString(), nullptr, nullptr, _setting, group, i));
                if (motion) {
                    if (_motions[name]) ACubismMotion::Delete(_motions[name]);
                    _motions[name] = motion;
                    // Add group name to motion names list (avoid duplicates)
                    if (std::find(_motionNames.begin(), _motionNames.end(), std::string(group)) == _motionNames.end())
                        _motionNames.push_back(group);
                }
                DeleteBuffer(buf);
            }
        }
    }

    // Layout
    csmMap<csmString, csmFloat32> layout;
    _setting->GetLayoutMap(layout);
    _modelMatrix->SetupFromLayout(layout);

    _model->SaveParameters();
    _motionManager->StopAllMotions();

    // Cache parameter IDs
    auto* ids = CubismFramework::GetIdManager();
    _idParamAngleX     = ids->GetId(ParamAngleX);
    _idParamAngleY     = ids->GetId(ParamAngleY);
    _idParamAngleZ     = ids->GetId(ParamAngleZ);
    _idParamBodyAngleX = ids->GetId(ParamBodyAngleX);
    _idParamEyeBallX   = ids->GetId(ParamEyeBallX);
    _idParamEyeBallY   = ids->GetId(ParamEyeBallY);
    _idParamMouthOpenY = ids->GetId("ParamMouthOpenY");
    _idParamMouthForm  = ids->GetId("ParamMouthForm");

    _updating    = false;
    _initialized = true;
}

#ifdef _WIN32
void Live2DModel::SetupTextures(ID3D11Device* device, ID3D11DeviceContext* context)
{
    const int texCount = _setting->GetTextureCount();
    _textures.resize(texCount);

    auto* renderer = GetRenderer<Rendering::CubismRenderer_D3D11>();

    for (int i = 0; i < texCount; ++i) {
        const char* fname = _setting->GetTextureFileName(i);
        if (!fname || fname[0] == '\0') continue;

        const std::string texPath = std::string(_modelDir.GetRawString()) + fname;

        // Convert to wide
        wchar_t wpath[1024];
        MultiByteToWideChar(CP_UTF8, 0, texPath.c_str(), -1, wpath, 1024);

        ID3D11Resource*           res = nullptr;
        ID3D11ShaderResourceView* srv = nullptr;
        HRESULT hr = DirectX::CreateWICTextureFromFileEx(
            device, context, wpath, 0,
            D3D11_USAGE_DEFAULT, D3D11_BIND_SHADER_RESOURCE, 0, 0,
            DirectX::WIC_LOADER_DEFAULT, &res, &srv);

        if (SUCCEEDED(hr)) {
            _textures[i] = { res, srv };
            renderer->BindTexture(i, srv);
        } else {
            Logger::Warn("Texture load failed for \"%s\": 0x%08X", texPath.c_str(), (unsigned)hr);
        }
    }

    renderer->IsPremultipliedAlpha(false);
}

#else  // Linux / OpenGL

void Live2DModel::SetupTextures()
{
    const int texCount = _setting->GetTextureCount();
    _textures.resize(texCount);

    auto* renderer = GetRenderer<Rendering::CubismRenderer_OpenGLES2>();

    for (int i = 0; i < texCount; ++i) {
        const char* fname = _setting->GetTextureFileName(i);
        if (!fname || fname[0] == '\0') continue;

        const std::string texPath = std::string(_modelDir.GetRawString()) + fname;

        int w = 0, h = 0, channels = 0;
        unsigned char* pixels = stbi_load(texPath.c_str(), &w, &h, &channels, STBI_rgb_alpha);
        if (!pixels) {
            Logger::Warn("Texture load failed: \"%s\" — %s",
                         texPath.c_str(), stbi_failure_reason());
            continue;
        }

        GLuint texId = 0;
        glGenTextures(1, &texId);
        glBindTexture(GL_TEXTURE_2D, texId);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,
                     w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glGenerateMipmap(GL_TEXTURE_2D);

        stbi_image_free(pixels);

        _textures[i] = { texId };
        renderer->BindTexture(i, texId);
    }

    renderer->IsPremultipliedAlpha(false);
}
#endif  // _WIN32

// ── Per-frame update ─────────────────────────────────────────────────────────
void Live2DModel::Update(float deltaTime, const MouthState& mouth, const CueState& cue)
{
    _userTime += deltaTime;

    _model->LoadParameters();

    if (!_motionManager->IsFinished()) {
        _motionManager->UpdateMotion(_model, deltaTime);
    }

    // Normalisation: move each parameter from its start value to the valid-entry
    // boundary using a smoothstep curve (ease-in/ease-out) over _normalisationDuration
    // seconds.  The position is written BEFORE SaveParameters so it becomes the
    // saved base for motion blending — the nod's FadeIn blends FROM the boundary,
    // not from the motion-only 0° returned by LoadParameters.
    //
    // Smoothstep: f(t) = t²(3-2t) for t ∈ [0,1].
    //   velocity = 0 at both endpoints → no snap-start or snap-stop.
    if (_normalisationActive) {
        _normalisationElapsed += deltaTime;
        const float t      = std::min(_normalisationElapsed / _normalisationDuration, 1.0f);
        const float smooth = t * t * (3.0f - 2.0f * t);  // smoothstep

        for (const auto& np : _normalisationParams)
            _model->SetParameterValue(np.id, np.start + (np.target - np.start) * smooth);

        if (t >= 1.0f) {
            _normalisationActive = false;
            PlayMotionGroup(_normalisationPendingMotion);
            // Prime the breath guard: UpdateMotion for the newly-queued motion
            // only runs next frame (GetCurrentPriority still 0 this frame).
            // Set flags now so the guard holds on this transition frame.
            // Use the same entry-ramp logic (not a snap) for consistency with #5.
            if (!_suppressBreathGuard) {
                _reactionFadeWeight += deltaTime / _cfg.animation.breath_guard_entry_fade_duration;
                if (_reactionFadeWeight > 1.0f) _reactionFadeWeight = 1.0f;
                _reactionWasActive = true;
            }
        }
    }

    _model->SaveParameters();  // captures normalised position; motion blends FROM here

    // Expressions
    if (_expressionManager)
        _expressionManager->UpdateMotion(_model, deltaTime);

    // Gaze / head from cue state.
    // Suppressed while: a reaction motion is playing (priority ≥ 2), normalisation
    // is active, OR the post-reaction breath-guard fade is still running
    // (_reactionFadeWeight > 0).  The fade condition prevents gaze from snapping
    // the head to the cue position on the one frame between normalisation completing
    // and the motion registering priority ≥ 2.
    if (_motionManager->GetCurrentPriority() < _cfg.animation.motion_priority_threshold
        && !_normalisationActive
        && _reactionFadeWeight <= 0.0f) {
        _model->SetParameterValue(_idParamEyeBallX, cue.gaze_x);
        _model->SetParameterValue(_idParamEyeBallY, cue.gaze_y);
        _model->SetParameterValue(_idParamAngleX,   cue.head_yaw);
        _model->SetParameterValue(_idParamAngleY,   cue.head_pitch);
        _model->SetParameterValue(_idParamAngleZ,   cue.head_roll);
    }

    // Mouth from lipsync sequencer
    _model->SetParameterValue(_idParamMouthOpenY, mouth.open, _cfg.lipsync.smoothing_open);
    _model->SetParameterValue(_idParamMouthForm,  mouth.form, _cfg.lipsync.smoothing_form);

    // Breath guard: suppress / blend breath during and after reaction motions.
    // Entry: _reactionFadeWeight ramps 0→1 over entry_fade_duration (fixes entry snap, #5).
    // Exit:  _reactionFadeWeight ramps 1→0 over exit_fade_duration after reaction ends.
    // Skipped entirely if the current reaction has breath_guard: "none".
    {
        const int currentPriority = _motionManager->GetCurrentPriority();
        if (currentPriority >= _cfg.animation.motion_priority_threshold || _normalisationActive) {
            if (!_suppressBreathGuard) {
                _reactionFadeWeight += deltaTime / _cfg.animation.breath_guard_entry_fade_duration;
                if (_reactionFadeWeight > 1.0f) _reactionFadeWeight = 1.0f;
                _reactionWasActive = true;
            }
        } else if (_reactionWasActive) {
            // TODO(renderer): exit breath guard fires only AFTER Cubism FadeOut completes (priority
            // drops below threshold). During FadeOut, breath remains fully suppressed and its phase
            // continues accumulating. The subsequent 0.5s exit fade is too short for large-amplitude
            // params (AngleX ±15° ⟹ 30°/s apparent velocity at w=1→0). This causes the visible
            // "snap" on motion exit for any reaction using breath_guard:"lerp" with >~35% range.
            //
            // Proper fix: begin the exit blend during FadeOut (overlap with Cubism weight ramp),
            // or play idle at priority 1 alongside the reaction FadeOut so breath never zeros.
            // Tracked in: https://github.com/hyang0129/live2d/issues/15
            _reactionFadeWeight -= deltaTime / _cfg.animation.breath_guard_exit_fade_duration;
            if (_reactionFadeWeight <= 0.0f) {
                _reactionFadeWeight = 0.0f;
                _reactionWasActive  = false;
            }
        }

        if (_breath) {
            if (_reactionFadeWeight > 0.0f) {
                const float savedAngleX     = _model->GetParameterValue(_idParamAngleX);
                const float savedAngleY     = _model->GetParameterValue(_idParamAngleY);
                const float savedAngleZ     = _model->GetParameterValue(_idParamAngleZ);
                const float savedBodyAngleX = _model->GetParameterValue(_idParamBodyAngleX);

                _breath->UpdateParameters(_model, deltaTime);

                const float w = _reactionFadeWeight;
                _model->SetParameterValue(_idParamAngleX,
                    _model->GetParameterValue(_idParamAngleX)     * (1.0f - w) + savedAngleX     * w);
                _model->SetParameterValue(_idParamAngleY,
                    _model->GetParameterValue(_idParamAngleY)     * (1.0f - w) + savedAngleY     * w);
                _model->SetParameterValue(_idParamAngleZ,
                    _model->GetParameterValue(_idParamAngleZ)     * (1.0f - w) + savedAngleZ     * w);
                _model->SetParameterValue(_idParamBodyAngleX,
                    _model->GetParameterValue(_idParamBodyAngleX) * (1.0f - w) + savedBodyAngleX * w);
            } else {
                _breath->UpdateParameters(_model, deltaTime);
            }
        }
    }
    if (_physics) _physics->Evaluate(_model, deltaTime);
    if (_pose)    _pose->UpdateParameters(_model, deltaTime);

    _model->Update();
}

void Live2DModel::Draw(CubismMatrix44& vpMatrix)
{
    if (!_model) return;
    vpMatrix.MultiplyByMatrix(_modelMatrix);
#ifdef _WIN32
    auto* renderer = GetRenderer<Rendering::CubismRenderer_D3D11>();
#else
    auto* renderer = GetRenderer<Rendering::CubismRenderer_OpenGLES2>();
#endif
    renderer->SetMvpMatrix(&vpMatrix);
    renderer->DrawModel();
}

void Live2DModel::SetExpression(const std::string& name)
{
    auto* motion = _expressions[name.c_str()];
    if (motion) {
        _expressionManager->StartMotion(motion, false);
    } else {
        Logger::Warn("SetExpression: \"%s\" not loaded", name.c_str());
    }
}

void Live2DModel::SetReactionEntries(const std::map<std::string, ReactionEntry>& entries)
{
    _reactionEntries = entries;
}

void Live2DModel::SetConfig(const RendererConfig& cfg)
{
    _cfg = cfg;
}

void Live2DModel::SetBreathSpeed(float multiplier)
{
    if (!_breath || multiplier <= 0.0f || _breathBaseParams.empty()) return;

    csmVector<CubismBreath::BreathParameterData> bp;
    for (const auto& p : _breathBaseParams)
        bp.PushBack({p.id, p.offset, p.peak, p.cycle / multiplier, p.weight});
    _breath->SetParameters(bp);
}

void Live2DModel::PlayMotionGroup(const std::string& name)
{
    for (int i = 0; i < _setting->GetMotionGroupCount(); ++i) {
        const csmChar* group = _setting->GetMotionGroupName(i);
        if (strcmp(group, name.c_str()) == 0 && _setting->GetMotionCount(group) > 0) {
            csmString motionName = Utils::CubismString::GetFormatedString("%s_0", group);
            auto* motion = static_cast<CubismMotion*>(_motions[motionName.GetRawString()]);
            if (motion) {
                _motionManager->StartMotionPriority(motion, false,
                    _cfg.animation.motion_priority_threshold);
                return;
            }
        }
    }
    Logger::Warn("PlayMotionGroup: group \"%s\" not found in motions", name.c_str());
}

std::vector<Live2DModel::NormParam> Live2DModel::BuildNormParams(
    const std::map<std::string, EntryBound>& valid_entry)
{
    std::vector<NormParam> params;
    auto* ids = CubismFramework::GetIdManager();
    for (const auto& [paramName, bound] : valid_entry) {
        const CubismId* id = ids->GetId(paramName.c_str());
        if (!id) {
            Logger::Warn("[norm_params] valid_entry param \"%s\" not found on model — skipping",
                         paramName.c_str());
            continue;
        }
        float cur = _model->GetParameterValue(id);
        if (cur < bound.min)
            params.push_back({id, cur, bound.min});   // start, target
        else if (cur > bound.max)
            params.push_back({id, cur, bound.max});
    }
    return params;
}

void Live2DModel::TriggerMotion(const std::string& name, float cue_time)
{
    // Resolve breath guard preference before any early returns.
    {
        auto bit = _reactionEntries.find(name);
        _suppressBreathGuard = (bit != _reactionEntries.end()
                                && bit->second.breath_guard == BreathGuardMode::None);
    }

    auto it = _reactionEntries.find(name);
    if (it != _reactionEntries.end() && it->second.entry_dependent
        && it->second.out_of_range_mode != OutOfRangeMode::None) {
        const ReactionEntry& meta = it->second;
        auto normParams = BuildNormParams(meta.valid_entry);

        if (!normParams.empty()) {
            // Determine normalisation rate.
            // If meta.normalise_rate == 0 (auto), derive from 2× the breath max
            // speed for the most-violated parameter.  This makes the normalisation
            // feel proportional to the natural idle motion rather than arbitrary.
            float rate = meta.normalise_rate;
            if (rate <= 0.0f) {
                float maxBreathSpeed = 0.0f;
                for (const auto& np : normParams) {
                    auto it = _breathMaxSpeed.find(np.id);
                    if (it != _breathMaxSpeed.end())
                        maxBreathSpeed = std::max(maxBreathSpeed, it->second);
                }
                rate = (maxBreathSpeed > 0.0f)
                    ? _cfg.normalisation.auto_rate_multiplier * maxBreathSpeed
                    : _cfg.normalisation.fallback_rate;
            }

            // Estimate normalisation duration from worst-case violation
            float maxDist = 0.0f;
            for (const auto& np : normParams) {
                float cur = _model->GetParameterValue(np.id);
                maxDist = std::max(maxDist, std::abs(np.target - cur));
            }

            // Guard against a zero rate (should not happen given auto-compute fallback,
            // but prevents UB if the path is ever reached with a bad registry value).
            if (rate <= 0.0f) {
                Logger::Warn("[norm] rate <= 0 after compute — clamping to fallback %.1f",
                             _cfg.normalisation.fallback_rate);
                rate = _cfg.normalisation.fallback_rate;
            }

            // Enforce minimum duration so even tiny violations produce a perceptible movement.
            const float kMinNormDuration = _cfg.normalisation.minimum_duration;
            const float rawDuration = maxDist / rate;
            if (rawDuration < kMinNormDuration && maxDist > 0.0f)
                rate = maxDist / kMinNormDuration;

            const float normDuration = maxDist / rate;
            const float actualStart  = cue_time + normDuration;
            const float recommended  = cue_time - normDuration;

            if (meta.out_of_range_mode == OutOfRangeMode::Explicit) {
                // Structured error log — do not play
                auto* ids = CubismFramework::GetIdManager();
                std::string violations;
                for (const auto& np : normParams) {
                    float cur = _model->GetParameterValue(np.id);
                    for (const auto& [pname, bound] : meta.valid_entry) {
                        if (ids->GetId(pname.c_str()) == np.id) {
                            char buf[256];
                            snprintf(buf, sizeof(buf),
                                " {param:%s value:%.1f valid:%.1f..%.1f}",
                                pname.c_str(), cur, bound.min, bound.max);
                            violations += buf;
                            break;
                        }
                    }
                }
                Logger::Error(
                    "[motion_entry_out_of_range] motion=%s cue_time=%.3fs"
                    " violations=%s"
                    " normalise_rate=%.1f estimated_norm_duration=%.3fs"
                    " recommended_trigger=%.3fs",
                    name.c_str(), cue_time, violations.c_str(),
                    rate, normDuration, recommended);
                return;
            } else {
                // Implicit: warn then queue normalise-then-play
                auto* ids = CubismFramework::GetIdManager();
                std::string violStr;
                for (const auto& np : normParams) {
                    float cur = _model->GetParameterValue(np.id);
                    for (const auto& [pname, bound] : meta.valid_entry) {
                        if (ids->GetId(pname.c_str()) == np.id) {
                            char buf[128];
                            snprintf(buf, sizeof(buf), " %s=%.1f(valid:%.1f..%.1f)",
                                     pname.c_str(), cur, bound.min, bound.max);
                            violStr += buf;
                            break;
                        }
                    }
                }
                Logger::Warn(
                    "[motion] %s: entry out of range —%s"
                    " | normalise_rate=%.1f units/s normalisation_duration=%.3fs"
                    " | actual_clip_start=t=%.3f (requested t=%.3f)"
                    " | to hit t=%.3f trigger normalisation at t=%.3f",
                    name.c_str(), violStr.c_str(),
                    rate, normDuration,
                    actualStart, cue_time,
                    cue_time, recommended);

                _normalisationActive        = true;
                _normalisationPendingMotion = name;
                _normalisationRate          = rate;         // retained for logging
                _normalisationElapsed       = 0.0f;
                _normalisationDuration      = normDuration;
                _normalisationParams        = normParams;
                return;
            }
        }
    }

    PlayMotionGroup(name);
}

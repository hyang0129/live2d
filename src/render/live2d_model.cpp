#include "live2d_model.h"
#include "../cli/logger.h"

#include <CubismModelSettingJson.hpp>
#include <CubismDefaultParameterId.hpp>
#include <Id/CubismIdManager.hpp>
#include <Motion/CubismMotion.hpp>
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

    // Breath
    {
        _breath = CubismBreath::Create();
        csmVector<CubismBreath::BreathParameterData> bp;
        auto* idMgr = CubismFramework::GetIdManager();
        bp.PushBack({idMgr->GetId(ParamAngleX),     0.f, 15.f,  6.5345f, 0.5f});
        bp.PushBack({idMgr->GetId(ParamAngleY),     0.f,  8.f,  3.5345f, 0.5f});
        bp.PushBack({idMgr->GetId(ParamAngleZ),     0.f, 10.f,  5.5345f, 0.5f});
        bp.PushBack({idMgr->GetId(ParamBodyAngleX), 0.f,  4.f, 15.5345f, 0.5f});
        bp.PushBack({idMgr->GetId(ParamBreath),     0.5f, 0.5f, 3.2345f, 0.5f});
        _breath->SetParameters(bp);
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

    // Idle motion if no motion running
    if (_motionManager->IsFinished()) {
        // Start first idle motion if available
        if (_setting->GetMotionCount("Idle") > 0 && _motions.GetSize() > 0) {
            csmString idleName = Utils::CubismString::GetFormatedString("Idle_0");
            auto* idle = static_cast<CubismMotion*>(_motions[idleName.GetRawString()]);
            if (idle) _motionManager->StartMotionPriority(idle, false, 1);
        }
    } else {
        _motionManager->UpdateMotion(_model, deltaTime);
    }

    _model->SaveParameters();

    // Expressions
    if (_expressionManager)
        _expressionManager->UpdateMotion(_model, deltaTime);

    // Gaze / head from cue state (set directly, overrides motion data)
    _model->SetParameterValue(_idParamEyeBallX,   cue.gaze_x);
    _model->SetParameterValue(_idParamEyeBallY,   cue.gaze_y);
    _model->SetParameterValue(_idParamAngleX,     cue.head_yaw);
    _model->SetParameterValue(_idParamAngleY,     cue.head_pitch);
    _model->SetParameterValue(_idParamAngleZ,     cue.head_roll);

    // Mouth from lipsync sequencer
    _model->SetParameterValue(_idParamMouthOpenY, mouth.open, 0.8f);
    _model->SetParameterValue(_idParamMouthForm,  mouth.form, 0.8f);

    // Breath and physics
    if (_breath)  _breath->UpdateParameters(_model, deltaTime);
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

void Live2DModel::TriggerMotion(const std::string& name)
{
    // Find first motion in this group
    for (int i = 0; i < _setting->GetMotionGroupCount(); ++i) {
        const csmChar* group = _setting->GetMotionGroupName(i);
        if (strcmp(group, name.c_str()) == 0 && _setting->GetMotionCount(group) > 0) {
            csmString motionName = Utils::CubismString::GetFormatedString("%s_0", group);
            auto* motion = static_cast<CubismMotion*>(_motions[motionName.GetRawString()]);
            if (motion) {
                _motionManager->StartMotionPriority(motion, false, 2);
                return;
            }
        }
    }
    Logger::Warn("TriggerMotion: group \"%s\" not found in motions", name.c_str());
}

#pragma once

#include <CubismFramework.hpp>
#include <Model/CubismUserModel.hpp>
#include <ICubismModelSetting.hpp>
#include <Motion/CubismExpressionMotion.hpp>
#include <Motion/ACubismMotion.hpp>
#include <Type/csmMap.hpp>
#include <Type/csmString.hpp>

#ifdef _WIN32
#  include <Rendering/D3D11/CubismOffscreenSurface_D3D11.hpp>
#  include <d3d11.h>
#else
#  include <GL/glew.h>
#endif

#include <string>
#include <vector>
#include <map>
#include "cue_sequencer.h"
#include "lipsync_sequencer.h"
#include "renderer_config.h"
#include "../cli/model_resolver.h"

class Live2DModel : public Csm::CubismUserModel {
public:
    Live2DModel();
    ~Live2DModel();

    // Load model from resolved .model3.json path.
#ifdef _WIN32
    // device/context must outlive this object.
    bool Load(const std::string& model3_json_path,
              ID3D11Device*        device,
              ID3D11DeviceContext* context);
#else
    // GL context must be current when called and must outlive this object.
    bool Load(const std::string& model3_json_path);
#endif

    // Names available on the loaded model (for cue validation)
    const std::vector<std::string>& ExpressionNames() const { return _expressionNames; }
    const std::vector<std::string>& MotionNames()     const { return _motionNames; }

    // Per-frame update. deltaTime in seconds.
    void Update(float deltaTime, const MouthState& mouth, const CueState& cue);

    // Draw to current render target using View-Projection matrix.
    void Draw(Csm::CubismMatrix44& vpMatrix);

    void SetExpression(const std::string& name);
    void TriggerMotion(const std::string& name, float cue_time);
    void SetReactionEntries(const std::map<std::string, ReactionEntry>& entries);
    // Scale breath speed: 2.0 = twice as fast (halves cycle period).
    // Must be called after Load().
    void SetBreathSpeed(float multiplier);
    // Apply renderer config. Must be called BEFORE Load() so SetupModel uses
    // the correct breath parameters.
    void SetConfig(const RendererConfig& cfg);

private:
    struct NormParam {
        const Csm::CubismId* id;
        float start;   // value at normalisation trigger time (breath-included)
        float target;  // boundary value to reach
    };

    // File I/O helpers (not virtual in base; pattern from LAppModel_Common)
    Csm::csmByte* CreateBuffer(const Csm::csmChar* path, Csm::csmSizeInt* size);
    void DeleteBuffer(Csm::csmByte* buffer, const Csm::csmChar* path = "");

    void PlayMotionGroup(const std::string& group_name);
    std::vector<NormParam> BuildNormParams(const std::map<std::string, EntryBound>& valid_entry);

    void SetupModel(Csm::ICubismModelSetting* setting);
#ifdef _WIN32
    void SetupTextures(ID3D11Device* device, ID3D11DeviceContext* context);
#else
    void SetupTextures();
#endif

    Csm::ICubismModelSetting* _setting = nullptr;
    Csm::csmString            _modelDir;

    // Motion and expression maps (same pattern as LAppModel sample)
    Csm::csmMap<Csm::csmString, Csm::ACubismMotion*> _motions;
    Csm::csmMap<Csm::csmString, Csm::ACubismMotion*> _expressions;

    std::vector<std::string> _expressionNames;
    std::vector<std::string> _motionNames;

    // Parameter IDs cached at load
    const Csm::CubismId* _idParamAngleX      = nullptr;
    const Csm::CubismId* _idParamAngleY      = nullptr;
    const Csm::CubismId* _idParamAngleZ      = nullptr;
    const Csm::CubismId* _idParamBodyAngleX  = nullptr;
    const Csm::CubismId* _idParamEyeBallX    = nullptr;
    const Csm::CubismId* _idParamEyeBallY    = nullptr;
    const Csm::CubismId* _idParamMouthOpenY  = nullptr;
    const Csm::CubismId* _idParamMouthForm   = nullptr;

    // Textures owned by this model
#ifdef _WIN32
    struct TexEntry {
        ID3D11Resource*           res = nullptr;
        ID3D11ShaderResourceView* srv = nullptr;
    };
#else
    struct TexEntry {
        GLuint id = 0;
    };
#endif
    std::vector<TexEntry> _textures;

    float _userTime = 0.0f;

    float _reactionFadeWeight    = 0.0f;
    bool  _reactionWasActive     = false;
    bool  _suppressBreathGuard   = false; // set from reaction's breath_guard registry field

    bool _normalisationActive = false;
    std::string _normalisationPendingMotion;
    float _normalisationRate     = 0.0f;  // retained for logging only
    float _normalisationElapsed  = 0.0f;  // time since normalisation started
    float _normalisationDuration = 0.0f;  // total normalisation time (seconds)
    std::vector<NormParam> _normalisationParams;
    std::map<std::string, ReactionEntry> _reactionEntries;

    // Breath base params (stored to allow SetBreathSpeed rescaling)
    struct BreathParam {
        const Csm::CubismId* id;
        float offset, peak, cycle, weight;
    };
    std::vector<BreathParam> _breathBaseParams;
    // Per-parameter maximum speed from breath (units/s), computed at load
    std::map<const Csm::CubismId*, float> _breathMaxSpeed;

    // Renderer config (set via SetConfig before Load; all fields have safe defaults)
    RendererConfig _cfg;
};

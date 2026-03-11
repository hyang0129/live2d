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
#include "cue_sequencer.h"
#include "lipsync_sequencer.h"

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
    void TriggerMotion(const std::string& name);

private:
    // File I/O helpers (not virtual in base; pattern from LAppModel_Common)
    Csm::csmByte* CreateBuffer(const Csm::csmChar* path, Csm::csmSizeInt* size);
    void DeleteBuffer(Csm::csmByte* buffer, const Csm::csmChar* path = "");

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
};

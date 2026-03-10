# Live2D Cubism SDK Native — Developer Reference

This document summarizes how to work with the Live2D Cubism SDK Native to load, animate, and render Live2D models.

---

## Repository Layout

```
cubism/
├── Core/                   # Precompiled C library + single header (Live2DCubismCore.h)
├── Framework/              # C++ wrappers for rendering and animation
│   └── src/
│       ├── Effect/         # EyeBlink, Breath, Pose
│       ├── Id/             # CubismId, CubismIdManager
│       ├── Math/           # Matrix, Vector, TargetPoint utilities
│       ├── Model/          # CubismMoc, CubismModel, CubismModelSettingJson
│       ├── Motion/         # CubismMotion, CubismMotionManager, expressions
│       ├── Physics/        # CubismPhysics
│       ├── Rendering/      # CubismRenderer + platform backends
│       ├── Type/           # csmVector, csmMap, csmString
│       └── Utils/          # CubismJson, CubismDebug
└── Samples/
    ├── D3D9/               # DirectX 9 demo
    ├── D3D11/              # DirectX 11 demo  ← best reference for Windows
    ├── OpenGL/             # OpenGL ES 2.0 demo (cross-platform)
    ├── Metal/              # Metal demo (macOS/iOS)
    └── Vulkan/             # Vulkan demo
```

---

## Core Concepts

| Concept | Description |
|---|---|
| **MOC** | Compiled model data (`*.moc3`). Loaded once, shared across instances. |
| **Model** | A runtime instance created from a MOC. Holds live parameter values. |
| **Parameters** | Named float values that drive deformation (e.g. eye open, head angle). |
| **Parts** | Groupings of drawables with their own opacity and color. |
| **Drawables** | Individual mesh pieces rendered each frame. |
| **Motion** | Animation clip loaded from `*.motion3.json`; applies parameter keyframes. |
| **Expression** | A static parameter overlay loaded from an expression JSON. |
| **Physics** | Pendulum-based secondary animation loaded from `*physics3.json`. |
| **Renderer** | Platform backend that submits drawables to the GPU. |

---

## Platform Support

| Platform | Graphics APIs | Architecture |
|---|---|---|
| Windows | D3D9, D3D11, OpenGL ES 2.0 | x86, x86_64 |
| macOS | Metal, OpenGL | x86_64, ARM64 |
| iOS | Metal | ARM64, x86_64 (sim) |
| Android | OpenGL ES 2.0 | ARM64, x86, x86_64 |
| Linux | OpenGL ES 2.0 | x86_64, ARM64 (experimental) |
| UWP | D3D11 | ARM, ARM64, x64, x86 |
| HarmonyOS | OpenGL ES 2.0 | ARM64, ARMv7, x86_64 |

---

## Building

The SDK uses CMake. Each sample platform has a `proj.XXX.cmake/` subdirectory with batch scripts.

**Windows (D3D11 example):**
```bat
cd Samples/D3D11/Demo/proj.d3d11.cmake/script
proj_msvc2022.bat          # generates Visual Studio solution
nmake_msvc2022.bat         # builds from command line
```

**OpenGL (cross-platform):**
```bat
cd Samples/OpenGL/Demo/proj.win.cmake/script
proj_msvc2022.bat
```

Requirements: CMake 3.10+, Visual Studio 2015–2022 (Windows), Xcode (macOS), Android NDK (Android).

---

## End-to-End Usage

### 1 — Initialize the Framework

Implement `ICubismAllocator` to provide memory management, then start up once at application launch.

```cpp
#include "CubismFramework.hpp"

class MyAllocator : public Csm::ICubismAllocator {
    void* Allocate(const Csm::csmSizeType size) override { return malloc(size); }
    void  Deallocate(void* memory) override { free(memory); }
    void* AllocateAligned(const Csm::csmSizeType size, const Csm::csmUint32 alignment) override {
        return _aligned_malloc(size, alignment);
    }
    void  DeallocateAligned(void* alignedMemory) override { _aligned_free(alignedMemory); }
};

MyAllocator allocator;
Csm::CubismFramework::Option option;
option.LogFunction   = MyLogCallback;        // optional; can be nullptr
option.LoggingLevel  = Csm::CubismFramework::Option::LogLevel_Verbose;

Csm::CubismFramework::StartUp(&allocator, &option);
Csm::CubismFramework::Initialize();
```

### 2 — Load a Model

```cpp
#include "Model/CubismMoc.hpp"
#include "Model/CubismModel.hpp"

// Read raw bytes from disk (platform-specific)
Csm::csmSizeInt mocSize;
Csm::csmByte*   mocBytes = LoadFile("Haru/Haru.moc3", &mocSize);

Csm::CubismMoc*   moc   = Csm::CubismMoc::Create(mocBytes, mocSize);
Csm::CubismModel* model = moc->CreateModel();

free(mocBytes); // bytes are no longer needed after Create
```

### 3 — Parse Model Settings (model3.json)

`model3.json` is the manifest that lists textures, motions, expressions, physics, etc.

```cpp
#include "Model/CubismModelSettingJson.hpp"

Csm::csmSizeInt settingSize;
Csm::csmByte*   settingBytes = LoadFile("Haru/Haru.model3.json", &settingSize);

Csm::ICubismModelSetting* setting =
    new Csm::CubismModelSettingJson(settingBytes, settingSize);

free(settingBytes);

// Query the manifest
const Csm::csmChar* mocFile     = setting->GetModelFileName();      // "Haru.moc3"
Csm::csmInt32       texCount    = setting->GetTextureCount();
const Csm::csmChar* tex0        = setting->GetTextureFileName(0);   // "Haru.2048/texture_00.png"
Csm::csmInt32       motionGroups = setting->GetMotionGroupCount();
```

### 4 — Create a Platform Renderer

Choose the renderer that matches your graphics API. All share the same abstract interface.

```cpp
// DirectX 11
#include "Rendering/D3D11/CubismRenderer_D3D11.hpp"
Csm::Rendering::CubismRenderer_D3D11::InitializeConstantSettings(device, context);
Csm::Rendering::CubismRenderer* renderer = Csm::Rendering::CubismRenderer::Create();
renderer->Initialize(model);

// OpenGL ES 2.0
#include "Rendering/OpenGL/CubismRenderer_OpenGLES2.hpp"
Csm::Rendering::CubismRenderer* renderer = Csm::Rendering::CubismRenderer::Create();
renderer->Initialize(model);
```

Textures must be uploaded to the GPU and registered before the first `DrawModel()` call:

```cpp
// D3D11 example
auto* d3dRenderer =
    static_cast<Csm::Rendering::CubismRenderer_D3D11*>(renderer);
d3dRenderer->BindTexture(textureIndex, d3d11ShaderResourceView);
```

### 5 — Load Motions and Expressions

```cpp
#include "Motion/CubismMotion.hpp"
#include "Motion/CubismMotionManager.hpp"
#include "Motion/CubismExpressionMotion.hpp"

Csm::CubismMotionManager* motionManager    = new Csm::CubismMotionManager();
Csm::CubismMotionManager* expressionManager = new Csm::CubismMotionManager();

// Load a motion clip
Csm::csmSizeInt motSize;
Csm::csmByte*   motBytes = LoadFile("motions/idle_01.motion3.json", &motSize);

auto* motion = static_cast<Csm::CubismMotion*>(
    Csm::CubismMotion::Create(motBytes, motSize));
motion->SetLoop(true);
free(motBytes);

// Load an expression
Csm::csmSizeInt exprSize;
Csm::csmByte*   exprBytes = LoadFile("expressions/f01.exp3.json", &exprSize);
auto* expression = Csm::CubismExpressionMotion::Create(exprBytes, exprSize);
free(exprBytes);
```

### 6 — Load Physics

```cpp
#include "Physics/CubismPhysics.hpp"

Csm::csmSizeInt physSize;
Csm::csmByte*   physBytes = LoadFile("Haru.physics3.json", &physSize);
Csm::CubismPhysics* physics = Csm::CubismPhysics::Create(physBytes, physSize);
free(physBytes);
```

### 7 — Load Eye Blink / Breath Effects

```cpp
#include "Effect/CubismEyeBlink.hpp"
#include "Effect/CubismBreath.hpp"

Csm::CubismEyeBlink* eyeBlink = Csm::CubismEyeBlink::Create(setting);
Csm::CubismBreath*   breath   = Csm::CubismBreath::Create();

// Optional: configure breath parameters manually
Csm::csmVector<Csm::CubismBreath::BreathParameterData> params;
params.PushBack({
    Csm::CubismFramework::GetIdManager()->GetId("ParamBreath"),
    0.0f, 0.5f, 3.0f, 0.5f
});
breath->SetParameters(params);
```

---

## The Main Loop

Call this every frame, passing the elapsed time in seconds.

```cpp
void Update(float deltaTime)
{
    // --- Restore parameter defaults before applying any layer ---
    model->LoadParameters();  // save/restore idiom used in samples

    // --- Apply animation layers ---
    motionManager->UpdateMotion(model, deltaTime);     // keyframe motion
    expressionManager->UpdateMotion(model, deltaTime); // expression overlay

    model->SaveParameters();

    // --- Apply automatic effects ---
    eyeBlink->UpdateParameters(model, deltaTime);
    breath->UpdateParameters(model, deltaTime);

    // --- Apply physics-based secondary animation ---
    physics->Evaluate(model, deltaTime);

    // --- Flush to Core ---
    model->Update();
}

void Draw(Csm::CubismMatrix44& mvpMatrix)
{
    // D3D11: wrap the frame
    Csm::Rendering::CubismRenderer_D3D11::StartFrame(device, context, width, height);

    renderer->SetMvpMatrix(&mvpMatrix);
    renderer->DrawModel();

    Csm::Rendering::CubismRenderer_D3D11::EndFrame(device);
}
```

---

## Manipulating Parameters Directly

Parameters are identified by `CubismIdHandle` (string-interned at startup).

```cpp
Csm::CubismIdHandle paramHeadX =
    Csm::CubismFramework::GetIdManager()->GetId("ParamAngleX");

// Set absolute value (clamped to [min, max] unless repeat mode)
model->SetParameterValue(paramHeadX, 15.0f);

// Add a delta (useful for layered animations)
model->AddParameterValue(paramHeadX, 5.0f);

// Blend toward a value (weight 0.0–1.0)
model->SetParameterValue(paramHeadX, 15.0f, 0.5f);

// Read current value
float currentVal = model->GetParameterValue(paramHeadX);

// Query constraints
float minVal  = model->GetParameterMinimumValue(paramHeadX);
float maxVal  = model->GetParameterMaximumValue(paramHeadX);
float defVal  = model->GetParameterDefaultValue(paramHeadX);
```

### Common Standard Parameter IDs

| ID String | Description |
|---|---|
| `ParamAngleX` | Head yaw (left/right) |
| `ParamAngleY` | Head pitch (up/down) |
| `ParamAngleZ` | Head roll (tilt) |
| `ParamEyeLOpen` | Left eye open amount |
| `ParamEyeROpen` | Right eye open amount |
| `ParamEyeBallX` | Eye gaze horizontal |
| `ParamEyeBallY` | Eye gaze vertical |
| `ParamMouthOpenY` | Mouth open |
| `ParamBreath` | Breathing cycle |
| `ParamBodyAngleX` | Body lean |

---

## Controlling Motions

```cpp
// Play a motion (priority 1=idle, 2=normal, 3=force)
Csm::CubismMotionQueueEntryHandle handle =
    motionManager->StartMotionPriority(motion, /*autoDelete=*/false, /*priority=*/2);

// Check if still playing
bool isFinished = motionManager->IsFinished();

// Stop all motions
motionManager->StopAllMotions();
```

---

## Hit Testing

Use drawable hit areas defined in `model3.json` to respond to touches.

```cpp
// ICubismModelSetting provides hit area names and drawable IDs
Csm::csmInt32 hitCount = setting->GetHitAreasCount();
for (Csm::csmInt32 i = 0; i < hitCount; i++) {
    const Csm::csmChar* areaName  = setting->GetHitAreaName(i);
    const Csm::csmChar* drawableId = setting->GetHitAreaId(i);

    Csm::CubismIdHandle id = Csm::CubismFramework::GetIdManager()->GetId(drawableId);
    Csm::csmInt32 drawableIndex = model->GetDrawableIndex(id);

    // Get bounding box from current vertex positions
    const Csm::csmFloat32* vertices = model->GetDrawableVertices(drawableIndex);
    Csm::csmInt32 vertexCount       = model->GetDrawableVertexCount(drawableIndex);
    // ... compute AABB and test point (touchX, touchY)
}
```

---

## Clipping Masks

By default, up to 36 mask groups are batched into a single offscreen texture (fast). For complex models, switch to high-precision mode:

```cpp
renderer->UseHighPrecisionMask(true);  // render mask per-drawable (higher quality, slower)
```

---

## Part Colors and Opacity

Individual parts can have multiply/screen color tints applied on top of the model's animation.

```cpp
Csm::CubismIdHandle partId =
    Csm::CubismFramework::GetIdManager()->GetId("PartBody");

// Opacity
model->SetPartOpacity(partId, 0.8f);

// Tint colors (RGBA, 0.0–1.0)
Csm::CubismTextureColor multiplyColor(1.0f, 0.8f, 0.8f, 1.0f);
model->SetPartMultiplyColor(partId, multiplyColor);

Csm::CubismTextureColor screenColor(0.2f, 0.0f, 0.0f, 0.0f);
model->SetPartScreenColor(partId, screenColor);
```

---

## Shutdown and Cleanup

```cpp
// Destroy objects in reverse order
Csm::CubismPhysics::Delete(physics);
delete eyeBlink;
delete breath;
delete motionManager;
delete expressionManager;
delete motion;
delete expression;

Csm::Rendering::CubismRenderer::Delete(renderer);
Csm::CubismMoc::Delete(moc);  // also destroys model

delete setting;

Csm::CubismFramework::Dispose();
Csm::CubismFramework::CleanUp();
```

---

## Key Files Quick Reference

| File | Purpose |
|---|---|
| `Core/include/Live2DCubismCore.h` | Low-level C API (csmMoc, csmModel, csmUpdateModel, etc.) |
| `Framework/src/CubismFramework.hpp` | SDK lifecycle: StartUp / Initialize / Dispose |
| `Framework/src/Model/CubismMoc.hpp` | Load `.moc3`, create model instances |
| `Framework/src/Model/CubismModel.hpp` | Parameter / part / drawable access and manipulation |
| `Framework/src/Model/CubismModelSettingJson.hpp` | Parse `model3.json` |
| `Framework/src/Rendering/CubismRenderer.hpp` | Abstract renderer (SetMvpMatrix, DrawModel) |
| `Framework/src/Motion/CubismMotion.hpp` | Animation clip loading and playback |
| `Framework/src/Motion/CubismMotionManager.hpp` | Priority-based motion queue |
| `Framework/src/Motion/CubismExpressionMotion.hpp` | Expression overlays |
| `Framework/src/Physics/CubismPhysics.hpp` | Physics-based secondary animation |
| `Framework/src/Effect/CubismEyeBlink.hpp` | Automatic blink effect |
| `Framework/src/Effect/CubismBreath.hpp` | Breathing effect |
| `Samples/D3D11/Demo/` | Full Windows reference application |
| `Samples/OpenGL/Demo/` | Full cross-platform reference application |

---

## See Also

- [Live2D Cubism SDK for Native official documentation](https://docs.live2d.com/cubism-sdk-manual/cubism-sdk-for-native/)
- `Samples/D3D11/Demo/src/LAppModel.cpp` — complete model loading and update example
- `Samples/D3D11/Demo/src/LAppLive2DManager.cpp` — scene management and rendering loop

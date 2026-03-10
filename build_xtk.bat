@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
if %errorlevel% neq 0 (echo VCVARS FAILED & exit /b 1)
cd "C:\Users\HongM\Code Projects\live2d\cubism\Samples\D3D11\thirdParty\DirectXTK"
msbuild DirectXTK_Desktop_2022.sln /v:m /t:build /p:Platform=x64;Configuration=Release
if %errorlevel% neq 0 (echo MSBUILD FAILED & exit /b 1)
echo XTK BUILD SUCCESS
exit /b 0

Import-Module 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\Microsoft.VisualStudio.DevShell.dll'
Enter-VsDevShell -VsInstallPath 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools' -SkipAutomaticLocation -DevCmdArguments '-arch=x64'

$fxcDir = 'C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64'
$env:PATH = "$fxcDir;$env:PATH"
$env:WindowsSdkVerBinPath = "$fxcDir\"

$xtkDir  = 'C:\Users\HongM\Code Projects\live2d\cubism\Samples\D3D11\thirdParty\DirectXTK'
$buildDir = 'C:\Users\HongM\Code Projects\live2d\cubism\Samples\D3D11\thirdParty\DirectXTK\cmake_build_x64'

Write-Host "--- Building DirectXTK Release (shaders pre-compiled) ---"
cmake --build $buildDir --config Release -- /v:m
if ($LASTEXITCODE -ne 0) { Write-Error "cmake build failed"; exit 1 }

$lib = Get-ChildItem $buildDir -Filter "DirectXTK.lib" -Recurse | Select-Object -First 1
Write-Host "SUCCESS - lib at: $($lib.FullName)"

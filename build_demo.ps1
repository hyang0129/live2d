Import-Module 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\Microsoft.VisualStudio.DevShell.dll'
Enter-VsDevShell -VsInstallPath 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools' -SkipAutomaticLocation -DevCmdArguments '-arch=x64'

$demoSrc  = 'C:\Users\HongM\Code Projects\live2d\cubism\Samples\D3D11\Demo\proj.d3d11.cmake'
$buildDir = "$demoSrc\build\vs2022_x64_mt"

Write-Host "--- Configuring Minimum Demo ---"
cmake -S $demoSrc -B $buildDir `
    -G "Visual Studio 17 2022" -A x64 `
    -DCORE_CRL_MD=OFF `
    -DCSM_MINIMUM_DEMO=ON
if ($LASTEXITCODE -ne 0) { Write-Error "cmake config failed"; exit 1 }

Write-Host "--- Building Minimum Demo Release ---"
cmake --build $buildDir --config Release -- /v:m
if ($LASTEXITCODE -ne 0) { Write-Error "cmake build failed"; exit 1 }

$exe = Get-ChildItem $buildDir -Filter "Demo.exe" -Recurse | Select-Object -First 1
Write-Host "SUCCESS - exe at: $($exe.FullName)"

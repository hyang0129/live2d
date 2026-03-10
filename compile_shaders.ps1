Import-Module 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\Microsoft.VisualStudio.DevShell.dll'
Enter-VsDevShell -VsInstallPath 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools' -SkipAutomaticLocation -DevCmdArguments '-arch=x64'

$fxcDir = 'C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64'
$env:PATH = "$fxcDir;$env:PATH"
$env:WindowsSdkVerBinPath = "$fxcDir\"
$env:PROCESSOR_ARCHITECTURE = 'AMD64'

Write-Host "fxc: $(& fxc.exe 2>&1 | Select-Object -First 1)"

$xtkShaders = 'C:\Users\HongM\Code Projects\live2d\cubism\Samples\D3D11\thirdParty\DirectXTK\Src\Shaders'
$compiledOut = 'C:\Users\HongM\Code Projects\live2d\cubism\Samples\D3D11\thirdParty\DirectXTK\cmake_build_x64\Shaders\Compiled'

# Create output dir
New-Item -ItemType Directory -Force $compiledOut | Out-Null

$env:CompileShadersOutput = $compiledOut

Set-Location $xtkShaders
Write-Host "Running CompileShaders.cmd from: $xtkShaders"
Write-Host "Output dir: $compiledOut"

$proc = Start-Process -FilePath 'cmd.exe' -ArgumentList "/c .\CompileShaders.cmd" `
    -WorkingDirectory $xtkShaders `
    -Wait -PassThru -NoNewWindow `
    -RedirectStandardOutput "$compiledOut\compileshaders.log" `
    -RedirectStandardError "$compiledOut\compileshaders_err.log"

Write-Host "Exit code: $($proc.ExitCode)"
if ($proc.ExitCode -ne 0) {
    Write-Host "=== stdout ==="
    Get-Content "$compiledOut\compileshaders.log" -ErrorAction SilentlyContinue | Select-Object -Last 20
    Write-Host "=== stderr ==="
    Get-Content "$compiledOut\compileshaders_err.log" -ErrorAction SilentlyContinue | Select-Object -Last 20
    exit 1
}

$incCount = (Get-ChildItem $compiledOut -Filter "*.inc").Count
Write-Host "SUCCESS - compiled $incCount shader .inc files"

<#
.SYNOPSIS
  Build the Windows release folder dist\yummy-dl\ and dist\yummy-dl-windows.zip:
    yummy-dl-gui.exe + _internal\   desktop app (one-folder build, starts fast)
    yummy-dl.exe                    command-line tool (single file)
    ffmpeg.exe                      with -BundleFfmpeg
    LICENSE, THIRD-PARTY-NOTICES.md, licenses\   licence texts for yummy-dl and everything bundled
    licenses\ffmpeg\ffmpeg-*.tar.xz  FFmpeg source code, with -FfmpegSource (the GPL asks for it)

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
  powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -BundleFfmpeg [-FfmpegPath C:\...\ffmpeg.exe] [-FfmpegSource C:\...\ffmpeg-8.0.1.tar.xz]
#>
param(
    [switch]$BundleFfmpeg,
    [string]$FfmpegPath = "",
    [string]$FfmpegSource = "",
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venv = Join-Path $root ".venv-win"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    & $Python -m venv $venv
    if ($LASTEXITCODE) { throw "venv creation failed" }
}
$py = "$venv\Scripts\python.exe"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet ".[gui]" "pyinstaller>=6.10"
if ($LASTEXITCODE) { throw "pip install failed" }

if (Test-Path dist\yummy-dl) { Remove-Item -Recurse -Force dist\yummy-dl }

# GUI: one-folder build -> dist\yummy-dl\
& $py -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\yummy-dl-gui.spec
if ($LASTEXITCODE) { throw "PyInstaller (GUI) failed" }

# CLI: single file, no Qt
& $py -m PyInstaller --noconfirm --onefile --console `
    --name yummy-dl `
    --icon src\yummy_dl\gui\assets\logo.ico `
    --collect-submodules yummy_dl `
    --collect-submodules rich._unicode_data `
    --exclude-module PySide6 `
    --distpath dist --workpath build `
    src\yummy_dl\__main__.py
if ($LASTEXITCODE) { throw "PyInstaller (CLI) failed" }

& dist\yummy-dl.exe --help | Out-Null
if ($LASTEXITCODE) { throw "built CLI exe failed to run" }

$stage = Join-Path $root "dist\yummy-dl"
Copy-Item dist\yummy-dl.exe, README.md, LICENSE, THIRD-PARTY-NOTICES.md $stage -Force

$licenseArgs = @("scripts\collect_licenses.py", "$stage\licenses")
if ($BundleFfmpeg) {
    if (-not $FfmpegPath) {
        $cmd = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
        if (-not $cmd) { throw "ffmpeg.exe not on PATH; pass -FfmpegPath" }
        $FfmpegPath = $cmd.Source
    }
    Copy-Item $FfmpegPath $stage -Force
    $licenseArgs += @("--ffmpeg", $FfmpegPath)
}
# Licence texts of everything bundled (Qt, ffmpeg, Python, packages), at the versions just built.
& $py @licenseArgs
if ($LASTEXITCODE) { throw "collecting licences failed" }
if ($FfmpegSource) {
    if (-not $BundleFfmpeg) { throw "-FfmpegSource only makes sense with -BundleFfmpeg" }
    Copy-Item $FfmpegSource "$stage\licenses\ffmpeg\" -Force
}

$zip = "dist\yummy-dl-windows.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $stage -DestinationPath $zip
Write-Host "Built $stage and $zip"

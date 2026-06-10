$ErrorActionPreference = "Stop"

.\build_windows.ps1

$iscc = Get-ChildItem `
    "$env:LOCALAPPDATA\Programs\Inno Setup *\ISCC.exe", `
    "C:\Program Files (x86)\Inno Setup *\ISCC.exe", `
    "C:\Program Files\Inno Setup *\ISCC.exe" `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1

if (-not $iscc) {
    throw "Inno Setup est introuvable. Installez-le avec : winget install JRSoftware.InnoSetup"
}

& $iscc.FullName "installer\PdfEditor.iss"
if ($LASTEXITCODE -ne 0) {
    throw "La génération de l'installateur a échoué."
}

Write-Host "Installateur généré dans dist\installer\PdfEditor-Setup-0.4.0.exe"

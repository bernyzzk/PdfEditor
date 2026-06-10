$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.12 -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tools\generate_icon.py
$workPath = Join-Path $env:TEMP "pdfeditor-pyinstaller"
$distPath = Join-Path $env:TEMP "pdfeditor-dist"
.\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --workpath $workPath `
    --distpath $distPath `
    --windowed `
    --name "PdfEditor" `
    --icon "assets\pdfeditor.ico" `
    --collect-all pymupdf `
    --add-data "ocr-data;ocr-data" `
    --add-data "assets;assets" `
    run.py

if ($LASTEXITCODE -ne 0) {
    throw "La génération de l'application a échoué."
}

$finalPath = "dist\PdfEditor 0.4.0"
New-Item -ItemType Directory -Path $finalPath -Force | Out-Null
Copy-Item -Path "$distPath\PdfEditor\*" -Destination $finalPath -Recurse -Force
Write-Host "Application générée dans $finalPath\PdfEditor.exe"

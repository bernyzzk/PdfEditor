param([Parameter(Mandatory=$true)][string[]]$Paths)

$ErrorActionPreference = "Stop"
$certificate = $env:PDFEDITOR_CERTIFICATE
$password = $env:PDFEDITOR_CERTIFICATE_PASSWORD
if (-not $certificate) {
    Write-Warning "Aucun certificat Authenticode configuré. Définissez PDFEDITOR_CERTIFICATE et PDFEDITOR_CERTIFICATE_PASSWORD."
    return
}

$signtool = Get-ChildItem `
    "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe", `
    "$env:ProgramFiles\Windows Kits\10\bin\*\x64\signtool.exe" `
    -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1
if (-not $signtool) {
    throw "signtool.exe est introuvable. Installez le Windows SDK."
}

foreach ($path in $Paths) {
    & $signtool.FullName sign /fd SHA256 /td SHA256 /tr "http://timestamp.digicert.com" /f $certificate /p $password $path
    if ($LASTEXITCODE -ne 0) { throw "Échec de la signature Authenticode : $path" }
    & $signtool.FullName verify /pa $path
    if ($LASTEXITCODE -ne 0) { throw "Échec de la vérification Authenticode : $path" }
}

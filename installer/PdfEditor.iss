#define MyAppName "PdfEditor"
#define MyAppVersion "0.5.0"
#define MyAppPublisher "ERA Informatique"
#define MyAppExeName "PdfEditor.exe"

[Setup]
AppId={{5B6487C2-D260-4BC6-B75A-77D03A4CF180}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=PdfEditor-Setup-{#MyAppVersion}
SetupIconFile=..\assets\pdfeditor.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\LICENSE

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le bureau"; GroupDescription: "Icônes supplémentaires :"; Flags: unchecked

[Files]
Source: "..\dist\PdfEditor 0.5.0\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PdfEditor"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\PdfEditor"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer PdfEditor"; Flags: nowait postinstall skipifsilent

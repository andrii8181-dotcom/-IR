; Inno Setup — інсталятор S.A.D. (збирається в GitHub Actions після PyInstaller; потребує dist\SAD\)
#ifndef AppVersion
  #define AppVersion "2.1"
#endif

[Setup]
AppId={{8C1A5E7B-3D44-4B7E-9A1F-5AD0F0C5D211}
AppName=S.A.D. — Статистичний аналіз даних
AppVersion={#AppVersion}
DefaultDirName={autopf}\SAD
DefaultGroupName=S.A.D.
OutputDir=installer_output
OutputBaseFilename=SAD-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName=S.A.D.

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"

[Tasks]
Name: "desktopicon"; Description: "Створити ярлик на робочому столі"; GroupDescription: "Додатково:"

[Files]
Source: "dist\SAD\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[Icons]
Name: "{group}\S.A.D."; Filename: "{app}\SAD.exe"
Name: "{autodesktop}\S.A.D."; Filename: "{app}\SAD.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SAD.exe"; Description: "Запустити S.A.D."; Flags: nowait postinstall skipifsilent

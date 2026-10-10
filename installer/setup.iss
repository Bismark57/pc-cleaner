; PC Cleaner — Inno Setup installer script.
; AppVersion is passed from CI: ISCC.exe /DAppVersion=1.2.3 installer\setup.iss

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8F3B2A1C-9D4E-4F6A-B7C8-D0E1F2A3B4C5}
AppName=PC Cleaner
AppVersion={#AppVersion}
AppVerName=PC Cleaner {#AppVersion}
AppPublisher=Bismark57
AppPublisherURL=https://github.com/Bismark57/pc-cleaner
DefaultDirName={autopf}\PC Cleaner
DefaultGroupName=PC Cleaner
OutputDir=..\installer-output
OutputBaseFilename=PC-Cleaner-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName=PC Cleaner
VersionInfoVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\PC Cleaner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PC Cleaner"; Filename: "{app}\PC Cleaner.exe"
Name: "{group}\Uninstall PC Cleaner"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PC Cleaner"; Filename: "{app}\PC Cleaner.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\PC Cleaner.exe"; Description: "Launch PC Cleaner"; Flags: nowait postinstall skipifsilent shellexec

; Bismark PC Cleaner — Inno Setup installer script.
; AppVersion is passed from CI: ISCC.exe /DAppVersion=1.2.3 installer\setup.iss

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8F3B2A1C-9D4E-4F6A-B7C8-D0E1F2A3B4C5}
AppName=Bismark PC Cleaner
AppVersion={#AppVersion}
AppVerName=Bismark PC Cleaner {#AppVersion}
AppPublisher=Bismark57
AppPublisherURL=https://github.com/Bismark57/pc-cleaner
DefaultDirName={autopf}\Bismark PC Cleaner
DefaultGroupName=Bismark PC Cleaner
OutputDir=..\installer-output
OutputBaseFilename=Bismark-PC-Cleaner-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName=Bismark PC Cleaner
VersionInfoVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\Bismark PC Cleaner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Bismark PC Cleaner"; Filename: "{app}\Bismark PC Cleaner.exe"
Name: "{group}\Uninstall Bismark PC Cleaner"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Bismark PC Cleaner"; Filename: "{app}\Bismark PC Cleaner.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\Bismark PC Cleaner.exe"; Description: "Launch Bismark PC Cleaner"; Flags: nowait postinstall skipifsilent shellexec

#define AppName "bili-auto"
#define AppPublisher "bili-auto"
#define AppURL "https://example.com"
#ifndef SourceDir
  #define SourceDir "..\dist\release"
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{A04D8AE4-AC8D-4D2E-8C44-5D7D2D5FA1A7}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\bili-auto
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=bili-auto-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
UsePreviousAppDir=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\.env.example"; DestDir: "{localappdata}\bili-auto"; DestName: ".env"; Flags: onlyifdoesntexist ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\bili-launcher\bili-launcher.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\bili-launcher\bili-launcher.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\bili-launcher\bili-launcher.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; Inno Setup 6 script - builds SleepifySetup-<version>.exe from dist\Sleepify (made by PyInstaller)
; Build:  ISCC.exe /DAppVersion=1.0.0 installer\Sleepify.iss     (build.bat does this for you)

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{C7D518C8-6FBC-424D-BC2F-69BF48FEA467}
AppName=Sleepify
AppVersion={#AppVersion}
AppPublisher=Sleepify
DefaultDirName={autopf}\Sleepify
DefaultGroupName=Sleepify
DisableDirPage=no
DisableProgramGroupPage=yes
; installs for the current user only, so no administrator password is needed
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=SleepifySetup-{#AppVersion}
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\Sleepify.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Sleepify creates this mutex while it runs, so Setup can ask you to close it first
AppMutex=Sleepify_Single_Instance
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start Sleepify with &Windows (hidden in the tray, near the clock)"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\Sleepify\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Sleepify"; Filename: "{app}\Sleepify.exe"
Name: "{autodesktop}\Sleepify"; Filename: "{app}\Sleepify.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Sleepify"; ValueData: """{app}\Sleepify.exe"" --hidden"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\Sleepify.exe"; Description: "Start Sleepify now"; Flags: nowait postinstall skipifsilent

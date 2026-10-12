; Bulls'n'Bier – Windows-Installer (Inno Setup 6). Wird von GitHub Actions gebaut.
#define AppVer GetEnv("BNB_VERSION")
#if AppVer == ""
  #define AppVer "1.0.0"
#endif

[Setup]
AppId={{6B2F3C1E-8A4D-4E7B-9C1F-B0115B1E0001}
AppName=Bulls'n'Bier
AppVersion={#AppVer}
AppPublisher=Buschi's Ballerbude
DefaultDirName={autopf}\BullsnBier
DefaultGroupName=Bulls'n'Bier
DisableProgramGroupPage=yes
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=BullsnBier-Setup-{#AppVer}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\BullsnBier.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfungen anlegen"; GroupDescription: "Verknüpfungen:"
Name: "autostart"; Description: "Bulls'n'Bier mit Windows starten (Live, Kameras)"; GroupDescription: "Autostart:"; Flags: unchecked
Name: "firewall"; Description: "Zugriff aus dem Heimnetz erlauben (Handy-Fernbedienung, Port 8090)"; GroupDescription: "Netzwerk:"

[Files]
Source: "..\dist\BullsnBier\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Bulls'n'Bier"; Filename: "{app}\BullsnBier.exe"; Parameters: "--open"; IconFilename: "{app}\BullsnBier.exe"
Name: "{group}\Bulls'n'Bier Simulator"; Filename: "{app}\BullsnBier.exe"; Parameters: "--sim --open"; IconFilename: "{app}\BullsnBier.exe"
Name: "{group}\Stimme laden (Thorsten)"; Filename: "{app}\BullsnBier.exe"; Parameters: "--get-voice de_DE-thorsten-high"
Name: "{group}\Datenordner"; Filename: "{localappdata}\BullsnBier"
Name: "{group}\Bulls'n'Bier deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Bulls'n'Bier"; Filename: "{app}\BullsnBier.exe"; Parameters: "--open"; Tasks: desktopicon
Name: "{autodesktop}\Bulls'n'Bier Simulator"; Filename: "{app}\BullsnBier.exe"; Parameters: "--sim --open"; Tasks: desktopicon
Name: "{userstartup}\Bulls'n'Bier"; Filename: "{app}\BullsnBier.exe"; Parameters: "--open"; Tasks: autostart

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""Bulls'n'Bier"" dir=in action=allow program=""{app}\BullsnBier.exe"" enable=yes profile=private"; Flags: runhidden; Tasks: firewall; Check: IsAdminInstallMode
Filename: "{app}\BullsnBier.exe"; Parameters: "--get-voice de_DE-thorsten-high"; Description: "Natürliche Stimme laden (ca. 110 MB, Internet nötig)"; Flags: postinstall unchecked
Filename: "{app}\BullsnBier.exe"; Parameters: "--sim --open"; Description: "Simulator jetzt starten"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Bulls'n'Bier"""; Flags: runhidden; RunOnceId: "fw"; Check: IsAdminInstallMode

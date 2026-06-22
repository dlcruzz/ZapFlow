[Setup]
AppName=ZapFlow
AppVersion=1.0
AppPublisher=Dlima15
AppPublisherURL=https://github.com/dlcruzz/ZapFlow
DefaultDirName={autopf}\ZapFlow
DefaultGroupName=ZapFlow
OutputDir=installer
OutputBaseFilename=ZapFlow_Setup
SetupIconFile=img\zapflow.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
LicenseFile=
PrivilegesRequired=lowest

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "dist\ZapFlow.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\contatos.csv"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{group}\ZapFlow";        FileName: "{app}\ZapFlow.exe"
Name: "{group}\Desinstalar ZapFlow"; FileName: "{uninstallexe}"
Name: "{userdesktop}\ZapFlow";  FileName: "{app}\ZapFlow.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ZapFlow.exe"; Description: "Abrir ZapFlow agora"; Flags: nowait postinstall skipifsilent

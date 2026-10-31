; Instalador Inno Setup por usuário, sem administrador (ADR-0006).
; O CI passa a versão: iscc /DVersao=0.2.0 empacotamento\gastroepi.iss
; O cofre mora em %LOCALAPPDATA%\GastroEpi, fora da pasta do programa: instalar,
; atualizar ou desinstalar nunca toca o banco nem os backups (ADR-0005).

#ifndef Versao
  #define Versao "0.0.0"
#endif

[Setup]
AppId={{6E0B7C1A-4F7E-4C55-9C1E-9A3B2F0D6A11}
AppName=GastroEpi
AppVersion={#Versao}
AppPublisher=Mateus Campelo
DefaultDirName={localappdata}\Programs\GastroEpi
DefaultGroupName=GastroEpi
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=GastroEpi-{#Versao}-instalador
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\GastroEpi.exe
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "..\dist\GastroEpi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\GastroEpi"; Filename: "{app}\GastroEpi.exe"
Name: "{userdesktop}\GastroEpi"; Filename: "{app}\GastroEpi.exe"; Tasks: atalho

[Run]
Filename: "{app}\GastroEpi.exe"; Description: "Abrir o GastroEpi"; Flags: nowait postinstall skipifsilent

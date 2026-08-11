#define MyAppName "PCPanel"
#define MyAppVersion "0.10.0"
#define MyAppPublisher "parrelladev"
#define MyAppId "{{62C2F744-6CBA-4A97-A6D7-FDA3E81E412D}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PCPanel
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=PCPanelSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=PCPanel
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Tasks]
Name: "serviceautostart"; Description: "Iniciar o Telemetry Service automaticamente com o Windows"; Flags: unchecked
Name: "agentautostart"; Description: "Iniciar o PCPanel Agent quando eu entrar no Windows"; Flags: unchecked
Name: "startnow"; Description: "Iniciar Service e Agent ao concluir a instalação"; Flags: unchecked
Name: "firewall"; Description: "Permitir acesso ao Agent pela rede privada local"; Flags: unchecked

[Files]
Source: "..\dist\PCPanelAgent\*"; DestDir: "{app}\Agent"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\PCPanelTelemetryService\*"; DestDir: "{app}\TelemetryService"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PCPanelAgent"; ValueData: """{app}\Agent\PCPanelAgent.exe"""; Tasks: agentautostart; Flags: uninsdeletevalue

[Icons]
Name: "{autoprograms}\PCPanel"; Filename: "{app}\Agent\PCPanelAgent.exe"

[Run]
Filename: "{sys}\sc.exe"; Parameters: "create PCPanelTelemetry binPath= ""{app}\TelemetryService\PCPanelTelemetryService.exe"" start= demand obj= LocalSystem DisplayName= ""PCPanel Telemetry Service"""; Flags: runhidden; Check: ServiceDoesNotExist
Filename: "{sys}\sc.exe"; Parameters: "config PCPanelTelemetry binPath= ""{app}\TelemetryService\PCPanelTelemetryService.exe"" obj= LocalSystem start= {code:ServiceStartMode}"; Flags: runhidden
Filename: "{sys}\sc.exe"; Parameters: "description PCPanelTelemetry ""Hardware telemetry provider for PCPanel"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PCPanel Agent (Private LAN)"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""PCPanel Agent (Private LAN)"" dir=in action=allow program=""{app}\Agent\PCPanelAgent.exe"" enable=yes profile=private remoteip=LocalSubnet"; Flags: runhidden; Tasks: firewall
Filename: "{sys}\sc.exe"; Parameters: "start PCPanelTelemetry"; Flags: runhidden; Tasks: startnow
Filename: "{app}\Agent\PCPanelAgent.exe"; Flags: nowait postinstall skipifsilent runasoriginaluser; Tasks: startnow

[UninstallRun]
Filename: "{app}\Agent\PCPanelAgent.exe"; Parameters: "--shutdown-existing"; Flags: runhidden skipifdoesntexist
Filename: "{sys}\net.exe"; Parameters: "stop PCPanelTelemetry /y"; Flags: runhidden
Filename: "{sys}\sc.exe"; Parameters: "delete PCPanelTelemetry"; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PCPanel Agent (Private LAN)"""; Flags: runhidden

[Code]
var
  RemoveUserData: Boolean;

function ServiceDoesNotExist: Boolean;
var
  ResultCode: Integer;
begin
  Result := not Exec(ExpandConstant('{sys}\sc.exe'), 'query PCPanelTelemetry', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0);
end;

function ServiceStartMode(Param: String): String;
begin
  if WizardIsTaskSelected('serviceautostart') then
    Result := 'auto'
  else
    Result := 'demand';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\Agent\PCPanelAgent.exe')) then begin
    Exec(ExpandConstant('{app}\Agent\PCPanelAgent.exe'), '--shutdown-existing', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1500);
  end;
  Exec(ExpandConstant('{sys}\net.exe'), 'stop PCPanelTelemetry /y', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    if not WizardIsTaskSelected('agentautostart') then
      RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'PCPanelAgent');
  end;
end;

function InitializeUninstall(): Boolean;
begin
  RemoveUserData := False;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveUserData := SuppressibleMsgBox(
      'Deseja remover também os dados do usuário, dispositivos pareados e Actions?'#13#10#13#10 +
      'A opção segura e recomendada é Não.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
  if (CurUninstallStep = usPostUninstall) and RemoveUserData then
    DelTree(ExpandConstant('{localappdata}\PCPanel'), True, True, True);
end;

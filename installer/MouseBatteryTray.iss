; Per-user installer (no admin) for the PyInstaller folder build in dist\MouseBatteryTray.
; Built by scripts\build.py, which passes AppVersion from pyproject.toml.

#ifndef AppVersion
  #error Pass the version: ISCC /DAppVersion=x.y.z installer\MouseBatteryTray.iss
#endif

#define AppName "Mouse Battery Tray"
#define AppExe "MouseBatteryTray.exe"
; The app's own names: autostart.VALUE_NAME, app_identity's app id, and the data folder in app.main
#define RunKey "Software\Microsoft\Windows\CurrentVersion\Run"
#define RunValue "MouseBatteryTray"
#define AumidKey "Software\Classes\AppUserModelId\MouseBatteryTray"
#define DataDir "mouse-battery-tray"

[Setup]
; Never change AppId: upgrades and the uninstaller find the installed copy by it.
AppId={{720A1B69-1837-43CF-A183-E1B4FB4DCC98}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=bodypas
AppPublisherURL=https://github.com/bodypas/mouse-battery-tray
DefaultDirName={autopf}\{#AppName}
; The user picks the folder, but the Run entry starts this exe at every logon, so the folder must not be writable by
; other accounts: a folder made on a second drive such as E:\ inherits Modify for Authenticated Users, letting any
; account swap the exe (found in the 2026-11-18 security review). Setup therefore refuses folders that hold other files
; or are a whole drive (NextButtonClick, PrepareToInstall), and makes the folder private right after creating it and
; before copying anything (LockAppFolder), stopping if it can't.
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=MouseBatteryTraySetup-{#AppVersion}
SetupIconFile=..\build\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes

[Tasks]
Name: startup; Description: "Start with Windows"

[Dirs]
; [Dirs] runs before [Files], so the folder is private before the first file lands in it.
Name: "{app}"; AfterInstall: LockAppFolder

[InstallDelete]
; PyInstaller's support files change between versions; drop the old ones on upgrade.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\MouseBatteryTray\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autoprograms}\{#AppName} diagnose"; Filename: "{app}\{#AppExe}"; Parameters: "--diagnose"

[Registry]
; The same value the app's "Start with Windows" menu item writes, so the menu shows it ticked.
Root: HKCU; Subkey: "{#RunKey}"; ValueType: string; ValueName: "{#RunValue}"; ValueData: """{app}\{#AppExe}"""; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Logs, hang dumps, the diagnose report and the notification logo.
Type: filesandordirs; Name: "{localappdata}\{#DataDir}"

[Code]
const
  // Built-in SIDs: group names are translated on non-English Windows.
  SystemSid = '*S-1-5-18';
  AdministratorsSid = '*S-1-5-32-544';

procedure CloseRunningApp;
var
  ResultCode: Integer;
begin
  // The tray app is nearly always running and keeps its files locked.
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(500);
end;

function IsDriveRoot(Dir: String): Boolean;
begin
  Result := CompareText(AddBackslash(Dir), AddBackslash(ExtractFileDrive(Dir))) = 0;
end;

function FolderIsFree(Dir: String): Boolean;
var
  FindRec: TFindRec;
begin
  // A new folder, an empty one, or an earlier install of this app: Setup never changes permissions on other files.
  Result := not IsDriveRoot(Dir);
  if (not Result) or (not DirExists(Dir)) or FileExists(AddBackslash(Dir) + '{#AppExe}') then
    Exit;
  if FindFirst(AddBackslash(Dir) + '*', FindRec) then
    try
      repeat
        Result := (FindRec.Name = '.') or (FindRec.Name = '..');
      until (not Result) or (not FindNext(FindRec));
    finally
      FindClose(FindRec);
    end;
end;

function FolderInUseMessage(Dir: String): String;
begin
  Result := Dir + ' already holds other files or is a whole drive. Choose a new or empty folder: Setup makes the ' +
    'install folder private to your account, so it doesn''t share it with other files.';
end;

function MakePrivate(Dir: String): Boolean;
var
  ResultCode: Integer;
begin
  // Drop inherited rights, leaving only this account, SYSTEM and Administrators.
  Result := Exec(ExpandConstant('{sys}\icacls.exe'),
      '"' + Dir + '" /inheritance:r /grant:r "' + GetEnv('USERDOMAIN') + '\' + GetUserNameString + ':(OI)(CI)F" ' +
      SystemSid + ':(OI)(CI)F ' + AdministratorsSid + ':(OI)(CI)F',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

procedure LockAppFolder;
var
  Dir: String;
begin
  // Runs right after Setup creates the folder, before any file is copied into it.
  Dir := ExpandConstant('{app}');
  if not MakePrivate(Dir) then
    RaiseException('Setup could not make ' + Dir + ' private to your account, so it did not install there. ' +
      'Choose a folder on an NTFS drive; FAT32 and exFAT drives, like most USB sticks, have no permissions.');
  if not FolderIsFree(Dir) then
    RaiseException(FolderInUseMessage(Dir));  // something got in before the folder was locked
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := (CurPageID <> wpSelectDir) or FolderIsFree(RemoveBackslashUnlessRoot(WizardDirValue));
  if not Result then
    SuppressibleMsgBox(FolderInUseMessage(WizardDirValue), mbError, MB_OK, IDOK);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Dir: String;
begin
  // Checked again here in case the folder page was skipped.
  Dir := RemoveBackslashUnlessRoot(ExpandConstant('{app}'));
  if FolderIsFree(Dir) then
  begin
    CloseRunningApp;
    Result := '';
  end
  else
    Result := FolderInUseMessage(Dir);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command: String;
begin
  if CurUninstallStep = usUninstall then
    CloseRunningApp;
  if CurUninstallStep <> usPostUninstall then
    Exit;
  // The app writes these itself, so setup has no record of them. Only a Run value that starts this install is
  // removed: a source checkout uses the same value name for pythonw.
  if RegQueryStringValue(HKCU, '{#RunKey}', '{#RunValue}', Command) and
     (CompareText(Command, '"' + ExpandConstant('{app}\{#AppExe}') + '"') = 0) then
    RegDeleteValue(HKCU, '{#RunKey}', '{#RunValue}');
  RegDeleteKeyIncludingSubkeys(HKCU, '{#AumidKey}');
end;

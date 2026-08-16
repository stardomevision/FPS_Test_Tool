; ============================================================
;  FPS Test Tool v2.2.2 · Windows Installer (Inno Setup)
;  用法：
;    Inno Setup 6+ 中打开本文件 → 编译 (Ctrl+F9)
;    或通过  一键构建并生成安装包.bat  自动编译
;  产物：
;    Output\FPS_Test_Tool_v2.2.2_Windows-x64_Setup.exe
;           → 标准 Windows 安装程序，用户双击即可一键安装
; ============================================================

#define AppName      "星穹视界帧率测试"
#define AppNameEn    "FPS Test Tool"
#define AppVersion   "2.2.2"
#define AppPublisher "Stardomevision / 星穹视界"
#define AppURL       "https://github.com/stardomevision/FPS_Test_Tool"
#define AppExeName   "星穹视界帧率测试.exe"
#define AppSupport   "stardomevision@outlook.com"

[Setup]
AppId={{A500B680-9F7D-4D22-B836-9609A8B6D2E0}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
AppContact={#AppSupport}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=Output
OutputBaseFilename=FPS_Test_Tool_v2.2.2_Windows-x64_Setup
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
MinVersion=10.0.14393  ; Win10 x64 1607 / Win11
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
ChangesAssociations=no
SetupIconFile=resources\app_icon.ico

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式 (&C)"; GroupDescription: "附加图标:"; Flags: unchecked
Name: "quicklaunchicon"; Description: "创建任务栏快捷方式 (&T)"; GroupDescription: "附加图标:"; Flags: unchecked; OnlyBelowVersion: 6.1
Name: "runapp"; Description: "安装完成后运行 {#AppName} (&R)"; GroupDescription: "运行:"; Flags: unchecked

[Files]
; 主程序目录：把 PyInstaller onedir 产物 (dist\星穹视界帧率测试\) 全部拷入安装目录
Source: "dist\星穹视界帧率测试\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\resources\app_icon.ico"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\resources\app_icon.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\resources\app_icon.ico"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "运行 {#AppName}"; Tasks: runapp; Flags: nowait postinstall skipifsilent

[Registry]
; 让卸载列表里显示图标和发布信息
Root: HKLM64; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting('AppId')}"; ValueType: string; ValueName: "DisplayIcon"; ValueData: "{app}\{#AppExeName}"; Flags: uninsdeletekeyifempty
Root: HKLM64; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting('AppId')}"; ValueType: string; ValueName: "HelpLink"; ValueData: "{#AppURL}"; Flags: uninsdeletekeyifempty
Root: HKLM64; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting('AppId')}"; ValueType: string; ValueName: "Publisher"; ValueData: "{#AppPublisher}"; Flags: uninsdeletekeyifempty
Root: HKLM64; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting('AppId')}"; ValueType: string; ValueName: "URLInfoAbout"; ValueData: "{#AppURL}"; Flags: uninsdeletekeyifempty

[Code]
// 若找不到图标文件则退回默认，避免编译失败
function InitializeSetup(): Boolean;
var
  IconPath: String;
begin
  IconPath := ExpandConstant('{src}\resources\app_icon.ico');
  if not FileExists(IconPath) then
  begin
    Log('Icon not found at ' + IconPath + ', using default.');
  end;
  Result := True;
end;

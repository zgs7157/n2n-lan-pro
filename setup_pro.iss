; N2N LAN Pro 安装脚本（Inno Setup 6）
; 编译：ISCC.exe setup_pro.iss
; 与免费版独立：不同 AppId，可与免费版并存
#define MyAppName "N2N LAN Pro"
#define MyAppVersion "1.0.2"
#define MyAppPublisher "n2n-lan"
#define MyAppURL "https://zgs7157.github.io/n2n-lan-pro/"
#define MyAppExeName "n2n_pro_manager.exe"
#define MyAppIcon "n2n-lan-pro.ico"

[Setup]
AppId={{B3F7D2E1-6A9C-4F58-9D24-7E1C5A8B3D62}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}releases
VersionInfoVersion=1.0.2.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} 安装程序
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
DefaultDirName={autopf}\n2n-lan-pro
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist_installer_pro
OutputBaseFilename=n2n-lan-pro-setup-{#MyAppVersion}
SetupIconFile=client\{#MyAppIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes
DisableWelcomePage=no

[Languages]
Name: "chs"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Pro 版全部内容：n2n_pro_manager.exe、bin（edge/supernode/udp6 转发器）、TAP 驱动、源码、mac/linux 脚本
Source: "client_pro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "logs\*,logs_pro\*,config.json,config_pro.json,n2n_room_manager.exe,__pycache__\*,*.pyc,*.bak,audit_reports\*"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIcon}"; Comment: "N2N LAN Pro 虚拟局域网专业版（诊断 / 审计 / 房间库）"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconFilename: "{app}\{#MyAppIcon}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIcon}"; Tasks: desktopicon; Comment: "N2N LAN Pro 虚拟局域网专业版"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\logs_pro"
Type: filesandordirs; Name: "{app}\audit_reports"
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\config_pro.json"
Type: dirifempty; Name: "{app}"

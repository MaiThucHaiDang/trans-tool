; Bộ cài đặt cho Dịch (Inno Setup 6). Build:  iscc /DAppVersion=1.0.0 installer.iss
; Cài vào thư mục của người dùng, không cần quyền quản trị (hợp với máy ở trường).

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F3C2B1E-9A4D-4E8B-B7C1-D1C7A0E5F2A9}
AppName=Dịch
AppVersion={#AppVersion}
AppPublisher=MaiThucHaiDang
AppPublisherURL=https://github.com/MaiThucHaiDang/trans-tool
DefaultDirName={localappdata}\Programs\Dich
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=Dich-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\Dich.exe
UninstallDisplayName=Dịch
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
MinVersion=10.0

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng Dịch ngoài Desktop"
Name: "autostart"; Description: "Tự chạy Dịch khi bật máy"

[Files]
Source: "dist\Dich\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{userprograms}\Dịch"; Filename: "{app}\Dich.exe"
Name: "{userdesktop}\Dịch"; Filename: "{app}\Dich.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "Dich"; ValueData: """{app}\Dich.exe"" --an"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\Dich.exe"; Description: "Mở Dịch ngay"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM Dich.exe"; Flags: runhidden; RunOnceId: "StopDich"
Filename: "{sys}\reg.exe"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v Dich /f"; \
  Flags: runhidden; RunOnceId: "RemoveAutostart"

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\Dich"

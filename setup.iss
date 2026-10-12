; setup.iss
; สคริปต์สร้างตัวติดตั้ง Polo Optimizer ด้วย Inno Setup 6 (ฟรี)
; ไม่ต้องเปิดไฟล์นี้เอง ดับเบิลคลิก build_setup.bat แล้วจะได้ release\PoloOptimizer-Setup-<เวอร์ชัน>.exe
; ตัวติดตั้งจะ: ลงโปรแกรมไว้ใน Program Files, สร้างไอคอนบน Start Menu และ Desktop (เลือกได้),
; และเพิ่มรายการใน Settings > Apps ให้ถอนการติดตั้งได้ตามปกติ

#ifndef AppVersion
  #define AppVersion "1.3"
#endif
#define AppName "Polo Optimizer"
#define AppExe "PoloOptimizer.exe"

[Setup]
; AppId ห้ามเปลี่ยน Windows ใช้รหัสนี้รู้ว่าเป็นโปรแกรมเดิม (ลงเวอร์ชันใหม่ทับได้ ไม่ขึ้นซ้ำ 2 รายการ)
AppId={{8F3C2A51-6B7E-4D2A-9C1F-5E0B7A4D3C21}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Polo (โปสรินท์ สุขดี)
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} Setup
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; โปรแกรมต้องใช้สิทธิ์ Admin อยู่แล้ว ตัวติดตั้งเลยลงแบบทั้งเครื่อง
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=release
OutputBaseFilename=PoloOptimizer-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile=assets\setup\wizard.bmp,assets\setup\wizard@2x.bmp
WizardSmallImageFile=assets\setup\small.bmp,assets\setup\small@2x.bmp
Compression=lzma2/ultra64
SolidCompression=yes
; ถ้าโปรแกรมเปิดค้างอยู่ตอนอัปเดต ให้ตัวติดตั้งช่วยปิดให้ก่อน
CloseApplications=yes

[Languages]
Name: "thai"; MessagesFile: "compiler:Languages\Thai.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; ตัวโปรแกรมแบบโฟลเดอร์ (สร้างโดย build_setup.bat) ทั้งโฟลเดอร์ รวมโฟลเดอร์ _internal ที่มีไลบรารี
Source: "dist_setup\PoloOptimizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[UninstallDelete]
; ลบไฟล์ที่โปรแกรมสร้างเพิ่มในโฟลเดอร์ติดตั้ง (ไฟล์ตั้งค่าของผู้ใช้ใน %APPDATA% เก็บไว้ ถ้าลงใหม่จะได้ไม่ต้องตั้งค่าใหม่)
Type: filesandordirs; Name: "{app}\_internal"

[Run]
; เปิดโปรแกรมหลังติดตั้งเสร็จ (มีช่องติ๊กให้เลือกในหน้าสุดท้าย)
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

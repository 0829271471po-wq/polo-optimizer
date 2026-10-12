@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   สร้างตัวติดตั้ง Polo Optimizer (Setup.exe)
echo ============================================
echo.

rem ---- 1) ต้องมี .venv และไลบรารีก่อน ถ้ายังไม่มีให้ build.bat เตรียมให้ ----
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo [1/4] ยังไม่มี .venv กำลังเตรียมด้วย build.bat ...
    call build.bat || goto :fail
)

rem ---- 2) สร้างโปรแกรมแบบโฟลเดอร์ (onedir) สำหรับตัวติดตั้งโดยเฉพาะ ----
rem แบบโฟลเดอร์ไม่ต้องแตกไฟล์ตัวเองลง Temp ทุกครั้งที่เปิด จึงเปิดเร็วกว่า และแอนติไวรัสเตือนผิด ๆ น้อยกว่าแบบไฟล์เดียว
echo [1/4] กำลังสร้างโปรแกรมแบบโฟลเดอร์ ^(ใช้เวลาประมาณ 1-2 นาที^) ...
"%VPY%" make_version_info.py || goto :fail
"%VPY%" -m PyInstaller --noconfirm --clean --log-level WARN ^
    --onedir --windowed --uac-admin --noupx ^
    --icon icon.ico --add-data "icon.ico;." --add-data "logo.png;." --add-data "assets\apps;assets\apps" ^
    --collect-all customtkinter --version-file version_info.txt ^
    --distpath dist_setup --workpath build_setup_tmp ^
    --name PoloOptimizer main.py || goto :fail

rem ---- 3) หา Inno Setup (ถ้าไม่มี ลงให้ผ่าน winget) ----
set "ISCC="
for %%P in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do (
    if exist %%P set "ISCC=%%~P"
)
if not defined ISCC (
    echo [2/4] ยังไม่มี Inno Setup กำลังติดตั้งผ่าน winget ...
    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
    for %%P in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do (
        if exist %%P set "ISCC=%%~P"
    )
)
if not defined ISCC (
    echo [X] หา Inno Setup ไม่เจอ โหลดเองได้ที่ https://jrsoftware.org/isdl.php
    goto :fail
)
echo [2/4] ใช้ Inno Setup: %ISCC%

rem ---- 4) วาดรูปหน้าตัวติดตั้ง อ่านเลขเวอร์ชันจาก main.py แล้วสร้าง Setup.exe ----
echo [3/4] กำลังวาดรูปหน้าตัวติดตั้ง ...
"%VPY%" make_setup_images.py || goto :fail
set /p VER=<assets\setup\version.txt
echo [4/4] กำลังสร้างตัวติดตั้งเวอร์ชัน %VER% ...
"%ISCC%" /Q /DAppVersion=%VER% setup.iss || goto :fail

echo.
echo ============================================
echo   เสร็จแล้ว: release\PoloOptimizer-Setup-%VER%.exe
echo ============================================
pause
exit /b 0

:fail
echo.
echo [X] สร้างตัวติดตั้งไม่สำเร็จ ดูข้อความ error ด้านบน
pause
exit /b 1

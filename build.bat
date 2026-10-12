@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   สร้างไฟล์ PoloOptimizer.exe
echo ============================================
echo.

rem ---- 1) หา Python (ใช้ 3.12 ก่อน ถ้าไม่มีค่อยใช้ตัวที่มีในเครื่อง) ----
set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [X] ไม่พบ Python ในเครื่อง
    echo     โหลด Python 3.12 จาก https://www.python.org/downloads/
    echo     ตอนติดตั้งให้ติ๊ก "Add python.exe to PATH" ด้วย
    goto :fail
)
echo [1/4] ใช้ Python:
%PY% --version

rem ---- 2) สร้าง virtual environment แยกไว้ในโฟลเดอร์ .venv (ไม่ยุ่งกับ Python หลักของเครื่อง) ----
if not exist ".venv\Scripts\python.exe" (
    echo [2/4] กำลังสร้าง .venv ...
    %PY% -m venv .venv || goto :fail
) else (
    echo [2/4] มี .venv อยู่แล้ว
)
set "VPY=.venv\Scripts\python.exe"

rem ---- 3) ลงไลบรารีที่ต้องใช้ ----
echo [3/4] กำลังลงไลบรารีจาก requirements.txt ...
"%VPY%" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :fail
if not exist "logo.png" (
    "%VPY%" make_icon.py || goto :fail
)
if not exist "assets\apps" (
    echo       กำลังดึงโลโก้แอป ^(ครั้งแรกครั้งเดียว^) ...
    "%VPY%" fetch_icons.py
)

"%VPY%" make_version_info.py || goto :fail

rem ---- 4) สร้าง .exe ไฟล์เดียว ----
echo [4/4] กำลังสร้าง .exe (ใช้เวลาประมาณ 1-2 นาที) ...
"%VPY%" -m PyInstaller --noconfirm --clean --log-level WARN ^
    --onefile --windowed --uac-admin ^
    --icon icon.ico --add-data "icon.ico;." --add-data "logo.png;." --add-data "assets\apps;assets\apps" ^
    --collect-all customtkinter ^
    --version-file version_info.txt --noupx ^
    --name PoloOptimizer main.py || goto :fail

echo.
echo ============================================
echo   เสร็จแล้ว: dist\PoloOptimizer.exe
echo ============================================
pause
exit /b 0

:fail
echo.
echo [X] สร้างไม่สำเร็จ ดูข้อความ error ด้านบน
pause
exit /b 1

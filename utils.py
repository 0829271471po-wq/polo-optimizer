"""
utils.py
ฟังก์ชันกลางที่ไฟล์อื่นเรียกใช้ร่วมกัน
เช่น รันคำสั่งแบบไม่ให้หน้าต่างดำเด้งขึ้นมา, รัน PowerShell, เช็กสิทธิ์ Admin, แปลงขนาดไฟล์ให้อ่านง่าย
"""

import base64
import ctypes
import json
import os
import subprocess
import sys

# ธงของ Windows ที่บอกว่า "รันคำสั่งโดยไม่ต้องเปิดหน้าต่าง console"
CREATE_NO_WINDOW = 0x08000000
# ธงสำหรับเปิดหน้าต่าง cmd ใหม่ให้ผู้ใช้เห็น
CREATE_NEW_CONSOLE = 0x00000010

POWERSHELL = os.path.join(
    os.environ.get("SystemRoot", r"C:\Windows"),
    "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
)


def _oem_encoding():
    """หา code page ของหน้าต่าง cmd ในเครื่องนี้ (เครื่องภาษาไทยมักเป็น cp874)
    ใช้ถอดข้อความจากคำสั่งรุ่นเก่า เช่น powercfg ที่ไม่ได้ส่งออกมาเป็น UTF-8"""
    try:
        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        return "mbcs"


def decode_output(data):
    """แปลง bytes ที่ได้จากคำสั่งให้เป็นข้อความ
    ลอง UTF-8 ก่อน ถ้าไม่ได้ค่อยใช้ code page ของเครื่อง จะได้ไม่เจอภาษาต่างดาว"""
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode(_oem_encoding())
    except (UnicodeDecodeError, LookupError):
        return data.decode("mbcs", errors="replace")


def to_signed32(code):
    """Windows ส่ง exit code กลับมาเป็นเลข 32 บิตแบบไม่ติดลบ (เช่น 2316632107)
    ฟังก์ชันนี้แปลงเป็นเลขติดลบ (เช่น -1978335189) เพื่อเอาไปเทียบกับรหัสของ winget ได้ตรง ๆ"""
    if code is not None and code > 0x7FFFFFFF:
        code -= 0x100000000
    return code


def run_cmd(args, timeout=120):
    """รันคำสั่งทั่วไปแบบซ่อนหน้าต่าง แล้วคืนค่า (exit code, ข้อความ stdout, ข้อความ stderr)
    ถ้ารันไม่สำเร็จหรือเกินเวลา จะไม่ทำให้โปรแกรมพัง แต่คืน code = -1 พร้อมข้อความ error"""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            stdin=subprocess.DEVNULL,
        )
        return to_signed32(proc.returncode), decode_output(proc.stdout), decode_output(proc.stderr)
    except subprocess.TimeoutExpired:
        return -1, "", "คำสั่งใช้เวลานานเกินไป เลยหยุดรอ"
    except FileNotFoundError:
        return -1, "", f"หาโปรแกรม {args[0] if isinstance(args, list) else args} ไม่เจอ"
    except Exception as e:
        return -1, "", str(e)


def run_powershell(script, timeout=90):
    """รันสคริปต์ PowerShell แบบซ่อนหน้าต่าง แล้วคืนค่า (exit code, stdout, stderr)
    ส่งสคริปต์ผ่าน -EncodedCommand (เข้ารหัส base64) จะได้ไม่ต้องกังวลเรื่องเครื่องหมายคำพูดหรือภาษาไทยในสคริปต์
    และบังคับให้ผลลัพธ์ออกมาเป็น UTF-8 เพื่อให้ชื่ออุปกรณ์ภาษาไทยอ่านออก"""
    full = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
        "$ProgressPreference = 'SilentlyContinue';"
        + script
    )
    encoded = base64.b64encode(full.encode("utf-16-le")).decode("ascii")
    return run_cmd(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-EncodedCommand", encoded],
        timeout=timeout,
    )


def ps_json(script, timeout=90):
    """รัน PowerShell ที่ปิดท้ายด้วย ConvertTo-Json แล้วแปลงผลเป็น dict/list ของ Python
    ถ้าไม่มีผลลัพธ์หรืออ่าน JSON ไม่ได้ จะคืน None"""
    code, out, err = run_powershell(script, timeout=timeout)
    out = out.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def as_list(value):
    """PowerShell ชอบคืนของชิ้นเดียวเป็น dict แต่หลายชิ้นเป็น list
    ฟังก์ชันนี้ทำให้เป็น list เสมอ โค้ดที่เอาไปวนลูปจะได้ไม่ต้องเช็กหลายแบบ"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def format_size(num_bytes):
    """แปลงจำนวน byte เป็นข้อความอ่านง่าย เช่น 1536 -> '1.5 KB'"""
    try:
        size = float(num_bytes or 0)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def is_admin():
    """เช็กว่าโปรแกรมกำลังรันด้วยสิทธิ์ Admin อยู่หรือเปล่า"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """เปิดโปรแกรมตัวเองใหม่ด้วยสิทธิ์ Admin (Windows จะเด้งหน้าต่าง UAC ถาม)
    คืน True ถ้าผู้ใช้กดยอม (ตัวเก่าควรปิดตัวเองต่อ) คืน False ถ้าผู้ใช้กดไม่ยอม
    ปกติไฟล์ .exe ที่ build ด้วย --uac-admin จะขอสิทธิ์เองอยู่แล้ว ฟังก์ชันนี้ใช้ตอนรันจาก main.py ตรง ๆ"""
    try:
        if getattr(sys, "frozen", False):
            exe, params = sys.executable, subprocess.list2cmdline(sys.argv[1:])
        else:
            exe = sys.executable
            params = subprocess.list2cmdline([os.path.abspath(sys.argv[0])] + sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        return ret > 32
    except Exception:
        return False


def resource_path(name):
    """หาที่อยู่ไฟล์ที่แนบไปกับ .exe (เช่น icon.ico)
    ตอนเป็น .exe ไฟล์จะถูกแตกไปไว้ในโฟลเดอร์ชั่วคราว sys._MEIPASS ตอนรัน .py ปกติจะอยู่ข้าง ๆ ไฟล์โค้ด"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def open_url(url):
    """เปิดเว็บหรือหน้า Settings ของ Windows (ms-settings:...) ด้วย ShellExecute ผ่าน os.startfile
    เดิมเคยสั่งผ่าน explorer.exe แต่ explorer อ่านลิงก์ที่มี ? หรือ % ไม่ออก (เช่นลิงก์ค้นหาของ Microsoft Update Catalog)
    แล้วไปเปิดโฟลเดอร์ Documents แทน เลยเปลี่ยนมาใช้วิธีมาตรฐานนี้ ถ้าไม่สำเร็จค่อยใช้ webbrowser ของ Python"""
    try:
        os.startfile(url)
    except OSError:
        import webbrowser
        webbrowser.open(url)


def open_system_tool(name):
    """เปิดเครื่องมือของ Windows เช่น devmgmt.msc (Device Manager) ที่ต้องใช้สิทธิ์ Admin"""
    os.startfile(name)


def to_json_text(data):
    """แปลง dict เป็นข้อความ JSON ที่อ่านภาษาไทยออก (ไม่แปลงเป็น \\uXXXX)"""
    return json.dumps(data, ensure_ascii=False, indent=2)

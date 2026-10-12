"""
startup.py
จัดการโปรแกรมที่เปิดพร้อมเครื่อง โดยใช้วิธีเดียวกับ Task Manager แท็บ Startup
- อ่านรายชื่อจาก Run key ใน registry ทั้งของผู้ใช้ (HKCU) และของทั้งเครื่อง (HKLM)
- ไม่ลบรายการทิ้ง แต่เขียนสถานะลงใน StartupApproved\\Run
  byte แรก 02 = เปิด, 03 = ปิด  (ผู้ใช้เปิดกลับได้ทั้งในโปรแกรมนี้และใน Task Manager)
"""

import struct
import time
import winreg

_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN32 = r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
_APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"

# แต่ละแหล่ง: (root, path ของ Run key, path ของ StartupApproved, คำอธิบายภาษาไทย)
# โปรแกรม 32 บิตบน Windows 64 บิตจะไปอยู่ใต้ WOW6432Node และใช้ StartupApproved\Run32
SOURCES = [
    (winreg.HKEY_CURRENT_USER, _RUN, _APPROVED + r"\Run", ("เฉพาะผู้ใช้นี้", "This user")),
    (winreg.HKEY_LOCAL_MACHINE, _RUN, _APPROVED + r"\Run", ("ทุกผู้ใช้", "All users")),
    (winreg.HKEY_LOCAL_MACHINE, _RUN32, _APPROVED + r"\Run32", ("ทุกผู้ใช้ (32 บิต)", "All users (32-bit)")),
]

# บังคับอ่าน registry ฝั่ง 64 บิตเสมอ ไม่ให้ Windows แอบเปลี่ยนเส้นทาง
_WOW64 = winreg.KEY_WOW64_64KEY


def _filetime_now():
    """เวลาปัจจุบันในรูปแบบ FILETIME ของ Windows (หน่วย 100 นาโนวินาที นับจากปี 1601)
    Task Manager เก็บเวลาที่ผู้ใช้กดปิดไว้ในส่วนนี้ เราเลยทำเหมือนกัน"""
    return int((time.time() + 11644473600) * 10_000_000)


def _read_approved(root, path, name):
    """อ่านสถานะจาก StartupApproved คืน True = เปิด, False = ปิด
    ถ้าไม่มีข้อมูลเลย แปลว่าผู้ใช้ไม่เคยปิด ถือว่าเปิดอยู่
    byte แรกเป็นเลขคู่ (02, 06) = เปิด, เลขคี่ (03, 07) = ปิด"""
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | _WOW64) as key:
            data, _type = winreg.QueryValueEx(key, name)
        if isinstance(data, (bytes, bytearray)) and data:
            return data[0] % 2 == 0
    except OSError:
        pass
    return True


def list_startup():
    """อ่านโปรแกรมเปิดพร้อมเครื่องทั้งหมด คืน list ของ dict
    {name, command, scope, enabled, source(index ใน SOURCES)}
    แหล่งไหนอ่านไม่ได้ก็ข้ามไป"""
    items = []
    for index, (root, run_path, approved_path, scope) in enumerate(SOURCES):
        try:
            key = winreg.OpenKey(root, run_path, 0, winreg.KEY_READ | _WOW64)
        except OSError:
            continue
        with key:
            i = 0
            while True:
                try:
                    name, command, _type = winreg.EnumValue(key, i)
                except OSError:
                    break
                i += 1
                if not name:
                    continue
                items.append({
                    "name": name,
                    "command": str(command),
                    "scope": scope,
                    "enabled": _read_approved(root, approved_path, name),
                    "source": index,
                })
    items.sort(key=lambda x: x["name"].lower())
    return items


def set_enabled(item, enabled):
    """เปิด/ปิดโปรแกรมเปิดพร้อมเครื่อง 1 ตัว ด้วยการเขียนค่า 12 byte ลง StartupApproved
    เปิด: 02 + ศูนย์ 11 ตัว / ปิด: 03 00 00 00 + เวลาที่ปิด (FILETIME 8 byte) แบบเดียวกับ Task Manager
    รายการของทุกผู้ใช้ (HKLM) ต้องใช้สิทธิ์ Admin"""
    root, _run, approved_path, _scope = SOURCES[item["source"]]
    if enabled:
        data = b"\x02" + b"\x00" * 11
    else:
        data = b"\x03\x00\x00\x00" + struct.pack("<Q", _filetime_now())
    with winreg.CreateKeyEx(root, approved_path, 0, winreg.KEY_WRITE | _WOW64) as key:
        winreg.SetValueEx(key, item["name"], 0, winreg.REG_BINARY, data)
    item["enabled"] = enabled


def count_enabled():
    """นับจำนวนโปรแกรมที่ยังเปิดพร้อมเครื่องอยู่ (ใช้ส่งให้ AI และแสดงในคำแนะนำ)"""
    try:
        return sum(1 for item in list_startup() if item["enabled"])
    except Exception:
        return 0

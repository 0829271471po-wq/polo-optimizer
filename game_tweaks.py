"""
game_tweaks.py
ค่าปรับแต่งสำหรับเล่นเกม ทุกอย่างเป็นสวิตช์ที่เปิด/ปิดกลับได้
แก้เฉพาะ registry ของผู้ใช้ (HKCU) กับแผนพลังงานเท่านั้น
ไม่แตะ Windows Defender, Windows Update, mitigations หรือ Services ของระบบ
"""

import ctypes
import re
import winreg

from i18n import tr, tx
from utils import run_cmd

# ---------- ตัวช่วยอ่าน/เขียน registry ----------

def _read_value(root, path, name, default=None):
    """อ่านค่าจาก registry ถ้าไม่มีคีย์หรือไม่มีค่านั้นคืน default"""
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
            value, _type = winreg.QueryValueEx(key, name)
            return value
    except OSError:
        return default


def _write_value(root, path, name, value, value_type):
    """เขียนค่าลง registry ถ้ายังไม่มีคีย์ก็สร้างให้"""
    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_WRITE) as key:
        winreg.SetValueEx(key, name, 0, value_type, value)


# ---------- Game Mode ----------
_GAMEBAR = r"Software\Microsoft\GameBar"


def get_game_mode():
    """เช็กว่า Game Mode เปิดอยู่ไหม (ถ้าไม่มีค่าใน registry แปลว่าใช้ค่าเริ่มต้นของ Windows ซึ่งคือเปิด)"""
    return _read_value(winreg.HKEY_CURRENT_USER, _GAMEBAR, "AutoGameModeEnabled", 1) != 0


def set_game_mode(enabled):
    """เปิด/ปิด Game Mode: Windows จะให้ความสำคัญกับเกมที่กำลังเล่นก่อนโปรแกรมเบื้องหลัง"""
    _write_value(winreg.HKEY_CURRENT_USER, _GAMEBAR, "AutoGameModeEnabled", 1 if enabled else 0, winreg.REG_DWORD)


# ---------- Mouse acceleration (Enhance pointer precision) ----------
_MOUSE = r"Control Panel\Mouse"
SPI_SETMOUSE = 0x0004
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02


def get_mouse_accel():
    """เช็กว่าเปิดการเร่งความเร็วเมาส์อยู่ไหม (MouseSpeed ไม่ใช่ '0' = เปิด)"""
    return str(_read_value(winreg.HKEY_CURRENT_USER, _MOUSE, "MouseSpeed", "1")) != "0"


def set_mouse_accel(enabled):
    """เปิด/ปิดการเร่งความเร็วเมาส์
    เปิด = 1/6/10 (ค่าเดิมของ Windows), ปิด = 0/0/0 (เมาส์ขยับเท่ากันทุกครั้ง เล็งในเกมแม่นขึ้น)
    เขียน registry แล้วเรียก SystemParametersInfo ด้วย เพื่อให้มีผลทันทีไม่ต้องรีสตาร์ท"""
    speed, th1, th2 = (1, 6, 10) if enabled else (0, 0, 0)
    _write_value(winreg.HKEY_CURRENT_USER, _MOUSE, "MouseSpeed", str(speed), winreg.REG_SZ)
    _write_value(winreg.HKEY_CURRENT_USER, _MOUSE, "MouseThreshold1", str(th1), winreg.REG_SZ)
    _write_value(winreg.HKEY_CURRENT_USER, _MOUSE, "MouseThreshold2", str(th2), winreg.REG_SZ)
    params = (ctypes.c_int * 3)(th1, th2, speed)
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETMOUSE, 0, params, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)


# ---------- Background recording (Xbox Game Bar อัดวิดีโอเบื้องหลัง) ----------
_GAMECONFIG = r"System\GameConfigStore"
_GAMEDVR = r"Software\Microsoft\Windows\CurrentVersion\GameDVR"


def get_background_recording():
    """เช็กว่าเปิดการอัดวิดีโอเบื้องหลังอยู่ไหม (ถ้าค่าใดค่าหนึ่งเป็น 1 ถือว่าเปิด)"""
    dvr = _read_value(winreg.HKEY_CURRENT_USER, _GAMECONFIG, "GameDVR_Enabled", 1)
    capture = _read_value(winreg.HKEY_CURRENT_USER, _GAMEDVR, "AppCaptureEnabled", 0)
    return dvr != 0 and capture != 0


def set_background_recording(enabled):
    """เปิด/ปิดการอัดวิดีโอเบื้องหลังของ Game Bar ปิดแล้วเกมจะลื่นขึ้นเล็กน้อย เพราะไม่ต้องอัดภาพตลอดเวลา"""
    value = 1 if enabled else 0
    _write_value(winreg.HKEY_CURRENT_USER, _GAMECONFIG, "GameDVR_Enabled", value, winreg.REG_DWORD)
    _write_value(winreg.HKEY_CURRENT_USER, _GAMEDVR, "AppCaptureEnabled", value, winreg.REG_DWORD)


# รายการสวิตช์ทั้งหมด ใช้สร้างหน้าจอแบบวนลูป (key, ชื่อ, คำอธิบาย, ค่าที่แนะนำ, ฟังก์ชันอ่าน, ฟังก์ชันเขียน)
TWEAKS = [
    {
        "key": "game_mode",
        "name": "Game Mode",
        "desc": ("ให้ Windows ยกความสำคัญให้เกมก่อน และไม่อัปเดตกลางเกม", "Windows prioritizes your game and won't install updates mid-game"),
        "recommended": True,
        "get": get_game_mode,
        "set": set_game_mode,
    },
    {
        "key": "mouse_accel",
        "name": ("เร่งความเร็วเมาส์ (Mouse acceleration)", "Mouse acceleration"),
        "desc": ("ถ้าเปิด เมาส์จะไปไกลขึ้นเมื่อสะบัดเร็ว ทำให้เล็งในเกมยิงไม่แม่น", "When on, the pointer moves further on fast flicks, making aim inconsistent"),
        "recommended": False,
        "get": get_mouse_accel,
        "set": set_mouse_accel,
    },
    {
        "key": "background_recording",
        "name": ("อัดวิดีโอเบื้องหลัง (Background recording)", "Background recording"),
        "desc": ("Game Bar อัดภาพเกมเก็บไว้ตลอดเวลา กินแรงเครื่อง ถ้าไม่ได้ใช้ควรปิด", "Game Bar records gameplay all the time and costs performance. Turn off if unused"),
        "recommended": False,
        "get": get_background_recording,
        "set": set_background_recording,
    },
]


def apply_recommended():
    """ตั้งทุกสวิตช์เป็นค่าที่แนะนำ คืน (สำเร็จไหม, ข้อความ)"""
    failed = []
    for tweak in TWEAKS:
        try:
            tweak["set"](tweak["recommended"])
        except OSError:
            failed.append(tx(tweak["name"]))
    if failed:
        return False, tr("ปรับไม่สำเร็จบางรายการ: ", "Some tweaks failed: ") + ", ".join(failed)
    return True, tr("ปรับค่าเล่นเกมที่แนะนำแล้ว (เปิด Game Mode, ปิดเร่งความเร็วเมาส์, ปิดอัดวิดีโอเบื้องหลัง)",
                    "Recommended gaming tweaks applied (Game Mode on, mouse acceleration off, background recording off)")


# ---------- แผนพลังงาน (Power plan) ----------
BALANCED_GUID = "381b4222-f694-41f0-9685-ff5bb260df2e"
HIGH_PERFORMANCE_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
ULTIMATE_TEMPLATE_GUID = "e9a42b02-d5df-448d-aa00-03f14749eb61"
_GUID_RE = re.compile(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")


def list_power_plans():
    """อ่านรายการแผนพลังงานจาก powercfg /list คืน list ของ dict {guid, name, active}
    แต่ละบรรทัดหน้าตาแบบนี้:  Power Scheme GUID: 381b...  (Balanced) *
    ใช้ regex หา GUID ชื่อในวงเล็บ และเครื่องหมาย * ท้ายบรรทัด จึงใช้ได้กับ Windows ภาษาไทยด้วย"""
    code, out, err = run_cmd(["powercfg", "/list"], timeout=30)
    if code != 0:
        raise RuntimeError(err or tr("อ่านแผนพลังงานไม่ได้", "Couldn't read power plans"))
    plans = []
    for line in out.splitlines():
        match = _GUID_RE.search(line)
        if not match:
            continue
        rest = line[match.end():].strip()
        name_match = re.search(r"\((.*)\)", rest)
        plans.append({
            "guid": match.group(1).lower(),
            "name": name_match.group(1) if name_match else match.group(1),
            "active": rest.endswith("*"),
        })
    return plans


def set_power_plan(guid):
    """เปลี่ยนแผนพลังงานที่ใช้อยู่ คืน (สำเร็จไหม, ข้อความ)"""
    code, _out, err = run_cmd(["powercfg", "/setactive", guid], timeout=30)
    if code == 0:
        return True, tr("เปลี่ยนแผนพลังงานแล้ว", "Power plan changed")
    return False, tr(f"เปลี่ยนแผนพลังงานไม่สำเร็จ {err.strip()}", f"Couldn't change power plan {err.strip()}")


def add_ultimate_performance(known_guid=""):
    """เพิ่มแผน Ultimate Performance (แผนแรงสุดที่ Windows ซ่อนไว้) โดยคัดลอกจากแม่แบบ
    known_guid = GUID ที่เคยสร้างไว้ครั้งก่อน (เก็บใน config) ถ้ายังมีอยู่จะไม่สร้างซ้ำ
    คืน (สำเร็จไหม, ข้อความ, guid ของแผน)"""
    existing = list_power_plans()
    for plan in existing:
        if plan["guid"] == (known_guid or "").lower() or "ultimate" in plan["name"].lower():
            return True, tr("มีแผน Ultimate Performance อยู่แล้ว", "Ultimate Performance already exists"), plan["guid"]
    code, out, err = run_cmd(["powercfg", "-duplicatescheme", ULTIMATE_TEMPLATE_GUID], timeout=30)
    match = _GUID_RE.search(out)
    if code != 0 or not match:
        return False, tr("เพิ่มแผนไม่สำเร็จ เครื่องนี้อาจไม่รองรับ ", "Couldn't add the plan, this PC may not support it ") + err.strip(), ""
    return True, tr("เพิ่มแผน Ultimate Performance แล้ว", "Ultimate Performance added"), match.group(1).lower()


def restore_windows_defaults(ultimate_guid=""):
    """คืนค่าทุกอย่างในไฟล์นี้กลับเป็นค่าเริ่มต้นของ Windows (ใช้ตอนปรับแล้วเครื่องแปลก ๆ หรืออยากเริ่มใหม่)
    - Game Mode: เปิด, เร่งความเร็วเมาส์: เปิด (1/6/10)
    - อัดวิดีโอเบื้องหลัง: ค่าเริ่มต้นของ Windows คือ GameDVR_Enabled = 1 และ AppCaptureEnabled = 0
    - แผนพลังงาน: Balanced และลบแผน Ultimate Performance ที่โปรแกรมนี้เคยสร้าง (ถ้ามี)
    คืน (สำเร็จไหม, รายการที่ทำแล้ว, รายการที่ทำไม่สำเร็จ)"""
    done, failed = [], []
    steps = [
        (tr("เปิด Game Mode", "Game Mode on"), lambda: set_game_mode(True)),
        (tr("เปิดเร่งความเร็วเมาส์", "Mouse acceleration on"), lambda: set_mouse_accel(True)),
        (tr("อัดวิดีโอเบื้องหลังกลับเป็นค่าเดิม", "Background recording back to default"), lambda: (
            _write_value(winreg.HKEY_CURRENT_USER, _GAMECONFIG, "GameDVR_Enabled", 1, winreg.REG_DWORD),
            _write_value(winreg.HKEY_CURRENT_USER, _GAMEDVR, "AppCaptureEnabled", 0, winreg.REG_DWORD))),
    ]
    for name, func in steps:
        try:
            func()
            done.append(name)
        except OSError:
            failed.append(name)
    ok, _msg = set_power_plan(BALANCED_GUID)
    (done if ok else failed).append(tr("แผนพลังงาน Balanced", "Balanced power plan"))
    if ultimate_guid and ok:
        code, _o, _e = run_cmd(["powercfg", "-delete", ultimate_guid], timeout=30)
        if code == 0:
            done.append(tr("ลบแผน Ultimate ที่โปรแกรมสร้าง", "Removed the Ultimate plan this app added"))
    return not failed, done, failed


def use_high_performance(known_ultimate=""):
    """ใช้แผนพลังงานแบบแรง (สำหรับปุ่มของ AI)
    ลอง High performance ก่อน โน้ตบุ๊กรุ่นใหม่บางรุ่นไม่มีแผนนี้ ก็จะเพิ่ม Ultimate Performance แล้วใช้แทน
    คืน (สำเร็จไหม, ข้อความ, guid ของ Ultimate ถ้าสร้างใหม่)"""
    guids = {p["guid"] for p in list_power_plans()}
    if HIGH_PERFORMANCE_GUID in guids:
        ok, msg = set_power_plan(HIGH_PERFORMANCE_GUID)
        return ok, (tr("เปลี่ยนเป็นแผน High performance แล้ว", "Switched to High performance") if ok else msg), ""
    ok, msg, guid = add_ultimate_performance(known_ultimate)
    if not ok:
        return False, msg, ""
    ok, msg = set_power_plan(guid)
    return ok, (tr("เปลี่ยนเป็นแผน Ultimate Performance แล้ว", "Switched to Ultimate Performance") if ok else msg), guid

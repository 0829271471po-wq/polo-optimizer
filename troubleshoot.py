"""
troubleshoot.py
เครื่องมือแก้ปัญหาที่เจอบ่อย
- ซ่อมไฟล์ระบบ (DISM + SFC) เปิดหน้าต่าง cmd ให้เห็นความคืบหน้า
- รีเซ็ตอินเทอร์เน็ต (ล้าง DNS, ขอ IP ใหม่, รีเซ็ต Winsock และ TCP/IP)
- รีสตาร์ททาสก์บาร์ (ปิดแล้วเปิด explorer.exe ใหม่)
- เช็กสุขภาพดิสก์ (Get-PhysicalDisk)
"""

import os
import subprocess
import time

import psutil

from i18n import tr
from utils import open_url
from utils import run_cmd, ps_json, as_list, format_size, CREATE_NEW_CONSOLE, CREATE_NO_WINDOW

# ข้อความในหน้าต่าง cmd ใช้ภาษาอังกฤษ เพราะฟอนต์ของหน้าต่าง cmd ใน Windows 10 ส่วนใหญ่แสดงภาษาไทยไม่ได้
_REPAIR_COMMAND = (
    'cmd.exe /k "title Polo Optimizer - Repair Windows'
    " & echo [1/2] DISM: repairing Windows image... (may take 10-20 minutes)"
    " & DISM /Online /Cleanup-Image /RestoreHealth"
    " & echo. & echo [2/2] SFC: checking system files..."
    " & sfc /scannow"
    ' & echo. & echo Done. Please restart your computer, then close this window."'
)


def repair_windows():
    """เปิดหน้าต่าง cmd ใหม่ที่รัน DISM แล้วต่อด้วย sfc /scannow ให้ผู้ใช้เห็นความคืบหน้าเอง
    DISM ซ่อมต้นฉบับไฟล์ระบบก่อน แล้ว SFC จึงเอาต้นฉบับนั้นมาแทนไฟล์ที่เสีย (เลยต้องทำตามลำดับนี้)
    ฟังก์ชันนี้แค่เปิดหน้าต่างแล้วจบทันที ไม่รอให้ซ่อมเสร็จ"""
    subprocess.Popen(_REPAIR_COMMAND, creationflags=CREATE_NEW_CONSOLE)
    return True, tr("เปิดหน้าต่างซ่อมไฟล์ระบบแล้ว ใช้เวลาประมาณ 15-30 นาที ห้ามปิดหน้าต่างจนกว่าจะขึ้นว่า Done",
                    "Repair window opened. It takes about 15-30 minutes, don't close it until it says Done")


# ขั้นตอนรีเซ็ตเน็ต (คำอธิบาย, คำสั่ง)
_NETWORK_STEPS = [
    (("ล้างแคช DNS", "Flush DNS"), ["ipconfig", "/flushdns"]),
    (("คืน IP เดิม", "Release IP"), ["ipconfig", "/release"]),
    (("ขอ IP ใหม่", "Renew IP"), ["ipconfig", "/renew"]),
    (("รีเซ็ต Winsock", "Reset Winsock"), ["netsh", "winsock", "reset"]),
    (("รีเซ็ต TCP/IP", "Reset TCP/IP"), ["netsh", "int", "ip", "reset"]),
]


def reset_network(progress=None):
    """รีเซ็ตการตั้งค่าเน็ตทีละขั้น (ระหว่างนี้เน็ตจะหลุดไปสักครู่)
    progress = ฟังก์ชันที่ถูกเรียกพร้อมข้อความขั้นตอนปัจจุบัน
    คืน (สำเร็จไหม, ข้อความ) ขั้นไหนพลาดจะทำขั้นต่อไปต่อ แล้วสรุปทีเดียวตอนจบ"""
    failed = []
    for i, (label, args) in enumerate(_NETWORK_STEPS, start=1):
        if progress:
            progress(f"{i}/{len(_NETWORK_STEPS)} {tr(*label)}")
        code, _out, _err = run_cmd(args, timeout=90)
        # ipconfig /release และ /renew คืน error ได้ถ้ามีการ์ดเน็ตที่ไม่ได้เสียบสาย ซึ่งไม่ใช่ปัญหาจริง
        if code != 0 and args[0] != "ipconfig":
            failed.append(tr(*label))
    if failed:
        return False, tr("รีเซ็ตเน็ตเสร็จแต่บางขั้นไม่สำเร็จ: ", "Network reset finished but some steps failed: ") + ", ".join(failed)
    return True, tr("รีเซ็ตเน็ตเสร็จแล้ว ควรรีสตาร์ทเครื่อง 1 ครั้งเพื่อให้มีผลครบ", "Network reset done. Restart once for it to take full effect")


def _explorer_running():
    """เช็กว่า explorer.exe (ทาสก์บาร์และเดสก์ท็อป) ทำงานอยู่ไหม"""
    for proc in psutil.process_iter(["name"]):
        if (proc.info.get("name") or "").lower() == "explorer.exe":
            return True
    return False


def _start_explorer_as_user():
    """เปิด explorer.exe ใหม่ด้วยสิทธิ์ผู้ใช้ปกติ (ไม่ใช่ Admin)
    ถ้าเปิดตรง ๆ จากโปรแกรมที่เป็น Admin ทาสก์บาร์จะติดสิทธิ์ Admin ไปด้วย ซึ่งไม่ปลอดภัย
    เลยใช้ Task Scheduler สร้างงานชั่วคราวแบบ LIMITED (สิทธิ์ปกติ) ให้มันเปิดให้ แล้วลบงานทิ้ง"""
    task = "PoloOptimizer_RestartExplorer"
    code, _o, _e = run_cmd(["schtasks", "/create", "/tn", task, "/tr", "explorer.exe",
                            "/sc", "once", "/st", "00:00", "/rl", "LIMITED", "/f"], timeout=30)
    if code == 0:
        run_cmd(["schtasks", "/run", "/tn", task], timeout=30)
        time.sleep(2)
        run_cmd(["schtasks", "/delete", "/tn", task, "/f"], timeout=30)
    if not _explorer_running():
        # ทางสำรองสุดท้าย ถ้า Task Scheduler ใช้ไม่ได้
        subprocess.Popen(["explorer.exe"], creationflags=CREATE_NO_WINDOW)


def restart_explorer():
    """ปิดแล้วเปิด explorer.exe ใหม่ แก้อาการทาสก์บาร์ค้าง กดปุ่ม Start ไม่ได้ หรือไอคอนหาย
    หลังปิด Windows มักเปิด explorer กลับมาเองภายในไม่กี่วินาที ถ้าไม่เปิดเองเราจึงสั่งเปิดให้"""
    run_cmd(["taskkill", "/f", "/im", "explorer.exe"], timeout=30)
    for _ in range(10):
        time.sleep(0.5)
        if _explorer_running():
            return True, tr("รีสตาร์ททาสก์บาร์เรียบร้อย", "Taskbar restarted")
    _start_explorer_as_user()
    time.sleep(1)
    if _explorer_running():
        return True, tr("รีสตาร์ททาสก์บาร์เรียบร้อย", "Taskbar restarted")
    return False, tr("เปิดทาสก์บาร์ใหม่ไม่สำเร็จ กด Ctrl+Shift+Esc > File > Run new task > พิมพ์ explorer",
                     "Couldn't reopen the taskbar. Press Ctrl+Shift+Esc > File > Run new task > type explorer")


_DISK_SCRIPT = r"""
@(Get-PhysicalDisk | Select-Object FriendlyName, Size,
   @{n='MediaType';e={"$($_.MediaType)"}},
   @{n='HealthStatus';e={"$($_.HealthStatus)"}},
   @{n='OperationalStatus';e={"$($_.OperationalStatus)"}}) | ConvertTo-Json -Compress
"""

# บางเครื่อง PowerShell คืนสถานะเป็นตัวเลข เลยแปลงไว้ด้วย (0 = Healthy, 1 = Warning, 2 = Unhealthy)
_HEALTH_NAMES = {"0": "Healthy", "1": "Warning", "2": "Unhealthy", "5": "Unknown"}
_HEALTH_TEXT = {"Healthy": ("ปกติดี", "Healthy"), "Warning": ("เริ่มมีปัญหา", "Warning"),
                "Unhealthy": ("เสียหาย", "Unhealthy"), "Unknown": ("ไม่ทราบ", "Unknown")}


def disk_health():
    """อ่านสุขภาพดิสก์ทุกลูก คืน list ของ dict {name, size, health, health_th, healthy}
    healthy = False ถ้าสถานะไม่ใช่ Healthy (หน้าจอจะเตือนสีแดงให้รีบสำรองไฟล์)"""
    disks = []
    for d in as_list(ps_json(_DISK_SCRIPT)):
        health = str(d.get("HealthStatus") or "Unknown")
        health = _HEALTH_NAMES.get(health, health)
        disks.append({
            "name": d.get("FriendlyName") or tr("ดิสก์", "Disk"),
            "size": format_size(d.get("Size")),
            "health": health,
            "health_text": tr(*_HEALTH_TEXT[health]) if health in _HEALTH_TEXT else health,
            "healthy": health == "Healthy",
        })
    return disks


def open_system_restore():
    """เปิดหน้าต่าง System Restore ของ Windows ให้ผู้ใช้เลือกจุดคืนค่าที่เครื่องยังดีอยู่ แล้วย้อนกลับไป
    (ไฟล์ส่วนตัวไม่หาย แต่โปรแกรม/ไดรเวอร์/การตั้งค่าที่ลงหลังจุดนั้นจะถูกย้อน)"""
    subprocess.Popen([os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "rstrui.exe")])
    return True, tr("เปิด System Restore แล้ว เลือกจุดคืนค่าแล้วกด Next", "System Restore opened. Pick a restore point and press Next")


def open_reset_pc():
    """เปิดหน้า Recovery ใน Settings ที่มีปุ่ม Reset this PC (ลง Windows ใหม่ เลือกเก็บไฟล์ส่วนตัวไว้ได้)
    โปรแกรมนี้แค่เปิดหน้าให้ ผู้ใช้ต้องกดยืนยันใน Windows เองอีกหลายขั้น"""
    open_url("ms-settings:recovery")
    return True, tr("เปิดหน้า Recovery แล้ว กด Reset PC แล้วเลือก Keep my files", "Recovery opened. Press Reset PC and choose Keep my files")
"""
diagnostics.py
ตรวจเครื่องจริงเพื่อให้ผู้ช่วย AI ตอบจากสภาพเครื่องตอนนี้ ไม่ใช่ตอบตามสูตร
ทุกฟังก์ชันในไฟล์นี้ "อ่านอย่างเดียว" ไม่แก้อะไรในเครื่อง
- โปรแกรมที่กิน CPU/RAM มากที่สุดตอนนี้
- เปิดเครื่องมานานแค่ไหนแล้ว (ไม่เคยรีสตาร์ทเลยก็ทำให้เครื่องรวนได้)
- ทดสอบเน็ตจริง: ต่อเราเตอร์ได้ไหม ออกเน็ตได้ไหม DNS ใช้ได้ไหม ปิงเท่าไร
- ประวัติจอฟ้า เครื่องดับเอง และโปรแกรมที่เด้งบ่อย (จาก Event Log ของ Windows)
- อุปกรณ์เสียง แบตเตอรี่ และการอัปเดตที่รอรีสตาร์ท
ใช้ thread หลายตัวรันพร้อมกัน จะได้เสร็จในไม่กี่วินาที
"""

import os
import re
import socket
import time
import winreg
from concurrent.futures import ThreadPoolExecutor

import psutil

import cleaner
import drivers
import game_tweaks
import startup
import system_info
import troubleshoot
from utils import run_cmd, ps_json, as_list, format_size

# โปรเซสของระบบที่ไม่ต้องเอามาจัดอันดับ (ผู้ใช้ปิดเองไม่ได้ และไม่ได้เป็นต้นเหตุจริง)
_IGNORE_PROCS = {"system idle process", "system", "registry", "memory compression", "memcompression", "idle", ""}


def top_processes(limit=5):
    """หาโปรแกรมที่กิน CPU และ RAM มากที่สุดตอนนี้ (รวมโปรเซสชื่อเดียวกัน เช่น chrome หลายตัว ให้เป็นอันเดียว)
    วัด CPU 2 ครั้งห่างกัน 1 วินาที เพราะค่าครั้งแรกของ psutil จะเป็น 0 เสมอ
    คืน {"cpu": [(ชื่อ, %)], "ram": [(ชื่อ, byte)]}"""
    procs = []
    for p in psutil.process_iter(["name"]):
        try:
            p.cpu_percent(None)
            procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(1.0)
    cpu_count = psutil.cpu_count() or 1
    cpu, ram = {}, {}
    for p in procs:
        try:
            name = (p.info.get("name") or "").lower()
            if name in _IGNORE_PROCS:
                continue
            cpu[name] = cpu.get(name, 0) + p.cpu_percent(None) / cpu_count
            ram[name] = ram.get(name, 0) + p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    top_cpu = sorted(cpu.items(), key=lambda x: x[1], reverse=True)[:limit]
    top_ram = sorted(ram.items(), key=lambda x: x[1], reverse=True)[:limit]
    return {"cpu": [(n, round(v, 1)) for n, v in top_cpu if v >= 0.5], "ram": top_ram}


def uptime_days():
    """เปิดเครื่องมาแล้วกี่วัน (นับจากการบูตจริงครั้งล่าสุด ถ้าเปิด Fast Startup การกด Shut down จะไม่รีเซ็ตตัวเลขนี้)"""
    return round((time.time() - psutil.boot_time()) / 86400, 1)


def _ping(host, count=2):
    """ปิง host แล้วคืน (ถึงไหม, เวลาเฉลี่ย ms หรือ None)
    เช็กจากคำว่า TTL= ในผลลัพธ์ ซึ่งมีทั้งใน Windows ภาษาไทยและอังกฤษ"""
    code, out, _err = run_cmd(["ping", "-n", str(count), "-w", "1500", host], timeout=15)
    ok = "TTL=" in out.upper()
    times = [int(t) for t in re.findall(r"[=<](\d+)\s*ms", out)]
    return ok, (round(sum(times) / len(times)) if times else None)


def _default_gateway():
    """หา IP ของเราเตอร์ (default gateway) จาก PowerShell คืน None ถ้าไม่มี (เช่นไม่ได้ต่อเน็ตเลย)"""
    data = ps_json(r"""
@(Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object { $_.IPv4DefaultGateway } |
  ForEach-Object { [pscustomobject]@{ Gateway = $_.IPv4DefaultGateway.NextHop; Alias = $_.InterfaceAlias } }) | ConvertTo-Json -Compress
""", timeout=20)
    items = as_list(data)
    return (items[0].get("Gateway"), items[0].get("Alias")) if items else (None, None)


def network_check():
    """ทดสอบเน็ตทีละชั้น เพื่อบอกได้ว่าเสียตรงไหน
    1) มีการ์ดเน็ตที่เชื่อมต่ออยู่ไหม  2) ปิงเราเตอร์ได้ไหม  3) ปิง 1.1.1.1 ได้ไหม (ออกเน็ตได้)  4) แปลงชื่อเว็บเป็น IP ได้ไหม (DNS)
    คืน dict ผลแต่ละชั้น และ verdict สรุปว่าน่าจะเสียที่ไหน"""
    result = {"adapters": [], "gateway": None, "gateway_ok": None, "internet_ok": None,
              "dns_ok": None, "ping_ms": None, "verdict": ""}
    try:
        for name, stats in psutil.net_if_stats().items():
            if stats.isup and "loopback" not in name.lower() and "vethernet" not in name.lower():
                result["adapters"].append(name)
    except Exception:
        pass
    gateway, alias = _default_gateway()
    result["gateway"] = gateway
    if alias:
        result["adapters"] = [alias] + [a for a in result["adapters"] if a != alias]
    if gateway:
        result["gateway_ok"], _ = _ping(gateway)
    result["internet_ok"], result["ping_ms"] = _ping("1.1.1.1", count=4)
    try:
        socket.setdefaulttimeout(4)
        socket.gethostbyname("www.google.com")
        result["dns_ok"] = True
    except OSError:
        result["dns_ok"] = False
    finally:
        socket.setdefaulttimeout(None)

    if not gateway:
        result["verdict"] = "no_connection"      # ไม่ได้ต่อ Wi-Fi/สายแลน หรือไม่ได้ IP
    elif result["gateway_ok"] is False and not result["internet_ok"]:
        result["verdict"] = "router"             # ต่อเราเตอร์ไม่ติด
    elif not result["internet_ok"] and not result["dns_ok"]:
        result["verdict"] = "isp"                # เราเตอร์ได้ แต่ออกเน็ตไม่ได้ (เน็ตบ้านล่ม)
    elif result["internet_ok"] and not result["dns_ok"]:
        result["verdict"] = "dns"                # ออกเน็ตได้แต่แปลงชื่อเว็บไม่ได้
    elif result["ping_ms"] and result["ping_ms"] > 80:
        result["verdict"] = "high_ping"
    else:
        result["verdict"] = "ok"
    return result


_EVENTS_SCRIPT = r"""
$since14 = (Get-Date).AddDays(-14)
$since7  = (Get-Date).AddDays(-7)
$bsod  = @(Get-WinEvent -FilterHashtable @{LogName='System'; Id=1001; ProviderName='Microsoft-Windows-WER-SystemErrorReporting'; StartTime=$since14} -ErrorAction SilentlyContinue)
$power = @(Get-WinEvent -FilterHashtable @{LogName='System'; Id=41; ProviderName='Microsoft-Windows-Kernel-Power'; StartTime=$since14} -ErrorAction SilentlyContinue)
$apps  = @(Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000; ProviderName='Application Error'; StartTime=$since7} -MaxEvents 200 -ErrorAction SilentlyContinue)
[pscustomobject]@{
  Bsod      = $bsod.Count
  BsodLast  = if ($bsod.Count) { $bsod[0].TimeCreated.ToString('yyyy-MM-dd HH:mm') } else { '' }
  BsodText  = if ($bsod.Count) { "$($bsod[0].Properties[0].Value)" } else { '' }
  PowerLoss = $power.Count
  AppCrash  = @($apps | ForEach-Object { "$($_.Properties[0].Value)" } | Group-Object | Sort-Object Count -Descending |
               Select-Object -First 5 | ForEach-Object { [pscustomobject]@{ Name = $_.Name; Count = $_.Count } })
} | ConvertTo-Json -Depth 3 -Compress
"""

# รหัสจอฟ้าที่เจอบ่อย กับสาเหตุที่มักเป็น (ไทย, อังกฤษ)
BUGCHECKS = {
    "0x00000116": ("ไดรเวอร์การ์ดจอค้าง (VIDEO_TDR_FAILURE)", "graphics driver hang (VIDEO_TDR_FAILURE)"),
    "0x00000117": ("ไดรเวอร์การ์ดจอค้าง (VIDEO_TDR_TIMEOUT)", "graphics driver hang (VIDEO_TDR_TIMEOUT)"),
    "0x0000001a": ("RAM มีปัญหา (MEMORY_MANAGEMENT)", "RAM problem (MEMORY_MANAGEMENT)"),
    "0x0000003b": ("ไดรเวอร์หรือไฟล์ระบบมีปัญหา (SYSTEM_SERVICE_EXCEPTION)", "driver or system file problem (SYSTEM_SERVICE_EXCEPTION)"),
    "0x0000007e": ("ไดรเวอร์ทำงานผิดพลาด (SYSTEM_THREAD_EXCEPTION)", "faulty driver (SYSTEM_THREAD_EXCEPTION)"),
    "0x000000d1": ("ไดรเวอร์มีปัญหา มักเป็นเน็ต/Wi-Fi (DRIVER_IRQL_NOT_LESS_OR_EQUAL)", "driver bug, often network/Wi-Fi (DRIVER_IRQL_NOT_LESS_OR_EQUAL)"),
    "0x0000000a": ("ไดรเวอร์หรือ RAM มีปัญหา (IRQL_NOT_LESS_OR_EQUAL)", "driver or RAM problem (IRQL_NOT_LESS_OR_EQUAL)"),
    "0x00000050": ("RAM หรือไดรเวอร์มีปัญหา (PAGE_FAULT_IN_NONPAGED_AREA)", "RAM or driver problem (PAGE_FAULT_IN_NONPAGED_AREA)"),
    "0x00000124": ("ฮาร์ดแวร์มีปัญหา เช่นร้อนเกินหรือไฟไม่พอ (WHEA_UNCORRECTABLE_ERROR)", "hardware error, e.g. overheating or power (WHEA_UNCORRECTABLE_ERROR)"),
    "0x0000009f": ("ไดรเวอร์มีปัญหาตอนพัก/ปิดเครื่อง (DRIVER_POWER_STATE_FAILURE)", "driver failed on sleep/shutdown (DRIVER_POWER_STATE_FAILURE)"),
    "0x000000ef": ("ไฟล์ระบบสำคัญพัง (CRITICAL_PROCESS_DIED)", "critical system process died (CRITICAL_PROCESS_DIED)"),
    "0x00000133": ("ไดรเวอร์หรือ SSD ตอบสนองช้า (DPC_WATCHDOG_VIOLATION)", "driver or SSD timeout (DPC_WATCHDOG_VIOLATION)"),
}


def recent_crashes():
    """อ่าน Event Log: จอฟ้า (14 วัน), เครื่องดับเองไม่ได้ปิดปกติ (14 วัน), โปรแกรมที่แครชบ่อย (7 วัน)
    คืน dict {bsod, bsod_last, bsod_code, power_loss, app_crashes: [(ชื่อ, ครั้ง)]}"""
    data = ps_json(_EVENTS_SCRIPT, timeout=45) or {}
    code_match = re.search(r"0x[0-9a-fA-F]{8}", data.get("BsodText") or "")
    return {
        "bsod": data.get("Bsod") or 0,
        "bsod_last": data.get("BsodLast") or "",
        "bsod_code": code_match.group(0).lower() if code_match else "",
        "power_loss": data.get("PowerLoss") or 0,
        "app_crashes": [(a.get("Name"), a.get("Count")) for a in as_list(data.get("AppCrash")) if a.get("Name")],
    }


_AUDIO_SCRIPT = r"""
[pscustomobject]@{
  Service = "$((Get-Service Audiosrv -ErrorAction SilentlyContinue).Status)"
  Devices = @(Get-CimInstance Win32_SoundDevice | Select-Object Name, ConfigManagerErrorCode)
} | ConvertTo-Json -Depth 3 -Compress
"""


def audio_check():
    """อ่านสถานะเสียง: บริการ Windows Audio ทำงานไหม และอุปกรณ์เสียงแต่ละตัวมีปัญหาไหม (อ่านอย่างเดียว)"""
    data = ps_json(_AUDIO_SCRIPT, timeout=30) or {}
    devices = [{"name": d.get("Name") or "?", "ok": (d.get("ConfigManagerErrorCode") or 0) == 0}
               for d in as_list(data.get("Devices"))]
    return {"service": data.get("Service") or "", "devices": devices}


def battery_info():
    """อ่านแบตเตอรี่ (ถ้าเป็นโน้ตบุ๊ก) คืน None ถ้าไม่มีแบต"""
    try:
        b = psutil.sensors_battery()
    except Exception:
        return None
    if b is None:
        return None
    return {"percent": round(b.percent), "plugged": bool(b.power_plugged)}


def pending_reboot():
    """เช็กว่ามีอัปเดต Windows ที่ลงแล้วแต่รอรีสตาร์ทอยู่ไหม (ดูจาก registry ที่ Windows Update เขียนไว้)"""
    keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
    ]
    for path in keys:
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY))
            return True
        except OSError:
            continue
    return False


def active_power_plan():
    """ชื่อแผนพลังงานที่ใช้อยู่"""
    for plan in game_tweaks.list_power_plans():
        if plan["active"]:
            return plan["name"]
    return ""


def _safe(func, default=None):
    """เรียกฟังก์ชันตรวจ ถ้าพังให้คืนค่า default แทน (การตรวจอย่างเดียวพังต้องไม่ทำให้ทั้งหมดพัง)"""
    try:
        return func()
    except Exception:
        return default


def collect_all():
    """รันการตรวจทุกอย่างพร้อมกันด้วย thread pool แล้วรวมผลเป็น dict เดียว
    ใช้เวลาประมาณ 3-8 วินาที (ช้าสุดคือทดสอบเน็ตกับสแกนไฟล์ขยะ) ต้องเรียกจาก thread แยก"""
    jobs = {
        "specs": lambda: dict(system_info.summarize_specs(system_info.get_specs())),
        "usage": system_info.get_usage,
        "top": top_processes,
        "uptime_days": uptime_days,
        "startup_count": startup.count_enabled,
        "junk": lambda: sum(size for size, _c in cleaner.scan(cleaner.default_keys()).values()),
        "problem_devices": drivers.get_problem_devices,
        "gpus": drivers.get_gpus,
        "network": network_check,
        "crashes": recent_crashes,
        "audio": audio_check,
        "battery": battery_info,
        "pending_reboot": pending_reboot,
        "power_plan": active_power_plan,
        "disk_health": troubleshoot.disk_health,
    }
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {key: pool.submit(_safe, func) for key, func in jobs.items()}
        data = {key: f.result() for key, f in futures.items()}
    data["junk_size"] = format_size(data.get("junk") or 0)
    return data

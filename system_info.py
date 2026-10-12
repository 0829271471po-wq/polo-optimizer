"""
system_info.py
อ่านสเปกเครื่อง (Windows, CPU, การ์ดจอ, RAM, เมนบอร์ด, ดิสก์) ผ่าน PowerShell Get-CimInstance
และอ่านเปอร์เซ็นต์การใช้งาน CPU/RAM/ดิสก์ ด้วย psutil สำหรับเกจในหน้าแรก
"""

import os

import psutil

from i18n import tr
from utils import ps_json, as_list, format_size

# สคริปต์ PowerShell ตัวเดียวที่ดึงข้อมูลทุกอย่างแล้วแปลงเป็น JSON
# รันครั้งเดียวจบ เร็วกว่าเรียก PowerShell แยกทีละอย่าง
_SPEC_SCRIPT = r"""
$os    = Get-CimInstance Win32_OperatingSystem
$cpu   = Get-CimInstance Win32_Processor | Select-Object -First 1
# AdapterRAM เก็บได้สูงสุดแค่ 4GB เลยอ่าน VRAM จริงจาก registry ของไดรเวอร์การ์ดจอแทน (ถ้ามี)
$vram  = @{}
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*' -ErrorAction SilentlyContinue |
  ForEach-Object { $q = $_.'HardwareInformation.qwMemorySize'; if ($q -and $_.DriverDesc) { $vram[$_.DriverDesc] = [uint64]$q } }
$gpu   = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, PNPDeviceID,
           @{n='AdapterRAM';e={ if ($vram.ContainsKey($_.Name)) { $vram[$_.Name] } else { $_.AdapterRAM } }})
$mem   = @(Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, Speed, ConfiguredClockSpeed)
$slots = (Get-CimInstance Win32_PhysicalMemoryArray | Measure-Object -Property MemoryDevices -Sum).Sum
$board = Get-CimInstance Win32_BaseBoard | Select-Object -First 1
$cs    = Get-CimInstance Win32_ComputerSystem
$disk  = @()
try {
  $disk = @(Get-PhysicalDisk | Select-Object FriendlyName, Size,
      @{n='MediaType';e={"$($_.MediaType)"}}, @{n='BusType';e={"$($_.BusType)"}})
} catch {}
[pscustomobject]@{
  OS        = @{ Caption = $os.Caption; Version = $os.Version; Build = $os.BuildNumber; Arch = $os.OSArchitecture }
  CPU       = @{ Name = $cpu.Name; Cores = $cpu.NumberOfCores; Threads = $cpu.NumberOfLogicalProcessors; MaxClock = $cpu.MaxClockSpeed }
  GPU       = $gpu
  RAM       = $mem
  RAMSlots  = $slots
  Board     = @{ Manufacturer = $board.Manufacturer; Product = $board.Product }
  System    = @{ Manufacturer = $cs.Manufacturer; Model = $cs.Model; PCSystemType = $cs.PCSystemType; TotalRAM = $cs.TotalPhysicalMemory }
  Disks     = $disk
} | ConvertTo-Json -Depth 4 -Compress
"""

# รหัสประเภทดิสก์ บางเครื่อง PowerShell คืนมาเป็นตัวเลข บางเครื่องเป็นข้อความ เลยแปลงไว้ทั้งสองแบบ
_MEDIA_TYPES = {"3": "HDD", "4": "SSD", "5": "SCM", "0": "", "Unspecified": ""}

# เก็บผลสเปกไว้ จะได้ไม่ต้องอ่านใหม่ทุกครั้ง (หน้า AI กับหน้าไดรเวอร์เอาไปใช้ต่อได้)
_cache = {}


def get_specs(refresh=False):
    """อ่านสเปกเครื่องทั้งหมด คืนค่าเป็น dict ข้อมูลดิบจาก PowerShell
    ถ้าอ่านไม่ได้จะคืน dict ว่าง (ไม่ throw error) และจำผลไว้ใช้ครั้งต่อไป"""
    if _cache.get("specs") and not refresh:
        return _cache["specs"]
    data = ps_json(_SPEC_SCRIPT, timeout=60) or {}
    _cache["specs"] = data
    return data


def summarize_specs(data):
    """แปลงข้อมูลดิบจาก get_specs() ให้เป็นรายการ (หัวข้อ, ข้อความ) สำหรับแสดงบนหน้าจอและส่งให้ AI"""
    rows = []

    os_info = data.get("OS") or {}
    if os_info:
        rows.append(("Windows", f"{os_info.get('Caption', '')} ({os_info.get('Arch', '')}) build {os_info.get('Build', '')}".strip()))

    cpu = data.get("CPU") or {}
    if cpu:
        ghz = (cpu.get("MaxClock") or 0) / 1000
        rows.append(("CPU", f"{(cpu.get('Name') or '').strip()}  •  {cpu.get('Cores')} {tr('คอร์', 'cores')} "
                            f"{cpu.get('Threads')} {tr('เธรด', 'threads')}  •  {ghz:.2f} GHz"))

    gpus = as_list(data.get("GPU"))
    if gpus:
        names = []
        for g in gpus:
            name = g.get("Name") or tr("ไม่ทราบชื่อ", "Unknown")
            ram = g.get("AdapterRAM") or 0
            # ถ้าอ่าน VRAM จาก registry ไม่ได้ ค่าจาก AdapterRAM จะตันที่ ~4GB เลยไม่แสดงค่าที่ตันพอดี เพราะอาจไม่ใช่ค่าจริง
            if ram >= 256 * 1024 ** 2 and not (4290000000 <= ram < 4 * 1024 ** 3):
                name += f" ({format_size(ram)})"
            names.append(name)
        rows.append((tr("การ์ดจอ", "Graphics"), "\n".join(names)))

    sticks = as_list(data.get("RAM"))
    total = (data.get("System") or {}).get("TotalRAM") or sum((s.get("Capacity") or 0) for s in sticks)
    if total:
        speeds = [s.get("ConfiguredClockSpeed") or s.get("Speed") for s in sticks]
        speeds = [s for s in speeds if s]
        speed_text = f"{max(speeds)} MT/s" if speeds else tr("ไม่ทราบความเร็ว", "unknown speed")
        slots = data.get("RAMSlots")
        slot_text = tr(f"{len(sticks)} แถว", f"{len(sticks)} stick(s)") + (tr(f" (จากช่องทั้งหมด {slots} ช่อง)", f" of {slots} slots") if slots else "")
        sizes = sorted({round((s.get("Capacity") or 0) / 1024 ** 3) for s in sticks})
        layout = f" [{sizes[0]}GB x {len(sticks)}]" if len(sizes) == 1 and sizes[0] else ""
        rows.append(("RAM", f"{format_size(total)}{layout}  •  {speed_text}  •  {slot_text}"))

    board = data.get("Board") or {}
    if board.get("Manufacturer") or board.get("Product"):
        rows.append((tr("เมนบอร์ด", "Motherboard"), f"{board.get('Manufacturer') or ''} {board.get('Product') or ''}".strip()))

    disks = as_list(data.get("Disks"))
    if disks:
        lines = []
        for d in disks:
            media = _MEDIA_TYPES.get(str(d.get("MediaType")), str(d.get("MediaType") or ""))
            bus = d.get("BusType") or ""
            # NVMe ส่วนใหญ่บอก BusType เป็น NVMe ตรง ๆ ดูง่ายกว่า MediaType
            kind = "NVMe SSD" if bus == "NVMe" or bus == "17" else media
            lines.append(f"{d.get('FriendlyName') or tr('ดิสก์', 'Disk')}  •  {format_size(d.get('Size'))}" + (f"  •  {kind}" if kind else ""))
        rows.append((tr("ดิสก์", "Disks"), "\n".join(lines)))

    return rows


def system_drive():
    """คืนตัวอักษรไดรฟ์ที่ลง Windows ไว้ เช่น 'C:\\'"""
    return os.environ.get("SystemDrive", "C:") + "\\"


def get_usage():
    """อ่านเปอร์เซ็นต์การใช้งาน CPU, RAM และพื้นที่ไดรฟ์ Windows คืนเป็น dict
    cpu_percent(interval=None) จะคืนค่าเฉลี่ยตั้งแต่ครั้งที่แล้วที่เรียก ไม่ต้องรอ เลยเรียกจาก UI ได้โดยไม่ค้าง"""
    usage = {"cpu": 0.0, "ram": 0.0, "disk": 0.0, "ram_used": 0, "ram_total": 0, "disk_free": 0, "disk_total": 0}
    try:
        usage["cpu"] = psutil.cpu_percent(interval=None)
    except Exception:
        pass
    try:
        vm = psutil.virtual_memory()
        usage["ram"] = vm.percent
        usage["ram_used"] = vm.total - vm.available
        usage["ram_total"] = vm.total
    except Exception:
        pass
    try:
        du = psutil.disk_usage(system_drive())
        usage["disk"] = du.percent
        usage["disk_free"] = du.free
        usage["disk_total"] = du.total
    except Exception:
        pass
    return usage

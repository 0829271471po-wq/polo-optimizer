"""
drivers.py
ตรวจไดรเวอร์: ดูยี่ห้อการ์ดจอ, ดูว่าเป็นโน้ตบุ๊กหรือ PC ประกอบ, หาอุปกรณ์ที่มีปัญหา
แล้วพาผู้ใช้ไปหน้าเว็บโหลดไดรเวอร์ "ของผู้ผลิตโดยตรง" เท่านั้น (ไม่โหลดจากเว็บรวมไดรเวอร์)
"""

import re
import urllib.parse

from i18n import tr, tx
from utils import ps_json, as_list, open_url, open_system_tool

# หน้าโหลดไดรเวอร์การ์ดจอของแต่ละค่าย (เว็บทางการ)
GPU_DRIVER_URLS = {
    "nvidia": ("NVIDIA", "https://www.nvidia.com/en-us/software/nvidia-app/"),
    "amd": ("AMD", "https://www.amd.com/en/support/download/drivers.html"),
    "intel": ("Intel", "https://www.intel.com/content/www/us/en/support/detect.html"),
}

# รหัสผู้ผลิตชิป (Vendor ID) ที่อยู่ใน PNPDeviceID เช่น PCI\VEN_10DE&DEV_...
# ใช้ตัวนี้แม่นกว่าดูจากชื่อ เพราะการ์ดที่ยังไม่มีไดรเวอร์จะชื่อ "Microsoft Basic Display Adapter" แต่รหัสยังบอกยี่ห้อได้
_VENDOR_IDS = {"VEN_10DE": "nvidia", "VEN_1002": "amd", "VEN_1022": "amd", "VEN_8086": "intel"}

# เว็บซัพพอร์ตของยี่ห้อเครื่อง/เมนบอร์ด (keyword ที่หาในชื่อผู้ผลิต, ชื่อที่แสดง, ลิงก์)
SUPPORT_SITES = [
    (("ASUSTEK", "ASUS"), "ASUS", "https://www.asus.com/support/download-center/"),
    (("MICRO-STAR", "MSI"), "MSI", "https://www.msi.com/support/download"),
    (("GIGABYTE",), "Gigabyte", "https://www.gigabyte.com/Support"),
    (("ASROCK",), "ASRock", "https://www.asrock.com/support/index.asp"),
    (("DELL",), "Dell", "https://www.dell.com/support/home/"),
    (("HEWLETT", "HP"), "HP", "https://support.hp.com/drivers"),
    (("LENOVO",), "Lenovo", "https://pcsupport.lenovo.com/"),
    (("ACER",), "Acer", "https://www.acer.com/us-en/support/drivers-and-manuals"),
]

# ความหมายของรหัสปัญหาใน Device Manager ที่เจอบ่อย
ERROR_CODES = {
    1: ("ตั้งค่าอุปกรณ์ไม่ถูกต้อง", "Device not configured correctly"),
    3: ("ไดรเวอร์เสียหรือหน่วยความจำไม่พอ", "Driver corrupted or out of memory"),
    10: ("อุปกรณ์เริ่มทำงานไม่ได้", "Device cannot start"),
    18: ("ต้องลงไดรเวอร์ใหม่", "Driver needs reinstalling"),
    19: ("ข้อมูลใน registry เสีย", "Registry data is corrupted"),
    22: ("อุปกรณ์ถูกปิดใช้งานอยู่", "Device is disabled"),
    24: ("ไม่พบอุปกรณ์หรือไดรเวอร์ไม่ครบ", "Device missing or driver incomplete"),
    28: ("ยังไม่ได้ลงไดรเวอร์", "No driver installed"),
    31: ("ไดรเวอร์ทำงานไม่ถูกต้อง", "Driver not working properly"),
    39: ("โหลดไดรเวอร์ไม่ได้ (อาจเสีย)", "Driver failed to load (may be corrupted)"),
    43: ("อุปกรณ์แจ้งว่ามีปัญหา", "Device reported a problem"),
    52: ("ไดรเวอร์ไม่ผ่านการรับรองลายเซ็น", "Driver signature not verified"),
}

_GPU_SCRIPT = r"""
@(Get-CimInstance Win32_VideoController | Select-Object Name, PNPDeviceID, DriverVersion, Status) | ConvertTo-Json -Compress
"""

_SYSTEM_SCRIPT = r"""
$cs = Get-CimInstance Win32_ComputerSystem
$bb = Get-CimInstance Win32_BaseBoard | Select-Object -First 1
[pscustomobject]@{
  Manufacturer = $cs.Manufacturer; Model = $cs.Model; PCSystemType = $cs.PCSystemType
  BoardMaker = $bb.Manufacturer; BoardProduct = $bb.Product
} | ConvertTo-Json -Compress
"""

# ConfigManagerErrorCode 45 = อุปกรณ์ที่เคยเสียบแต่ตอนนี้ไม่ได้เสียบ ไม่ใช่ปัญหา เลยไม่นับ
_PROBLEM_SCRIPT = r"""
@(Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -ne 0 -and $_.ConfigManagerErrorCode -ne 45 } |
  Select-Object Name, PNPClass, DeviceID, ConfigManagerErrorCode, @{n='HardwareID';e={@($_.HardwareID)[0]}}) | ConvertTo-Json -Compress
"""

# หน้าโหลดไดรเวอร์ชิปเซ็ตของ AMD แยกตามซ็อกเก็ตและชิปเซ็ต เช่น .../chipsets/am5/b650.html
AMD_CHIPSET_URL = "https://www.amd.com/en/support/downloads/drivers.html/chipsets/{socket}/{chipset}.html"
AMD_DRIVERS_URL = "https://www.amd.com/en/support/download/drivers.html"
ASUS_MODEL_URL = "https://www.asus.com/supportonly/{}/helpdesk_download/"
INTEL_DSA_URL = "https://www.intel.com/content/www/us/en/support/detect.html"
# Microsoft Update Catalog: เว็บทางการของ Microsoft ที่รวมไดรเวอร์ ค้นด้วย Hardware ID ได้ตรงตัว
CATALOG_URL = "https://www.catalog.update.microsoft.com/Search.aspx?q={}"

# ชิปเซ็ต AMD แต่ละรุ่นอยู่บนซ็อกเก็ตไหน (ดูจากเลขชุดแรกของชื่อชิปเซ็ต)
_AMD_SOCKETS = {"3": "am4", "4": "am4", "5": "am4", "6": "am5", "8": "am5"}


def _vendor_of(gpu):
    """บอกยี่ห้อการ์ดจอ (nvidia/amd/intel) จาก Vendor ID ก่อน ถ้าไม่มีค่อยดูจากชื่อ"""
    pnp = (gpu.get("PNPDeviceID") or "").upper()
    for ven, vendor in _VENDOR_IDS.items():
        if ven in pnp:
            return vendor
    name = (gpu.get("Name") or "").upper()
    if any(k in name for k in ("NVIDIA", "GEFORCE", "QUADRO", "RTX", "GTX")):
        return "nvidia"
    if any(k in name for k in ("AMD", "RADEON")):
        return "amd"
    if "INTEL" in name:
        return "intel"
    return None


def get_gpus():
    """อ่านรายการการ์ดจอทั้งหมด คืน list ของ dict ที่มี name, vendor, driver_version, no_driver
    no_driver = True ถ้าชื่อเป็น Microsoft Basic Display Adapter (แปลว่ายังไม่ได้ลงไดรเวอร์)
    ข้ามการ์ดจอเสมือน (เช่นของโปรแกรมรีโมต) ที่ไม่ได้เป็นฮาร์ดแวร์จริง"""
    gpus = []
    for g in as_list(ps_json(_GPU_SCRIPT)):
        pnp = (g.get("PNPDeviceID") or "").upper()
        name = g.get("Name") or tr("ไม่ทราบชื่อ", "Unknown")
        is_basic = "BASIC DISPLAY" in name.upper() or "BASIC RENDER" in name.upper()
        if not pnp.startswith("PCI\\") and not is_basic:
            continue  # การ์ดจอเสมือน (ROOT\...) เช่น Parsec, Remote Desktop
        gpus.append({
            "name": name,
            "vendor": _vendor_of(g),
            "driver_version": g.get("DriverVersion") or "-",
            "no_driver": is_basic,
        })
    return gpus


def _match_support_site(*names):
    """หาว่าชื่อผู้ผลิตตรงกับยี่ห้อไหนใน SUPPORT_SITES คืน (ชื่อยี่ห้อ, ลิงก์) หรือ None"""
    for raw in names:
        text = (raw or "").upper()
        if not text:
            continue
        for keywords, brand, url in SUPPORT_SITES:
            for k in keywords:
                # HP สั้นมาก ต้องเป็นคำขึ้นต้นเท่านั้น กันไปชนกับชื่ออื่น
                if (k == "HP" and (text == "HP" or text.startswith("HP "))) or (k != "HP" and k in text):
                    return brand, url
    return None


def get_system_brand():
    """ดูว่าเป็นโน้ตบุ๊ก (PCSystemType = 2) หรือ PC ประกอบ แล้วหายี่ห้อที่ควรไปโหลดไดรเวอร์
    - โน้ตบุ๊ก/เครื่องแบรนด์: ใช้ยี่ห้อเครื่อง เพราะไดรเวอร์ถูกปรับมาเฉพาะรุ่น
    - PC ประกอบ: ใช้ยี่ห้อเมนบอร์ด
    คืน dict ที่มี is_laptop, maker, model, brand, url"""
    info = ps_json(_SYSTEM_SCRIPT) or {}
    is_laptop = info.get("PCSystemType") == 2
    if is_laptop:
        maker, model = info.get("Manufacturer"), info.get("Model")
        match = _match_support_site(maker)
    else:
        maker, model = info.get("BoardMaker"), info.get("BoardProduct")
        # เครื่องแบรนด์แบบตั้งโต๊ะ (Dell, HP) เมนบอร์ดมักเขียนชื่อแบรนด์เดียวกัน ถ้าไม่เจอค่อยลองยี่ห้อเครื่อง
        match = _match_support_site(maker, info.get("Manufacturer"))
    model = (model or "").strip()
    url = match[1] if match else None
    # ASUS มีหน้าโหลดไดรเวอร์แยกตามรุ่นที่เข้าได้ตรง ๆ (ทดสอบแล้วกับ PRIME B650M-A II) ยี่ห้ออื่นใช้หน้าค้นหารวม
    if match and match[0] == "ASUS" and model and model.lower() not in ("system product name", "to be filled by o.e.m."):
        url = ASUS_MODEL_URL.format(urllib.parse.quote(model))
    return {
        "is_laptop": is_laptop,
        "maker": (maker or tr("ไม่ทราบ", "Unknown")).strip(),
        "model": model,
        "brand": match[0] if match else None,
        "url": url,
    }


def _device_vendor(hwid, pnp_class):
    """บอกว่าอุปกรณ์เป็นของค่ายไหน จาก Hardware ID (เช่น PCI\\VEN_1022&DEV_1649 -> AMD)
    คืน amd_chipset / amd_gpu / intel / nvidia / realtek / other"""
    h = (hwid or "").upper()
    if "VEN_10DE" in h:
        return "nvidia"
    if "VEN_1002" in h or ("VEN_1022" in h and (pnp_class or "").lower() == "display"):
        return "amd_gpu"
    if "VEN_1022" in h or "VEN_AMDI" in h or h.startswith("ACPI\\AMDI"):
        return "amd_chipset"
    if "VEN_8086" in h or "VEN_INTC" in h or h.startswith("ACPI\\INT"):
        return "intel"
    if "VEN_10EC" in h or "VEN_REAL" in h:
        return "realtek"
    return "other"


def _short_hwid(hwid):
    """ตัด Hardware ID ให้สั้นพอสำหรับค้นหา เช่น PCI\\VEN_1022&DEV_1649&SUBSYS_...&REV_00 -> PCI\\VEN_1022&DEV_1649"""
    parts = (hwid or "").split("&")
    return "&".join(parts[:2]) if len(parts) >= 2 else (hwid or "")


def get_problem_devices():
    """หาอุปกรณ์ที่ Device Manager ขึ้นเครื่องหมายตกใจ (ConfigManagerErrorCode ไม่ใช่ 0)
    คืน list ของ dict ที่มี name, code, problem (คำอธิบาย), missing_driver (True ถ้ารหัส 28),
    hwid (Hardware ID), vendor (ค่ายของอุปกรณ์), catalog_url (ลิงก์ค้นไดรเวอร์ตัวนี้ใน Microsoft Update Catalog)"""
    devices = []
    for d in as_list(ps_json(_PROBLEM_SCRIPT)):
        code = d.get("ConfigManagerErrorCode") or 0
        hwid = d.get("HardwareID") or d.get("DeviceID") or ""
        vendor = _device_vendor(hwid, d.get("PNPClass"))
        name = d.get("Name")
        if not name:
            # อุปกรณ์ที่ยังไม่มีไดรเวอร์มักไม่มีชื่อ ตั้งชื่อให้อ่านรู้เรื่องจากค่าย + รหัสอุปกรณ์
            dev_code = (d.get("DeviceID") or "").split("\\")[1] if "\\" in (d.get("DeviceID") or "") else hwid
            prefix = {"amd_chipset": tr("อุปกรณ์ชิปเซ็ต AMD", "AMD chipset device"), "intel": tr("อุปกรณ์ Intel", "Intel device"),
                      "nvidia": "NVIDIA", "amd_gpu": "AMD Radeon", "realtek": "Realtek"}.get(vendor, tr("อุปกรณ์ไม่ทราบชื่อ", "Unknown device"))
            name = f"{prefix} ({dev_code})"
        short = _short_hwid(hwid)
        devices.append({
            "name": name,
            "code": code,
            "problem": tx(ERROR_CODES[code]) if code in ERROR_CODES else tr(f"มีปัญหา (รหัส {code})", f"Problem (code {code})"),
            "missing_driver": code == 28,
            "hwid": short,
            "vendor": vendor,
            "catalog_url": CATALOG_URL.format(urllib.parse.quote(short)) if short else None,
        })
    return devices


def amd_chipset_page(board_model):
    """หาลิงก์หน้าไดรเวอร์ชิปเซ็ต AMD ที่ตรงกับเมนบอร์ด เช่น "PRIME B650M-A II" -> ชิปเซ็ต B650 ซ็อกเก็ต AM5
    คืน (ชื่อชิปเซ็ต เช่น "B650", ลิงก์) ถ้าเดาชิปเซ็ตไม่ได้คืน (None, หน้าไดรเวอร์รวมของ AMD)"""
    match = re.search(r"\b([ABX])(\d)(\d0)(E)?", (board_model or "").upper())
    if match and match.group(2) in _AMD_SOCKETS:
        chipset = f"{match.group(1)}{match.group(2)}{match.group(3)}{match.group(4) or ''}"
        # รุ่น E (เช่น X670E) ใช้ไดรเวอร์ตัวเดียวกับรุ่นปกติ เลยลิงก์ไปหน้ารุ่นปกติ
        base = chipset.rstrip("E")
        return chipset, AMD_CHIPSET_URL.format(socket=_AMD_SOCKETS[match.group(2)], chipset=base.lower())
    return None, AMD_DRIVERS_URL


def driver_fixes(devices, brand):
    """จัดกลุ่มอุปกรณ์ที่มีปัญหาตามแหล่งไดรเวอร์ที่ต้องโหลด (อุปกรณ์หลายตัวมักแก้ได้ด้วยไดรเวอร์ตัวเดียว)
    brand = ผลจาก get_system_brand() ใช้หารุ่นชิปเซ็ตและเว็บซัพพอร์ตของเมนบอร์ด/เครื่อง
    คืน list ของ dict {title, why, count, links: [(ข้อความปุ่ม, ลิงก์, คำอธิบาย)]}"""
    groups = {}
    for d in devices:
        groups.setdefault(d["vendor"], []).append(d)
    support = []
    if brand and brand.get("url"):
        support = [(tr(f"🌐  เว็บซัพพอร์ต {brand['brand']}", f"🌐  {brand['brand']} support"), brand["url"],
                    (tr(f"หน้าโหลดไดรเวอร์ของรุ่น \"{brand['model']}\" โดยตรง", f"Driver downloads for \"{brand['model']}\" directly")
                     if "supportonly" in brand["url"] else
                     tr(f"ค้นหารุ่น \"{brand['model']}\" แล้วโหลดไดรเวอร์ที่ตรงรุ่น", f"Search \"{brand['model']}\" for drivers made for your model")))]
    fixes = []
    for vendor, items in groups.items():
        count = len(items)
        if vendor == "amd_chipset":
            chipset, url = amd_chipset_page((brand or {}).get("model", ""))
            name = f"AMD Chipset Driver{f' ({chipset})' if chipset else ''}"
            fixes.append({
                "title": tr(f"ลง {name}", f"Install {name}"),
                "why": tr(f"อุปกรณ์ {count} ตัวเป็นชิปเซ็ตของ AMD (รหัส VEN_1022 / AMDI) ลงไดรเวอร์ชิปเซ็ตตัวเดียวจะหายทั้งหมด",
                          f"{count} device(s) belong to the AMD chipset (VEN_1022 / AMDI). One chipset driver fixes them all"),
                "count": count,
                "links": [(tr("⬇  โหลดจากเว็บ AMD", "⬇  Download from AMD"), url,
                           tr("เลือก Windows 10/11 แล้วกดโหลด AMD Chipset Drivers ติดตั้งเสร็จรีสตาร์ท 1 ครั้ง",
                              "Choose Windows 10/11 and download AMD Chipset Drivers, then restart once"))] + support,
            })
        elif vendor == "intel":
            fixes.append({
                "title": tr("ลงไดรเวอร์ Intel", "Install Intel drivers"),
                "why": tr(f"อุปกรณ์ {count} ตัวเป็นของ Intel โปรแกรม Intel Driver & Support Assistant จะตรวจและลงให้เอง",
                          f"{count} device(s) are Intel. Intel Driver & Support Assistant detects and installs them"),
                "count": count,
                "links": [(tr("⬇  เปิด Intel Driver & Support Assistant", "⬇  Open Intel Driver & Support Assistant"), INTEL_DSA_URL,
                           tr("เว็บทางการของ Intel ตรวจเครื่องแล้วบอกไดรเวอร์ที่ต้องลง", "Intel's official tool finds the drivers you need"))] + support,
            })
        elif vendor in ("nvidia", "amd_gpu"):
            label, url = GPU_DRIVER_URLS["nvidia" if vendor == "nvidia" else "amd"]
            fixes.append({
                "title": tr(f"ลงไดรเวอร์การ์ดจอ {label}", f"Install {label} graphics driver"),
                "why": tr(f"อุปกรณ์ {count} ตัวเป็นการ์ดจอ/เสียงผ่านจอของ {label}", f"{count} device(s) are {label} graphics/HDMI audio"),
                "count": count,
                "links": [(tr(f"⬇  โหลดไดรเวอร์ {label}", f"⬇  Get {label} driver"), url,
                           tr(f"เว็บทางการของ {label}", f"{label}'s official website"))],
            })
        else:
            what = "Realtek (เสียง/แลน)" if vendor == "realtek" else tr("อื่น ๆ", "other")
            fixes.append({
                "title": tr(f"ไดรเวอร์จากเว็บยี่ห้อเครื่อง/เมนบอร์ด", "Drivers from your PC/motherboard maker"),
                "why": tr(f"อุปกรณ์ {count} ตัว ({what}) ไดรเวอร์ที่ตรงรุ่นที่สุดอยู่ในเว็บซัพพอร์ตของเครื่อง หรือใน Optional updates",
                          f"{count} device(s) ({'Realtek audio/LAN' if vendor == 'realtek' else 'other'}). The best match is on your maker's support site or Optional updates"),
                "count": count,
                "links": support + [(tr("➕  เปิด Optional updates", "➕  Open Optional updates"), "ms-settings:windowsupdate-optionalupdates",
                                     tr("ไดรเวอร์เสริมจาก Windows Update", "Extra drivers from Windows Update"))],
            })
    fixes.sort(key=lambda f: -f["count"])
    return fixes


def open_gpu_driver_page(vendor):
    """เปิดหน้าโหลดไดรเวอร์การ์ดจอของค่ายนั้น ๆ"""
    if vendor in GPU_DRIVER_URLS:
        open_url(GPU_DRIVER_URLS[vendor][1])


def open_device_manager():
    """เปิด Device Manager ของ Windows"""
    open_system_tool("devmgmt.msc")


def open_windows_update():
    """เปิดหน้า Windows Update ใน Settings"""
    open_url("ms-settings:windowsupdate")


def open_optional_updates():
    """เปิดหน้า Optional updates ซึ่งมักมีไดรเวอร์จากผู้ผลิตที่ Windows ไม่ได้ลงให้อัตโนมัติ"""
    open_url("ms-settings:windowsupdate-optionalupdates")

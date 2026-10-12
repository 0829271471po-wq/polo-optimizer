"""
ai_assistant.py
ผู้ช่วย AI ที่ตอบจาก "สภาพเครื่องจริง" ไม่ใช่ตอบตามหัวข้อตายตัว
ทุกครั้งที่ผู้ใช้ถาม จะตรวจเครื่องก่อนด้วย diagnostics.collect_all() (โปรแกรมที่กินเครื่อง, ทดสอบเน็ต, ประวัติจอฟ้า ฯลฯ)
แล้วค่อยตอบด้วยวิธีใดวิธีหนึ่ง
- โหมด Gemini (มี API key + มีเน็ต): ส่งคำถาม + ผลตรวจ + บทสนทนาก่อนหน้า ให้ Google Gemini วิเคราะห์ ถามอะไรก็ได้แบบอิสระ
- โหมดออฟไลน์: หาว่าคำถามตรงกับปัญหาแบบไหน (มีราว 20 แบบ) แล้วตอบโดยใช้ผลตรวจจริงประกอบ
  ถ้าไม่ตรงแบบไหนเลย จะสรุปสิ่งผิดปกติที่ตรวจเจอในเครื่องให้แทน
  ถ้าผู้ใช้บอกว่า "ยังไม่หาย" จะเสนอวิธีขั้นต่อไปที่ลึกขึ้น

ความปลอดภัย
- AI ตอบได้แค่ข้อความ + รายชื่อ action ที่อยู่ใน ALLOWED_ACTIONS เท่านั้น action อื่นถูกตัดทิ้ง
- AI สั่งทำอะไรเองไม่ได้ ผู้ใช้ต้องกดปุ่ม "ทำเลย" เองทุกครั้ง
- ข้อมูลเครื่องออกนอกเครื่องเฉพาะตอนผู้ใช้กดส่งคำถามในโหมด Gemini
"""

import json
import re
import urllib.error
import urllib.request

import diagnostics
import installer
from i18n import tr, tx, get_language
from utils import format_size

# action ที่ AI แนะนำได้: รหัส -> ((ชื่อปุ่ม ไทย, อังกฤษ), (คำอธิบาย ไทย, อังกฤษ))
ALLOWED_ACTIONS = {
    "clean_junk": (("ล้างไฟล์ขยะ", "Clean junk files"),
                   ("ลบไฟล์ชั่วคราวและแคช (ไม่รวมถังขยะ) ไฟล์ส่วนตัวไม่ถูกแตะ",
                    "Delete temp files and caches (not the Recycle Bin). Personal files are untouched")),
    "clear_ram": (("คืน RAM", "Free up RAM"),
                  ("สั่งให้โปรแกรมปล่อย RAM ที่ไม่ได้ใช้ ผลอยู่ชั่วคราว", "Ask programs to release unused RAM (temporary effect)")),
    "game_tweaks": (("ปรับค่าเล่นเกม", "Apply gaming tweaks"),
                    ("เปิด Game Mode, ปิดเร่งความเร็วเมาส์, ปิดอัดวิดีโอเบื้องหลัง",
                     "Turn on Game Mode, turn off mouse acceleration and background recording")),
    "high_performance": (("ใช้แผนพลังงานแรงสุด", "Use max performance power plan"),
                         ("ให้ CPU ทำงานเต็มที่ โน้ตบุ๊กจะกินแบตเร็วขึ้น", "Lets the CPU run at full speed. Laptops drain battery faster")),
    "restore_point": (("สร้างจุดคืนค่า", "Create a restore point"),
                      ("เก็บสถานะเครื่องไว้ ถ้ามีปัญหาย้อนกลับได้", "Save the current state so you can roll back")),
    "repair_windows": (("ซ่อมไฟล์ระบบ", "Repair system files"),
                       ("เปิดหน้าต่างรัน DISM + SFC ใช้เวลา 15-30 นาที", "Opens a window running DISM + SFC, takes 15-30 minutes")),
    "fix_network": (("รีเซ็ตอินเทอร์เน็ต", "Reset network"),
                    ("ล้างค่าเน็ตทั้งหมด เน็ตจะหลุดสักครู่ แล้วควรรีสตาร์ทเครื่อง",
                     "Resets all network settings. Internet drops briefly, restart afterwards")),
    "restart_explorer": (("รีสตาร์ททาสก์บาร์", "Restart taskbar"),
                         ("ปิดแล้วเปิด explorer.exe ใหม่ หน้าต่างที่เปิดอยู่ไม่หาย", "Restarts explorer.exe. Open windows stay open")),
    "open_drivers": (("ไปหน้าไดรเวอร์", "Go to Drivers page"),
                     ("เปิดหน้าตรวจไดรเวอร์ในโปรแกรมนี้", "Open the driver check page in this app")),
    "open_startup": (("ไปหน้าโปรแกรมเปิดพร้อมเครื่อง", "Go to Startup apps page"),
                     ("เปิดหน้าที่ปิดโปรแกรมเปิดพร้อมเครื่องได้", "Open the page where you can turn off startup apps")),
    "open_taskmgr": (("เปิด Task Manager", "Open Task Manager"),
                     ("ดูและปิดโปรแกรมที่กินเครื่องได้เอง", "See and close programs that use a lot of resources")),
    "open_security": (("เปิด Windows Security", "Open Windows Security"),
                      ("สแกนไวรัสด้วยแอนติไวรัสของ Windows", "Scan for viruses with Windows' built-in antivirus")),
    "open_sound": (("เปิดตั้งค่าเสียง", "Open sound settings"),
                   ("เลือกลำโพง/หูฟัง/ไมค์ที่ใช้", "Choose which speaker/headphone/mic to use")),
    "restore_defaults": (("คืนค่าเริ่มต้น Windows", "Restore Windows defaults"),
                         ("คืนค่าทุกอย่างที่ Polo Optimizer เคยปรับ กลับเป็นค่าเดิมของ Windows", "Undo every setting Polo Optimizer changed, back to Windows defaults")),
    "open_system_restore": (("ย้อนกลับไปจุดคืนค่า", "Go back to a restore point"),
                            ("เปิด System Restore ให้เลือกวันที่เครื่องยังดีอยู่ ไฟล์ส่วนตัวไม่หาย", "Opens System Restore to roll back to a day the PC worked. Personal files stay")),
    "open_windows_update": (("เปิด Windows Update", "Open Windows Update"),
                            ("เช็กและลงอัปเดต/รีสตาร์ทให้อัปเดตเสร็จ", "Check for updates or restart to finish them")),
}

PRIVACY_NOTE = (
    "เมื่อกดส่งคำถามในโหมด Gemini โปรแกรมจะส่งคำถามของคุณพร้อมผลตรวจเครื่อง (สเปก, % การใช้งาน, ชื่อโปรแกรมที่กินเครื่อง, "
    "ผลทดสอบเน็ต, ประวัติจอฟ้า, ชื่ออุปกรณ์ที่มีปัญหา) ไปที่ Google Gemini เพื่อวิเคราะห์ ไม่ส่งชื่อไฟล์หรือข้อมูลส่วนตัวอื่น "
    "ถ้าไม่ใส่ API key จะใช้โหมดออฟไลน์ ไม่มีข้อมูลออกนอกเครื่องเลย",
    "In Gemini mode, your question is sent to Google Gemini together with this PC's check results (specs, usage %, "
    "names of heavy programs, network test, blue screen history, names of problem devices). No file names or other personal "
    "data are sent. Without an API key, offline mode is used and nothing leaves this PC.",
)

QUICK_QUESTIONS = [
    ("ทำไมเครื่องช้า", "Why is my PC slow?"),
    ("เล่นเกมกระตุก", "Games are stuttering"),
    ("เน็ตเข้าเว็บไม่ได้", "Websites won't load"),
    ("ทำไมจอฟ้า/ดับเอง", "Why does it blue screen?"),
    ("ตรวจเครื่องทั้งหมดให้หน่อย", "Check my whole PC"),
    ("ควรลงแอปอะไรบ้าง", "Which apps should I install?"),
]

_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def action_label(action):
    """แปลงรหัส action เป็น (ข้อความบนปุ่ม, คำอธิบาย) ตามภาษาปัจจุบัน ใช้ได้ทั้ง action ปกติและ install:<id>"""
    if action.startswith("install:"):
        app = installer.find_app(action.split(":", 1)[1])
        name = app["name"] if app else action.split(":", 1)[1]
        return tr(f"ติดตั้ง {name}", f"Install {name}"), tr("ติดตั้งผ่าน winget จากแหล่งทางการ", "Installs via winget from the official source")
    if action in ALLOWED_ACTIONS:
        name, desc = ALLOWED_ACTIONS[action]
        return tx(name), tx(desc)
    return action, ""


def validate_actions(actions):
    """กรอง action ที่ได้มา เหลือเฉพาะที่อยู่ในรายการอนุญาต (กันกรณี AI แต่งคำสั่งขึ้นมาเอง)
    install:<id> ต้องเป็นแอปที่อยู่ในหน้าติดตั้งแอปเท่านั้น ตัดตัวซ้ำ และจำกัดไม่เกิน 5 ปุ่ม"""
    if not isinstance(actions, list):
        return []
    allowed_apps = installer.allowed_ids()
    result = []
    for a in actions:
        if not isinstance(a, str):
            continue
        a = a.strip()
        ok = a in ALLOWED_ACTIONS or (a.startswith("install:") and a.split(":", 1)[1] in allowed_apps)
        if ok and a not in result:
            result.append(a)
    return result[:5]


def collect_context():
    """ตรวจเครื่องทั้งหมด (ใช้เวลา 3-8 วินาที ต้องเรียกจาก thread แยก) และเติมค่าที่หน้าแรกใช้คิดคะแนนสุขภาพ"""
    ctx = diagnostics.collect_all()
    usage = ctx.get("usage") or {}
    ctx["usage_simple"] = {"cpu_percent": usage.get("cpu", 0), "ram_percent": usage.get("ram", 0),
                           "disk_percent": usage.get("disk", 0), "disk_free": format_size(usage.get("disk_free", 0))}
    ctx["junk_bytes"] = ctx.get("junk") or 0
    return ctx


# ================================================================
# สิ่งผิดปกติที่ตรวจเจอ (ใช้ทั้งโหมดออฟไลน์และสรุปให้ Gemini)
# ================================================================

def findings(ctx):
    """แปลงผลตรวจเป็นรายการ "สิ่งที่ผิดปกติ" เรียงจากหนักไปเบา
    แต่ละอันคือ dict {key, level (3=หนัก 2=กลาง 1=เบา), text, actions}"""
    out = []

    def add(key, level, text, actions=()):
        out.append({"key": key, "level": level, "text": text, "actions": list(actions)})

    for d in ctx.get("disk_health") or []:
        if not d.get("healthy"):
            add("disk_bad", 3, tr(f"ดิสก์ {d['name']} สถานะ \"{d['health']}\" อาจเสียเร็ว ๆ นี้ ควรสำรองไฟล์สำคัญทันที",
                                  f"Disk {d['name']} reports \"{d['health']}\". It may fail soon, back up important files now"))

    crashes = ctx.get("crashes") or {}
    if crashes.get("bsod"):
        code = crashes.get("bsod_code", "")
        cause = tx(diagnostics.BUGCHECKS[code]) if code in diagnostics.BUGCHECKS else ""
        add("bsod", 3, tr(
            f"จอฟ้า {crashes['bsod']} ครั้งใน 14 วัน (ล่าสุด {crashes['bsod_last']}"
            + (f", รหัส {code}" if code else "") + ")" + (f" มักเกิดจาก{cause}" if cause else ""),
            f"{crashes['bsod']} blue screen(s) in 14 days (latest {crashes['bsod_last']}"
            + (f", code {code}" if code else "") + ")" + (f", usually caused by {cause}" if cause else "")),
            ["open_drivers", "repair_windows"])
    extra_power = (crashes.get("power_loss") or 0) - (crashes.get("bsod") or 0)
    if extra_power > 0:
        add("power_loss", 2, tr(f"เครื่องดับ/รีสตาร์ทแบบไม่ปกติ {extra_power} ครั้งใน 14 วัน (ไม่ใช่จอฟ้า) อาจเป็นเรื่องไฟ, ความร้อน หรือกดปิดค้าง",
                                f"{extra_power} unexpected shutdown(s) in 14 days (not blue screens). Possible power, heat or forced power-off"))
    if crashes.get("app_crashes"):
        names = ", ".join(f"{n} ({c})" for n, c in crashes["app_crashes"][:3])
        add("app_crash", 1, tr(f"โปรแกรมที่แครชใน 7 วันนี้: {names}", f"Programs that crashed in the last 7 days: {names}"))

    for g in ctx.get("gpus") or []:
        if g.get("no_driver"):
            add("gpu_driver", 3, tr("การ์ดจอยังไม่มีไดรเวอร์ (Microsoft Basic Display Adapter) ภาพจะช้าและเล่นเกมไม่ได้",
                                    "The graphics card has no driver (Microsoft Basic Display Adapter). Graphics will be slow and games won't run"),
                ["open_drivers"])

    usage = ctx.get("usage") or {}
    if usage.get("disk", 0) > 90:
        add("disk_full", 3, tr(f"ไดรฟ์ Windows เต็ม {usage['disk']:.0f}% (เหลือ {format_size(usage.get('disk_free'))}) เครื่องจะช้าและอัปเดตไม่ได้",
                               f"Windows drive is {usage['disk']:.0f}% full ({format_size(usage.get('disk_free'))} free). This slows the PC and blocks updates"),
            ["clean_junk"])
    elif usage.get("disk", 0) > 80:
        add("disk_full", 1, tr(f"ไดรฟ์ Windows ใช้ไป {usage['disk']:.0f}% แล้ว", f"Windows drive is {usage['disk']:.0f}% full"), ["clean_junk"])
    if usage.get("ram", 0) > 85:
        add("ram_high", 2, tr(f"RAM ใช้ไป {usage['ram']:.0f}% เกือบเต็ม", f"RAM is {usage['ram']:.0f}% used, almost full"), ["clear_ram", "open_taskmgr"])

    top = ctx.get("top") or {}
    for name, cpu in top.get("cpu", [])[:2]:
        if cpu >= 30:
            add("cpu_hog", 2, tr(f"{name} กิน CPU {cpu:.0f}% อยู่ตอนนี้ ถ้าไม่ได้ใช้อยู่ ปิดได้ใน Task Manager",
                                 f"{name} is using {cpu:.0f}% CPU right now. If you're not using it, close it in Task Manager"),
                ["open_taskmgr"])
    total_ram = usage.get("ram_total") or 1
    for name, used in top.get("ram", [])[:2]:
        if used > 2 * 1024 ** 3 or used / total_ram > 0.25:
            add("ram_hog", 1, tr(f"{name} ใช้ RAM {format_size(used)}", f"{name} is using {format_size(used)} of RAM"), ["open_taskmgr"])

    net = ctx.get("network") or {}
    verdict = net.get("verdict")
    if verdict and verdict not in ("ok", "high_ping"):
        add("network", 3, network_explain(net), ["fix_network"])
    elif verdict == "high_ping":
        add("network", 1, network_explain(net))

    devices = ctx.get("problem_devices") or []
    if devices:
        missing = sum(1 for d in devices if d.get("missing_driver"))
        add("devices", 2 if missing else 1, tr(
            f"มีอุปกรณ์ที่มีปัญหา {len(devices)} ตัว" + (f" (ยังไม่มีไดรเวอร์ {missing} ตัว)" if missing else ""),
            f"{len(devices)} device(s) have problems" + (f" ({missing} without drivers)" if missing else "")), ["open_drivers"])

    if (ctx.get("uptime_days") or 0) >= 7:
        add("uptime", 1, tr(f"ไม่ได้รีสตาร์ทมา {ctx['uptime_days']:.0f} วันแล้ว ลองกด Restart (ไม่ใช่ Shut down) สักครั้ง",
                            f"No restart for {ctx['uptime_days']:.0f} days. Try Restart (not Shut down) once"))
    if ctx.get("pending_reboot"):
        add("reboot", 1, tr("มีอัปเดต Windows ที่รอรีสตาร์ทอยู่", "A Windows update is waiting for a restart"), ["open_windows_update"])
    if (ctx.get("startup_count") or 0) > 8:
        add("startup", 1, tr(f"มีโปรแกรมเปิดพร้อมเครื่อง {ctx['startup_count']} ตัว ทำให้บูตช้า",
                             f"{ctx['startup_count']} programs start with Windows, slowing boot"), ["open_startup"])
    if (ctx.get("junk") or 0) > 1024 ** 3:
        add("junk", 1, tr(f"มีไฟล์ขยะ {ctx['junk_size']} ที่ลบได้", f"{ctx['junk_size']} of junk files can be deleted"), ["clean_junk"])
    battery = ctx.get("battery")
    if battery and not battery["plugged"] and battery["percent"] < 25:
        add("battery", 1, tr(f"แบตเหลือ {battery['percent']}% และไม่ได้เสียบสาย เครื่องจะลดความแรงลงเพื่อประหยัดแบต",
                             f"Battery at {battery['percent']}% and unplugged. Windows slows the PC to save power"))
    out.sort(key=lambda f: -f["level"])
    return out


def network_explain(net):
    """อธิบายผลทดสอบเน็ตเป็นภาษาคน ว่าเสียตรงไหน"""
    verdict = net.get("verdict")
    if verdict == "no_connection":
        return tr("เครื่องไม่ได้เชื่อมต่อเน็ตเลย (ไม่มี Wi-Fi/สายแลนที่ได้ IP)", "This PC isn't connected (no Wi-Fi/Ethernet with an IP address)")
    if verdict == "router":
        return tr(f"ต่อเราเตอร์ ({net.get('gateway')}) ไม่ติด ปัญหาอยู่ระหว่างเครื่องกับเราเตอร์ (Wi-Fi อ่อน/สายหลุด/เราเตอร์ค้าง)",
                  f"Can't reach the router ({net.get('gateway')}). The problem is between this PC and the router (weak Wi-Fi, loose cable, frozen router)")
    if verdict == "isp":
        return tr("ต่อเราเตอร์ได้ แต่ออกเน็ตไม่ได้ น่าจะเป็นที่เน็ตบ้านหรือเราเตอร์ ไม่ใช่ที่เครื่องนี้",
                  "The router responds but there's no internet. Likely your home internet or router, not this PC")
    if verdict == "dns":
        return tr("ออกเน็ตได้ แต่แปลงชื่อเว็บไม่ได้ (DNS มีปัญหา) เลยเข้าเว็บไม่ได้ รีเซ็ตเน็ตมักแก้ได้",
                  "Internet works but website names can't be resolved (DNS problem). A network reset usually fixes it")
    if verdict == "high_ping":
        return tr(f"เน็ตใช้ได้ แต่ปิงสูง {net.get('ping_ms')} ms (ปกติควรต่ำกว่า 50) อาจมีคนในบ้านโหลดของหนัก ๆ หรือใช้ Wi-Fi ไกลเราเตอร์",
                  f"Internet works but ping is high: {net.get('ping_ms')} ms (should be under 50). Someone may be downloading, or Wi-Fi is far from the router")
    return tr(f"ทดสอบเน็ตแล้วปกติ (ปิง {net.get('ping_ms')} ms, DNS ใช้ได้)", f"Network test passed (ping {net.get('ping_ms')} ms, DNS works)")


# ================================================================
# โหมดออฟไลน์: หัวข้อปัญหา
# ================================================================
# แต่ละหัวข้อมี
#   kw       = คำที่ใช้จับ (ไทย+อังกฤษ)
#   related  = finding ที่เกี่ยวข้อง (จะยกผลตรวจพวกนี้ขึ้นมาตอบ)
#   steps    = วิธีแก้แต่ละระดับ [(ข้อความ ไทย, อังกฤษ, actions)] ถ้าผู้ใช้บอกว่ายังไม่หาย จะขยับไปขั้นต่อไป
#   suggest  = คำถามต่อที่แนะนำให้กด

TOPICS = [
    {
        "id": "slow",
        "kw": ["ช้า", "อืด", "หน่วง", "ค้าง", "แฮงค์", "แฮง", "โหลดนาน", "ไม่ลื่น", "slow", "freeze", "hang", "laggy"],
        "related": ["cpu_hog", "ram_hog", "ram_high", "disk_full", "junk", "startup", "uptime", "disk_bad", "battery"],
        "steps": [
            ("ลองตามนี้ก่อน: ปิดโปรแกรมที่กินเครื่องที่เห็นด้านบน, ล้างไฟล์ขยะ, และปิดโปรแกรมเปิดพร้อมเครื่องที่ไม่ได้ใช้ทุกวัน",
             "Try this first: close the heavy programs listed above, clean junk files, and turn off startup apps you don't use daily",
             ["clean_junk", "open_taskmgr", "open_startup"]),
            ("ถ้ายังช้า: รีสตาร์ทเครื่อง 1 ครั้ง (ไม่ใช่ Shut down), สแกนไวรัสด้วย Windows Security และซ่อมไฟล์ระบบ",
             "Still slow? Restart once (not Shut down), scan for viruses with Windows Security, and repair system files",
             ["open_security", "repair_windows"]),
            ("ถ้ายังไม่ดีขึ้นอีก มักเป็นที่ฮาร์ดแวร์: ถ้าเครื่องใช้ HDD การเปลี่ยนเป็น SSD ช่วยได้มากที่สุด และถ้า RAM ต่ำกว่า 8 GB ควรเพิ่ม RAM",
             "If it's still slow, it's usually hardware: switching an HDD to an SSD helps the most, and add RAM if you have less than 8 GB",
             []),
        ],
        "suggest": [("เปิดเครื่องนานมาก", "Boot takes forever"), ("โปรแกรมไหนกินเครื่อง", "Which program is heavy?")],
    },
    {
        "id": "boot",
        "kw": ["เปิดเครื่องนาน", "บูต", "บูท", "boot", "startup slow", "เปิดเครื่องช้า"],
        "related": ["startup", "disk_bad", "disk_full", "reboot"],
        "steps": [
            ("เปิดเครื่องนานส่วนใหญ่มาจากโปรแกรมเปิดพร้อมเครื่องเยอะ ลองปิดตัวที่ไม่ได้ใช้ทุกวัน (เช่น Steam, Discord, Spotify)",
             "Slow boot is usually caused by too many startup apps. Turn off ones you don't use daily (e.g. Steam, Discord, Spotify)",
             ["open_startup"]),
            ("ถ้ายังนาน: ลงอัปเดต Windows ที่ค้างให้เสร็จ แล้วซ่อมไฟล์ระบบ",
             "Still slow? Finish pending Windows updates, then repair system files", ["open_windows_update", "repair_windows"]),
            ("ถ้ายังนานเกิน 2 นาที และเครื่องใช้ HDD การเปลี่ยนเป็น SSD จะเห็นผลชัดที่สุด",
             "If boot still takes over 2 minutes and you have an HDD, upgrading to an SSD makes the biggest difference", []),
        ],
        "suggest": [("ปิดโปรแกรมตัวไหนได้บ้าง", "Which startup apps can I disable?")],
    },
    {
        "id": "game",
        "kw": ["กระตุก", "เกม", "fps", "เฟรม", "game", "stutter", "drop"],
        "related": ["gpu_driver", "cpu_hog", "ram_high", "ram_hog", "battery", "bsod"],
        "steps": [
            ("ลองตามนี้: ปรับค่าเล่นเกม, ใช้แผนพลังงานแรงสุด, ปิดโปรแกรมที่กินเครื่องระหว่างเล่น และอัปเดตไดรเวอร์การ์ดจอจากเว็บผู้ผลิต",
             "Try this: apply gaming tweaks, use the max performance power plan, close heavy programs while playing, and update your GPU driver from the vendor site",
             ["game_tweaks", "high_performance", "open_drivers"]),
            ("ถ้ายังกระตุก: ล้างแคช shader (หน้าล้างเครื่อง > D3DSCache และแคช NVIDIA) แล้วลดกราฟิกในเกมลง 1 ระดับ ถ้าเป็นโน้ตบุ๊กต้องเสียบสายชาร์จตอนเล่น",
             "Still stuttering? Clear the shader caches (Clean page > D3DSCache and NVIDIA cache), then lower in-game graphics one step. On a laptop, keep the charger plugged in",
             ["clean_junk"]),
            ("ถ้ายังไม่ดีขึ้น อาจเป็นเพราะความร้อน: เครื่องร้อนจัดจะลดความเร็วตัวเอง ลองทำความสะอาดฝุ่น/เปลี่ยนซิลิโคน หรือให้ร้านตรวจ",
             "If it still stutters, heat may be the cause: hot PCs throttle themselves. Clean the dust/replace thermal paste or have a shop check it",
             []),
        ],
        "suggest": [("ปิงสูง เล่นเกมแลค", "High ping in games"), ("เครื่องร้อนมาก", "PC gets very hot")],
    },
    {
        "id": "network",
        "kw": ["เน็ต", "อินเทอร์เน็ต", "อินเตอร์เน็ต", "เว็บ", "wifi", "wi-fi", "ไวไฟ", "internet", "เชื่อมต่อ", "หลุด", "network", "dns",
               "เฟสบุ๊ค", "เฟซบุ๊ก", "เฟส", "facebook", "ยูทูป", "ยูทูบ", "youtube", "google", "กูเกิล", "tiktok", "ติ๊กต็อก",
               "โหลดไม่ขึ้น", "เข้าไม่ได้", "ไม่ขึ้น", "website", "browser", "เบราว์เซอร์", "สายแลน", "lan", "router", "เราเตอร์"],
        "related": ["network"],
        "steps": [
            ("ถ้าปัญหาอยู่ที่เครื่องนี้ กด 'รีเซ็ตอินเทอร์เน็ต' (เน็ตจะหลุดสักครู่) แล้วรีสตาร์ทเครื่อง ถ้าเครื่องอื่นในบ้านก็ใช้ไม่ได้ ให้ปิดเปิดเราเตอร์ใหม่ (ถอดปลั๊กรอ 30 วินาที)",
             "If the problem is this PC, press 'Reset network' (internet drops briefly) and restart. If other devices also have no internet, power-cycle the router (unplug for 30 seconds)",
             ["fix_network"]),
            ("ถ้ายังไม่ได้: อัปเดตไดรเวอร์การ์ดเน็ต/Wi-Fi จากเว็บยี่ห้อเครื่องหรือเมนบอร์ด และลองต่อสายแลนตรงเพื่อเช็กว่าเป็นที่ Wi-Fi ไหม",
             "Still not working? Update the network/Wi-Fi driver from your PC or motherboard maker, and try an Ethernet cable to see if Wi-Fi is the problem",
             ["open_drivers"]),
            ("ถ้าทุกเครื่องในบ้านใช้ไม่ได้และปิดเปิดเราเตอร์แล้ว ให้โทรแจ้งผู้ให้บริการเน็ต",
             "If no device at home has internet even after restarting the router, call your internet provider", []),
        ],
        "suggest": [("ปิงสูง เล่นเกมแลค", "High ping in games"), ("Wi-Fi หลุดบ่อย", "Wi-Fi keeps disconnecting")],
    },
    {
        "id": "ping",
        "kw": ["ปิง", "แลค", "ping", "lag", "ดีเลย์", "delay", "latency"],
        "related": ["network"],
        "steps": [
            ("ปิงสูงส่วนใหญ่มาจาก Wi-Fi (ไกลเราเตอร์/มีกำแพงกั้น) หรือมีคนโหลดของหนัก ๆ ในบ้าน ถ้าทำได้ ใช้สายแลนเล่นเกมจะนิ่งที่สุด และปิดโปรแกรมที่โหลดไฟล์อยู่เบื้องหลัง (Steam, Google Drive)",
             "High ping usually comes from Wi-Fi (far from the router/walls) or someone downloading at home. Use Ethernet for games if possible and pause background downloads (Steam, Google Drive)",
             ["open_taskmgr"]),
            ("ถ้ายังแลค: ลองรีเซ็ตอินเทอร์เน็ต และเลือกเซิร์ฟเวอร์เกมที่ใกล้ที่สุด (เช่น SEA/Singapore)",
             "Still lagging? Try a network reset and pick the closest game server (e.g. SEA/Singapore)", ["fix_network"]),
        ],
        "suggest": [("เน็ตหลุดบ่อย", "Internet keeps dropping")],
    },
    {
        "id": "bsod",
        "kw": ["จอฟ้า", "bluescreen", "blue screen", "bsod", "ดับเอง", "รีสตาร์ทเอง", "restart เอง", "ปิดเอง", "crash", "แครช"],
        "related": ["bsod", "power_loss", "gpu_driver", "devices", "disk_bad"],
        "steps": [
            ("ส่วนใหญ่จอฟ้าเกิดจากไดรเวอร์ ให้อัปเดตไดรเวอร์การ์ดจอและชิปเซ็ตจากเว็บผู้ผลิต สร้างจุดคืนค่าไว้ก่อน แล้วซ่อมไฟล์ระบบ",
             "Blue screens are usually caused by drivers. Update GPU and chipset drivers from the vendor site, create a restore point first, then repair system files",
             ["open_drivers", "restore_point", "repair_windows"]),
            ("ถ้ายังเป็น: ตรวจ RAM ด้วย Windows Memory Diagnostic (กด Win แล้วพิมพ์ mdsched) ถ้าเพิ่งโอเวอร์คล็อกหรือเปิด XMP/EXPO ให้ลองปิดก่อน",
             "Still happening? Test RAM with Windows Memory Diagnostic (press Win and type mdsched). If you overclocked or enabled XMP/EXPO, try turning it off",
             []),
            ("ถ้ายังจอฟ้าอีก อาจเป็นฮาร์ดแวร์ (RAM, พาวเวอร์ซัพพลาย, ความร้อน) ควรให้ร้านตรวจ หรือใช้ Reset this PC แบบเก็บไฟล์ไว้",
             "If it keeps happening, it may be hardware (RAM, power supply, heat). Have a shop check it, or use Reset this PC and keep your files",
             []),
        ],
        "suggest": [("โปรแกรมเด้งออกเอง", "Programs close by themselves"), ("เครื่องร้อนมาก", "PC gets very hot")],
    },
    {
        "id": "app_crash",
        "kw": ["เด้งออก", "เด้ง", "ไม่ตอบสนอง", "not responding", "ปิดตัวเอง", "เปิดไม่ขึ้น", "เปิดไม่ได้", "error", "dll"],
        "related": ["app_crash", "ram_high", "disk_full"],
        "steps": [
            ("ลองลงไลบรารีที่โปรแกรม/เกมต้องใช้ (Visual C++, DirectX, .NET) ส่วนใหญ่โปรแกรมที่เด้งหรือขึ้น error .dll จะหายหลังลงตัวพวกนี้",
             "Install the runtime libraries programs/games need (Visual C++, DirectX, .NET). Most crashes and .dll errors go away after this",
             ["install:Microsoft.VCRedist.2015+.x64", "install:Microsoft.VCRedist.2015+.x86", "install:Microsoft.DirectX"]),
            ("ถ้ายังเด้ง: อัปเดตโปรแกรมนั้นเป็นเวอร์ชันล่าสุด หรือลบแล้วลงใหม่ และซ่อมไฟล์ระบบ",
             "Still crashing? Update that program or reinstall it, and repair system files", ["repair_windows"]),
        ],
        "suggest": [("ทำไมจอฟ้า", "Why do I get blue screens?")],
    },
    {
        "id": "sound",
        "kw": ["เสียง", "ลำโพง", "หูฟัง", "ไมค์", "sound", "audio", "speaker", "headphone", "mic"],
        "related": ["devices"],
        "steps": [
            ("คลิกไอคอนลำโพงมุมขวาล่าง แล้วเช็กว่าเลือกอุปกรณ์เสียงถูกตัว (ลำโพง/หูฟัง) และไม่ได้ปิดเสียงไว้ ถ้าเป็นไมค์ ให้เช็กสิทธิ์ไมค์ใน Settings > Privacy",
             "Click the speaker icon at the bottom right and check the right output device is selected and not muted. For a mic, check Settings > Privacy > Microphone",
             ["open_sound"]),
            ("ถ้ายังไม่มีเสียง: ลงไดรเวอร์เสียง (Realtek ฯลฯ) จากเว็บยี่ห้อเครื่องหรือเมนบอร์ด แล้วรีสตาร์ท",
             "Still no sound? Install the audio driver (Realtek, etc.) from your PC or motherboard maker, then restart", ["open_drivers"]),
            ("ถ้ายังไม่หาย ลองเสียบหูฟังอีกช่อง/อีกเครื่อง เพื่อดูว่าเสียที่ลำโพงหรือที่เครื่อง",
             "If it still fails, try another jack or device to see if the speaker or the PC is at fault", []),
        ],
        "suggest": [("ไมค์ไม่ติด", "Microphone not working")],
    },
    {
        "id": "display",
        "kw": ["จอ", "ภาพ", "การ์ดจอ", "ความละเอียด", "กระพริบ", "จอดำ", "display", "screen", "resolution", "monitor", "gpu"],
        "related": ["gpu_driver", "bsod"],
        "steps": [
            ("ปัญหาจอกระพริบ ภาพแตก หรือความละเอียดเพี้ยน ส่วนใหญ่แก้ได้ด้วยการลงไดรเวอร์การ์ดจอล่าสุดจากเว็บผู้ผลิต",
             "Flickering, artifacts or wrong resolution are usually fixed by installing the latest GPU driver from the vendor site",
             ["open_drivers"]),
            ("ถ้ายังเป็น: เช็กสายจอว่าเสียบแน่น ลองเปลี่ยนสาย/ช่อง และถ้าเป็น PC ให้เสียบสายจอที่การ์ดจอ ไม่ใช่ที่เมนบอร์ด",
             "Still happening? Check the cable is firmly connected, try another cable/port, and on a desktop plug the monitor into the graphics card, not the motherboard",
             []),
        ],
        "suggest": [("เล่นเกมกระตุก", "Games stutter")],
    },
    {
        "id": "storage",
        "kw": ["เต็ม", "พื้นที่", "ไดรฟ์ c", "ไดร์ฟ", "ความจุ", "storage", "disk full", "space"],
        "related": ["disk_full", "junk", "disk_bad"],
        "steps": [
            ("ล้างไฟล์ขยะก่อน แล้วลองล้างถังขยะ (หน้าล้างเครื่อง) จากนั้นดูใน Settings > System > Storage ว่าโฟลเดอร์ไหนใหญ่สุด เช่น Downloads หรือเกมที่ไม่ได้เล่นแล้ว",
             "Clean junk files first, then empty the Recycle Bin (Clean page). Then check Settings > System > Storage to see what's largest, e.g. Downloads or games you no longer play",
             ["clean_junk"]),
            ("ถ้ายังเต็ม: ย้ายรูป/วิดีโอไปไว้ไดรฟ์อื่นหรือ Google Drive และลบแอปที่ไม่ได้ใช้ใน Settings > Apps",
             "Still full? Move photos/videos to another drive or Google Drive, and uninstall unused apps in Settings > Apps", []),
        ],
        "suggest": [("ทำไมเครื่องช้า", "Why is my PC slow?")],
    },
    {
        "id": "ram",
        "kw": ["แรม", "ram", "memory", "หน่วยความจำ"],
        "related": ["ram_high", "ram_hog"],
        "steps": [
            ("ดูรายชื่อโปรแกรมที่ใช้ RAM เยอะด้านบน ปิดตัวที่ไม่ได้ใช้ (เบราว์เซอร์ที่เปิดแท็บเยอะกิน RAM มาก) แล้วลองคืน RAM",
             "Check the RAM-heavy programs above and close what you don't need (browsers with many tabs use a lot), then free up RAM",
             ["clear_ram", "open_taskmgr"]),
            ("ถ้า RAM เต็มบ่อยเป็นปกติ แปลว่า RAM ไม่พอกับงาน ควรเพิ่ม RAM (เกมสมัยนี้ควรมี 16 GB)",
             "If RAM is always full, you need more RAM for your workload (16 GB is recommended for modern games)", []),
        ],
        "suggest": [("ทำไมเครื่องช้า", "Why is my PC slow?")],
    },
    {
        "id": "heat",
        "kw": ["ร้อน", "พัดลม", "ดัง", "hot", "heat", "fan", "overheat", "temperature", "อุณหภูมิ"],
        "related": ["cpu_hog", "power_loss"],
        "steps": [
            ("เครื่องร้อนหรือพัดลมดังตลอดมักเพราะมีโปรแกรมกิน CPU อยู่เบื้องหลัง (ดูด้านบน) ถ้าไม่มี ให้ทำความสะอาดฝุ่นที่ช่องระบายลม และอย่าวางโน้ตบุ๊กบนที่นอน/หมอน",
             "A hot PC or loud fans usually means a program is using CPU in the background (see above). If not, clean dust from the vents and don't put a laptop on a bed or pillow",
             ["open_taskmgr"]),
            ("ถ้ายังร้อน: ซิลิโคนระบายความร้อนอาจแห้งแล้ว (มักเป็นเครื่องที่ใช้มาเกิน 2-3 ปี) ควรให้ร้านเปลี่ยนให้",
             "Still hot? The thermal paste may have dried out (common after 2-3 years). Have a shop replace it", []),
        ],
        "suggest": [("เล่นเกมกระตุก", "Games stutter")],
    },
    {
        "id": "battery",
        "kw": ["แบต", "battery", "ชาร์จ", "charge"],
        "related": ["battery", "cpu_hog"],
        "steps": [
            ("แบตหมดไวมักเพราะความสว่างจอสูง, แผนพลังงานแบบแรง และโปรแกรมเบื้องหลัง ลองลดความสว่าง เปิด Battery saver และปิดโปรแกรมที่ไม่ใช้",
             "Fast battery drain usually comes from high brightness, a performance power plan and background apps. Lower brightness, turn on Battery saver and close unused programs",
             ["open_taskmgr", "open_startup"]),
            ("ถ้าแบตเก็บไฟได้น้อยลงมากเทียบกับตอนซื้อ แบตอาจเสื่อม (ใช้มานานหลายปี) ควรเปลี่ยนแบตที่ศูนย์",
             "If battery capacity dropped a lot compared to when new, the battery may be worn out. Replace it at a service center", []),
        ],
        "suggest": [("เครื่องร้อนมาก", "PC gets very hot")],
    },
    {
        "id": "taskbar",
        "kw": ["ทาสก์บาร์", "ทาสบาร์", "taskbar", "start menu", "เมนูเริ่ม", "ปุ่ม start", "ไอคอนหาย", "explorer"],
        "related": [],
        "steps": [
            ("กด 'รีสตาร์ททาสก์บาร์' ได้เลย หน้าต่างที่เปิดอยู่จะไม่หาย", "Press 'Restart taskbar'. Your open windows stay open",
             ["restart_explorer"]),
            ("ถ้ายังค้างบ่อย: ซ่อมไฟล์ระบบ แล้วรีสตาร์ทเครื่อง", "Still freezing often? Repair system files, then restart", ["repair_windows"]),
        ],
        "suggest": [],
    },
    {
        "id": "update",
        "kw": ["อัปเดต", "อัพเดท", "อัพเดต", "update"],
        "related": ["reboot", "disk_full"],
        "steps": [
            ("ถ้าอัปเดตค้างหรือไม่ผ่าน: เช็กว่าไดรฟ์ C เหลือที่อย่างน้อย 20 GB, รีสตาร์ทเครื่อง แล้วลองอัปเดตใหม่",
             "If updates hang or fail: make sure drive C has at least 20 GB free, restart, then try again", ["open_windows_update", "clean_junk"]),
            ("ถ้ายังไม่ผ่าน: ซ่อมไฟล์ระบบ (DISM + SFC) แล้วลองอีกครั้ง", "Still failing? Repair system files (DISM + SFC) and try again", ["repair_windows"]),
        ],
        "suggest": [],
    },
    {
        "id": "virus",
        "kw": ["ไวรัส", "virus", "มัลแวร์", "malware", "โฆษณาเด้ง", "ป๊อปอัพ", "popup", "pop-up", "hack", "แฮก"],
        "related": ["cpu_hog"],
        "steps": [
            ("เปิด Windows Security แล้วสแกนแบบ Full scan ถ้ามีโฆษณาเด้งในเบราว์เซอร์ ให้ลบส่วนขยาย (extension) แปลก ๆ และปิดการแจ้งเตือนจากเว็บที่ไม่รู้จัก",
             "Open Windows Security and run a Full scan. For browser pop-ups, remove unknown extensions and block notifications from unknown sites",
             ["open_security"]),
            ("ถ้ายังมีอาการ: สแกนแบบ Microsoft Defender Offline scan (เครื่องจะรีสตาร์ทไปสแกน) และเปลี่ยนรหัสผ่านอีเมล/โซเชียลจากเครื่องอื่น",
             "Still suspicious? Run a Microsoft Defender Offline scan (it restarts to scan) and change your email/social passwords from another device",
             ["open_security"]),
        ],
        "suggest": [],
    },
    {
        "id": "devices",
        "kw": ["usb", "ปริ้น", "printer", "พริ้น", "เมาส์", "คีย์บอร์ด", "keyboard", "mouse", "bluetooth", "บลูทูธ", "ไดรเวอร์", "driver", "อุปกรณ์"],
        "related": ["devices", "gpu_driver"],
        "steps": [
            ("ลองถอดแล้วเสียบอุปกรณ์ใหม่อีกช่อง ถ้ายังไม่ได้ ไปหน้าไดรเวอร์ดูว่าอุปกรณ์นั้นขึ้นว่ามีปัญหาไหม แล้วลงไดรเวอร์จากเว็บผู้ผลิต",
             "Unplug and reconnect the device to another port. If it still fails, check the Drivers page for problems and install the driver from the maker's site",
             ["open_drivers"]),
            ("ถ้ายังไม่ได้: ดูใน Windows Update > Optional updates มักมีไดรเวอร์อุปกรณ์ให้ลง",
             "Still not working? Check Windows Update > Optional updates, it often has device drivers", ["open_windows_update"]),
        ],
        "suggest": [],
    },
    {
        "id": "broken",
        "kw": ["วินพัง", "วินโดว์พัง", "วินโดพัง", "windows พัง", "ระบบพัง", "ไฟล์เสีย", "ไฟล์ระบบ", "corrupt", "broken", "repair", "ซ่อม",
               "รีเซ็ตวิน", "รีเซ็ตเครื่อง", "reset pc", "reset windows", "ค่าเดิม", "ค่าเริ่มต้น", "default", "ย้อนกลับ", "restore", "คืนค่า"],
        "related": ["bsod", "disk_bad", "reboot"],
        "steps": [
            ("สร้างจุดคืนค่าไว้ก่อน แล้วกดซ่อมไฟล์ระบบ (DISM + SFC) ใช้เวลา 15-30 นาที เสร็จแล้วรีสตาร์ท",
             "Create a restore point first, then repair system files (DISM + SFC). Takes 15-30 minutes, restart when done",
             ["restore_point", "repair_windows"]),
            ("ถ้ายังมีปัญหา: ถ้าเริ่มเป็นหลังปรับเครื่องด้วยโปรแกรมนี้ กด 'คืนค่าเริ่มต้น Windows' หรือย้อนกลับไปจุดคืนค่าวันที่เครื่องยังดีอยู่ (ไฟล์ส่วนตัวไม่หาย)",
             "Still broken? If it started after tuning with this app, press 'Restore Windows defaults', or roll back to a restore point from a day the PC worked (personal files stay)",
             ["restore_defaults", "open_system_restore"]),
            ("ทางสุดท้าย: Settings > System > Recovery > Reset this PC เลือก 'Keep my files' จะลง Windows ใหม่แต่เก็บไฟล์ส่วนตัวไว้ (แอปต้องลงใหม่)",
             "Last resort: Settings > System > Recovery > Reset this PC, choose 'Keep my files'. Windows is reinstalled but personal files are kept (apps must be reinstalled)",
             []),
        ],
        "suggest": [("ทำไมจอฟ้า", "Why do I get blue screens?")],
    },
    {
        "id": "apps",
        "kw": ["ลงแอป", "แอปอะไร", "โปรแกรมอะไร", "ควรลง", "แนะนำแอป", "recommend app", "which app", "install"],
        "related": [],
        "steps": [
            ("แนะนำให้ลงหมวด 'จำเป็น' ก่อน (Visual C++, DirectX, .NET) เพราะเกมและโปรแกรมส่วนใหญ่ต้องใช้ จากนั้นค่อยลงแอปที่ใช้จริง เช่น Chrome, LINE, 7-Zip",
             "Install the 'Essentials' first (Visual C++, DirectX, .NET) since most games and programs need them. Then add what you actually use, like Chrome, LINE and 7-Zip",
             ["install:Microsoft.VCRedist.2015+.x64", "install:Microsoft.DirectX", "install:Google.Chrome", "install:7zip.7zip"]),
        ],
        "suggest": [],
    },
    {
        "id": "checkup",
        "kw": ["ตรวจเครื่อง", "ตรวจทั้งหมด", "สุขภาพ", "เช็กเครื่อง", "เช็คเครื่อง", "check", "scan", "health", "ปกติไหม", "มีปัญหาอะไร"],
        "related": "*",
        "steps": [
            ("ผมเรียงจากเรื่องที่หนักที่สุดไว้ด้านบนแล้ว กดปุ่มด้านล่างแก้ทีละข้อได้เลย", "Most serious issues are listed first. Use the buttons below to fix them one by one", []),
        ],
        "suggest": [("ทำไมเครื่องช้า", "Why is my PC slow?")],
    },
]

# คำที่แปลว่าผู้ใช้ลองแล้วแต่ยังไม่หาย (ให้ขยับไปวิธีขั้นต่อไปของหัวข้อเดิม)
_FOLLOWUP = ["ยังไม่หาย", "ไม่หาย", "ยังเป็น", "ยังไม่ได้", "ไม่ได้ผล", "ทำแล้ว", "ลองแล้ว", "เหมือนเดิม", "ยังช้า", "ยังกระตุก",
             "ยังค้าง", "ยังแลค", "still", "didn't work", "not fixed", "same problem", "again"]


def _match_topics(question):
    """ให้คะแนนแต่ละหัวข้อจากคำที่เจอในคำถาม (คำยาวได้คะแนนมากกว่า เพราะเจาะจงกว่า) คืนหัวข้อเรียงตามคะแนน"""
    q = question.lower()
    scored = []
    for topic in TOPICS:
        score = sum(len(k) for k in topic["kw"] if k in q)
        if score:
            scored.append((score, topic))
    # "จอฟ้า" มีคำว่า "จอ" อยู่ด้วย ถ้าตรงหัวข้อจอฟ้าแล้วไม่ต้องตอบเรื่องจอซ้ำ (เช่นเดียวกับ "เปิดเครื่องนาน" กับ "ช้า")
    ids = {t["id"] for _s, t in scored}
    drop = set()
    if "bsod" in ids:
        drop.add("display")
    if "boot" in ids:
        drop.add("slow")
    if "taskbar" in ids:
        drop.add("slow")
    if "ping" in ids:
        drop.add("game")
    scored = [(s, t) for s, t in scored if t["id"] not in drop]
    scored.sort(key=lambda x: -x[0])
    return [t for _s, t in scored]


def _is_followup(question):
    """เช็กว่าผู้ใช้กำลังบอกว่าทำแล้วยังไม่หาย"""
    q = question.lower()
    return any(k in q for k in _FOLLOWUP)


def _topic_findings(topic, found):
    """เลือกเฉพาะผลตรวจที่เกี่ยวกับหัวข้อนี้ (หัวข้อตรวจทั้งหมดใช้ทุกอัน) และเรื่องหนัก ๆ ที่ควรรู้เสมอ"""
    if topic["related"] == "*":
        return found
    related = [f for f in found if f["key"] in topic["related"]]
    urgent = [f for f in found if f["level"] >= 3 and f not in related]
    return related + urgent[:1]


def _extra_lines(topic, ctx):
    """ข้อมูลเฉพาะหัวข้อที่ควรบอกแม้จะไม่ผิดปกติ เช่นผลทดสอบเน็ต หรือโปรแกรมที่กินเครื่องอันดับต้น ๆ"""
    lines = []
    tid = topic["id"]
    top = ctx.get("top") or {}
    if tid in ("network", "ping"):
        lines.append(network_explain(ctx.get("network") or {}))
    if tid in ("slow", "game", "heat", "ram", "battery") and top:
        cpu = ", ".join(f"{n} {v:.0f}%" for n, v in top.get("cpu", [])[:3])
        ram = ", ".join(f"{n} {format_size(v)}" for n, v in top.get("ram", [])[:3])
        if cpu:
            lines.append(tr(f"กิน CPU มากสุดตอนนี้: {cpu}", f"Top CPU right now: {cpu}"))
        if ram:
            lines.append(tr(f"ใช้ RAM มากสุด: {ram}", f"Top RAM: {ram}"))
    if tid == "game":
        plan = ctx.get("power_plan")
        if plan:
            lines.append(tr(f"แผนพลังงานที่ใช้อยู่: {plan}", f"Current power plan: {plan}"))
        for g in ctx.get("gpus") or []:
            lines.append(tr(f"การ์ดจอ: {g['name']} (ไดรเวอร์ {g['driver_version']})", f"GPU: {g['name']} (driver {g['driver_version']})"))
    if tid == "sound":
        audio = ctx.get("audio") or {}
        if audio.get("service") and audio["service"] != "Running":
            lines.append(tr(f"บริการเสียงของ Windows ไม่ได้ทำงาน (สถานะ {audio['service']}) ลองรีสตาร์ทเครื่อง",
                            f"Windows Audio service isn't running ({audio['service']}). Try restarting"))
        bad = [d["name"] for d in audio.get("devices", []) if not d["ok"]]
        if bad:
            lines.append(tr(f"อุปกรณ์เสียงที่มีปัญหา: {', '.join(bad)}", f"Audio devices with problems: {', '.join(bad)}"))
        elif audio.get("devices"):
            lines.append(tr(f"เจออุปกรณ์เสียง {len(audio['devices'])} ตัว ทุกตัวสถานะปกติ", f"Found {len(audio['devices'])} audio devices, all OK"))
    if tid == "battery":
        b = ctx.get("battery")
        lines.append(tr(f"แบตตอนนี้ {b['percent']}% ({'เสียบสายอยู่' if b['plugged'] else 'ไม่ได้เสียบสาย'})",
                        f"Battery now {b['percent']}% ({'plugged in' if b['plugged'] else 'on battery'})") if b
                     else tr("เครื่องนี้ไม่มีแบตเตอรี่ (เป็น PC ตั้งโต๊ะ)", "This PC has no battery (desktop)"))
    if tid == "storage":
        u = ctx.get("usage") or {}
        lines.append(tr(f"ไดรฟ์ Windows ใช้ไป {u.get('disk', 0):.0f}% เหลือ {format_size(u.get('disk_free'))}, ไฟล์ขยะที่ลบได้ {ctx.get('junk_size')}",
                        f"Windows drive {u.get('disk', 0):.0f}% used, {format_size(u.get('disk_free'))} free, {ctx.get('junk_size')} of junk"))
    if tid == "bsod":
        c = ctx.get("crashes") or {}
        if not c.get("bsod") and not c.get("power_loss"):
            lines.append(tr("ใน 14 วันนี้ Windows ไม่ได้บันทึกว่าเกิดจอฟ้าหรือดับเองเลย", "Windows recorded no blue screens or unexpected shutdowns in the last 14 days"))
    return lines


def offline_answer(question, ctx, state=None, note=""):
    """ตอบแบบออฟไลน์จากผลตรวจจริง
    state = dict ที่หน้าแชตเก็บไว้ จำว่าคุยหัวข้อไหนอยู่และถึงขั้นไหนแล้ว (ใช้ตอนผู้ใช้บอกว่ายังไม่หาย)
    คืน dict {reply, actions, suggestions}"""
    state = state if state is not None else {}
    found = findings(ctx)
    topics = _match_topics(question)

    # ผู้ใช้บอกว่ายังไม่หาย และไม่ได้พูดถึงเรื่องใหม่ -> ขั้นต่อไปของหัวข้อเดิม
    if _is_followup(question) and state.get("topic") and (not topics or topics[0]["id"] == state["topic"]):
        topic = next(t for t in TOPICS if t["id"] == state["topic"])
        level = min(state.get("level", 0) + 1, len(topic["steps"]) - 1)
        if level == state.get("level", 0):
            text = tr("ลองครบทุกวิธีที่ผมแนะนำได้แล้ว ถ้ายังไม่หาย ปัญหาน่าจะอยู่ที่ฮาร์ดแวร์ ควรให้ร้านซ่อมตรวจ หรือใส่ Gemini API key เพื่อให้ AI วิเคราะห์ละเอียดกว่านี้",
                      "That's every fix I can suggest offline. If it's still happening, it's likely hardware: have a repair shop check it, or add a Gemini API key for a deeper analysis")
            return {"reply": text, "actions": [], "suggestions": []}
        state["level"] = level
        step_th, step_en, actions = topic["steps"][level]
        return {"reply": tr(f"โอเค ลองขั้นต่อไปนะครับ\n\n{step_th}", f"OK, let's try the next step.\n\n{step_en}"),
                "actions": validate_actions(actions),
                "suggestions": [tx(("ยังไม่หาย", "Still not fixed"))] if level < len(topic["steps"]) - 1 else []}

    # ไม่ตรงหัวข้อไหนเลย -> สรุปสิ่งที่ตรวจเจอในเครื่อง แล้วถามกลับให้เล่าเพิ่ม
    if not topics:
        state.clear()
        parts = []
        if found:
            parts.append(tr("ผมยังไม่แน่ใจว่าหมายถึงอาการไหน แต่ตรวจเครื่องแล้วเจอแบบนี้:",
                            "I'm not sure which problem you mean, but here's what I found on this PC:"))
            parts += [f"• {f['text']}" for f in found[:5]]
        else:
            parts.append(tr("ผมยังไม่แน่ใจว่าหมายถึงอาการไหน และตรวจเครื่องแล้วยังไม่เจออะไรผิดปกติชัด ๆ",
                            "I'm not sure which problem you mean, and the check found nothing obviously wrong"))
        parts.append(tr("\nลองเล่าเพิ่มหน่อยว่าเป็นตอนไหน เช่น 'เปิด Chrome แล้วค้าง', 'เล่น Valorant แล้วเฟรมตก', 'เสียบหูฟังแล้วไม่มีเสียง'",
                        "\nTell me a bit more, e.g. 'Chrome freezes', 'FPS drops in Valorant', 'no sound with headphones'"))
        actions = [a for f in found[:3] for a in f["actions"]]
        return {"reply": "\n".join(parts), "actions": validate_actions(actions),
                "suggestions": [tx(q) for q in QUICK_QUESTIONS[:4]]}

    # ตอบหัวข้อหลัก (และหัวข้อรองถ้ามี) โดยยกผลตรวจที่เกี่ยวข้องขึ้นมาก่อน
    main_topic = topics[0]
    state["topic"], state["level"] = main_topic["id"], 0
    related = _topic_findings(main_topic, found)
    extra = _extra_lines(main_topic, ctx)
    parts = []
    if related or extra:
        parts.append(tr("ตรวจเครื่องแล้วเจอแบบนี้:", "Here's what I found on this PC:"))
        parts += [f"• {f['text']}" for f in related[:5]] + [f"• {line}" for line in extra if line]
    else:
        parts.append(tr("ตรวจเครื่องแล้ว ส่วนที่เกี่ยวกับเรื่องนี้ยังดูปกติดี", "I checked the PC and the related areas look normal"))
    step_th, step_en, actions = main_topic["steps"][0]
    parts.append("\n" + tr(step_th, step_en))
    actions = [a for f in related for a in f["actions"]] + list(actions)
    if len(topics) > 1:
        second = topics[1]
        s_th, s_en, s_actions = second["steps"][0]
        parts.append("\n" + tr(f"ส่วนเรื่องอื่นที่ถามมา: {s_th}", f"About the other thing you mentioned: {s_en}"))
        actions += s_actions
    suggestions = [tx(s) for s in main_topic["suggest"]]
    if len(main_topic["steps"]) > 1:
        suggestions.insert(0, tx(("ทำแล้วยังไม่หาย", "Tried it, still not fixed")))
    text = "\n".join(parts)
    if note:
        text = f"({note})\n\n{text}"
    return {"reply": text, "actions": validate_actions(actions), "suggestions": suggestions[:3]}


# ================================================================
# โหมด Gemini
# ================================================================

def context_text(ctx):
    """แปลงผลตรวจเป็นข้อความสรุปสำหรับส่งให้ Gemini (เขียนเป็นอังกฤษล้วน AI อ่านแม่นกว่า และไม่ขึ้นกับภาษาของหน้าจอ)"""
    u = ctx.get("usage") or {}
    top = ctx.get("top") or {}
    net = ctx.get("network") or {}
    crashes = ctx.get("crashes") or {}
    lines = ["[PC check results, collected just now]"]
    for k, v in (ctx.get("specs") or {}).items():
        lines.append(f"- {k}: {str(v).replace(chr(10), ' / ')}")
    lines.append(f"- Usage: CPU {u.get('cpu', 0):.0f}%, RAM {u.get('ram', 0):.0f}% "
                 f"({format_size(u.get('ram_used'))}/{format_size(u.get('ram_total'))}), "
                 f"Windows drive {u.get('disk', 0):.0f}% used ({format_size(u.get('disk_free'))} free)")
    if top.get("cpu"):
        lines.append("- Top CPU processes: " + ", ".join(f"{n} {v}%" for n, v in top["cpu"]))
    if top.get("ram"):
        lines.append("- Top RAM processes: " + ", ".join(f"{n} {format_size(v)}" for n, v in top["ram"]))
    lines.append(f"- Uptime since last real boot: {ctx.get('uptime_days')} days; pending update reboot: {ctx.get('pending_reboot')}")
    lines.append(f"- Startup apps enabled: {ctx.get('startup_count')}; junk files deletable: {ctx.get('junk_size')}")
    lines.append(f"- Power plan: {ctx.get('power_plan')}; battery: {ctx.get('battery') or 'none (desktop)'}")
    lines.append(f"- Network test: verdict={net.get('verdict')}, gateway={net.get('gateway')} reachable={net.get('gateway_ok')}, "
                 f"internet(1.1.1.1)={net.get('internet_ok')}, DNS={net.get('dns_ok')}, ping={net.get('ping_ms')}ms, adapters={net.get('adapters')}")
    lines.append(f"- Blue screens (14 days): {crashes.get('bsod', 0)}, latest {crashes.get('bsod_last') or '-'}, "
                 f"bugcheck {crashes.get('bsod_code') or '-'}; unexpected shutdowns (Kernel-Power 41): {crashes.get('power_loss', 0)}")
    if crashes.get("app_crashes"):
        lines.append("- App crashes (7 days): " + ", ".join(f"{n} x{c}" for n, c in crashes["app_crashes"]))
    gpus = ctx.get("gpus") or []
    lines.append("- GPUs: " + (", ".join(f"{g['name']} driver {g['driver_version']}" + (" (NO DRIVER)" if g['no_driver'] else "") for g in gpus) or "-"))
    devices = ctx.get("problem_devices") or []
    lines.append("- Problem devices: " + (", ".join(f"{d['name']} (code {d['code']})" for d in devices[:10]) or "none"))
    audio = ctx.get("audio") or {}
    lines.append(f"- Audio service: {audio.get('service') or '-'}; audio devices with problems: "
                 + (", ".join(d['name'] for d in audio.get('devices', []) if not d['ok']) or "none"))
    lines.append("- Disk health: " + (", ".join(f"{d['name']} {d['health']}" for d in ctx.get('disk_health') or []) or "-"))
    return "\n".join(lines)


def _system_prompt():
    """คำสั่งระบบที่บอก Gemini ว่าเป็นใคร ต้องตอบยังไง และเลือก action ได้จากรายการไหนบ้าง"""
    actions = "\n".join(f"- {k}: {v[0][1]} ({v[1][1]})" for k, v in ALLOWED_ACTIONS.items())
    apps = ", ".join(sorted(installer.allowed_ids()))
    language = "Thai (casual, friendly, like a helpful friend who knows computers)" if get_language() == "th" else "English (friendly, plain words)"
    return (
        "You are the PC troubleshooting assistant inside 'Polo Optimizer', a Windows app for people who are not good with computers.\n"
        f"Always reply in {language}. Avoid jargon; when you must use a technical term, explain it in a few words.\n\n"
        "How to answer:\n"
        "1. The user describes a real problem in their own words. Figure out what they actually mean, even if it's vague or has typos.\n"
        "2. Use the PC check results attached to every message as evidence. Quote the real numbers and names "
        "(e.g. which process uses the CPU, the bugcheck code, the ping, which network layer failed). Don't invent data that isn't there.\n"
        "3. Give the most likely cause first, then clear numbered steps the user can follow, easiest first.\n"
        "4. If the description is too vague to diagnose, ask ONE short clarifying question (and still give a first thing to try).\n"
        "5. Remember earlier messages in this conversation. If the user says a fix didn't work, move on to the next deeper step instead of repeating.\n"
        "6. If the evidence points to hardware failure (failing disk, overheating, RAM errors), say so honestly and suggest a repair shop.\n"
        "7. Never suggest disabling Windows Defender, Windows Update, system services or security mitigations, "
        "and never suggest downloading tools from unofficial sites.\n"
        "8. Keep it reasonably short: about 4-10 lines.\n\n"
        "Return JSON only: {\"reply\": \"...\", \"actions\": [...], \"suggestions\": [...]}\n"
        "- actions: buttons the user can press to apply a fix. Only use IDs from this list, max 4, only if relevant (or []):\n"
        f"{actions}\n"
        f"- install:<id> to suggest installing an app, where id must be one of: {apps}\n"
        "- suggestions: 2-3 short follow-up messages the user might want to send next, written in the reply language "
        "(e.g. 'still not fixed', or a related question). Max 40 characters each.\n"
        "Do not mention the action IDs inside the reply text."
    )


def ask_gemini(question, ctx, api_key, model, history=None):
    """ส่งคำถาม + ผลตรวจเครื่อง + บทสนทนาก่อนหน้าไปที่ Gemini แล้วคืน dict {reply, actions, suggestions}
    history = [(role, text), ...] ส่งไปล่าสุด 10 ข้อความ ให้ AI จำเรื่องที่คุยกันได้
    ถ้าเรียก API ไม่สำเร็จจะ throw RuntimeError พร้อมข้อความ ให้ฝั่งหน้าจอไปใช้โหมดออฟไลน์แทน"""
    if not re.fullmatch(r"[A-Za-z0-9._\-]+", model or ""):
        raise RuntimeError(tr("ชื่อโมเดลไม่ถูกต้อง", "Invalid model name"))
    contents = []
    for role, text in (history or [])[-10:]:
        contents.append({"role": "model" if role == "ai" else "user", "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": f"{context_text(ctx)}\n\n[User message]\n{question}"}]})
    body = {
        "system_instruction": {"parts": [{"text": _system_prompt()}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.5,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "reply": {"type": "STRING"},
                    "actions": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "suggestions": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["reply", "actions", "suggestions"],
            },
        },
    }
    request = urllib.request.Request(
        _API_URL.format(model=model),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        messages = {
            400: tr("API key หรือคำขอไม่ถูกต้อง", "Invalid API key or request"),
            401: tr("API key ไม่ถูกต้อง", "Invalid API key"),
            403: tr("API key นี้ไม่มีสิทธิ์ใช้งาน", "This API key isn't allowed"),
            404: tr(f"ไม่พบโมเดล '{model}' ลองเปลี่ยนชื่อโมเดลในช่องตั้งค่า", f"Model '{model}' not found. Change the model name in settings"),
            429: tr("ใช้โควตาฟรีครบแล้ว รอสักพักแล้วลองใหม่", "Free quota used up. Wait a bit and try again"),
        }
        raise RuntimeError(messages.get(e.code, tr(f"Gemini ตอบกลับผิดพลาด (HTTP {e.code})", f"Gemini error (HTTP {e.code})")))
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError(tr("เชื่อมต่อ Gemini ไม่ได้ (อาจไม่มีเน็ต)", "Couldn't reach Gemini (no internet?)"))

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        reply = str(parsed.get("reply", "")).strip()
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        raise RuntimeError(tr("อ่านคำตอบจาก Gemini ไม่ได้", "Couldn't read Gemini's answer"))
    if not reply:
        raise RuntimeError(tr("Gemini ไม่ได้ตอบอะไรกลับมา", "Gemini returned an empty answer"))
    suggestions = [str(s)[:60] for s in parsed.get("suggestions") or [] if isinstance(s, str) and s.strip()][:3]
    return {"reply": reply, "actions": validate_actions(parsed.get("actions")), "suggestions": suggestions}

"""
installer.py
รายชื่อแอปที่ติดตั้งได้ (แยกหมวด) และฟังก์ชันติดตั้งผ่าน winget
winget คือตัวติดตั้งแอปของ Microsoft ที่มากับ Windows 10/11 ดาวน์โหลดจากแหล่งทางการของแต่ละแอปโดยตรง
"""

import json
import os
import shutil

from i18n import tr
from utils import run_cmd, open_url

# winget คืนรหัสพวกนี้เมื่อแอปมีอยู่ในเครื่องแล้ว ให้ถือว่าติดตั้งสำเร็จ
#   -1978335189 (0x8A15002B) = มีเวอร์ชันล่าสุดอยู่แล้ว ไม่มีอะไรให้อัปเดต
#   -1978335135 (0x8A150061) = แอปนี้ติดตั้งอยู่แล้ว
ALREADY_INSTALLED_CODES = {-1978335189, -1978335135}

# หน้า App Installer (ตัวที่มี winget) ใน Microsoft Store
APP_INSTALLER_STORE = "ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1"

# รายชื่อแอปทั้งหมด แยกหมวด
#   id     = รหัสแอปใน winget (ต้องตรงตัวอักษรเป๊ะ เพราะใช้ -e)
#   source = ร้านที่ใช้ค้น (winget = คลังหลัก, msstore = Microsoft Store)
CATALOG = [
    {
        "name": ("จำเป็น", "Essentials"),
        "icon": "🧩",
        "desc": ("ไลบรารีที่เกมและโปรแกรมส่วนใหญ่ต้องใช้ ถ้าขาดมักเจอ error ว่าหาไฟล์ .dll ไม่เจอ", "Libraries most games and programs need. Missing them often causes '.dll not found' errors"),
        "default": True,
        "apps": [
            {"id": "Microsoft.VCRedist.2015+.x64", "name": ("Visual C++ 2015-2022 (64 บิต)", "Visual C++ 2015-2022 (64-bit)"), "desc": ("ไลบรารีพื้นฐานของโปรแกรมและเกม 64 บิต", "Core library for 64-bit programs and games")},
            {"id": "Microsoft.VCRedist.2015+.x86", "name": ("Visual C++ 2015-2022 (32 บิต)", "Visual C++ 2015-2022 (32-bit)"), "desc": ("ไลบรารีพื้นฐานของโปรแกรมและเกม 32 บิต", "Core library for 32-bit programs and games")},
            {"id": "Microsoft.DirectX", "name": "DirectX End-User Runtime", "desc": ("ไฟล์ DirectX รุ่นเก่าที่เกมหลายเกมยังต้องใช้", "Older DirectX files many games still need")},
            {"id": "Microsoft.DotNet.DesktopRuntime.8", "name": ".NET Desktop Runtime 8", "desc": ("ตัวรันโปรแกรมที่เขียนด้วย .NET", "Runs programs built with .NET")},
            {"id": "Microsoft.EdgeWebView2Runtime", "name": "WebView2 Runtime", "desc": ("ตัวแสดงหน้าเว็บที่แอปใหม่ ๆ ใช้ข้างใน", "Web view engine used inside newer apps")},
        ],
    },
    {
        "name": ("ใช้ทุกวัน", "Everyday"),
        "icon": "🌐",
        "desc": ("แอปพื้นฐานที่คนส่วนใหญ่ใช้", "Basic apps most people use"),
        "default": False,
        "apps": [
            {"id": "Google.Chrome", "name": "Google Chrome", "desc": ("เว็บเบราว์เซอร์", "Web browser")},
            {"id": "XPFCC4CD725961", "name": "LINE", "desc": ("แชต โทร วิดีโอคอล (ติดตั้งจาก Microsoft Store)", "Chat, calls, video calls (from Microsoft Store)"), "source": "msstore"},
            {"id": "7zip.7zip", "name": "7-Zip", "desc": ("แตกไฟล์ .zip .rar .7z", "Open .zip .rar .7z files")},
            {"id": "VideoLAN.VLC", "name": "VLC", "desc": ("เล่นวิดีโอและเพลงได้แทบทุกนามสกุล", "Plays almost any video or music format")},
            {"id": "Adobe.Acrobat.Reader.64-bit", "name": "Adobe Acrobat Reader", "desc": ("เปิดอ่านไฟล์ PDF", "Read PDF files")},
            {"id": "Google.GoogleDrive", "name": "Google Drive", "desc": ("ซิงก์ไฟล์กับ Google Drive", "Sync files with Google Drive")},
        ],
    },
    {
        "name": ("เกม", "Gaming"),
        "icon": "🎮",
        "desc": ("ร้านเกมและโปรแกรมที่คนเล่นเกมใช้", "Game stores and tools gamers use"),
        "default": False,
        "apps": [
            {"id": "Valve.Steam", "name": "Steam", "desc": ("ร้านเกม PC ที่ใหญ่ที่สุด", "The biggest PC game store")},
            {"id": "EpicGames.EpicGamesLauncher", "name": "Epic Games Launcher", "desc": ("ร้านเกมที่แจกเกมฟรีทุกสัปดาห์", "Game store with free games every week")},
            {"id": "Garena.Garena", "name": "Garena", "desc": ("ตัวเปิดเกมของ Garena", "Garena's game launcher")},
            {"id": "Discord.Discord", "name": "Discord", "desc": ("คุยเสียงและแชตกับเพื่อนตอนเล่นเกม", "Voice and text chat with friends while gaming")},
            {"id": "OBSProject.OBSStudio", "name": "OBS Studio", "desc": ("อัดหน้าจอและไลฟ์สด", "Screen recording and live streaming")},
        ],
    },
    {
        "name": ("เรียน/ทำงาน", "Study/Work"),
        "icon": "📚",
        "desc": ("แอปเรียนออนไลน์ ประชุม และทำงานเอกสาร", "Online classes, meetings and documents"),
        "default": False,
        "apps": [
            {"id": "Zoom.Zoom", "name": "Zoom", "desc": ("ประชุมและเรียนออนไลน์", "Online meetings and classes")},
            {"id": "Microsoft.Teams", "name": "Microsoft Teams", "desc": ("ประชุมและส่งงานของหลายโรงเรียน/บริษัท", "Meetings and assignments for many schools/companies")},
            {"id": "TheDocumentFoundation.LibreOffice", "name": "LibreOffice", "desc": ("โปรแกรมเอกสารฟรี เปิดไฟล์ Word/Excel/PowerPoint ได้", "Free office suite, opens Word/Excel/PowerPoint files")},
            {"id": "Canva.Canva", "name": "Canva", "desc": ("ออกแบบโปสเตอร์ สไลด์ รูปโพสต์", "Design posters, slides and social posts")},
            {"id": "ByteDance.CapCut", "name": "CapCut", "desc": ("ตัดต่อวิดีโอแบบง่าย", "Easy video editing")},
            {"id": "Spotify.Spotify", "name": "Spotify", "desc": ("ฟังเพลง", "Music streaming")},
        ],
    },
]


def all_apps():
    """คืนรายการแอปทั้งหมดจากทุกหมวดเป็น list เดียว"""
    return [app for cat in CATALOG for app in cat["apps"]]


def allowed_ids():
    """คืนชุดรหัสแอปทั้งหมดในหน้าติดตั้ง ใช้เช็กว่า AI แนะนำแอปที่อยู่ในรายการจริงหรือเปล่า"""
    return {app["id"] for app in all_apps()}


def find_app(app_id):
    """หาข้อมูลแอปจากรหัส winget ถ้าไม่เจอคืน None"""
    for app in all_apps():
        if app["id"] == app_id:
            return app
    return None


def winget_path():
    """หาที่อยู่ของ winget.exe ในเครื่อง ถ้าไม่เจอคืน None
    ปกติอยู่ใน PATH อยู่แล้ว ถ้าไม่เจอค่อยลองดูในโฟลเดอร์ WindowsApps ของผู้ใช้"""
    path = shutil.which("winget")
    if path:
        return path
    candidate = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "winget.exe")
    return candidate if os.path.exists(candidate) else None


def has_winget():
    """เช็กว่าเครื่องนี้ใช้ winget ได้ไหม โดยลองสั่ง winget --version"""
    path = winget_path()
    if not path:
        return False
    code, out, _err = run_cmd([path, "--version"], timeout=30)
    return code == 0 and out.strip().startswith("v")


def installed_ids():
    """หาว่าแอปไหนในรายการติดตั้งอยู่แล้ว โดยสั่ง winget export ส่งออกรายชื่อแอปในเครื่องเป็นไฟล์ JSON แล้วอ่านรหัสแอป
    (แม่นกว่าอ่านตารางจาก winget list ที่ชื่อยาว ๆ โดนตัด) ใช้เวลาประมาณ 5-10 วินาที ต้องเรียกจาก thread แยก
    แอปที่ลงแบบเฉพาะผู้ใช้บางตัว (เช่น Discord) winget อาจจับคู่ไม่ได้ ถ้ากดติดตั้งซ้ำ winget จะตอบว่ามีอยู่แล้วเอง
    คืน set ของรหัสแอป (ว่างถ้าใช้ winget ไม่ได้)"""
    path = winget_path()
    if not path:
        return set()
    out_file = os.path.join(os.environ.get("TEMP", "."), "polo_winget_export.json")
    try:
        run_cmd([path, "export", "-o", out_file, "--accept-source-agreements", "--disable-interactivity"], timeout=120)
        with open(out_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        found = {p.get("PackageIdentifier") for s in data.get("Sources", []) for p in s.get("Packages", [])}
        return {app_id for app_id in allowed_ids() if app_id in found}
    except (OSError, ValueError):
        return set()
    finally:
        try:
            os.remove(out_file)
        except OSError:
            pass


def open_app_installer_store():
    """เปิด Microsoft Store หน้า App Installer ให้ผู้ใช้กดติดตั้ง winget เอง"""
    open_url(APP_INSTALLER_STORE)


def install_app(app):
    """ติดตั้งแอป 1 ตัวด้วย winget แบบเงียบ (ไม่มีหน้าต่างถาม) คืน (สำเร็จไหม, ข้อความ)
    ใช้เวลาตั้งแต่ไม่กี่วินาทีถึงหลายนาทีตามขนาดแอป เลยต้องเรียกจาก thread แยก"""
    path = winget_path()
    if not path:
        return False, tr("เครื่องนี้ไม่มี winget", "winget is not available on this PC")
    args = [
        path, "install", "--id", app["id"], "-e", "--silent",
        "--accept-package-agreements", "--accept-source-agreements",
        "--disable-interactivity",
        # ระบุร้านให้ชัด จะได้ไม่เจอปัญหา "เจอแอปชื่อซ้ำหลายร้าน"
        "--source", app.get("source", "winget"),
    ]
    code, out, err = run_cmd(args, timeout=60 * 30)
    if code == 0:
        return True, tr("ติดตั้งเสร็จ", "Installed")
    if code in ALREADY_INSTALLED_CODES:
        return True, tr("มีอยู่ในเครื่องแล้ว", "Already installed")
    if code == -1:
        return False, err or tr("รัน winget ไม่สำเร็จ", "winget failed to run")
    return False, tr(f"ติดตั้งไม่สำเร็จ (รหัส {code})", f"Install failed (code {code})")

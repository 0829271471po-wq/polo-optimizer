"""
cleaner.py
สแกนและลบไฟล์ขยะ ลบได้เฉพาะโฟลเดอร์แคชและไฟล์ชั่วคราวที่กำหนดไว้ในรายการ CATEGORIES เท่านั้น
ไม่แตะไฟล์ส่วนตัวของผู้ใช้ (Documents, Desktop, Pictures ฯลฯ) เด็ดขาด

หลักความปลอดภัยที่ใช้ในไฟล์นี้
- ลบเฉพาะ "ของข้างใน" โฟลเดอร์แคช ไม่ลบตัวโฟลเดอร์หลัก
- ไม่เดินเข้า junction/symlink เพราะมันอาจชี้ไปที่ไฟล์จริงของผู้ใช้
- ไฟล์ที่โปรแกรมอื่นเปิดค้างอยู่ ลบไม่ได้ก็ข้ามไปเงียบ ๆ
- ใน Temp จะไม่ลบไฟล์ที่อายุไม่ถึง 1 วัน เผื่อเป็นของโปรแกรมที่กำลังติดตั้งอยู่
- ไม่ลบโฟลเดอร์ที่ Polo Optimizer แตกไฟล์ตัวเองไว้ (โฟลเดอร์ _MEI ตอนรันเป็น .exe)
"""

import ctypes
import glob
import os
import stat
import sys
import time
from ctypes import wintypes

ONE_DAY = 24 * 60 * 60
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _env(name, fallback=""):
    """อ่านตัวแปรสภาพแวดล้อม (เช่น TEMP, LOCALAPPDATA) ถ้าไม่มีคืนค่าสำรอง"""
    return os.environ.get(name, fallback)


def _windir():
    """คืนที่อยู่โฟลเดอร์ Windows เช่น C:\\Windows"""
    return _env("SystemRoot", r"C:\Windows")


# รายการหมวดไฟล์ขยะทั้งหมด
#   dirs   = โฟลเดอร์ที่จะลบ "ของข้างใน" ทั้งหมด
#   files  = รูปแบบชื่อไฟล์ (glob) ที่ลบเป็นไฟล์ ๆ
#   min_age = ลบเฉพาะไฟล์ที่เก่ากว่ากี่วินาที
#   default = ติ๊กไว้ให้ตั้งแต่แรกไหม
CATEGORIES = [
    {
        "key": "temp_user",
        "name": ("ไฟล์ชั่วคราวของผู้ใช้ (%TEMP%)", "User temp files (%TEMP%)"),
        "desc": ("ไฟล์ที่โปรแกรมต่าง ๆ สร้างทิ้งไว้ระหว่างทำงาน ลบได้ปลอดภัย", "Files programs leave behind while working. Safe to delete"),
        "dirs": lambda: [_env("TEMP")],
        "files": lambda: [],
        "min_age": ONE_DAY,
        "default": True,
    },
    {
        "key": "temp_windows",
        "name": ("ไฟล์ชั่วคราวของ Windows (Windows\\Temp)", "Windows temp files (Windows\\Temp)"),
        "desc": ("ไฟล์ชั่วคราวจากตัวติดตั้งและบริการของ Windows", "Temp files from installers and Windows services"),
        "dirs": lambda: [os.path.join(_windir(), "Temp")],
        "files": lambda: [],
        "min_age": ONE_DAY,
        "default": True,
    },
    {
        "key": "thumbnail",
        "name": ("แคชรูปตัวอย่าง (Thumbnail cache)", "Thumbnail cache"),
        "desc": ("รูปย่อที่ File Explorer เก็บไว้ ลบแล้ว Windows จะสร้างใหม่เอง", "Preview images File Explorer keeps. Windows rebuilds them automatically"),
        "dirs": lambda: [],
        "files": lambda: [os.path.join(_env("LOCALAPPDATA"), "Microsoft", "Windows", "Explorer", "thumbcache_*.db")],
        "min_age": 0,
        "default": True,
    },
    {
        "key": "crash_dumps",
        "name": ("ไฟล์บันทึกตอนโปรแกรมแครช (Crash dumps)", "Crash dumps"),
        "desc": ("ไฟล์ที่ระบบเก็บไว้ตอนโปรแกรมหรือ Windows ค้าง/จอฟ้า ใช้แค่ตอนช่างวิเคราะห์ปัญหา", "Files saved when programs or Windows crash. Only useful to technicians"),
        "dirs": lambda: [
            os.path.join(_env("LOCALAPPDATA"), "CrashDumps"),
            os.path.join(_windir(), "Minidump"),
        ],
        "files": lambda: [os.path.join(_windir(), "MEMORY.DMP")],
        "min_age": 0,
        "default": True,
    },
    {
        "key": "d3dscache",
        "name": ("แคช DirectX Shader (D3DSCache)", "DirectX shader cache (D3DSCache)"),
        "desc": ("แคชกราฟิกของเกม ลบแล้วเกมจะสร้างใหม่ ช่วงแรกอาจโหลดนานขึ้นนิดหน่อย", "Game graphics cache. Games rebuild it, first loads may be a bit slower"),
        "dirs": lambda: [os.path.join(_env("LOCALAPPDATA"), "D3DSCache")],
        "files": lambda: [],
        "min_age": 0,
        "default": True,
    },
    {
        "key": "nvidia_cache",
        "name": ("แคชของการ์ดจอ NVIDIA", "NVIDIA graphics cache"),
        "desc": ("แคช shader ของ NVIDIA (DXCache, GLCache) ช่วยได้ตอนเกมกระตุกหลังอัปเดตไดรเวอร์", "NVIDIA shader cache (DXCache, GLCache). Helps when games stutter after a driver update"),
        "dirs": lambda: [
            os.path.join(_env("LOCALAPPDATA"), "NVIDIA", "DXCache"),
            os.path.join(_env("LOCALAPPDATA"), "NVIDIA", "GLCache"),
            os.path.join(_env("USERPROFILE"), "AppData", "LocalLow", "NVIDIA", "PerDriverVersion", "DXCache"),
            os.path.join(_env("ProgramData", r"C:\ProgramData"), "NVIDIA Corporation", "NV_Cache"),
        ],
        "files": lambda: [],
        "min_age": 0,
        "default": True,
    },
    {
        "key": "recycle_bin",
        "name": ("ถังขยะ (Recycle Bin)", "Recycle Bin"),
        "desc": ("ไฟล์ที่ลบไปแล้วแต่ยังกู้คืนได้ ถ้าล้างแล้วจะกู้คืนไม่ได้อีก เลยไม่ได้ติ๊กไว้ให้", "Deleted files you can still restore. Emptying it is permanent, so it isn't ticked by default"),
        "dirs": lambda: [],
        "files": lambda: [],
        "min_age": 0,
        "default": False,
    },
]

# ชื่อโฟลเดอร์ที่ยอมให้ลบของข้างในได้ ใช้กันพลาดกรณีตัวแปร TEMP ถูกตั้งค่าแปลก ๆ (เช่นชี้ไปที่ C:\)
_SAFE_DIR_NAMES = {"temp", "tmp", "crashdumps", "minidump", "d3dscache", "dxcache", "glcache", "nv_cache"}


def _is_safe_dir(path):
    """เช็กว่าโฟลเดอร์นี้เป็นโฟลเดอร์แคชจริง ๆ ไม่ใช่ราก drive หรือโฟลเดอร์ผู้ใช้
    ดูจากชื่อโฟลเดอร์สุดท้ายหรือรองสุดท้าย (เช่น ...\\Temp หรือ ...\\Temp\\2 ตอนใช้ Remote Desktop)"""
    if not path:
        return False
    full = os.path.abspath(path)
    parts = [p.lower() for p in full.rstrip("\\").split("\\") if p]
    if len(parts) < 2:
        return False
    return parts[-1] in _SAFE_DIR_NAMES or (len(parts) >= 3 and parts[-2] in _SAFE_DIR_NAMES)


def _own_bundle_dir():
    """ตอนรันเป็น .exe แบบไฟล์เดียว PyInstaller จะแตกไฟล์โปรแกรมไว้ใน %TEMP%\\_MEIxxxx
    ต้องข้ามโฟลเดอร์นี้ ไม่งั้นจะลบไฟล์ของตัวเองทิ้งระหว่างรัน"""
    path = getattr(sys, "_MEIPASS", None)
    return os.path.normcase(os.path.abspath(path)) if path else None


def _is_link(entry):
    """เช็กว่าเป็น junction หรือ symlink ไหม ถ้าใช่จะไม่เดินเข้าไปเด็ดขาด"""
    try:
        st = entry.stat(follow_symlinks=False)
        return entry.is_symlink() or bool(getattr(st, "st_file_attributes", 0) & _REPARSE)
    except OSError:
        return True


def _walk_files(root, min_age):
    """ไล่หาไฟล์ทั้งหมดในโฟลเดอร์ (รวมโฟลเดอร์ย่อย) แบบ generator คืน (path, ขนาด)
    ข้าม junction/symlink, ข้ามโฟลเดอร์ของตัวโปรแกรมเอง และข้ามไฟล์ที่ใหม่กว่า min_age วินาที"""
    skip_dir = _own_bundle_dir()
    now = time.time()
    stack = [root]
    while stack:
        current = stack.pop()
        if skip_dir and os.path.normcase(os.path.abspath(current)) == skip_dir:
            continue
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                if _is_link(entry):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                    continue
                st = entry.stat(follow_symlinks=False)
                if min_age and now - st.st_mtime < min_age:
                    continue
                yield entry.path, st.st_size
            except OSError:
                continue


def _remove_empty_dirs(folder, is_root=True):
    """หลังลบไฟล์แล้ว ลองลบโฟลเดอร์ย่อยที่ว่างเปล่า (ไล่จากชั้นในสุดออกมา) แต่ไม่ลบโฟลเดอร์หลัก
    ถ้าโฟลเดอร์ไหนยังมีของเหลือ os.rmdir จะ error เองแล้วเราก็ข้ามไป
    เขียนเองแทน os.walk เพราะ os.walk ใน Python รุ่นเก่าเดินเข้า junction ได้"""
    skip_dir = _own_bundle_dir()
    if skip_dir and os.path.normcase(os.path.abspath(folder)) == skip_dir:
        return
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return
    for entry in entries:
        try:
            if _is_link(entry) or not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        _remove_empty_dirs(entry.path, is_root=False)
    if not is_root:
        try:
            os.rmdir(folder)
        except OSError:
            pass


def _pattern_files(patterns):
    """หาไฟล์จากรูปแบบชื่อ เช่น thumbcache_*.db คืน (path, ขนาด) ของไฟล์ที่มีอยู่จริง"""
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                if os.path.isfile(path) and not os.path.islink(path):
                    yield path, os.path.getsize(path)
            except OSError:
                continue


def _iter_category(cat):
    """รวมไฟล์ทั้งหมดของหมวดหนึ่ง ทั้งจากโฟลเดอร์และจากรูปแบบชื่อไฟล์"""
    # ถ้าตัวแปรอย่าง LOCALAPPDATA หายไป path จะกลายเป็นแบบสั้น (relative) เลยรับเฉพาะ path เต็มเท่านั้น
    for folder in cat["dirs"]():
        if folder and os.path.isabs(folder) and os.path.isdir(folder) and _is_safe_dir(folder):
            yield from _walk_files(folder, cat["min_age"])
    yield from _pattern_files([p for p in cat["files"]() if os.path.isabs(p)])


# ---------- ถังขยะ (ใช้ API ของ Windows ผ่าน ctypes) ----------

class _SHQUERYRBINFO(ctypes.Structure):
    """โครงสร้างข้อมูลที่ Windows ใช้ตอบว่าถังขยะมีกี่ไฟล์ ขนาดเท่าไร"""
    _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]


def recycle_bin_size():
    """ถามขนาดถังขยะของทุกไดรฟ์ คืน (ขนาด byte, จำนวนไฟล์)"""
    info = _SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(info)
    res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
    if res != 0:
        return 0, 0
    return int(info.i64Size), int(info.i64NumItems)


def empty_recycle_bin():
    """ล้างถังขยะทุกไดรฟ์โดยไม่เด้งหน้าต่างถาม ไม่โชว์แถบความคืบหน้า และไม่มีเสียง (flag 0x7)"""
    size, count = recycle_bin_size()
    if count == 0:
        return 0, 0
    res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)
    return (size, count) if res == 0 else (0, 0)


# ---------- ฟังก์ชันหลักที่หน้าจอเรียกใช้ ----------

def scan(keys=None, progress=None):
    """สแกนหาไฟล์ขยะ (ยังไม่ลบ) คืน dict {key: (ขนาดรวม byte, จำนวนไฟล์)}
    keys = หมวดที่จะสแกน (None = ทุกหมวด), progress = ฟังก์ชันที่จะถูกเรียกพร้อมชื่อหมวดที่กำลังสแกน"""
    result = {}
    for cat in CATEGORIES:
        if keys is not None and cat["key"] not in keys:
            continue
        if progress:
            progress(cat["name"])
        if cat["key"] == "recycle_bin":
            result[cat["key"]] = recycle_bin_size()
            continue
        total = count = 0
        for _path, size in _iter_category(cat):
            total += size
            count += 1
        result[cat["key"]] = (total, count)
    return result


def clean(keys, progress=None):
    """ลบไฟล์ขยะในหมวดที่เลือก คืน dict สรุปผล {'freed': byte ที่ได้คืน, 'deleted': จำนวนไฟล์ที่ลบ, 'skipped': จำนวนที่ข้าม}
    ไฟล์ที่ถูกใช้งานอยู่หรือไม่มีสิทธิ์ลบจะถูกข้ามแบบเงียบ ๆ (นับรวมใน skipped)"""
    freed = deleted = skipped = 0
    for cat in CATEGORIES:
        if cat["key"] not in keys:
            continue
        if progress:
            progress(cat["name"])
        if cat["key"] == "recycle_bin":
            size, count = empty_recycle_bin()
            freed += size
            deleted += count
            continue
        for path, size in list(_iter_category(cat)):
            try:
                # ไฟล์ที่ตั้งค่าเป็น read-only จะลบไม่ได้ เลยปลดออกก่อน
                os.chmod(path, stat.S_IWRITE)
            except OSError:
                pass
            try:
                os.remove(path)
                freed += size
                deleted += 1
            except OSError:
                skipped += 1
        for folder in cat["dirs"]():
            if folder and os.path.isabs(folder) and os.path.isdir(folder) and _is_safe_dir(folder):
                _remove_empty_dirs(folder)
    return {"freed": freed, "deleted": deleted, "skipped": skipped}


def default_keys():
    """คืนรายชื่อหมวดที่ติ๊กไว้ให้ตั้งแต่แรก (ทุกหมวดยกเว้นถังขยะ) ใช้ในปุ่มดูแลเครื่องคลิกเดียวและปุ่มของ AI"""
    return [c["key"] for c in CATEGORIES if c["default"]]

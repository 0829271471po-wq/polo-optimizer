"""
config.py
จัดการไฟล์ตั้งค่าของโปรแกรม เก็บไว้ที่ %APPDATA%\\PoloOptimizer\\config.json
ตอนนี้เก็บแค่ API key ของ Gemini, ชื่อโมเดล และ GUID ของแผนพลังงาน Ultimate ที่โปรแกรมเคยสร้าง
"""

import json
import os

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PoloOptimizer")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
# ที่เก็บไฟล์ตั้งค่าของรุ่นเก่า (ตอนโปรแกรมยังชื่อ Nova Optimizer) ใช้ย้ายค่าเดิมมาให้อัตโนมัติ
OLD_CONFIG_PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "NovaOptimizer", "config.json")

# ค่าเริ่มต้น ใช้ตอนยังไม่มีไฟล์ตั้งค่า หรือไฟล์เสีย
DEFAULTS = {
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "ultimate_plan_guid": "",
    "language": "th",
    "welcome_seen": False,
    "startup_disabled": [],  # โปรแกรมเปิดพร้อมเครื่องที่ Polo Optimizer เป็นคนปิด [[แหล่ง, ชื่อ], ...] ใช้ตอนคืนค่าเริ่มต้น
}


def load_config():
    """อ่านไฟล์ตั้งค่า ถ้ายังไม่มีหรืออ่านไม่ได้ให้ใช้ค่าเริ่มต้นแทน (โปรแกรมจะไม่พัง)
    ถ้ายังไม่มีไฟล์ของชื่อใหม่ แต่มีไฟล์ของชื่อเก่า จะอ่านจากไฟล์เก่าแทน API key ที่เคยใส่ไว้จะได้ไม่หาย"""
    data = dict(DEFAULTS)
    path = CONFIG_PATH if os.path.exists(CONFIG_PATH) or not os.path.exists(OLD_CONFIG_PATH) else OLD_CONFIG_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            data.update({k: v for k, v in saved.items() if k in DEFAULTS})
    except (OSError, json.JSONDecodeError):
        pass
    return data


def save_config(data):
    """บันทึกค่าตั้งค่าลงไฟล์ ถ้ายังไม่มีโฟลเดอร์ก็สร้างให้
    เขียนลงไฟล์ชั่วคราวก่อนแล้วค่อยแทนที่ไฟล์จริง กันไฟล์เสียถ้าไฟดับกลางทาง"""
    os.makedirs(APP_DIR, exist_ok=True)
    merged = load_config()
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    tmp_path = CONFIG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, CONFIG_PATH)
    return merged

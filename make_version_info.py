"""
make_version_info.py
สร้างไฟล์ version_info.txt ให้ PyInstaller ฝังข้อมูลโปรแกรมลงใน .exe (ใช้แค่ตอน build)
ข้อมูลนี้จะโผล่ในหน้า Properties > Details ของไฟล์, ใน Task Manager และในหน้าต่าง UAC
ไฟล์ .exe ที่ไม่มีข้อมูลพวกนี้ดูน่าสงสัยในสายตาแอนติไวรัส ใส่ไว้ช่วยลดโอกาสโดนเตือนผิด ๆ
เลขเวอร์ชันอ่านจาก APP_VERSION ใน main.py ที่เดียว
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Polo'),
      StringStruct('FileDescription', 'Polo Optimizer - Windows PC care tool'),
      StringStruct('FileVersion', '{dotted}'),
      StringStruct('InternalName', 'PoloOptimizer'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 Polo'),
      StringStruct('OriginalFilename', 'PoloOptimizer.exe'),
      StringStruct('ProductName', 'Polo Optimizer'),
      StringStruct('ProductVersion', '{dotted}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def app_version():
    """อ่านเลขเวอร์ชันจาก APP_VERSION ใน main.py"""
    with open(os.path.join(HERE, "main.py"), encoding="utf-8") as f:
        return re.search(r'APP_VERSION = "([^"]+)"', f.read()).group(1)


def main():
    """เขียน version_info.txt (เลขเวอร์ชันต้องมี 4 ตัว เช่น 1.3 -> 1.3.0.0)"""
    parts = [int(p) for p in re.findall(r"\d+", app_version())][:4]
    parts += [0] * (4 - len(parts))
    text = TEMPLATE.format(nums=tuple(parts), dotted=".".join(map(str, parts)))
    with open(os.path.join(HERE, "version_info.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    print("สร้าง version_info.txt แล้ว:", ".".join(map(str, parts)))


if __name__ == "__main__":
    main()

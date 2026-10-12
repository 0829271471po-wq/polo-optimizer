"""
restore_point.py
สร้างจุดคืนค่าระบบ (System Restore Point) ก่อนปรับแต่งเครื่อง
ถ้าปรับแล้วมีปัญหา ผู้ใช้ย้อนกลับได้ที่ Control Panel > Recovery > Open System Restore
"""

from i18n import tr
from utils import run_powershell

# -WarningVariable จับคำเตือนของ Windows ไว้ เช่นกรณีที่วันนี้เคยสร้างจุดคืนค่าไปแล้ว
# (Windows อนุญาตให้สร้างได้ 1 จุดต่อ 24 ชั่วโมง ถ้าสร้างถี่กว่านั้นจะข้ามไปเฉย ๆ)
_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
try {
  Enable-ComputerRestore -Drive "$env:SystemDrive\"
  Checkpoint-Computer -Description 'Polo Optimizer' -RestorePointType 'MODIFY_SETTINGS' -WarningVariable w -WarningAction SilentlyContinue
  if ($w) { Write-Output 'SKIPPED' } else { Write-Output 'OK' }
} catch {
  Write-Output ('ERROR:' + $_.Exception.Message)
}
"""


def create_restore_point():
    """เปิดระบบ System Restore ที่ไดรฟ์ Windows (ถ้ายังปิดอยู่) แล้วสร้างจุดคืนค่าชื่อ 'Polo Optimizer'
    คืนค่า (สำเร็จไหม, ข้อความภาษาไทยที่จะแสดงให้ผู้ใช้)
    ใช้เวลาประมาณ 10 วินาทีถึง 2 นาที เลยต้องเรียกจาก thread แยก"""
    code, out, err = run_powershell(_SCRIPT, timeout=300)
    out = out.strip()
    if out.endswith("OK"):
        return True, tr("สร้างจุดคืนค่าเรียบร้อย ถ้ามีปัญหาย้อนกลับได้", "Restore point created. You can roll back if anything goes wrong")
    if out.endswith("SKIPPED"):
        # ไม่นับเป็นความผิดพลาด เพราะมีจุดคืนค่าของวันนี้อยู่แล้ว
        return True, tr("วันนี้มีจุดคืนค่าอยู่แล้ว (Windows ให้สร้างได้วันละครั้ง) ใช้จุดเดิมได้เลย",
                       "A restore point already exists today (Windows allows one per day), so that one will be used")
    message = out.split("ERROR:", 1)[-1].strip() if "ERROR:" in out else (err.strip() or tr("ไม่ทราบสาเหตุ", "unknown reason"))
    return False, tr(f"สร้างจุดคืนค่าไม่สำเร็จ: {message[:200]}", f"Couldn't create a restore point: {message[:200]}")

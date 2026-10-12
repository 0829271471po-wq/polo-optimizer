"""
ram.py
คืน RAM ด้วย Windows API ผ่าน ctypes (ไม่ต้องลงไลบรารีเพิ่ม)
1) EmptyWorkingSet: บอกทุกโปรเซสให้ปล่อยหน่วยความจำส่วนที่ไม่ได้ใช้ออกไปก่อน
2) ล้าง Standby list: ทิ้งแคชไฟล์ที่ Windows เก็บไว้ใน RAM (NtSetSystemInformation class 80 คำสั่ง 4)

หมายเหตุที่ควรรู้ (เผื่อโดนถามตอนสัมภาษณ์): RAM ที่คืนมาเป็นผลชั่วคราว
โปรแกรมจะดึงกลับไปใช้เมื่อต้องการ วิธีนี้ช่วยได้ตอน RAM ใกล้เต็มจริง ๆ แต่ไม่ได้ทำให้เครื่องเร็วขึ้นถาวร
"""

import ctypes
from ctypes import wintypes

import psutil

from i18n import tr

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_SET_QUOTA = 0x0100
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002
ERROR_NOT_ALL_ASSIGNED = 1300

SYSTEM_MEMORY_LIST_INFORMATION = 80  # class 80 = SystemMemoryListInformation
MEMORY_PURGE_STANDBY_LIST = 4        # คำสั่ง 4 = ล้าง standby list

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_ntdll = ctypes.WinDLL("ntdll")

# กำหนดชนิดของพารามิเตอร์ให้ ctypes รู้ ไม่งั้น handle บน Windows 64 บิตอาจถูกตัดเหลือ 32 บิต
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
_psapi.EmptyWorkingSet.restype = wintypes.BOOL
_ntdll.NtSetSystemInformation.argtypes = [ctypes.c_int, ctypes.c_void_p, wintypes.ULONG]
_ntdll.NtSetSystemInformation.restype = ctypes.c_long


class _LUID(ctypes.Structure):
    """รหัสประจำสิทธิ์พิเศษของ Windows (เช่น สิทธิ์ล้างหน่วยความจำ)"""
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _LUID_AND_ATTRIBUTES(ctypes.Structure):
    """รหัสสิทธิ์ + สถานะว่าจะเปิดหรือปิดสิทธิ์นั้น"""
    _fields_ = [("Luid", _LUID), ("Attributes", wintypes.DWORD)]


class _TOKEN_PRIVILEGES(ctypes.Structure):
    """โครงสร้างที่ส่งให้ AdjustTokenPrivileges เพื่อขอเปิดสิทธิ์ 1 อย่าง"""
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", _LUID_AND_ATTRIBUTES * 1)]


_advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
_advapi32.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(_LUID)]
_advapi32.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(_TOKEN_PRIVILEGES),
                                            wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]


def _enable_privilege(name):
    """เปิดสิทธิ์พิเศษให้โปรเซสของเรา (ต้องรันแบบ Admin อยู่แล้ว ฟังก์ชันนี้แค่ 'กดเปิด' สิทธิ์ที่มีอยู่)
    - SeProfileSingleProcessPrivilege ใช้ล้าง standby list
    - SeDebugPrivilege ใช้เปิดโปรเซสของระบบเพื่อสั่ง EmptyWorkingSet ได้ครบขึ้น
    คืน True ถ้าเปิดสิทธิ์ได้"""
    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(_kernel32.GetCurrentProcess(),
                                      TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(token)):
        return False
    try:
        luid = _LUID()
        if not _advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
            return False
        tp = _TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        if not _advapi32.AdjustTokenPrivileges(token, False, ctypes.byref(tp), 0, None, None):
            return False
        return ctypes.get_last_error() != ERROR_NOT_ALL_ASSIGNED
    finally:
        _kernel32.CloseHandle(token)


def empty_working_sets():
    """วนทุกโปรเซสแล้วเรียก EmptyWorkingSet ให้ปล่อย RAM ส่วนที่ไม่ได้ใช้
    โปรเซสไหนเปิดไม่ได้ (เช่นโปรเซสที่ระบบป้องกันไว้) ก็ข้ามไป คืนจำนวนโปรเซสที่ทำสำเร็จ"""
    _enable_privilege("SeDebugPrivilege")
    done = 0
    for pid in psutil.pids():
        if pid in (0, 4):  # 0 = System Idle, 4 = System เปิดไม่ได้อยู่แล้ว
            continue
        handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SET_QUOTA, False, pid)
        if not handle:
            continue
        try:
            if _psapi.EmptyWorkingSet(handle):
                done += 1
        finally:
            _kernel32.CloseHandle(handle)
    return done


def purge_standby_list():
    """ล้าง standby list (แคชไฟล์ใน RAM) ด้วย NtSetSystemInformation
    คืน True ถ้าสำเร็จ (NTSTATUS = 0)"""
    if not _enable_privilege("SeProfileSingleProcessPrivilege"):
        return False
    command = ctypes.c_int(MEMORY_PURGE_STANDBY_LIST)
    status = _ntdll.NtSetSystemInformation(SYSTEM_MEMORY_LIST_INFORMATION, ctypes.byref(command),
                                           ctypes.sizeof(command))
    return status == 0


def clear_ram():
    """ทำทั้งสองขั้นตอนแล้ววัด RAM ว่างก่อน/หลัง คืน (สำเร็จไหม, ข้อความภาษาไทย)"""
    before = psutil.virtual_memory().available
    count = empty_working_sets()
    standby_ok = purge_standby_list()
    after = psutil.virtual_memory().available
    gained_mb = max(0, (after - before) // (1024 * 1024))
    msg = tr(f"คืน RAM แล้ว ได้คืนมาประมาณ {gained_mb:,} MB (เคลียร์ {count} โปรแกรม)",
             f"RAM freed: about {gained_mb:,} MB ({count} programs trimmed)")
    if not standby_ok:
        msg += tr(" แต่ล้างแคชระบบไม่ได้ (ต้องเปิดโปรแกรมแบบ Admin)", " but the system cache couldn't be cleared (needs Admin)")
    return True, msg

"""
health.py
คิดคะแนนสุขภาพเครื่อง 0-100 จากผลตรวจจริง แล้วบอกว่ามีเรื่องอะไรที่ควรแก้ พร้อม action ที่กดแก้ได้
เริ่มที่ 100 คะแนน แล้วหักตามปัญหาที่เจอ (หักมากน้อยตามความหนักของปัญหา)
ใช้ผลตรวจชุดเดียวกับผู้ช่วย AI (ai_assistant.collect_context)
"""

from i18n import tr

GB = 1024 ** 3


def evaluate(ctx):
    """คิดคะแนนจากผลตรวจ คืน dict
    {score: 0-100, grade: คำบอกระดับ, color: ok/warn/error, issues: [(ข้อความปัญหา, action หรือ None)]}"""
    score = 100
    issues = []
    usage = ctx.get("usage") or {}

    for d in ctx.get("disk_health") or []:
        if not d.get("healthy"):
            score -= 30
            issues.append((tr(f"ดิสก์ {d['name']} เริ่มเสีย ควรสำรองไฟล์ทันที", f"Disk {d['name']} is failing, back up your files now"), None))

    crashes = ctx.get("crashes") or {}
    if crashes.get("bsod"):
        score -= min(20, 5 * crashes["bsod"])
        issues.append((tr(f"จอฟ้า {crashes['bsod']} ครั้งใน 14 วัน", f"{crashes['bsod']} blue screen(s) in 14 days"), "open_drivers"))

    disk = usage.get("disk") or 0
    if disk > 90:
        score -= 20
        issues.append((tr(f"ไดรฟ์ Windows เต็ม {disk:.0f}% เครื่องจะช้าและอัปเดตไม่ได้", f"Windows drive {disk:.0f}% full, slows the PC and blocks updates"), "clean_junk"))
    elif disk > 80:
        score -= 8
        issues.append((tr(f"ไดรฟ์ Windows ใช้ไป {disk:.0f}% เริ่มใกล้เต็ม", f"Windows drive {disk:.0f}% full, getting close"), "clean_junk"))

    junk = ctx.get("junk_bytes") or 0
    if junk > 1 * GB:
        score -= 15 if junk > 5 * GB else 8
        issues.append((tr(f"มีไฟล์ขยะ {ctx.get('junk_size')} ที่ลบได้", f"{ctx.get('junk_size')} of junk files can be deleted"), "clean_junk"))

    ram = usage.get("ram") or 0
    if ram > 85:
        score -= 15
        issues.append((tr(f"RAM ใช้ไป {ram:.0f}% เกือบเต็ม", f"RAM {ram:.0f}% used, almost full"), "clear_ram"))

    startup_count = ctx.get("startup_count") or 0
    if startup_count > 6:
        score -= 15 if startup_count > 10 else 8
        issues.append((tr(f"มีโปรแกรมเปิดพร้อมเครื่อง {startup_count} ตัว ทำให้บูตช้า", f"{startup_count} startup apps slow down boot"), "open_startup"))

    devices = ctx.get("problem_devices") or []
    if devices:
        score -= min(20, 5 * len(devices))
        issues.append((tr(f"มีอุปกรณ์ที่มีปัญหา/ไม่มีไดรเวอร์ {len(devices)} ตัว", f"{len(devices)} device(s) with problems or no driver"), "open_drivers"))

    net = (ctx.get("network") or {}).get("verdict")
    if net in ("no_connection", "router", "isp", "dns"):
        score -= 10
        issues.append((tr("ทดสอบเน็ตแล้วใช้งานไม่ได้", "Network test failed"), "fix_network"))

    score = max(0, min(100, score))
    if score >= 90:
        grade, color = tr("ดีมาก", "Excellent"), "ok"
    elif score >= 75:
        grade, color = tr("ดี", "Good"), "ok"
    elif score >= 55:
        grade, color = tr("ควรดูแลหน่อย", "Needs attention"), "warn"
    else:
        grade, color = tr("ต้องรีบดูแล", "Needs care now"), "error"
    return {"score": score, "grade": grade, "color": color, "issues": issues}

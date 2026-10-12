"""
ui_kit.py
ชุดเครื่องมือหน้าตาที่ทุกหน้าใช้ร่วมกัน: สี, ฟอนต์, ปุ่มแบบต่าง ๆ, การ์ด, label ที่ตัดบรรทัดภาษาไทยถูก, วงแหวนเกจ
แยกออกมาจาก main.py เพื่อให้ main.py มีแค่โครงหน้าต่างกับเนื้อหาแต่ละหน้า
"""

import math
import os
import random

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from utils import resource_path

# ---------- สี ----------
# โทนดำ-น้ำเงิน: พื้นเกือบดำ ไล่ความสว่างขึ้นทีละนิดตามชั้น (พื้น < เมนู < การ์ด < ช่องในการ์ด)
# ใช้สีน้ำเงินสีเดียวเป็นสีเน้น ส่วนเขียว/เหลือง/แดง ใช้เฉพาะบอกสถานะ (สำเร็จ/เตือน/ผิดพลาด)
C = {
    "bg": "#080a0e",
    "sidebar": "#0b0e13",
    "card": "#10141b",
    "card_alt": "#161b24",
    "border": "#1b222d",
    "primary": "#2f7bff",
    "primary_hover": "#5294ff",
    "accent": "#2f7bff",
    "nav_active": "#0f1d36",
    "secondary": "#161b24",
    "secondary_hover": "#1d2430",
    "secondary_border": "#262f3d",
    "chip_border": "#1e3a66",
    "chip_text": "#8fb8ff",
    "chip_hover": "#0f1d36",
    "danger": "#d9363e",
    "danger_hover": "#ec4d55",
    "text": "#e6edf6",
    "muted": "#8a94a6",
    "faint": "#576173",
    "ok": "#3ccf7a",
    "warn": "#f0b429",
    "error": "#ff5c5c",
    "user_bubble": "#14305e",
}

FONT_FAMILY = "Leelawadee UI"
FONTS = {}

# ความกว้างสูงสุดของข้อความในการ์ด (พิกเซล) App ปรับค่านี้ตามขนาดจอตอนเปิดโปรแกรม จอเล็กข้อความจะได้ไม่ล้นการ์ด
TEXT_WIDTH = 780


def set_text_width(width):
    """ตั้งความกว้างข้อความตามขนาดหน้าต่าง (เรียกจาก App ก่อนสร้างหน้าจอ)"""
    global TEXT_WIDTH
    TEXT_WIDTH = max(420, min(780, int(width)))


def wide():
    """ความกว้างข้อความสำหรับส่วนที่กว้างกว่าการ์ดปกติ (หัวข้อหน้า, คำอธิบายใต้หัวข้อ)"""
    return min(900, TEXT_WIDTH + 120)


def init_fonts():
    """สร้างฟอนต์ทั้งหมด (ต้องเรียกหลังสร้างหน้าต่างหลักแล้ว เพราะ tkinter สร้างฟอนต์ก่อนมีหน้าต่างไม่ได้)
    ตัวอักษรไทยของ Leelawadee UI ค่อนข้างเล็ก เลยใช้ขนาดใหญ่กว่าปกติ 1 ขั้นให้อ่านง่าย"""
    FONTS.update({
        "h1": ctk.CTkFont(FONT_FAMILY, 26, "bold"),
        "h2": ctk.CTkFont(FONT_FAMILY, 18, "bold"),
        "h3": ctk.CTkFont(FONT_FAMILY, 16, "bold"),
        "body": ctk.CTkFont(FONT_FAMILY, 15),
        "small": ctk.CTkFont(FONT_FAMILY, 14),
        "tiny": ctk.CTkFont(FONT_FAMILY, 13),
        "button": ctk.CTkFont(FONT_FAMILY, 15, "bold"),
        "button_big": ctk.CTkFont(FONT_FAMILY, 17, "bold"),
        "chip": ctk.CTkFont(FONT_FAMILY, 14),
        "nav": ctk.CTkFont(FONT_FAMILY, 15, "bold"),
        "gauge": ctk.CTkFont(FONT_FAMILY, 20, "bold"),
        "score": ctk.CTkFont(FONT_FAMILY, 42, "bold"),
        "logo": ctk.CTkFont(FONT_FAMILY, 19, "bold"),
    })


# ---------- ปุ่ม ----------
# แต่ละสไตล์: (สีพื้น, สีตอนเอาเมาส์ชี้, สีขอบ, ความหนาขอบ, สีตัวอักษร)
# ปุ่มหลักสว่างขึ้นตอนชี้ (ดูมีชีวิตกว่าเข้มลง) ปุ่มรองมีขอบบาง ๆ ปุ่ม chip เป็นแคปซูลขอบสีฟ้า
BUTTON_STYLES = {
    "primary": ("primary", "primary_hover", "primary", 0, "#ffffff"),
    "secondary": ("secondary", "secondary_hover", "secondary_border", 1, "text"),
    "danger": ("danger", "danger_hover", "danger", 0, "#ffffff"),
    "chip": ("bg", "chip_hover", "chip_border", 1, "chip_text"),
}


def _color(name):
    """แปลงชื่อสี (เช่น 'primary') เป็นรหัสสี ถ้าเป็นรหัสสีอยู่แล้วคืนตามเดิม"""
    return C.get(name, name)


def make_button(parent, text, command=None, style="primary", width=200, height=42, font="button"):
    """สร้างปุ่มมุมโค้งตามสไตล์ (primary / secondary / danger / chip) และให้เคอร์เซอร์เป็นรูปมือเวลาชี้
    ถ้าข้อความขึ้นต้นด้วยอีโมจิ (เช่น "💾  สร้างจุดคืนค่า") จะเปลี่ยนอีโมจิเป็นไอคอนสีวางหน้าข้อความ"""
    fg, hover, border, border_width, text_color = BUTTON_STYLES[style]
    radius = height // 2 if style == "chip" else 10
    icon, rest = split_icon(text)
    # ไอคอนในปุ่มใช้สีเดียวกับตัวอักษรของปุ่ม จะได้ดูเป็นชิ้นเดียวกัน
    image = emoji_image(icon, 18 if height >= 38 else 15, _color(text_color)) if icon else None
    return ctk.CTkButton(parent, text=(" " + rest) if image else text, image=image, compound="left",
                         command=command, width=width, height=height, corner_radius=radius,
                         fg_color=_color(fg), hover_color=_color(hover), border_color=_color(border),
                         border_width=border_width, text_color=_color(text_color), font=FONTS[font], cursor="hand2")


def make_chip(parent, text, command):
    """ปุ่มแคปซูลเล็ก ๆ สำหรับคำถามสำเร็จรูปและคำถามต่อ"""
    return make_button(parent, text, command, style="chip", width=40, height=34, font="chip")


# ---------- ตัดบรรทัดภาษาไทยเอง ----------
# Tk ตัดบรรทัดได้แค่ตรงเว้นวรรค ภาษาไทยไม่มีเว้นวรรคระหว่างคำ เลยต้องตัดเองก่อนส่งให้ Tk
# ห้ามตัดหน้าสระบน/ล่าง/วรรณยุกต์ และห้ามแยกสระหน้า (เ แ โ ใ ไ) ออกจากพยัญชนะที่ตามมา
_THAI_ATTACH = set("ัาำิีึืฺุูๅ็่้๊๋์ํ๎")
_THAI_LEADING = set("เแโใไ")


def _can_break(word, i):
    """เช็กว่าตัดคำระหว่างตัวที่ i-1 กับตัวที่ i ได้ไหม"""
    return 0 < i < len(word) and word[i] not in _THAI_ATTACH and word[i - 1] not in _THAI_LEADING


def thai_wrap(text, font, width):
    """ตัดบรรทัดข้อความให้กว้างไม่เกิน width พิกเซล คืนข้อความที่ใส่ขึ้นบรรทัดใหม่ (\\n) แล้ว
    ตัดตรงเว้นวรรคก่อน ถ้าคำเดียวยาวเกินบรรทัด ค่อยตัดกลางคำตรงจุดที่ตัดได้"""
    if not text or width <= 0:
        return text
    lines = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split(" "):
            candidate = f"{line} {word}" if line else word
            if font.measure(candidate) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
                line = ""
            while font.measure(word) > width:
                cut = 0
                for i in range(1, len(word)):
                    if font.measure(word[:i]) > width:
                        break
                    if _can_break(word, i):
                        cut = i
                if cut == 0:
                    break  # ตัดไม่ได้เลย (เช่นคำอังกฤษยาวมาก) ปล่อยยาวเกินไป
                lines.append(word[:cut])
                word = word[cut:]
            line = word
        lines.append(line)
    return "\n".join(lines)


# ---------- กันวรรณยุกต์หลุดตอน Tk วาดข้อความยาว ----------
# Tk บน Windows วาดข้อความเป็นท่อน ท่อนละประมาณ 200 byte (UTF-8) ดูได้ใน tkWinFont.c ฟังก์ชัน MultiFontTextOut
#     if ((thisSubFontPtr != lastSubFontPtr) || (p-source > 200)) {
# ภาษาไทย 1 ตัวใช้ 3 byte ถ้าจุดตัดตกหน้าสระบน/ล่างหรือวรรณยุกต์ Windows จะวาดมันแยก กลายเป็นวงกลมประ
# วิธีแก้: จำลองจุดตัดของ Tk ไว้ก่อน ถ้าไม่ปลอดภัย ให้แทรกตัวอักษรล่องหน (zero-width space) หน้าพยัญชนะตัวนั้น
_ZWSP = "​"


def _is_symbol(ch):
    """ตัวอักษรที่ Tk น่าจะต้องยืมฟอนต์อื่นมาวาด (สัญลักษณ์และอีโมจิ) Tk จะเริ่มท่อนใหม่ตรงนั้นเสมอ"""
    return ord(ch) >= 0x2000 and ch != _ZWSP


def _tk_split_points(line):
    """จำลองว่า Tk จะตัดท่อนก่อนตัวอักษรตำแหน่งไหนบ้าง (เลียนแบบเงื่อนไขใน MultiFontTextOut)"""
    points, start, pos, prev_symbol = [], 0, 0, None
    for i, ch in enumerate(line):
        symbol = _is_symbol(ch)
        if (prev_symbol is not None and symbol != prev_symbol) or pos - start > 200:
            points.append(i)
            start = pos
        prev_symbol = symbol
        pos += len(ch.encode("utf-8"))
    return points


def tk_safe(text):
    """แก้ข้อความทุกบรรทัดให้จุดตัดท่อนของ Tk ไม่ตกหน้าสระ/วรรณยุกต์ไทย"""
    lines = []
    for line in str(text).split("\n"):
        for _ in range(50):  # กันวนไม่จบ ปกติแก้ไม่เกิน 2-3 รอบ
            bad = next((i for i in _tk_split_points(line) if line[i] in _THAI_ATTACH), None)
            if bad is None:
                break
            base = bad
            while base > 0 and line[base] in _THAI_ATTACH:
                base -= 1  # ถอยไปหาพยัญชนะที่สระ/วรรณยุกต์ตัวนี้เกาะอยู่
            if base == 0:
                break
            line = line[:base] + _ZWSP + line[base:]
        lines.append(line)
    return "\n".join(lines)


class WrapLabel(ctk.CTkLabel):
    """CTkLabel สำหรับข้อความไทย: ตัดบรรทัดเองด้วย thai_wrap() และกันวรรณยุกต์หลุดด้วย tk_safe()
    ทำทั้งตอนสร้างและตอนเปลี่ยนข้อความทีหลัง"""

    def __init__(self, master, text="", wrap=780, font=None, **kwargs):
        """wrap = ความกว้างสูงสุดของบรรทัด (พิกเซล) ส่ง 0 ถ้าไม่ต้องตัดบรรทัด"""
        self._wrap_width = wrap
        self._wrap_font = font
        super().__init__(master, text=tk_safe(thai_wrap(text, font, wrap)), font=font, wraplength=0, **kwargs)

    def configure(self, require_redraw=False, **kwargs):
        """ดักการเปลี่ยนข้อความ ให้ตัดบรรทัดและกันวรรณยุกต์หลุดใหม่ทุกครั้ง"""
        if "text" in kwargs:
            kwargs["text"] = tk_safe(thai_wrap(kwargs["text"], self._wrap_font, self._wrap_width))
        super().configure(require_redraw=require_redraw, **kwargs)


def label(parent, text, font="body", color="text", **kwargs):
    """สร้าง label ข้อความชิดซ้าย ตัดบรรทัดภาษาไทยอัตโนมัติ (wraplength = ความกว้างสูงสุด, 0 = ไม่ตัด)"""
    wrap = kwargs.pop("wraplength", None)
    return WrapLabel(parent, text=text, wrap=TEXT_WIDTH if wrap is None else wrap, font=FONTS[font],
                     text_color=_color(color), anchor="w", justify="left", **kwargs)


# ---------- การ์ดและแถวปุ่ม ----------

def make_card(parent, title=None, desc=None):
    """สร้างการ์ดมุมโค้ง ขอบบาง ๆ แบบ Windows 11 มีหัวข้อและคำอธิบาย (ถ้าส่งมา) แล้ว pack ลงหน้าให้เลย"""
    card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=16, border_width=1, border_color=C["border"])
    card.pack(fill="x", pady=(0, 14), padx=(0, 6))
    if title:
        heading(card, title, "h2", 22).pack(fill="x", padx=22, pady=(18, 0 if desc else 8))
    if desc:
        label(card, desc, "small", "muted").pack(fill="x", padx=22, pady=(2, 10))
    return card


def action_row(parent, text, desc, command, style="primary", width=220):
    """แถว "ปุ่ม + คำอธิบายสั้น ๆ ว่ากดแล้วจะเกิดอะไร" (ทุกปุ่มในโปรแกรมใช้ตัวนี้) คืนตัวปุ่ม"""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=22, pady=6)
    button = make_button(row, text, command, style, width)
    button.pack(side="left")
    label(row, desc, "small", "muted", wraplength=max(260, TEXT_WIDTH - 240)).pack(side="left", padx=16, fill="x", expand=True)
    return button


def spacer(parent, height=10):
    """ช่องว่างแนวตั้ง ใช้ปิดท้ายการ์ด"""
    ctk.CTkFrame(parent, height=height, fg_color="transparent").pack()


def clear(frame):
    """ลบ widget ทั้งหมดในกรอบ ใช้ตอนโหลดข้อมูลใหม่"""
    for child in frame.winfo_children():
        child.destroy()


# ---------- รูปภาพ ----------

def ring_image(percent, color, size=110, thickness=11):
    """วาดวงแหวนแสดงเปอร์เซ็นต์ด้วย PIL แล้วคืนเป็น CTkImage
    วาดใหญ่ 6 เท่าแล้วย่อเหลือ 2 เท่า ขอบวงจะเนียนและยังคมบนจอความละเอียดสูง ปลายเส้นวาดเป็นวงกลมให้ดูมน"""
    k = 6
    big, t = size * k, thickness * k
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    box = [t // 2, t // 2, big - t // 2 - 1, big - t // 2 - 1]
    draw.ellipse(box, outline=C["card_alt"], width=t)
    p = min(max(percent, 0), 100) / 100
    if p > 0:
        start, end = -90, -90 + 360 * p
        draw.arc(box, start, end, fill=color, width=t)
        center, radius = big / 2, (big - t) / 2
        for angle in (start, end):
            x = center + radius * math.cos(math.radians(angle))
            y = center + radius * math.sin(math.radians(angle))
            draw.ellipse([x - t / 2, y - t / 2, x + t / 2, y + t / 2], fill=color)
    img = img.resize((size * 2, size * 2), Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


def load_logo(size):
    """โหลดโลโก้ logo.png ที่แนบมากับโปรแกรม ถ้าหาไม่เจอคืน None (เมนูจะแสดงแค่ชื่อแทน)"""
    try:
        img = Image.open(resource_path("logo.png"))
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except Exception:
        return None


def _ctk_image(img, size):
    """ห่อภาพ PIL เป็น CTkImage (ส่งภาพใหญ่กว่าขนาดแสดงจริงไว้ จะได้คมบนจอความละเอียดสูง)"""
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)


# ---------- ไอคอน ----------
# ในโค้ดเขียนอีโมจินำหน้าข้อความไว้ (เช่น "💾  สร้างจุดคืนค่า") เพราะอ่านง่าย แต่ตอนแสดงผลจะแปลงเป็น
# ไอคอนเส้นบางจากฟอนต์ Segoe MDL2 Assets (ชุดไอคอนเดียวกับหน้า Settings ของ Windows) แล้วระบายสีตามที่กำหนด
# หน้าตาจะเรียบและเป็นชุดเดียวกันทั้งโปรแกรม ถ้าเครื่องไม่มีฟอนต์นี้ จะใช้อีโมจิสีจาก Segoe UI Emoji แทน
_FONT_DIR = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts")
_EMOJI_FONT = os.path.join(_FONT_DIR, "seguiemj.ttf")
_ICON_FONT = os.path.join(_FONT_DIR, "segmdl2.ttf")
_cache = {}

# อีโมจิในโค้ด -> รหัสไอคอนใน Segoe MDL2 Assets
ICONS = {
    "🏠": 0xE80F, "🤖": 0xE99A, "📦": 0xE7B8, "🔧": 0xE90F, "🛠": 0xE90F, "🧹": 0xEA99, "🎮": 0xE7FC, "🕹": 0xE7FC,
    "🚀": 0xE7E8, "🩺": 0xE95E, "✨": 0xE734, "⭐": 0xE735, "🔄": 0xE72C, "💾": 0xE74E, "⚠": 0xE7BA, "🚑": 0xE7BA,
    "🌐": 0xE774, "🔍": 0xE721, "⬇": 0xE896, "📥": 0xE896, "🧰": 0xE71D, "🧠": 0xE9F5, "📌": 0xE718, "💽": 0xEDA2,
    "⚡": 0xE945, "🧭": 0xE8FD, "🛡": 0xEA18, "💻": 0xE770, "🖥": 0xE7F4, "➤": 0xE724, "🔑": 0xE8D7, "▶": 0xE768,
    "✖": 0xE711, "🛒": 0xE719, "➕": 0xE710, "🗑": 0xE74D, "📋": 0xE8FD, "↩": 0xE7A7, "⏪": 0xE81C, "🔁": 0xE777,
    "🔒": 0xE72E, "⚙": 0xE713, "📂": 0xE838, "🧩": 0xE8F1, "📚": 0xE7BE,
}


def split_icon(text):
    """แยกอีโมจิตัวแรกออกจากข้อความ เช่น "💾  สร้างจุดคืนค่า" -> ("💾", "สร้างจุดคืนค่า") ถ้าไม่ได้ขึ้นต้นด้วยอีโมจิคืน (None, ข้อความเดิม)"""
    text = str(text or "")
    stripped = text.lstrip()
    if stripped and ord(stripped[0]) >= 0x2190 and not ("\u0e00" <= stripped[0] <= "\u0e7f"):
        icon = stripped[0]
        rest = stripped[1:].lstrip("\ufe0f").strip()
        return icon, rest
    return None, text


def emoji_image(char, size=20, color=None):
    """แปลงอีโมจิเป็นไอคอน CTkImage ขนาด size (เก็บไว้ใช้ซ้ำ)
    ถ้ามีไอคอนคู่กันใน ICONS จะวาดเป็นไอคอนเส้นสีเดียว (color, ค่าเริ่มต้นสีน้ำเงินหลัก) ถ้าไม่มีจะวาดอีโมจิสี
    ถ้าวาดไม่ได้เลยคืน None"""
    color = color or C["primary"]
    key = ("icon", char, size, color)
    if key in _cache:
        return _cache[key]
    result = None
    try:
        if char in ICONS and os.path.exists(_ICON_FONT):
            font = ImageFont.truetype(_ICON_FONT, 128)
            img = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
            ImageDraw.Draw(img).text((20, 20), chr(ICONS[char]), font=font, fill=color)
        else:
            font = ImageFont.truetype(_EMOJI_FONT, 109)
            img = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
            ImageDraw.Draw(img).text((10, 10), char, font=font, embedded_color=True)
        box = img.getbbox()
        if box:
            img = img.crop(box)
            side = max(img.width, img.height)
            square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
            result = _ctk_image(square.resize((size * 2, size * 2), Image.LANCZOS), (size, size))
    except Exception:
        result = None
    _cache[key] = result
    return result


def heading(parent, text, font="h2", icon_size=22, color="text", wraplength=None):
    """หัวข้อที่ขึ้นต้นด้วยอีโมจิ: แสดงไอคอนสี + ข้อความ (ถ้าไม่มีอีโมจิ ก็เป็น label ธรรมดา)"""
    icon, rest = split_icon(text)
    wraplength = wraplength or TEXT_WIDTH - 20
    image = emoji_image(icon, icon_size) if icon else None
    if image is None:
        return label(parent, text, font, color, wraplength=wraplength)
    row = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(row, text="", image=image).pack(side="left", padx=(0, 10))
    label(row, rest, font, color, wraplength=wraplength).pack(side="left", fill="x", expand=True)
    return row


# ---------- โลโก้แอปในหน้าติดตั้ง ----------

def letter_tile(text, color, size=128):
    """วาดไอคอนตัวอักษร: สี่เหลี่ยมมุมโค้งสีที่กำหนด + ตัวอักษรสีขาวตรงกลาง (ใช้กับแอปที่ไม่มีไฟล์โลโก้)"""
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, big - 1, big - 1], radius=big // 4, fill=color)
    try:
        font = ImageFont.truetype("seguisb.ttf", int(big * (0.42 if len(text) <= 2 else 0.32)))
    except OSError:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((big - (box[2] - box[0])) / 2 - box[0], (big - (box[3] - box[1])) / 2 - box[1]), text, font=font, fill="white")
    return img.resize((size, size), Image.LANCZOS)


def app_icon(app_id, name, size=44):
    """โลโก้แอปจาก assets/apps/<รหัสแอป>.png (ดึงมาเก็บไว้ตอน build ด้วย fetch_icons.py) ถ้าไม่มีไฟล์จะวาดตัวอักษรแรกแทน"""
    key = ("app", app_id, size)
    if key not in _cache:
        try:
            img = Image.open(resource_path(os.path.join("assets", "apps", f"{app_id}.png"))).convert("RGBA")
        except Exception:
            img = letter_tile((name or "?")[:1].upper(), "#3a4354")
        _cache[key] = _ctk_image(img.resize((size * 2, size * 2), Image.LANCZOS), (size, size))
    return _cache[key]


def badge(parent, text, kind="info"):
    """ป้ายเล็กมุมโค้ง เช่น "winget", "Microsoft Store", "ติดตั้งแล้ว" kind = info / store / ok / warn"""
    colors = {"info": ("#0f2140", "#7fb0ff"), "store": ("#16243b", "#a9c4ee"),
              "ok": ("#123d2a", C["ok"]), "warn": ("#3d3112", C["warn"])}[kind]
    return ctk.CTkLabel(parent, text=f" {text} ", font=FONTS["tiny"], fg_color=colors[0], text_color=colors[1],
                        corner_radius=6, height=22)


# ---------- ภาพแบนเนอร์ / หน้าโหลด ----------

def _font(names, size):
    """โหลดฟอนต์ตัวแรกที่มีในเครื่องจากรายการ ถ้าไม่มีสักตัวใช้ฟอนต์พื้นฐานของ Pillow"""
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _gradient_text(img, xy, text, font, colors):
    """เขียนตัวอักษร (ภาษาอังกฤษ) ที่ไล่สีจากซ้ายไปขวา ลงบนภาพ"""
    xy = (int(xy[0]), int(xy[1]))
    draw = ImageDraw.Draw(img)
    box = [int(v) for v in draw.textbbox(xy, text, font=font)]
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=font, fill=255)
    width = max(1, box[2] - box[0])
    grad = Image.new("RGBA", img.size)
    gdraw = ImageDraw.Draw(grad)
    (r1, g1, b1), (r2, g2, b2) = colors
    for x in range(box[0], box[2] + 1):
        t = (x - box[0]) / width
        gdraw.line([(x, box[1]), (x, box[3])], fill=(int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t), 255))
    img.paste(grad, (0, 0), mask)
    return box


def _space_background(w, h, seed=7):
    """พื้นหลังโทนอวกาศ: ไล่สีน้ำเงินม่วงเข้ม + แสงเรือง 2 จุด + จุดดาวเล็ก ๆ + แถบแสงเฉียง (คล้ายหน้าโหลดในรูปตัวอย่าง)"""
    px = Image.new("RGBA", (2, 2))
    px.putpixel((0, 0), (10, 22, 46, 255))
    px.putpixel((1, 0), (7, 12, 24, 255))
    px.putpixel((0, 1), (6, 9, 16, 255))
    px.putpixel((1, 1), (8, 18, 38, 255))
    img = px.resize((w, h), Image.BILINEAR)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([-w * 0.15, -h * 0.6, w * 0.45, h * 0.9], fill=(47, 123, 255, 70))
    gdraw.ellipse([w * 0.6, h * 0.3, w * 1.2, h * 1.6], fill=(30, 90, 220, 60))
    glow = glow.filter(ImageFilter.GaussianBlur(h * 0.35))
    img = Image.alpha_composite(img, glow)
    streak = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(streak).polygon([(w * 0.55, 0), (w * 0.68, 0), (w * 0.48, h), (w * 0.35, h)], fill=(255, 255, 255, 14))
    img = Image.alpha_composite(img, streak.filter(ImageFilter.GaussianBlur(12)))
    rnd = random.Random(seed)
    dots = ImageDraw.Draw(img)
    for _ in range(int(w * h / 9000)):  # ดาวน้อย ๆ พอให้มีมิติ ไม่รก
        x, y, r = rnd.uniform(0, w), rnd.uniform(0, h), rnd.choice([1, 1, 1.5, 2])
        dots.ellipse([x - r, y - r, x + r, y + r], fill=(200, 210, 255, rnd.randint(40, 140)))
    return img


def _round_corners(img, radius):
    """ทำมุมภาพให้โค้ง (นอกมุมโปร่งใส)"""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def hero_image(width, height, tagline, byline):
    """แบนเนอร์ใหญ่หน้าเริ่มต้น: พื้นอวกาศ + โลโก้ + ชื่อ POLO OPTIMIZER ไล่สี + คำโปรย
    ข้อความในภาพเป็นภาษาอังกฤษเท่านั้น เพราะ Pillow วางสระ/วรรณยุกต์ไทยได้ไม่ถูกตำแหน่ง (ข้อความไทยใช้ widget แทน)
    วาดใหญ่ 2 เท่าแล้วให้ CTkImage ย่อ ภาพจะคมบนจอความละเอียดสูง"""
    k = 2
    w, h = width * k, height * k
    img = _space_background(w, h)
    try:
        logo = Image.open(resource_path("logo.png")).convert("RGBA")
        side = int(h * 0.56)
        logo = logo.resize((side, side), Image.LANCZOS)
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).ellipse([int(w * 0.05), int(h * 0.2), int(w * 0.05) + side, int(h * 0.2) + side], fill=(47, 123, 255, 120))
        img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(40)))
        img.paste(logo, (int(w * 0.05), int((h - side) / 2)), logo)
        text_x = int(w * 0.05) + side + int(w * 0.04)
    except Exception:
        text_x = int(w * 0.06)
    title_font = _font(["seguibl.ttf", "arialbd.ttf"], int(h * 0.2))
    _gradient_text(img, (text_x, int(h * 0.2)), "POLO OPTIMIZER", title_font, ((255, 255, 255), (110, 165, 255)))
    sub_font = _font(["seguisb.ttf", "arial.ttf"], int(h * 0.075))
    draw = ImageDraw.Draw(img)
    draw.text((text_x + 4, int(h * 0.5)), tagline, font=sub_font, fill=(230, 232, 240, 255))
    small_font = _font(["seguisb.ttf", "arial.ttf"], int(h * 0.06))
    draw.text((text_x + 4, int(h * 0.66)), byline, font=small_font, fill=(120, 150, 200, 255))
    return _ctk_image(_round_corners(img, 26 * k), (width, height))


def splash_image(width, height):
    """ภาพหน้าโหลดตอนเปิดโปรแกรม: โลโก้กลางภาพ + ชื่อโปรแกรมไล่สี + คำโปรย + by Polo"""
    k = 2
    w, h = width * k, height * k
    img = _space_background(w, h, seed=3)
    draw = ImageDraw.Draw(img)
    try:
        logo = Image.open(resource_path("logo.png")).convert("RGBA")
        side = int(h * 0.3)
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([(w - side) // 2, int(h * 0.1), (w + side) // 2, int(h * 0.1) + side], fill=(47, 123, 255, 140))
        img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(45)))
        logo = logo.resize((side, side), Image.LANCZOS)
        img.paste(logo, ((w - side) // 2, int(h * 0.1)), logo)
        draw = ImageDraw.Draw(img)
    except Exception:
        pass
    title_font = _font(["seguibl.ttf", "arialbd.ttf"], int(h * 0.11))
    tw = draw.textlength("POLO OPTIMIZER", font=title_font)
    _gradient_text(img, ((w - tw) / 2, int(h * 0.45)), "POLO OPTIMIZER", title_font, ((255, 255, 255), (110, 165, 255)))
    sub_font = _font(["consolab.ttf", "seguisb.ttf"], int(h * 0.045))
    for text, y, color in [("PC CARE  •  GAME BOOST  •  AI HELPER", 0.62, (232, 234, 242)), ("BY POLO", 0.69, (120, 150, 200))]:
        draw.text(((w - draw.textlength(text, font=sub_font)) / 2, int(h * y)), text, font=sub_font, fill=color)
    return _ctk_image(_round_corners(img, 30 * k), (width, height))


def number_badge(number, size=34):
    """วงกลมไล่สีม่วง-น้ำเงินพร้อมตัวเลข ใช้ในขั้นตอนวิธีใช้งาน"""
    key = ("num", number, size)
    if key not in _cache:
        k = 4
        s = size * k
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        grad = Image.new("RGBA", (s, s))
        gdraw = ImageDraw.Draw(grad)
        for y in range(s):
            t = y / s
            gdraw.line([(0, y), (s, y)], fill=(int(70 - 40 * t), int(140 - 60 * t), int(255 - 35 * t), 255))
        mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, s - 1, s - 1], fill=255)
        img.paste(grad, (0, 0), mask)
        draw = ImageDraw.Draw(img)
        font = _font(["seguibl.ttf", "arialbd.ttf"], int(s * 0.55))
        text = str(number)
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((s - (box[2] - box[0])) / 2 - box[0], (s - (box[3] - box[1])) / 2 - box[1]), text, font=font, fill="white")
        _cache[key] = _ctk_image(img.resize((size * 2, size * 2), Image.LANCZOS), (size, size))
    return _cache[key]

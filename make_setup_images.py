"""
make_setup_images.py
วาดรูปตกแต่งหน้าตัวติดตั้ง (Setup.exe) ให้เป็นโทนน้ำเงิน-ดำเหมือนในโปรแกรม (ใช้แค่ตอนสร้างตัวติดตั้ง)
- wizard.bmp / wizard@2x.bmp: รูปแนวตั้งด้านซ้ายของหน้าแรกและหน้าสุดท้าย (164x314 และขนาด 2 เท่าสำหรับจอความละเอียดสูง)
- small.bmp / small@2x.bmp: โลโก้เล็กมุมขวาบนของหน้าอื่น ๆ (55x55)
Inno Setup ต้องการไฟล์ .bmp เลยบันทึกเป็น bmp
"""

import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets", "setup")


def _font(names, size):
    """โหลดฟอนต์ตัวแรกที่มีในเครื่อง"""
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wizard_image(w, h):
    """รูปแนวตั้ง: พื้นไล่น้ำเงินเข้ม-ดำ + แสงเรืองสีน้ำเงิน + โลโก้ + ชื่อโปรแกรม"""
    top, bottom = (12, 30, 66), (6, 8, 14)
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        draw.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([-w * 0.4, h * 0.12, w * 1.4, h * 0.62], fill=(47, 123, 255, 90))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(w * 0.25)))
    logo = Image.open(os.path.join(HERE, "logo.png")).convert("RGBA")
    side = int(w * 0.55)
    logo = logo.resize((side, side), Image.LANCZOS)
    img.paste(logo, ((w - side) // 2, int(h * 0.22)), logo)
    draw = ImageDraw.Draw(img)
    for text, y, size, color in [("POLO", 0.56, 0.17, (255, 255, 255)), ("OPTIMIZER", 0.64, 0.105, (120, 170, 255)),
                                 ("PC CARE  •  GAME BOOST", 0.88, 0.055, (130, 145, 170))]:
        font = _font(["seguibl.ttf", "arialbd.ttf"] if size > 0.1 else ["seguisb.ttf", "arial.ttf"], int(w * size))
        tw = draw.textlength(text, font=font)
        draw.text(((w - tw) / 2, int(h * y)), text, font=font, fill=color)
    return img.convert("RGB")


def small_image(s):
    """โลโก้เล็กบนพื้นขาว (หน้าตัวติดตั้งช่วงกลางเป็นพื้นขาว)"""
    img = Image.new("RGB", (s, s), (255, 255, 255))
    logo = Image.open(os.path.join(HERE, "logo.png")).convert("RGBA").resize((s, s), Image.LANCZOS)
    img.paste(logo, (0, 0), logo)
    return img


def main():
    """สร้างรูปทั้งหมดลง assets/setup"""
    os.makedirs(OUT, exist_ok=True)
    wizard_image(164, 314).save(os.path.join(OUT, "wizard.bmp"))
    wizard_image(328, 628).save(os.path.join(OUT, "wizard@2x.bmp"))
    small_image(55).save(os.path.join(OUT, "small.bmp"))
    small_image(110).save(os.path.join(OUT, "small@2x.bmp"))
    # เขียนเลขเวอร์ชันจาก main.py (APP_VERSION) ไว้ให้ build_setup.bat อ่านไปตั้งชื่อไฟล์ตัวติดตั้ง
    with open(os.path.join(HERE, "main.py"), encoding="utf-8") as f:
        version = re.search(r'APP_VERSION = "([^"]+)"', f.read()).group(1)
    with open(os.path.join(OUT, "version.txt"), "w", encoding="ascii") as f:
        f.write(version)
    print(f"สร้างรูปตัวติดตั้งแล้ว (เวอร์ชัน {version})")


if __name__ == "__main__":
    main()

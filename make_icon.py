"""
make_icon.py
วาดโลโก้ Polo Optimizer: ตัว P สีขาวบนพื้นสี่เหลี่ยมมุมโค้งไล่สีน้ำเงิน และสายฟ้าสีฟ้าอ่อนข้าง ๆ (สื่อว่าทำให้เครื่องแรงขึ้น)
สร้าง 2 ไฟล์: icon.ico (ไอคอนของ .exe และหน้าต่าง) และ logo.png (โลโก้ในเมนูซ้าย)
build.bat เรียกไฟล์นี้อัตโนมัติถ้ายังไม่มีไฟล์โลโก้ ใช้แค่ตอน build ไม่ได้อยู่ใน .exe
"""

from PIL import Image, ImageDraw, ImageFilter

# วาดที่ขนาดใหญ่ 1024 แล้วค่อยย่อ ขอบจะเนียนไม่เป็นขั้นบันได
S = 1024


def _gradient(size, start, end):
    """สร้างภาพไล่สีแนวทแยง จากมุมซ้ายบน (start) ไปมุมขวาล่าง (end)"""
    small = Image.new("RGB", (64, 64))
    px = small.load()
    for y in range(64):
        for x in range(64):
            t = (x + y) / 126
            px[x, y] = tuple(int(start[i] + (end[i] - start[i]) * t) for i in range(3))
    return small.resize((size, size), Image.BICUBIC)


def _p_mask():
    """วาดตัว P แบบเรขาคณิตเป็น mask (ขาว = ตัวอักษร)
    ประกอบจาก 3 ส่วน: ก้านตั้ง, หัวโค้ง และรูตรงกลางหัว (ระบายดำเพื่อเจาะรู)"""
    mask = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([292, 214, 446, 812], radius=46, fill=255)        # ก้านตั้ง
    d.rounded_rectangle([292, 214, 752, 628], radius=207, fill=255)       # หัวโค้ง
    d.rectangle([292, 214, 520, 628], fill=255)                           # ทำมุมซ้ายของหัวให้เหลี่ยมต่อกับก้าน
    d.rounded_rectangle([446, 344, 622, 498], radius=77, fill=0)          # รูกลางหัว P
    return mask


def _bolt_points(scale=1.0, dx=0, dy=0):
    """จุดของรูปสายฟ้า (ปรับขนาด/เลื่อนได้)"""
    pts = [(700, 520), (548, 730), (640, 730), (590, 880), (770, 646), (676, 646), (744, 520)]
    return [(x * scale + dx, y * scale + dy) for x, y in pts]


def draw_logo():
    """วาดโลโก้ขนาด 1024x1024 คืนเป็นภาพ RGBA"""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # พื้นหลังมุมโค้งแบบไอคอน Windows 11 ไล่สีน้ำเงินสว่าง -> น้ำเงินเข้ม
    bg_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(bg_mask).rounded_rectangle([24, 24, S - 24, S - 24], radius=230, fill=255)
    img.paste(_gradient(S, (64, 140, 255), (18, 64, 200)), (0, 0), bg_mask)

    # แสงสะท้อนจาง ๆ มุมซ้ายบน ให้ดูมีมิติ
    glow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(glow).ellipse([-260, -320, 700, 520], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    glow = Image.composite(glow, Image.new("L", (S, S), 0), bg_mask)
    img.paste(Image.new("RGBA", (S, S), (255, 255, 255, 255)), (0, 0), glow)

    # เงาใต้ตัว P และสายฟ้า
    p_mask = _p_mask()
    bolt_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(bolt_mask).polygon(_bolt_points(), fill=255)
    shadow = Image.new("L", (S, S), 0)
    shadow.paste(p_mask, (10, 22))
    shadow.paste(255, (10, 22), bolt_mask.crop((0, 0, S - 10, S - 22)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.35))
    shadow = Image.composite(shadow, Image.new("L", (S, S), 0), bg_mask)
    img.paste(Image.new("RGBA", (S, S), (4, 16, 48, 255)), (0, 0), shadow)

    # ตัว P สีขาว และสายฟ้าสีฟ้าอ่อน (มีขอบสีพื้นบาง ๆ แยกออกจากตัว P)
    img.paste(Image.new("RGBA", (S, S), (255, 255, 255, 255)), (0, 0), p_mask)
    outline = bolt_mask.filter(ImageFilter.MaxFilter(25))
    img.paste(_gradient(S, (64, 140, 255), (18, 64, 200)).convert("RGBA"), (0, 0),
              Image.composite(outline, Image.new("L", (S, S), 0), p_mask))
    bolt_color = Image.new("RGBA", (S, S), (150, 210, 255, 255))
    img.paste(bolt_color, (0, 0), bolt_mask)
    return img


def make_icon(ico_path="icon.ico", png_path="logo.png"):
    """บันทึก icon.ico (มีหลายขนาดในไฟล์เดียว Windows เลือกขนาดที่เหมาะเอง) และ logo.png ขนาด 256"""
    logo = draw_logo()
    small = logo.resize((256, 256), Image.LANCZOS)
    small.save(png_path)
    small.save(ico_path, sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    make_icon()
    print("สร้าง icon.ico และ logo.png แล้ว")

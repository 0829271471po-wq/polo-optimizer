"""
fetch_icons.py
ดึงโลโก้ของแอปในหน้าติดตั้งแอปมาเก็บไว้ที่ assets/apps/<รหัสแอป>.png (ใช้แค่ตอน build ไม่ได้อยู่ใน .exe)
- ลองจากชุดไอคอน dashboard-icons (ผ่าน cdn.jsdelivr.net) ก่อน เพราะเป็น PNG คมชัด
- ถ้าไม่มี ลอง favicon ของเว็บแอปนั้นผ่าน icons.duckduckgo.com
- ไลบรารีที่ไม่มีโลโก้ชัด ๆ (Visual C++, DirectX, .NET, WebView2) หรือดึงไม่ได้ จะวาดไอคอนตัวอักษรตามสีของแอปแทน
ตอนเปิดโปรแกรมจริง จะใช้ไฟล์ที่เก็บไว้นี้ ไม่มีการดึงอะไรจากเน็ต
"""

import io
import os
import re
import urllib.request

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "apps")
SIZE = 128
# ชุดไอคอนเดียวกันอยู่ 2 ที่ (ย้ายบ้านไป homarr-labs แล้ว แต่ของเก่ายังอยู่) ลองทั้งคู่
CDNS = ["https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/{}.png",
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/{}.png"]
FAVICONS = ["https://icons.duckduckgo.com/ip3/{}.ico", "https://{}/favicon.ico"]

# รหัสแอป -> (ชื่อไฟล์ใน dashboard-icons ที่จะลอง, โดเมนสำหรับ favicon)
SOURCES = {
    "Google.Chrome": (["google-chrome", "chrome"], "google.com"),
    "XPFCC4CD725961": (["line"], "line.me"),
    "7zip.7zip": (["7-zip", "7zip"], "7-zip.org"),
    "VideoLAN.VLC": (["vlc", "vlc-media-player", "videolan"], "www.videolan.org"),
    "Adobe.Acrobat.Reader.64-bit": (["adobe-acrobat-reader", "adobe-acrobat", "acrobat", "adobe-reader"], "www.adobe.com"),
    "Google.GoogleDrive": (["google-drive"], "drive.google.com"),
    "Valve.Steam": (["steam"], "store.steampowered.com"),
    "EpicGames.EpicGamesLauncher": (["epic-games", "epic-games-store"], "epicgames.com"),
    "Garena.Garena": (["garena"], "garena.com"),
    "Discord.Discord": (["discord"], "discord.com"),
    "OBSProject.OBSStudio": (["obs-studio", "obs"], "obsproject.com"),
    "Zoom.Zoom": (["zoom"], "zoom.us"),
    "Microsoft.Teams": (["microsoft-teams", "teams"], "teams.microsoft.com"),
    "TheDocumentFoundation.LibreOffice": (["libreoffice"], "libreoffice.org"),
    "Canva.Canva": (["canva"], "canva.com"),
    "ByteDance.CapCut": (["capcut"], "capcut.com"),
    "Spotify.Spotify": (["spotify"], "spotify.com"),
}

# โลโก้ที่ต้องวางบนพื้นขาวเสมอ (ตัวหนังสือสีดำ แต่ตรวจอัตโนมัติไม่เจอเพราะมีพื้นขาวบางส่วน)
FORCE_PLATE = {"7zip.7zip"}

# ไอคอนที่วาดเอง: รหัสแอป -> (ตัวอักษร, สีพื้น)
TILES = {
    "Microsoft.VCRedist.2015+.x64": ("C++", "#68217A"),
    "Microsoft.VCRedist.2015+.x86": ("C++", "#865AB0"),
    "Microsoft.DirectX": ("DX", "#107C10"),
    "Microsoft.DotNet.DesktopRuntime.8": (".NET", "#512BD4"),
    "Microsoft.EdgeWebView2Runtime": ("WV2", "#0C7BD8"),
}


def _download(url):
    """โหลดไฟล์จาก url คืน bytes หรือ None ถ้าไม่สำเร็จ"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status == 200:
                return resp.read()
    except Exception:
        return None
    return None


def _to_png(data, force_plate=False):
    """แปลงรูป (png/ico) เป็นภาพสี่เหลี่ยมจัตุรัสขนาด SIZE พื้นโปร่งใส ถ้ารูปเล็กเกินไป (ต่ำกว่า 32) ถือว่าใช้ไม่ได้"""
    try:
        img = Image.open(io.BytesIO(data))
        if getattr(img, "n_frames", 1) > 1 or img.format == "ICO":
            # ไฟล์ .ico มีหลายขนาด เลือกขนาดใหญ่สุด
            sizes = sorted(img.info.get("sizes", {img.size}), reverse=True)
            if sizes:
                img.size = sizes[0]
        img = img.convert("RGBA")
    except Exception:
        return None
    if img.width < 32:
        return None
    bbox = img.getchannel("A").getbbox()
    if bbox:
        img = img.crop(bbox)  # ตัดขอบโปร่งใสออก โลโก้จะได้เต็มกรอบ
    dark = force_plate or _is_dark(img)
    inner = int(SIZE * (0.72 if dark else 1.0))
    scale = inner / max(img.width, img.height)
    # ขยาย/ย่อให้เต็มกรอบ (favicon มักมีขนาดแค่ 32 ต้องขยายขึ้น)
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    if dark:
        # โลโก้สีมืด (เช่น 7-Zip, LibreOffice) จะมองไม่เห็นบนพื้นมืดของโปรแกรม เลยวางบนแผ่นสีขาวมุมโค้ง
        ImageDraw.Draw(canvas).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=SIZE // 4, fill="#f4f6fa")
    canvas.paste(img, ((SIZE - img.width) // 2, (SIZE - img.height) // 2), img)
    return canvas


def _is_dark(img):
    """เช็กว่าโลโก้ส่วนใหญ่เป็นสีมืดไหม (ดูความสว่างเฉลี่ยของจุดที่ไม่โปร่งใส)"""
    small = img.resize((32, 32))
    pixels = [(r, g, b) for r, g, b, a in (small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()) if a > 128]
    if not pixels:
        return False
    brightness = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels) / len(pixels)
    return brightness < 70


def make_tile(text, color, size=SIZE):
    """วาดไอคอนตัวอักษร: สี่เหลี่ยมมุมโค้งสีของแอป + ตัวอักษรสีขาวตรงกลาง (ใช้กับแอปที่ไม่มีโลโก้)"""
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, big - 1, big - 1], radius=big // 4, fill=color)
    font_size = int(big * (0.42 if len(text) <= 2 else 0.32))
    try:
        font = ImageFont.truetype("seguisb.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), text, font=font)
    x = (big - (box[2] - box[0])) / 2 - box[0]
    y = (big - (box[3] - box[1])) / 2 - box[1]
    draw.text((x, y), text, font=font, fill="white")
    return img.resize((size, size), Image.LANCZOS)


def main():
    """ดึง/วาดไอคอนของทุกแอป แล้วบอกว่าแต่ละตัวได้มาจากไหน"""
    os.makedirs(OUT_DIR, exist_ok=True)
    for app_id, (text, color) in TILES.items():
        make_tile(text, color).save(os.path.join(OUT_DIR, f"{app_id}.png"))
        print("tile    ", app_id)
    for app_id, (names, domain) in SOURCES.items():
        img, source = None, ""
        for url in [cdn.format(n) for n in names for cdn in CDNS] + [f.format(domain) for f in FAVICONS]:
            data = _download(url)
            img = _to_png(data, app_id in FORCE_PLATE) if data else None
            if img:
                source = url.split("/")[2] + " " + url.rsplit("/", 1)[-1]
                break
        if img is None:
            letter = re.sub(r"[^A-Za-z0-9]", "", app_id.split(".")[-1])[:1].upper() or "?"
            img, source = make_tile(letter, "#3a4354"), "tile (ดึงไม่ได้)"
        img.save(os.path.join(OUT_DIR, f"{app_id}.png"))
        print(f"{source:28}", app_id)


if __name__ == "__main__":
    main()

"""
main.py
ไฟล์หลักของ Polo Optimizer: สร้างหน้าต่าง เมนูด้านซ้าย หน้าเนื้อหา 8 หน้า และแถบสถานะด้านล่าง
ไฟล์นี้ดูแลแค่ "หน้าตา" งานจริงทุกอย่างเรียกจากไฟล์อื่น (cleaner.py, installer.py ฯลฯ)
ส่วนสี ฟอนต์ ปุ่ม และตัวตัดบรรทัดภาษาไทย อยู่ใน ui_kit.py

หลักการที่ใช้ทั้งไฟล์
1) งานที่ใช้เวลานาน (อ่านสเปก, ติดตั้งแอป, ลบไฟล์) รันใน thread แยกผ่าน App.run_task() หน้าต่างจะไม่ค้าง
2) thread แยกห้ามแตะ widget ตรง ๆ (tkinter ไม่รองรับ) ต้องส่งงานผ่าน App.ui() เข้าคิว
   แล้ว main thread จะดึงงานจากคิวไปทำทุก 50 มิลลิวินาทีด้วย .after()
3) ทุก error ถูกจับไว้แล้วแสดงในแถบสถานะด้านล่าง โปรแกรมจะไม่เด้งปิด
4) ข้อความทุกจุดเขียนคู่ไทย/อังกฤษด้วย tr() ถ้าผู้ใช้เปลี่ยนภาษา จะสร้างหน้าจอใหม่ทั้งหมดด้วยภาษาใหม่
"""

import ctypes
import ctypes.wintypes
import os
import queue
import sys
import threading
import traceback
from tkinter import messagebox

import customtkinter as ctk

import ui_kit

import ai_assistant
import cleaner
import config
import drivers
import game_tweaks
import health
import i18n
import installer
import ram
import restore_point
import startup
import system_info
import troubleshoot
from i18n import tr, tx
from ui_kit import (C, FONTS, init_fonts, make_button, make_chip, make_card, action_row, label, spacer, clear,
                    ring_image, load_logo, WrapLabel, heading, emoji_image, split_icon, app_icon, badge,
                    hero_image, splash_image, number_badge, wide, set_text_width)
from utils import format_size, is_admin, relaunch_as_admin, resource_path, open_url, open_system_tool

APP_NAME = "Polo Optimizer"
APP_VERSION = "1.3"
# ข้อมูลเจ้าของโปรแกรม แสดงในหน้าเริ่มต้นและหน้าโหลด (แก้ตรงนี้ที่เดียว)
APP_AUTHOR = ("โปสรินท์ สุขดี (Polo)", "Polo (โปสรินท์ สุขดี)")
APP_AUTHOR_DETAIL = ("นักเรียนชั้น ม.6 โรงเรียนอยุธยาวิทยาลัย", "Grade 12 student, Ayutthaya Wittayalai School")


# ---------- เมนูด้านซ้าย ----------

class NavItem(ctk.CTkFrame):
    """ปุ่มเมนูด้านซ้าย 1 อัน มีแถบสีบอกหน้าที่เปิดอยู่ + ชื่อหน้า + คำอธิบายสั้น ๆ ใต้ชื่อ"""

    def __init__(self, master, title, desc, command, compact=False):
        """สร้างปุ่มเมนู และผูกการคลิก/เอาเมาส์ชี้ ให้ทั้งกรอบและข้อความข้างใน
        ถ้าชื่อขึ้นต้นด้วยอีโมจิ จะแสดงเป็นไอคอนเส้นด้านซ้ายแทน (เทาตอนปกติ ฟ้าตอนเป็นหน้าที่เปิดอยู่)"""
        super().__init__(master, fg_color="transparent", corner_radius=10, cursor="hand2")
        self.active = False
        self.command = command
        self.icon_label = None
        self.bar = ctk.CTkFrame(self, width=4, height=30, corner_radius=2, fg_color="transparent")
        self.bar.pack(side="left", padx=(6, 0))
        icon, title_text = split_icon(title)
        self.icons = (emoji_image(icon, 20, C["muted"]), emoji_image(icon, 20, C["primary"]), emoji_image(icon, 20, C["text"])) if icon else None
        image = self.icons[0] if self.icons else None
        icon_label = ctk.CTkLabel(self, text="", image=image, width=30, cursor="hand2") if image else None
        self.icon_label = icon_label
        if icon_label:
            icon_label.pack(side="left", padx=(10, 0))
            title = title_text
        text_box = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        text_box.pack(side="left", fill="x", expand=True)
        self.title = ctk.CTkLabel(text_box, text=title, font=FONTS["nav"], text_color=C["muted"], anchor="w", cursor="hand2")
        self.title.pack(fill="x", padx=10, pady=(5, 0))
        self.desc = ctk.CTkLabel(text_box, text=desc, font=FONTS["tiny"], text_color=C["faint"], anchor="w", cursor="hand2")
        if not compact:  # จอเตี้ยไม่แสดงคำอธิบายใต้ชื่อ เมนูจะได้ไม่ล้นจอ
            self.desc.pack(fill="x", padx=10, pady=(0, 5))
        else:
            self.title.pack_configure(pady=(7, 7))
        for widget in (self, self.bar, text_box, self.title, self.desc) + ((icon_label,) if icon_label else ()):
            widget.bind("<Button-1>", lambda _e: self.command())
            widget.bind("<Enter>", lambda _e: self._hover(True))
            widget.bind("<Leave>", self._on_leave)

    def _on_leave(self, _event):
        """ตอนเมาส์ออก เช็กก่อนว่าออกจากปุ่มจริง ไม่ได้แค่ย้ายไปอยู่บนข้อความข้างใน"""
        x, y = self.winfo_pointerxy()
        widget = self.winfo_containing(x, y)
        if widget is None or not str(widget).startswith(str(self)):
            self._hover(False)

    def _hover(self, on):
        """เปลี่ยนสีพื้นและสีตัวอักษรตอนเอาเมาส์ชี้ (ถ้าเป็นหน้าที่เปิดอยู่จะคงสีเดิม)"""
        if not self.active:
            self.configure(fg_color=C["card"] if on else "transparent")
            self.title.configure(text_color=C["text"] if on else C["muted"])
            if self.icon_label:
                self.icon_label.configure(image=self.icons[2] if on else self.icons[0])

    def set_active(self, active):
        """ไฮไลต์หน้าที่เปิดอยู่: พื้นน้ำเงินเข้ม แถบสีหลักด้านซ้าย และตัวอักษรสีขาว"""
        self.active = active
        self.configure(fg_color=C["nav_active"] if active else "transparent")
        self.bar.configure(fg_color=C["primary"] if active else "transparent")
        self.title.configure(text_color="#ffffff" if active else C["muted"])
        self.desc.configure(text_color="#8fa9d6" if active else C["faint"])
        if self.icon_label:
            self.icon_label.configure(image=self.icons[1] if active else self.icons[0])


# ---------- หน้าพื้นฐาน ----------

class Page(ctk.CTkScrollableFrame):
    """แม่แบบของทุกหน้า (เลื่อนขึ้นลงได้) มีหัวข้อและคำอธิบายหน้าอยู่ด้านบน
    title/subtitle เป็น tuple (ไทย, อังกฤษ) หน้าลูกเขียนเนื้อหาใน build() และเขียน on_show() ถ้าต้องโหลดข้อมูล"""
    title = ("", "")
    subtitle = ("", "")

    def __init__(self, master, app):
        """สร้างหน้า ใส่หัวข้อ แล้วเรียก build() ของหน้าลูก"""
        super().__init__(master, fg_color=C["bg"], scrollbar_button_color=C["card_alt"],
                         scrollbar_button_hover_color=C["secondary_hover"])
        self.app = app
        self.loaded = False
        if self.title[0]:
            heading(self, tx(self.title), "h1", 32, wraplength=wide() - 40).pack(fill="x", pady=(4, 0))
            label(self, tx(self.subtitle), "body", "muted", wraplength=wide()).pack(fill="x", pady=(2, 18))
        self.build()

    def build(self):
        """หน้าลูกเขียนทับเพื่อสร้าง widget ของตัวเอง"""

    def on_show(self):
        """ถูกเรียกทุกครั้งที่ผู้ใช้เปิดหน้านี้ หน้าลูกเขียนทับถ้าต้องโหลดข้อมูล"""

    def safe_open(self, func):
        """ห่อฟังก์ชันเปิดหน้าต่าง/เว็บ ให้ error ไปโผล่ที่แถบสถานะแทนที่จะทำให้โปรแกรมพัง"""
        def wrapper():
            try:
                func()
                self.app.set_status(tr("เปิดให้แล้ว", "Opened"), "ok")
            except Exception as e:
                self.app.report_error(e, tr("เปิดไม่ได้", "Couldn't open"))
        return wrapper


# ================================================================
# 0) หน้าเริ่มต้น (แนะนำโปรแกรม + วิธีใช้ + ผู้พัฒนา)
# ================================================================

class WelcomePage(Page):
    """หน้าแรกสุด: แบนเนอร์ชื่อโปรแกรม, บอกว่าเป็นโปรแกรมของใคร, วิธีใช้งาน 4 ขั้นตอน, ฟีเจอร์ทั้งหมด และคำสัญญาเรื่องความปลอดภัย"""
    title = ("", "")      # หน้านี้ใช้แบนเนอร์แทนหัวข้อปกติ
    subtitle = ("", "")

    def build(self):
        """สร้างทุกส่วนของหน้าเริ่มต้น เรียงจากบนลงล่าง"""
        hero_w = min(930, ui_kit.TEXT_WIDTH + 150)  # จอแคบให้แบนเนอร์แคบลงตาม (สัดส่วนเดิม)
        hero = hero_image(hero_w, int(hero_w * 270 / 930), "PC CARE  •  GAME BOOST  •  AI HELPER", f"Made by Polo  •  v{APP_VERSION}")
        ctk.CTkLabel(self, text="", image=hero).pack(anchor="w", pady=(2, 14), padx=(0, 6))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=(0, 14), padx=(0, 6))
        row.grid_columnconfigure(0, weight=3, uniform="welcome")
        row.grid_columnconfigure(1, weight=2, uniform="welcome")
        self._intro_card(row).grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self._author_card(row).grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        self._steps_card()
        self._features_card()
        self._safety_card()
        label(self, tr(f"© 2026 {APP_NAME}  •  {tx(APP_AUTHOR)}  •  เวอร์ชัน {APP_VERSION}",
                       f"© 2026 {APP_NAME}  •  {tx(APP_AUTHOR)}  •  version {APP_VERSION}"), "tiny", "faint", wraplength=0).pack(pady=(4, 16))

    def _intro_card(self, parent):
        """การ์ด "Polo Optimizer คืออะไร" พร้อมปุ่มเริ่มใช้งาน 2 ปุ่ม"""
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=16, border_width=1, border_color=C["border"])
        heading(card, tr("✨ Polo Optimizer คืออะไร", "✨ What is Polo Optimizer?"), "h2", 24, wraplength=int(ui_kit.TEXT_WIDTH * 0.55)).pack(fill="x", padx=22, pady=(18, 6))
        label(card, tr("โปรแกรมดูแลคอม Windows ที่รวมทุกอย่างไว้ในที่เดียว ทั้งตรวจสุขภาพเครื่อง ล้างไฟล์ขยะ ลงแอปและไดรเวอร์ "
                       "ปรับเครื่องให้เล่นเกมลื่น และมีผู้ช่วย AI ที่ตรวจเครื่องจริงก่อนตอบ ทำมาให้คนที่ใช้คอมไม่เก่งกดใช้ได้เองทุกปุ่ม "
                       "ทุกปุ่มบอกไว้ว่ากดแล้วจะเกิดอะไร และทุกอย่างที่ปรับย้อนกลับได้",
                       "An all-in-one Windows care app: health check, junk cleanup, apps and drivers, smoother gaming, and an AI "
                       "assistant that checks your PC before answering. Built so anyone can use every button: each one explains "
                       "what it does, and every change can be undone."),
              "body", "muted", wraplength=int(ui_kit.TEXT_WIDTH * 0.55)).pack(fill="x", padx=22, pady=(0, 14))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=22, pady=(0, 6))
        make_button(buttons, tr("🩺  เริ่มตรวจเครื่องเลย", "🩺  Check my PC"), lambda: self.app.show_page("home"),
                    width=210, height=46, font="button_big").pack(side="left")
        make_button(buttons, tr("🤖  ถามผู้ช่วย AI", "🤖  Ask the AI"), lambda: self.app.show_page("ai"),
                    style="secondary", width=180, height=46).pack(side="left", padx=10)
        label(card, tr("ปุ่มแรกพาไปหน้าแรกที่ให้คะแนนสุขภาพเครื่อง ปุ่มที่สองพาไปคุยกับผู้ช่วย AI",
                       "The first button opens the health score, the second opens the AI chat"),
              "tiny", "muted", wraplength=int(ui_kit.TEXT_WIDTH * 0.55)).pack(fill="x", padx=22, pady=(6, 18))
        return card

    def _author_card(self, parent):
        """การ์ดผู้พัฒนา: โลโก้ ชื่อเจ้าของโปรแกรม และรายละเอียด"""
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=16, border_width=1, border_color=C["border"])
        label(card, tr("ผู้พัฒนา", "DEVELOPER"), "tiny", "chip_text", wraplength=0).pack(anchor="w", padx=22, pady=(18, 8))
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=22)
        logo = load_logo(64)
        if logo:
            ctk.CTkLabel(top, text="", image=logo).pack(side="left", padx=(0, 14))
        names = ctk.CTkFrame(top, fg_color="transparent")
        names.pack(side="left", fill="x", expand=True)
        label(names, tx(APP_AUTHOR), "h2", wraplength=int(ui_kit.TEXT_WIDTH * 0.28)).pack(fill="x")
        label(names, tx(APP_AUTHOR_DETAIL), "small", "muted", wraplength=int(ui_kit.TEXT_WIDTH * 0.28)).pack(fill="x")
        info = ctk.CTkFrame(card, fg_color=C["card_alt"], corner_radius=12)
        info.pack(fill="x", padx=22, pady=(16, 18))
        for key, value in [(tr("โปรแกรม", "App"), f"{APP_NAME} v{APP_VERSION}"),
                           (tr("เจ้าของ", "Owner"), tx(APP_AUTHOR)),
                           (tr("สร้างด้วย", "Built with"), "Python • customtkinter • psutil"),
                           (tr("รองรับ", "Runs on"), "Windows 10 / 11")]:
            line = ctk.CTkFrame(info, fg_color="transparent")
            line.pack(fill="x", padx=14, pady=3)
            label(line, key, "small", "muted", wraplength=0, width=90).pack(side="left")
            label(line, value, "small", wraplength=230).pack(side="left", fill="x", expand=True)
        spacer(info, 4)
        return card

    def _steps_card(self):
        """การ์ดวิธีใช้งาน 4 ขั้นตอน เรียงเป็น 4 คอลัมน์ มีวงกลมตัวเลขไล่สี"""
        card = make_card(self, tr("🧭 เริ่มใช้งานใน 4 ขั้นตอน", "🧭 Get started in 4 steps"))
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=22, pady=(0, 18))
        steps = [
            ("🏠", ("ตรวจเครื่อง", "Check your PC"),
             ("เปิดหน้าแรก ดูคะแนนสุขภาพเครื่องและรายการปัญหาที่เจอ กด \"แก้เลย\" ทีละข้อได้", "Open Home to see the health score and issues. Press \"Fix\" on each")),
            ("✨", ("ดูแลคลิกเดียว", "One-click care"),
             ("กด \"ดูแลเครื่องคลิกเดียว\" โปรแกรมสร้างจุดคืนค่าให้ก่อน แล้วล้างขยะ คืน RAM และปรับค่าเล่นเกม", "Press \"One-click care\". A restore point is made first, then junk, RAM and gaming tweaks")),
            ("🤖", ("มีปัญหา ถาม AI", "Ask the AI"),
             ("เล่าอาการด้วยคำของคุณเอง ผู้ช่วยตรวจเครื่องจริงแล้วแนะนำ กดปุ่ม \"ทำเลย\" เพื่อแก้", "Describe the problem in your words. The assistant checks your PC and offers \"Do it\" buttons")),
            ("📦", ("ลงแอปและไดรเวอร์", "Apps and drivers"),
             ("ติ๊กแอปที่ต้องการแล้วกดติดตั้งทีเดียว และดูหน้าไดรเวอร์ว่ามีอุปกรณ์ไหนขาดไดรเวอร์", "Tick apps and install them at once, and check the Drivers page for missing drivers")),
        ]
        cols = 4 if ui_kit.TEXT_WIDTH >= 740 else 2
        cell_wrap = int(ui_kit.TEXT_WIDTH / cols) - 40
        for i, (icon, title, text) in enumerate(steps):
            grid.grid_columnconfigure(i % cols, weight=1, uniform="steps")
            cell = ctk.CTkFrame(grid, fg_color=C["card_alt"], corner_radius=14)
            cell.grid(row=i // cols, column=i % cols, sticky="nsew", padx=4, pady=4)
            top = ctk.CTkFrame(cell, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(14, 6))
            ctk.CTkLabel(top, text="", image=number_badge(i + 1, 34)).pack(side="left")
            image = emoji_image(icon, 28)
            if image:
                ctk.CTkLabel(top, text="", image=image).pack(side="right")
            label(cell, tx(title), "h3", wraplength=cell_wrap).pack(fill="x", padx=14)
            label(cell, tx(text), "tiny", "muted", wraplength=cell_wrap).pack(fill="x", padx=14, pady=(4, 14))

    def _features_card(self):
        """การ์ดฟีเจอร์ทั้งหมด: ช่องละ 1 หน้า กดแล้วไปหน้านั้นเลย (เอาเมาส์ชี้แล้วขอบจะสว่างขึ้น)"""
        card = make_card(self, tr("🧰 ทำอะไรได้บ้าง", "🧰 What it can do"),
                         tr("กดที่ช่องไหนก็ได้เพื่อไปหน้านั้น", "Click any tile to open that page"))
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=22, pady=(0, 18))
        features = [p for p in PAGES if p[0] != "welcome"]
        cols = 4 if ui_kit.TEXT_WIDTH >= 740 else 2
        cell_wrap = int(ui_kit.TEXT_WIDTH / cols) - 40
        for i, (key, title, desc, _cls) in enumerate(features):
            grid.grid_columnconfigure(i % cols, weight=1, uniform="features")
            tile = ctk.CTkFrame(grid, fg_color=C["card_alt"], corner_radius=14, border_width=1,
                                border_color=C["card_alt"], cursor="hand2")
            tile.grid(row=i // cols, column=i % cols, sticky="nsew", padx=4, pady=4)
            icon, name = split_icon(tx(title))
            widgets = [tile]
            image = emoji_image(icon, 34) if icon else None
            if image:
                widgets.append(ctk.CTkLabel(tile, text="", image=image, cursor="hand2"))
                widgets[-1].pack(anchor="w", padx=14, pady=(14, 6))
            widgets.append(label(tile, name, "h3", wraplength=cell_wrap, cursor="hand2"))
            widgets[-1].pack(fill="x", padx=14)
            widgets.append(label(tile, tx(desc), "tiny", "muted", wraplength=cell_wrap, cursor="hand2"))
            widgets[-1].pack(fill="x", padx=14, pady=(2, 14))
            for w in widgets:
                w.bind("<Button-1>", lambda _e, k=key: self.app.show_page(k))
                w.bind("<Enter>", lambda _e, t=tile: t.configure(border_color=C["primary"]))
                w.bind("<Leave>", lambda _e, t=tile: t.configure(border_color=C["card_alt"]))

    def _safety_card(self):
        """การ์ดคำสัญญาเรื่องความปลอดภัย 4 ข้อ"""
        card = make_card(self, tr("🛡 ปลอดภัยไว้ก่อน", "🛡 Safety first"))
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=22, pady=(0, 18))
        promises = [
            ("ไม่ปิด Windows Defender, Windows Update หรือ Services ของระบบ", "Never disables Windows Defender, Windows Update or system services"),
            ("ลบเฉพาะไฟล์ชั่วคราวและแคช ไม่แตะไฟล์ส่วนตัว", "Only deletes temp files and caches, never personal files"),
            ("โหลดแอปจาก winget และไดรเวอร์จากเว็บผู้ผลิตเท่านั้น", "Apps come from winget, drivers from the manufacturer only"),
            ("ข้อมูลไม่ออกนอกเครื่อง ยกเว้นตอนคุณถาม AI ในโหมด Gemini เอง", "Nothing leaves your PC unless you ask the AI in Gemini mode"),
        ]
        for i, text in enumerate(promises):
            grid.grid_columnconfigure(i % 2, weight=1, uniform="safety")
            label(grid, "✓  " + tx(text), "small", "ok", wraplength=420).grid(row=i // 2, column=i % 2, sticky="w", padx=4, pady=4)


# ================================================================
# 1) หน้าแรก
# ================================================================

class HomePage(Page):
    """หน้าแรก: คะแนนสุขภาพเครื่อง + ปุ่มดูแลเครื่องคลิกเดียว, เกจ CPU/RAM/ดิสก์, ปุ่มสร้างจุดคืนค่า และสเปกเครื่อง"""
    title = ("🏠 หน้าแรก", "🏠 Home")
    subtitle = ("ดูสถานะเครื่องตอนนี้ และดูแลเครื่องแบบกดปุ่มเดียวจบ", "See how your PC is doing and fix things with one click")

    def build(self):
        """สร้างการ์ดสุขภาพเครื่อง เกจ 3 ตัว การ์ดจุดคืนค่า และการ์ดสเปก"""
        self._build_health_card()

        gauges = ctk.CTkFrame(self, fg_color="transparent")
        gauges.pack(fill="x", pady=(0, 14), padx=(0, 6))
        self.gauges = {}
        names = [("cpu", "CPU"), ("ram", "RAM"), ("disk", tr("ไดรฟ์ Windows", "Windows drive"))]
        for col, (key, name) in enumerate(names):
            gauges.grid_columnconfigure(col, weight=1, uniform="gauge")
            card = ctk.CTkFrame(gauges, fg_color=C["card"], corner_radius=16, border_width=1, border_color=C["border"])
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 7, 0 if col == 2 else 7))
            ring = ctk.CTkLabel(card, text="–", font=FONTS["gauge"], text_color=C["text"], compound="center",
                                image=ring_image(0, C["primary"], 96, 9))
            ring.pack(side="left", padx=(16, 10), pady=16)
            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, pady=16)
            label(info, name, "h3").pack(fill="x", pady=(14, 0))
            detail = label(info, "", "tiny", "muted", wraplength=150)
            detail.pack(fill="x")
            self.gauges[key] = (ring, detail)

        card = make_card(self, tr("💾 จุดคืนค่า (Restore Point)", "💾 Restore point"),
                         tr("เหมือนกดเซฟเกมไว้ ถ้าปรับเครื่องแล้วมีปัญหา ย้อนกลับได้ที่ Control Panel > Recovery > Open System Restore",
                            "Like saving your game. If something goes wrong, roll back in Control Panel > Recovery > Open System Restore"))
        self.restore_btn = action_row(card, tr("💾  สร้างจุดคืนค่า", "💾  Create restore point"),
                                      tr("เปิดระบบ System Restore (ถ้ายังปิดอยู่) แล้วบันทึกสถานะเครื่องตอนนี้ไว้",
                                         "Turns on System Restore if needed, then saves the current state of your PC"),
                                      lambda: self.app.run_action("restore_point", self.restore_btn), style="secondary")
        spacer(card)

        card = make_card(self, tr("💻 สเปกเครื่อง", "💻 PC specs"))
        self.spec_box = ctk.CTkFrame(card, fg_color="transparent")
        self.spec_box.pack(fill="x", padx=22, pady=(0, 6))
        label(self.spec_box, tr("กำลังอ่านสเปกเครื่อง...", "Reading specs..."), "body", "muted").pack(fill="x")
        self.spec_btn = action_row(card, tr("🔄  อ่านสเปกใหม่", "🔄  Reload specs"),
                                   tr("อ่านข้อมูลเครื่องอีกครั้ง เช่นหลังเปลี่ยนการ์ดจอหรือเพิ่ม RAM",
                                      "Read the hardware info again, e.g. after changing the GPU or adding RAM"),
                                   lambda: self.load_specs(refresh=True), style="secondary")
        spacer(card)

        system_info.get_usage()  # เรียกครั้งแรกเพื่อเริ่มนับ CPU ครั้งต่อไปจะได้ค่าจริง
        self.after(500, self.update_gauges)

    def _build_health_card(self):
        """การ์ดใหญ่บนสุด: วงแหวนคะแนนสุขภาพเครื่องด้านซ้าย ด้านขวาเป็นรายการปัญหาและปุ่มดูแลเครื่องคลิกเดียว"""
        card = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=18, border_width=1, border_color=C["border"])
        card.pack(fill="x", pady=(0, 14), padx=(0, 6))
        card.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.grid(row=0, column=0, sticky="n", padx=(24, 10), pady=22)
        self.score_ring = ctk.CTkLabel(left, text="…", font=FONTS["score"], text_color=C["text"], compound="center",
                                       image=ring_image(0, C["primary"], 150, 13))
        self.score_ring.pack()
        label(left, tr("คะแนนสุขภาพเครื่อง", "PC health score"), "tiny", "muted", wraplength=0).pack(pady=(6, 0))

        right = ctk.CTkFrame(card, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 24), pady=22)
        self.grade_label = label(right, tr("กำลังตรวจเครื่อง...", "Checking your PC..."), "h2")
        self.grade_label.pack(fill="x")
        self.issue_box = ctk.CTkFrame(right, fg_color="transparent")
        self.issue_box.pack(fill="x", pady=(6, 12))
        label(self.issue_box, tr("ดูพื้นที่ดิสก์ RAM ไฟล์ขยะ จอฟ้า เน็ต โปรแกรมเปิดพร้อมเครื่อง และไดรเวอร์",
                                 "Checking disk space, RAM, junk, blue screens, network, startup apps and drivers"),
              "small", "muted").pack(fill="x")

        row = ctk.CTkFrame(right, fg_color="transparent")
        row.pack(fill="x")
        self.oneclick_btn = make_button(row, tr("✨  ดูแลเครื่องคลิกเดียว", "✨  One-click care"), self.run_one_click,
                                        width=250, height=50, font="button_big")
        self.oneclick_btn.pack(side="left")
        label(row, tr("สร้างจุดคืนค่า → ลบไฟล์ขยะ → คืน RAM → ปรับค่าเล่นเกม\nไม่ลบไฟล์ส่วนตัว ไม่ล้างถังขยะ ย้อนกลับได้ทุกอย่าง",
                      "Restore point → clean junk → free RAM → gaming tweaks\nNo personal files deleted, everything can be undone"),
              "small", "muted", wraplength=400).pack(side="left", padx=16)
        self.recheck_btn = make_button(row, tr("🔄 ตรวจใหม่", "🔄 Re-check"), self.check_health, style="secondary", width=110)
        self.recheck_btn.pack(side="right")

        self.oneclick_bar = ctk.CTkProgressBar(right, height=6, progress_color=C["ok"], fg_color=C["card_alt"])
        self.oneclick_bar.set(0)
        self.oneclick_label = label(right, "", "small", "muted")

    def on_show(self):
        """เปิดหน้าแรกครั้งแรกให้อ่านสเปกและตรวจสุขภาพเครื่อง"""
        if not self.loaded:
            self.loaded = True
            self.load_specs()
            self.check_health()

    def check_health(self):
        """ตรวจสุขภาพเครื่องใน thread แยก (ตรวจทุกอย่างเหมือนผู้ช่วย AI ใช้เวลาประมาณ 5-10 วินาที) แล้วแสดงคะแนน"""
        self.grade_label.configure(text=tr("กำลังตรวจเครื่อง...", "Checking your PC..."), text_color=C["text"])

        def done(result, error):
            if error:
                self.grade_label.configure(text=tr("ตรวจไม่สำเร็จ ลองกด 'ตรวจใหม่'", "Check failed, press 'Re-check'"),
                                           text_color=C["error"])
                return
            self._show_health(result)
            self.app.set_status(tr(f"ตรวจเครื่องเสร็จ ได้ {result['score']} คะแนน", f"Check finished: {result['score']} points"), "ok")

        self.app.run_task(tr("ตรวจสุขภาพเครื่อง", "Checking PC health"),
                          lambda: health.evaluate(ai_assistant.collect_context()), on_done=done, button=self.recheck_btn)

    def _show_health(self, result):
        """แสดงคะแนน (สีวงแหวนตามระดับ) และรายการปัญหาพร้อมปุ่ม "แก้เลย" ของแต่ละข้อ"""
        color = C[result["color"]]
        self.score_ring.configure(text=str(result["score"]), image=ring_image(result["score"], color, 150, 13))
        self.grade_label.configure(text=tr(f"สุขภาพเครื่อง: {result['grade']}", f"PC health: {result['grade']}"), text_color=color)
        clear(self.issue_box)
        if not result["issues"]:
            label(self.issue_box, tr("✓ ไม่เจอปัญหา เครื่องอยู่ในสภาพดี", "✓ No problems found, your PC is in good shape"),
                  "body", "ok").pack(fill="x")
            return
        for text, action in result["issues"]:
            row = ctk.CTkFrame(self.issue_box, fg_color=C["card_alt"], corner_radius=10)
            row.pack(fill="x", pady=2)
            label(row, f"•  {text}", "small", wraplength=470).pack(side="left", padx=12, pady=7)
            if action:
                btn = make_button(row, tr("แก้เลย", "Fix"), style="secondary", width=80, height=30, font="small")
                btn.configure(command=lambda a=action, b=btn: self.app.run_action(
                    a, b, on_done=lambda _r, _e: self.check_health()))
                btn.pack(side="right", padx=8, pady=5)

    def load_specs(self, refresh=False):
        """อ่านสเปกใน thread แยก (ใช้เวลา 2-5 วินาที) แล้วค่อยเอามาแสดง"""
        def work():
            return system_info.summarize_specs(system_info.get_specs(refresh=refresh))

        def done(rows, error):
            clear(self.spec_box)
            if error or not rows:
                label(self.spec_box, tr("อ่านสเปกไม่ได้ ลองกด 'อ่านสเปกใหม่'", "Couldn't read specs, try 'Reload specs'"),
                      "body", "error").pack(fill="x")
                return
            self.spec_box.grid_columnconfigure(1, weight=1)
            for r, (key, value) in enumerate(rows):
                label(self.spec_box, key, "body", "muted", width=120).grid(row=r, column=0, sticky="nw", pady=4)
                label(self.spec_box, value, "body", wraplength=640).grid(row=r, column=1, sticky="w", pady=4)

        self.app.run_task(tr("อ่านสเปกเครื่อง", "Reading specs"), work, on_done=done, button=self.spec_btn)

    def update_gauges(self):
        """อัปเดตเกจวงแหวนทุก 1.5 วินาที (psutil อ่านเร็วมาก เลยเรียกใน main thread ได้ไม่ค้าง)
        สีเปลี่ยนตามระดับ: ปกติน้ำเงิน, เกิน 75% เหลือง, ไดรฟ์เต็มเกิน 90% แดง
        ถ้าหน้านี้ถูกลบไปแล้ว (เช่นตอนเปลี่ยนภาษา) จะหยุดวนเอง"""
        if not self.winfo_exists():
            return
        try:
            u = system_info.get_usage()
            details = {
                "cpu": tr("ใช้งานอยู่ตอนนี้", "in use right now"),
                "ram": tr(f"ใช้ {format_size(u['ram_used'])}\nจาก {format_size(u['ram_total'])}",
                          f"{format_size(u['ram_used'])} used\nof {format_size(u['ram_total'])}"),
                "disk": tr(f"เหลือว่าง {format_size(u['disk_free'])}\nจาก {format_size(u['disk_total'])}",
                           f"{format_size(u['disk_free'])} free\nof {format_size(u['disk_total'])}"),
            }
            for key, (ring, detail) in self.gauges.items():
                percent = u[key]
                danger = key == "disk" and percent > 90
                color = C["error"] if danger else (C["warn"] if percent > 75 else C["primary"])
                ring.configure(text=f"{percent:.0f}%", image=ring_image(percent, color, 96, 9),
                               text_color=C["error"] if danger else C["text"])
                detail.configure(text=details[key] + (tr("\n⚠ พื้นที่ใกล้เต็ม", "\n⚠ almost full") if danger else ""),
                                 text_color=C["error"] if danger else C["muted"])
        except Exception as e:
            self.app.report_error(e)
        self.after(1500, self.update_gauges)

    def run_one_click(self):
        """ดูแลเครื่องคลิกเดียว: ทำ 4 ขั้นตอนตามลำดับใน thread แยก แสดงความคืบหน้า 1/4, 2/4, ...
        ขั้นไหนพลาดจะทำขั้นต่อไปต่อ แล้วสรุปผลทุกขั้นตอนตอนจบ และตรวจสุขภาพเครื่องใหม่ให้เห็นคะแนนที่ดีขึ้น"""
        steps = [
            (tr("สร้างจุดคืนค่า", "Creating restore point"), restore_point.create_restore_point),
            (tr("ลบไฟล์ขยะ", "Cleaning junk"), self.app.task_clean_default),
            (tr("คืน RAM", "Freeing RAM"), ram.clear_ram),
            (tr("ปรับค่าเล่นเกมที่แนะนำ", "Applying gaming tweaks"), game_tweaks.apply_recommended),
        ]
        self.oneclick_bar.set(0)
        self.oneclick_bar.pack(fill="x", pady=(14, 4))
        self.oneclick_label.pack(fill="x")

        def show_step(i, name):
            text = tr(f"ขั้นที่ {i}/{len(steps)}: กำลัง{name}...", f"Step {i}/{len(steps)}: {name}...")
            self.oneclick_label.configure(text=text, text_color=C["text"])
            self.app.set_status(text, "busy")

        def work():
            results = []
            for i, (name, func) in enumerate(steps, start=1):
                self.app.ui(show_step, i, name)
                try:
                    ok, msg = func()
                except Exception as e:
                    ok, msg = False, str(e)
                results.append((name, ok, msg))
                self.app.ui(self.oneclick_bar.set, i / len(steps))
            all_ok = all(ok for _n, ok, _m in results)
            # สรุปผลทุกขั้นเป็นบรรทัด ๆ เช่น "✓ ลบไฟล์ขยะ: ลบไฟล์ขยะแล้ว ได้พื้นที่คืน 1.2 GB"
            summary = "\n".join(f"{'✓' if ok else '✗'} {name}: {msg}" for name, ok, msg in results)
            return all_ok, summary

        def done(result, error):
            if error:
                self.oneclick_label.configure(text=tr(f"เกิดข้อผิดพลาด: {error}", f"Error: {error}"), text_color=C["error"])
                return
            all_ok, summary = result
            self.oneclick_label.configure(text=summary, text_color=C["ok"] if all_ok else C["warn"])
            self.app.set_status(tr("ดูแลเครื่องเสร็จครบทุกขั้นตอน", "All care steps finished") if all_ok
                                else tr("ดูแลเครื่องเสร็จ แต่บางขั้นตอนไม่สำเร็จ", "Finished, but some steps failed"),
                                "ok" if all_ok else "error")
            self.check_health()

        self.app.run_task(tr("ดูแลเครื่อง", "One-click care"), work, on_done=done, button=self.oneclick_btn)


# ================================================================
# 2) ผู้ช่วย AI
# ================================================================

class AIPage(ctk.CTkFrame):
    """หน้าแชตกับผู้ช่วย AI ไม่ได้ใช้ Page เพราะต้องการให้ช่องแชตยืดเต็มจอ และช่องพิมพ์อยู่ล่างสุดตลอด"""
    title = ("🤖 ผู้ช่วย AI", "🤖 AI assistant")
    subtitle = ("เล่าอาการของเครื่องด้วยคำของคุณเอง ผู้ช่วยจะตรวจเครื่องจริงก่อนตอบทุกครั้ง",
                "Describe the problem in your own words. The assistant checks your PC before every answer")

    def __init__(self, master, app):
        """สร้างหน้า AI: คำเตือนเรื่องข้อมูล, ตั้งค่า, คำถามสำเร็จรูป, ช่องแชต, ช่องพิมพ์"""
        super().__init__(master, fg_color=C["bg"])
        self.app = app
        self.history = []        # บทสนทนาที่ผ่านมา [(role, text)] ส่งให้ Gemini จะได้จำเรื่องที่คุยได้
        self.offline_state = {}  # โหมดออฟไลน์จำว่าคุยหัวข้อไหนอยู่ และแนะนำไปถึงขั้นไหนแล้ว
        self.waiting = False
        compact = app.compact  # จอเตี้ย: ย่อส่วนบนให้ช่องแชตมีที่พอ
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1, minsize=140)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        top = ctk.CTkFrame(head, fg_color="transparent")
        top.pack(fill="x")
        heading(top, tx(self.title), "h1", 32, wraplength=wide() - 200).pack(side="left", fill="x", expand=True, pady=(4, 0))
        # ปุ่มกาง/พับส่วนตั้งค่า Gemini (จอเตี้ยพับไว้ตั้งแต่แรก)
        self.settings_btn = make_button(top, tr("⚙  ตั้งค่า Gemini", "⚙  Gemini settings"), self.toggle_settings,
                                        style="secondary", width=160, height=36, font="small")
        self.settings_btn.pack(side="right")
        if not compact:
            label(head, tx(self.subtitle), "body", "muted", wraplength=wide()).pack(fill="x", pady=(2, 12))
        else:
            ctk.CTkFrame(head, height=8, fg_color="transparent").pack()

        # คำเตือนเรื่องการส่งข้อมูลออกนอกเครื่อง (ตามกฎความปลอดภัย) จอเตี้ยใช้ฉบับย่อที่ยังบอกครบว่าส่งอะไร ไปที่ไหน เมื่อไร
        privacy = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12, border_width=1, border_color=C["border"])
        privacy.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        note = tx(ai_assistant.PRIVACY_NOTE) if not compact else tr(
            "ข้อมูลเครื่อง (สเปก การใช้งาน ผลตรวจ) จะถูกส่งให้ Google Gemini เฉพาะตอนคุณถามในโหมด Gemini โหมดออฟไลน์ไม่มีข้อมูลออกนอกเครื่อง",
            "PC info (specs, usage, check results) goes to Google Gemini only when you ask in Gemini mode. Offline mode sends nothing")
        label(privacy, "🔒 " + note, "tiny", "muted", wraplength=wide()).pack(fill="x", padx=16, pady=8)

        self._build_settings()
        if compact:
            self.settings.grid_remove()

        # ปุ่มคำถามสำเร็จรูป (จอปกติ 2 แถว แถวละ 3 ปุ่ม, จอเตี้ยแถวเดียว 3 ปุ่ม)
        quick = ctk.CTkFrame(self, fg_color="transparent")
        quick.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        label(quick, tr("ลองถามเลย:", "Try asking:"), "small", "muted", wraplength=0).grid(row=0, column=0, rowspan=2, padx=(2, 10), sticky="w")
        questions = ai_assistant.QUICK_QUESTIONS[:3] if compact else ai_assistant.QUICK_QUESTIONS
        for i, q in enumerate(questions):
            make_chip(quick, tx(q), lambda text=tx(q): self.send(text)).grid(row=i // 3, column=1 + i % 3, padx=4, pady=3, sticky="w")

        # ช่องแชต
        self.chat = ctk.CTkScrollableFrame(self, fg_color=C["card"], corner_radius=16, border_width=1,
                                           border_color=C["border"], scrollbar_button_color=C["card_alt"])
        self.chat.grid(row=4, column=0, sticky="nsew", pady=(0, 10))
        self._add_ai({"reply": tr(
            "สวัสดีครับ เล่าอาการมาได้เลยแบบที่พูดกันปกติ เช่น \"เปิด Chrome แล้วค้างทุกที\" หรือ \"เล่น Valorant แล้วเครื่องดับเอง\" "
            "ผมจะตรวจเครื่องจริงก่อนตอบ ถ้าลองแล้วไม่หาย บอกได้เลยว่า \"ยังไม่หาย\" จะมีวิธีถัดไปให้ "
            "ปุ่ม \"ทำเลย\" ใต้คำตอบต้องกดเองถึงจะทำนะครับ",
            "Hi! Describe the problem the way you'd say it, e.g. \"Chrome keeps freezing\" or \"my PC shuts down when I play Valorant\". "
            "I'll check your PC before answering. If a fix doesn't work, just say \"still not fixed\" and I'll suggest the next step. "
            "Nothing happens until you press a \"Do it\" button yourself."), "actions": [], "suggestions": []})

        # ช่องพิมพ์คำถาม
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew")
        self.entry = ctk.CTkEntry(bottom, placeholder_text=tr("พิมพ์อาการ เช่น เครื่องดับเองตอนเล่นเกม, เน็ตหลุดทุกครึ่งชั่วโมง...",
                                                               "Type the problem, e.g. PC shuts down in games, Wi-Fi drops every 30 min..."),
                                  height=46, font=FONTS["body"], fg_color=C["card"], border_width=1,
                                  border_color=C["border"], corner_radius=12)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda _e: self.send())
        self.send_btn = make_button(bottom, tr("ส่ง  ➤", "Send  ➤"), self.send, width=110, height=46)
        self.send_btn.pack(side="left", padx=(8, 0))
        label(self, tr("กด Enter หรือปุ่ม 'ส่ง' เพื่อถาม ผู้ช่วยจะตอบพร้อมปุ่มแก้ปัญหา (ไม่มีอะไรทำงานเองจนกว่าคุณจะกด)",
                       "Press Enter or 'Send' to ask. Answers come with fix buttons (nothing runs until you press one)"),
              "tiny", "muted", wraplength=wide()).grid(row=6, column=0, sticky="ew", pady=(4, 0))

    def _build_settings(self):
        """แถวตั้งค่า: ช่อง API key, ชื่อโมเดล, ปุ่มบันทึก, ปุ่มขอ key ฟรี และบอกว่าตอนนี้ใช้โหมดไหน"""
        settings = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12, border_width=1, border_color=C["border"])
        settings.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.settings = settings
        row = ctk.CTkFrame(settings, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(12, 4))
        label(row, "Gemini API key", "small", "muted", wraplength=0).pack(side="left")
        self.key_entry = ctk.CTkEntry(row, width=300, show="•", font=FONTS["small"], fg_color=C["card_alt"], border_width=0)
        self.key_entry.pack(side="left", padx=(8, 16))
        label(row, tr("โมเดล", "Model"), "small", "muted", wraplength=0).pack(side="left")
        self.model_entry = ctk.CTkEntry(row, width=170, font=FONTS["small"], fg_color=C["card_alt"], border_width=0)
        self.model_entry.pack(side="left", padx=(8, 12))
        self.key_entry.insert(0, self.app.config_data.get("gemini_api_key", ""))
        self.model_entry.insert(0, self.app.config_data.get("gemini_model", "gemini-2.5-flash"))
        self.mode_label = label(row, "", "small", wraplength=0)
        self.mode_label.pack(side="right")

        row2 = ctk.CTkFrame(settings, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(4, 12))
        make_button(row2, tr("💾 บันทึก", "💾 Save"), self.save_settings, width=100, height=36, font="small").pack(side="left")
        label(row2, tr("เก็บ key ไว้ในเครื่องนี้เท่านั้น", "The key stays on this PC"), "tiny", "muted", wraplength=0).pack(side="left", padx=(8, 18))
        make_button(row2, tr("🔑 ขอ API key ฟรี", "🔑 Get a free API key"), lambda: open_url("https://aistudio.google.com/apikey"),
                    style="secondary", width=150, height=36, font="small").pack(side="left")
        label(row2, tr("เปิดเว็บ Google AI Studio ให้สร้าง key (ใส่แล้ว AI จะตอบได้อิสระและละเอียดกว่ามาก)",
                       "Opens Google AI Studio to create a key (with a key, answers are far more flexible and detailed)"),
              "tiny", "muted", wraplength=max(180, ui_kit.TEXT_WIDTH - 420)).pack(side="left", padx=(8, 0))
        self._update_mode()

    def toggle_settings(self):
        """กาง/พับส่วนตั้งค่า Gemini (API key, ชื่อโมเดล)"""
        if self.settings.winfo_ismapped():
            self.settings.grid_remove()
        else:
            self.settings.grid()

    def on_show(self):
        """เปิดหน้าแชตแล้วให้เคอร์เซอร์อยู่ในช่องพิมพ์เลย"""
        self.entry.focus_set()

    def _update_mode(self):
        """แสดงว่าตอนนี้ใช้โหมด Gemini หรือโหมดออฟไลน์"""
        if self.app.config_data.get("gemini_api_key"):
            self.mode_label.configure(text=tr("● โหมด Gemini", "● Gemini mode"), text_color=C["ok"])
        else:
            self.mode_label.configure(text=tr("● โหมดออฟไลน์", "● Offline mode"), text_color=C["muted"])

    def save_settings(self):
        """บันทึก API key และชื่อโมเดลลง %APPDATA%\\PoloOptimizer\\config.json"""
        try:
            key = self.key_entry.get().strip()
            model = self.model_entry.get().strip() or "gemini-2.5-flash"
            self.app.config_data = config.save_config({"gemini_api_key": key, "gemini_model": model})
            self._update_mode()
            self.app.set_status(tr("บันทึกการตั้งค่า AI แล้ว", "AI settings saved"), "ok")
        except Exception as e:
            self.app.report_error(e, tr("บันทึกการตั้งค่าไม่ได้", "Couldn't save settings"))

    def _bubble(self, text, is_user):
        """สร้างกล่องข้อความ 1 กล่อง (ของผู้ใช้ชิดขวา ของ AI ชิดซ้าย) คืน (กรอบนอก, กล่อง, label ข้อความ)"""
        outer = ctk.CTkFrame(self.chat, fg_color="transparent")
        outer.pack(fill="x", pady=6, padx=8)
        bubble = ctk.CTkFrame(outer, fg_color=C["user_bubble"] if is_user else C["card_alt"], corner_radius=14)
        bubble.pack(side="right" if is_user else "left", padx=(90, 0) if is_user else (0, 70))
        text_label = label(bubble, text, "body", wraplength=640)
        text_label.pack(padx=16, pady=12, fill="x")
        return outer, bubble, text_label

    def _scroll_bottom(self):
        """เลื่อนช่องแชตลงล่างสุด ให้เห็นข้อความล่าสุด"""
        try:
            self.chat.update_idletasks()
            self.chat._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _add_ai(self, answer):
        """แสดงคำตอบของ AI พร้อมปุ่ม "ทำเลย" ของแต่ละ action และปุ่มคำถามต่อ (suggestions) ใต้คำตอบ"""
        _outer, bubble, _text = self._bubble("🤖  " + answer["reply"], is_user=False)
        for action in answer.get("actions", []):
            text, desc = ai_assistant.action_label(action)
            row = ctk.CTkFrame(bubble, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(0, 8))
            btn = make_button(row, tr(f"▶  ทำเลย: {text}", f"▶  Do it: {text}"), width=230, height=38, font="small")
            btn.configure(command=lambda a=action, b=btn: self._do_action(a, b))
            btn.pack(side="left")
            label(row, desc, "tiny", "muted", wraplength=360).pack(side="left", padx=12)
        if answer.get("suggestions"):
            chips = ctk.CTkFrame(bubble, fg_color="transparent")
            chips.pack(fill="x", padx=16, pady=(2, 12))
            label(chips, tr("ถามต่อ:", "Ask next:"), "tiny", "muted", wraplength=0).pack(side="left", padx=(0, 6))
            for s in answer["suggestions"]:
                make_chip(chips, s, lambda text=s: self.send(text)).pack(side="left", padx=3)
        self.after(50, self._scroll_bottom)

    def _do_action(self, action, button):
        """ผู้ใช้กด "ทำเลย" เอง: สั่งงานผ่าน App.confirm_action (ถ้าเป็นงานที่ทำให้เน็ตหลุดจะถามยืนยันก่อน)"""
        def done(result, error):
            if not error and isinstance(result, tuple) and result[0]:
                button.configure(text=tr("✓ ทำแล้ว", "✓ Done"), image=None, fg_color=C["ok"], hover_color=C["ok"])

        self.app.confirm_action(action, button, on_done=done)

    def send(self, text=None):
        """ส่งคำถาม: แสดงข้อความผู้ใช้ ตรวจเครื่องจริง แล้วถาม Gemini (หรือตอบแบบออฟไลน์) ใน thread แยก"""
        question = (text or self.entry.get()).strip()
        if not question or self.waiting:
            return
        self.entry.delete(0, "end")
        self._bubble(question, is_user=True)
        thinking_outer, _b, thinking_text = self._bubble(
            tr("🤖  กำลังตรวจเครื่อง (CPU, RAM, เน็ต, จอฟ้า, ไดรเวอร์)...", "🤖  Checking your PC (CPU, RAM, network, crashes, drivers)..."),
            is_user=False)
        self.after(50, self._scroll_bottom)
        self.waiting = True
        api_key = self.app.config_data.get("gemini_api_key", "")
        model = self.app.config_data.get("gemini_model", "gemini-2.5-flash")
        history = list(self.history)

        def work():
            ctx = ai_assistant.collect_context()
            self.app.ui(thinking_text.configure, text=tr("🤖  ตรวจเสร็จแล้ว กำลังคิดคำตอบ...", "🤖  Check done, thinking..."))
            if api_key:
                try:
                    return ai_assistant.ask_gemini(question, ctx, api_key, model, history)
                except RuntimeError as e:
                    return ai_assistant.offline_answer(question, ctx, self.offline_state,
                                                       note=tr(f"{e} เลยตอบแบบออฟไลน์แทน", f"{e}, answering offline instead"))
            return ai_assistant.offline_answer(question, ctx, self.offline_state)

        def done(answer, error):
            self.waiting = False
            thinking_outer.destroy()
            if error:
                answer = {"reply": tr(f"ขอโทษครับ เกิดข้อผิดพลาด: {error}", f"Sorry, something went wrong: {error}"),
                          "actions": [], "suggestions": []}
            self._add_ai(answer)
            self.history += [("user", question), ("ai", answer["reply"])]

        self.app.run_task(tr("วิเคราะห์ปัญหา", "Analyzing"), work, on_done=done, button=self.send_btn)


# ================================================================
# 3) ติดตั้งแอป
# ================================================================

class InstallPage(Page):
    """หน้าติดตั้งแอป: การ์ดแอปพร้อมโลโก้แยกหมวด (3 คอลัมน์), ช่องค้นหา, ตัวกรองติดตั้งแล้ว/ยังไม่ติดตั้ง
    ติดตั้งได้ทีละตัวจากปุ่มบนการ์ด หรือติ๊กหลายตัวแล้วติดตั้งทีเดียวผ่าน winget"""
    title = ("📦 ติดตั้งแอป", "📦 Install apps")
    subtitle = ("รวมแอปยอดนิยมไว้ที่เดียว ติดตั้งจากแหล่งทางการผ่าน winget กดทีละตัว หรือติ๊กหลายตัวแล้วติดตั้งทีเดียวก็ได้",
                "Popular apps in one place, installed from official sources via winget. Install one at a time, or tick several and install them together")
    COLUMNS = 3

    def build(self):
        """สร้างแถบเครื่องมือ (ค้นหา/ตัวกรอง), การ์ดติดตั้งหลายตัว และการ์ดแอปของแต่ละหมวด"""
        self.installing = False
        self.winget_ok = None
        self.installed = set()
        self.cards = {}       # รหัสแอป -> dict ของ widget บนการ์ด
        self.sections = []    # [(หมวด, กรอบหัวข้อ, label จำนวน, กรอบตาราง)]
        self.status_text = {}  # รหัสแอป -> (ข้อความสถานะ, สี) ระหว่างติดตั้ง

        # ---------- แถบเครื่องมือ ----------
        bar = make_card(self)
        top = ctk.CTkFrame(bar, fg_color="transparent")
        top.pack(fill="x", padx=22, pady=(18, 8))
        self.search = ctk.CTkEntry(top, placeholder_text=tr("🔍  ค้นหาแอป เช่น Discord, Chrome, Zoom...", "🔍  Search apps, e.g. Discord, Chrome, Zoom..."),
                                   height=42, font=FONTS["body"], fg_color=C["card_alt"], border_width=1,
                                   border_color=C["border"], corner_radius=12)
        self.search.pack(side="left", fill="x", expand=True)
        self.search.bind("<KeyRelease>", lambda _e: self.render())
        self.refresh_btn = make_button(top, tr("🔄 ตรวจใหม่", "🔄 Re-check"), self.detect_installed, style="secondary", width=120)
        self.refresh_btn.pack(side="left", padx=(10, 0))
        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=(0, 6))
        self.filter = ctk.CTkSegmentedButton(row, values=[tr("ทั้งหมด", "All"), tr("ติดตั้งแล้ว", "Installed"), tr("ยังไม่ได้ติดตั้ง", "Not installed")],
                                             command=lambda _v: self.render(), font=FONTS["small"], height=34, corner_radius=10,
                                             selected_color=C["primary"], selected_hover_color=C["primary_hover"],
                                             unselected_color=C["secondary"], unselected_hover_color=C["secondary_hover"])
        self.filter.set(tr("ทั้งหมด", "All"))
        self.filter.pack(side="left")
        self.count_label = label(row, "", "small", "muted", wraplength=0)
        self.count_label.pack(side="right")
        self.winget_label = label(bar, tr("กำลังตรวจว่าเครื่องนี้มี winget ไหม และแอปไหนติดตั้งอยู่แล้ว...",
                                          "Checking winget and which apps are already installed..."), "tiny", "muted")
        self.winget_label.pack(fill="x", padx=22, pady=(2, 16))
        self.store_box = ctk.CTkFrame(bar, fg_color="transparent", height=1)  # กรอบว่างของ customtkinter สูง 200px ถ้าไม่กำหนด
        self.store_box.pack(fill="x")

        # ---------- ติดตั้งหลายตัว ----------
        card = make_card(self, tr("📥 ติดตั้งหลายตัวพร้อมกัน", "📥 Install several at once"),
                         tr("ติ๊กช่องมุมขวาบนของการ์ดแอปที่อยากได้ แล้วกดปุ่มนี้ แอปที่มีอยู่แล้วจะขึ้น ✓ โดยไม่ติดตั้งซ้ำ",
                            "Tick the box on each app card you want, then press this button. Already-installed apps show ✓ and aren't reinstalled"))
        self.install_btn = action_row(card, tr("📥  ติดตั้งที่เลือก", "📥  Install selected"),
                                      tr("ติดตั้งแอปที่ติ๊กไว้ทั้งหมด ทีละตัวตามลำดับ ระหว่างนี้ใช้เครื่องต่อได้", "Installs every ticked app one by one. You can keep using your PC"),
                                      self.install_selected)
        action_row(card, tr("✖  ล้างการเลือก", "✖  Clear selection"), tr("เอาเครื่องหมายติ๊กออกทั้งหมด", "Untick everything"),
                   self.clear_selection, style="secondary")
        self.progress = ctk.CTkProgressBar(card, height=8, progress_color=C["ok"], fg_color=C["card_alt"])
        self.progress.set(0)
        self.progress.pack(fill="x", padx=22, pady=(8, 4))
        self.progress_label = label(card, tr("ยังไม่ได้เริ่ม", "Not started"), "small", "muted")
        self.progress_label.pack(fill="x", padx=22, pady=(0, 16))

        # ---------- การ์ดแอปแยกหมวด ----------
        for cat in installer.CATALOG:
            head = ctk.CTkFrame(self, fg_color="transparent")
            icon = emoji_image(cat.get("icon", "📦"), 26)
            if icon:
                ctk.CTkLabel(head, text="", image=icon).pack(side="left", padx=(2, 10))
            label(head, tx(cat["name"]), "h2", wraplength=0).pack(side="left")
            count = label(head, "", "small", "muted", wraplength=0)
            count.pack(side="left", padx=10)
            grid = ctk.CTkFrame(self, fg_color="transparent")
            for col in range(self.COLUMNS):
                grid.grid_columnconfigure(col, weight=1, uniform="appcards")
            for app in cat["apps"]:
                self.cards[app["id"]] = self._make_card(grid, app, cat["default"])
            self.sections.append((cat, head, count, grid))
        self.render()

    def _make_card(self, parent, app, checked):
        """สร้างการ์ดแอป 1 ใบ: โลโก้, ชื่อ, คำอธิบาย, ช่องติ๊ก, ป้ายแหล่งที่มา และปุ่ม/สถานะด้านล่าง"""
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=14, border_width=1, border_color=C["border"])
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text="", image=app_icon(app["id"], tx(app["name"]), 46)).grid(row=0, column=0, rowspan=2, sticky="nw", padx=(14, 10), pady=(14, 0))
        label(card, tx(app["name"]), "h3", wraplength=170).grid(row=0, column=1, sticky="w", pady=(14, 0))
        var = ctk.BooleanVar(value=checked)
        ctk.CTkCheckBox(card, text="", variable=var, width=24, checkbox_width=22, checkbox_height=22, corner_radius=6,
                        fg_color=C["primary"], hover_color=C["primary_hover"], cursor="hand2").grid(row=0, column=2, sticky="ne", padx=(0, 10), pady=(14, 0))
        label(card, tx(app["desc"]), "tiny", "muted", wraplength=max(150, int(ui_kit.TEXT_WIDTH / 3) - 70)).grid(row=1, column=1, columnspan=2, sticky="nw", padx=(0, 12))
        tags = ctk.CTkFrame(card, fg_color="transparent")
        tags.grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(8, 0))
        if app.get("source") == "msstore":
            badge(tags, "Microsoft Store", "store").pack(side="left")
        else:
            badge(tags, "winget", "info").pack(side="left")
        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.grid(row=3, column=0, columnspan=3, sticky="ew", padx=14, pady=(10, 14))
        return {"frame": card, "var": var, "bottom": bottom, "app": app}

    def _refresh_card(self, app_id):
        """วาดส่วนล่างของการ์ดใหม่ตามสถานะ: ติดตั้งแล้ว / กำลังติดตั้ง / ปุ่มติดตั้ง (+ ข้อความ error ถ้ามี)"""
        item = self.cards[app_id]
        clear(item["bottom"])
        state = self.status_text.get(app_id)
        if app_id in self.installed:
            badge(item["bottom"], tr("✓ ติดตั้งแล้ว", "✓ Installed"), "ok").pack(side="left")
            return
        if state and state[1] in ("muted", "primary"):
            label(item["bottom"], state[0], "small", state[1], wraplength=0).pack(side="left")
            return
        btn = make_button(item["bottom"], tr("⬇  ติดตั้ง", "⬇  Install"), lambda: self.install_ids([app_id]),
                          width=110, height=34, font="small")
        btn.pack(side="left")
        if state:
            label(item["bottom"], state[0], "tiny", state[1], wraplength=150).pack(side="left", padx=8)

    def render(self):
        """จัดการ์ดใหม่ตามคำค้นและตัวกรอง (ซ่อนการ์ดที่ไม่ตรง แล้วเรียงที่เหลือเป็นตาราง 3 คอลัมน์)"""
        query = self.search.get().strip().lower()
        mode = self.filter.get()
        shown = total = 0
        for cat, head, count, grid in self.sections:
            visible = []
            installed_here = 0
            for app in cat["apps"]:
                total += 1
                is_installed = app["id"] in self.installed
                installed_here += is_installed
                text = " ".join([app["id"], *[str(x) for x in (app["name"], app["desc"])]]).lower()
                if query and query not in text:
                    continue
                if mode == tr("ติดตั้งแล้ว", "Installed") and not is_installed:
                    continue
                if mode == tr("ยังไม่ได้ติดตั้ง", "Not installed") and is_installed:
                    continue
                visible.append(app)
            for app in cat["apps"]:
                self.cards[app["id"]]["frame"].grid_forget()
            for i, app in enumerate(visible):
                self.cards[app["id"]]["frame"].grid(row=i // self.COLUMNS, column=i % self.COLUMNS, sticky="nsew", padx=5, pady=5)
                self._refresh_card(app["id"])
            count.configure(text=tr(f"{len(cat['apps'])} แอป · ติดตั้งแล้ว {installed_here}", f"{len(cat['apps'])} apps · {installed_here} installed"))
            head.pack_forget()
            grid.pack_forget()
            if visible:
                head.pack(fill="x", pady=(6, 6), padx=(0, 6))
                grid.pack(fill="x", pady=(0, 12), padx=(0, 6))
            shown += len(visible)
        self.count_label.configure(text=tr(f"แสดง {shown} จาก {total} แอป · ติดตั้งแล้ว {len(self.installed)}",
                                           f"Showing {shown} of {total} apps · {len(self.installed)} installed"))

    def set_filter(self, text):
        """ใส่คำค้นจากแถบค้นหาด้านบนของโปรแกรม แล้วแสดงเฉพาะแอปที่ตรง"""
        self.search.delete(0, "end")
        self.search.insert(0, text)
        self.filter.set(tr("ทั้งหมด", "All"))
        self.render()

    def on_show(self):
        """เปิดหน้าครั้งแรกให้ตรวจ winget และแอปที่ติดตั้งอยู่แล้ว"""
        if not self.loaded:
            self.loaded = True
            self.detect_installed()

    def detect_installed(self):
        """ตรวจใน thread แยกว่าเครื่องมี winget ไหม และแอปไหนติดตั้งแล้ว (ใช้เวลาประมาณ 5-10 วินาที)"""
        def work():
            ok = installer.has_winget()
            return {"ok": ok, "found": installer.installed_ids() if ok else set()}

        def done(result, error):
            if error:
                return
            self.winget_ok, found = result["ok"], result["found"]
            self.app.set_status(tr(f"ตรวจเสร็จ เจอแอปในรายการที่ติดตั้งแล้ว {len(found)} ตัว", f"Done: {len(found)} listed apps already installed"), "ok")
            clear(self.store_box)
            if self.winget_ok:
                self.installed = set(found)
                for app_id in self.installed:
                    self.cards[app_id]["var"].set(False)  # ของที่มีแล้วไม่ต้องติ๊กไว้
                self.winget_label.configure(text=tr("✓ winget พร้อมใช้งาน  •  แอปที่ติดตั้งผ่านช่องทางอื่นบางตัวอาจตรวจไม่เจอ ถ้ากดติดตั้งซ้ำจะขึ้นว่ามีอยู่แล้วเอง",
                                                    "✓ winget is ready  •  Some apps installed other ways may not be detected; installing again just reports them as installed"),
                                            text_color=C["ok"])
            else:
                self.winget_label.configure(text=tr("✗ เครื่องนี้ยังไม่มี winget ต้องติดตั้ง App Installer จาก Microsoft Store ก่อน (ฟรี ของ Microsoft) แล้วเปิดโปรแกรมนี้ใหม่",
                                                    "✗ winget isn't installed. Get App Installer from the Microsoft Store first (free, by Microsoft), then reopen this app"),
                                            text_color=C["error"])
                action_row(self.store_box, tr("🛒  เปิด Microsoft Store", "🛒  Open Microsoft Store"),
                           tr("ไปหน้า App Installer แล้วกด 'รับ' หรือ 'อัปเดต'", "Opens App Installer, press 'Get' or 'Update'"),
                           installer.open_app_installer_store)
                spacer(self.store_box, 8)
            self.render()

        self.app.run_task(tr("ตรวจแอปที่ติดตั้งแล้ว", "Checking installed apps"), work, on_done=done, button=self.refresh_btn)

    def clear_selection(self):
        """เอาติ๊กออกทุกแอป"""
        for item in self.cards.values():
            item["var"].set(False)

    def install_selected(self):
        """ติดตั้งทุกแอปที่ติ๊กไว้"""
        self.install_ids([app_id for app_id, item in self.cards.items() if item["var"].get()])

    def _set_status(self, app_id, text, color):
        """เปลี่ยนสถานะของแอประหว่างติดตั้ง แล้ววาดการ์ดใหม่"""
        self.status_text[app_id] = (text, color)
        self._refresh_card(app_id)

    def install_ids(self, ids):
        """ติดตั้งแอปตามรายการรหัส ทีละตัวใน thread แยก (ปุ่มบนการ์ด, ปุ่มติดตั้งหลายตัว และปุ่ม "ทำเลย" ของ AI ใช้ฟังก์ชันนี้)"""
        if self.installing:
            self.app.set_status(tr("กำลังติดตั้งแอปชุดก่อนอยู่ รอให้เสร็จก่อนนะ", "Still installing the previous batch, please wait"), "error")
            return
        if self.winget_ok is False:
            self.app.set_status(tr("เครื่องนี้ไม่มี winget กดปุ่ม 'เปิด Microsoft Store' ด้านบนก่อน",
                                   "winget is missing, press 'Open Microsoft Store' above first"), "error")
            return
        apps = [installer.find_app(i) for i in ids if installer.find_app(i)]
        if not apps:
            self.app.set_status(tr("ยังไม่ได้ติ๊กแอปที่จะติดตั้ง", "No apps ticked"), "error")
            return
        self.installing = True
        for app in apps:
            self._set_status(app["id"], tr("⏳ รอคิว", "⏳ Queued"), "muted")
        self.progress.set(0)
        total = len(apps)

        def work():
            success = 0
            for n, app in enumerate(apps):
                name = tx(app["name"])
                text = tr(f"กำลังติดตั้ง {name} ({n + 1}/{total})", f"Installing {name} ({n + 1}/{total})")
                self.app.ui(self._set_status, app["id"], tr("⬇ กำลังติดตั้ง...", "⬇ Installing..."), "primary")
                self.app.ui(self.progress_label.configure, text=text)
                self.app.ui(self.app.set_status, text, "busy")
                try:
                    ok, msg = installer.install_app(app)
                except Exception as e:
                    ok, msg = False, str(e)
                success += 1 if ok else 0
                self.app.ui(self._finish_app, app["id"], ok, msg)
                self.app.ui(self.progress.set, (n + 1) / total)
            return success == total, tr(f"ติดตั้งเสร็จ {success}/{total} แอป", f"Installed {success}/{total} apps")

        def done(result, error):
            self.installing = False
            if error:
                self.progress_label.configure(text=tr(f"เกิดข้อผิดพลาด: {error}", f"Error: {error}"), text_color=C["error"])
            else:
                self.progress_label.configure(text=result[1], text_color=C["ok"] if result[0] else C["warn"])
            self.render()

        self.app.run_task(tr("ติดตั้งแอป", "Installing apps"), work, on_done=done, button=self.install_btn)

    def _finish_app(self, app_id, ok, msg):
        """ติดตั้งแอป 1 ตัวเสร็จ: สำเร็จ = ย้ายไปกลุ่มติดตั้งแล้ว, ไม่สำเร็จ = แสดงสาเหตุใต้ปุ่มติดตั้ง"""
        self.cards[app_id]["var"].set(False)
        if ok:
            self.installed.add(app_id)
            self.status_text.pop(app_id, None)
            self._refresh_card(app_id)
        else:
            self._set_status(app_id, "✗ " + msg, "error")


# ================================================================
# 4) ไดรเวอร์
# ================================================================

class DriversPage(Page):
    """หน้าไดรเวอร์: การ์ดจอ, ยี่ห้อเครื่อง/เมนบอร์ด, อุปกรณ์ที่มีปัญหา, Windows Update"""
    title = ("🔧 ไดรเวอร์", "🔧 Drivers")
    subtitle = ("ตรวจว่าอุปกรณ์ไหนยังไม่มีไดรเวอร์ แล้วพาไปโหลดจากเว็บผู้ผลิตโดยตรง (ไม่โหลดจากเว็บรวมไดรเวอร์)",
                "Find devices without drivers and go straight to the manufacturer's site (never third-party driver sites)")

    def build(self):
        """สร้างการ์ด 4 ใบ เนื้อหาข้างในจะเติมตอนโหลดข้อมูลเสร็จ"""
        card = make_card(self)
        self.refresh_btn = action_row(card, tr("🔄  ตรวจใหม่", "🔄  Check again"),
                                      tr("อ่านข้อมูลการ์ดจอและอุปกรณ์ทั้งหมดอีกครั้ง เช่นหลังลงไดรเวอร์เสร็จ",
                                         "Read GPU and device info again, e.g. after installing a driver"),
                                      self.load, style="secondary")
        spacer(card, 6)

        card = make_card(self, tr("🎮 การ์ดจอ", "🎮 Graphics card"))
        self.gpu_box = ctk.CTkFrame(card, fg_color="transparent")
        self.gpu_box.pack(fill="x", pady=(0, 12))

        card = make_card(self, tr("🖥 ไดรเวอร์ของเครื่อง/เมนบอร์ด", "🖥 PC/motherboard drivers"),
                         tr("ไดรเวอร์ชิปเซ็ต เสียง LAN Wi-Fi ควรโหลดจากเว็บยี่ห้อเครื่อง (โน้ตบุ๊ก) หรือยี่ห้อเมนบอร์ด (PC ประกอบ)",
                            "Chipset, audio, LAN and Wi-Fi drivers should come from your laptop maker or your motherboard maker (custom PC)"))
        self.brand_box = ctk.CTkFrame(card, fg_color="transparent")
        self.brand_box.pack(fill="x", pady=(0, 12))

        card = make_card(self, tr("⚠ อุปกรณ์ที่มีปัญหา", "⚠ Devices with problems"),
                         tr("อุปกรณ์ที่ Device Manager ขึ้นเครื่องหมายตกใจสีเหลือง", "Devices that show a yellow warning in Device Manager"))
        self.problem_box = ctk.CTkFrame(card, fg_color="transparent")
        self.problem_box.pack(fill="x")
        action_row(card, tr("🧰  เปิด Device Manager", "🧰  Open Device Manager"),
                   tr("เปิดหน้าจัดการอุปกรณ์ของ Windows ดูรายละเอียดหรืออัปเดตไดรเวอร์ทีละตัว",
                      "Opens Windows Device Manager to see details or update drivers one by one"),
                   self.safe_open(drivers.open_device_manager), style="secondary")
        spacer(card)

        card = make_card(self, "🔄 Windows Update",
                         tr("Windows มีไดรเวอร์ให้โหลดบางส่วน โดยเฉพาะในหมวด Optional updates",
                            "Windows offers some drivers too, especially under Optional updates"))
        action_row(card, tr("🔄  เปิด Windows Update", "🔄  Open Windows Update"), tr("เช็กและติดตั้งอัปเดตของ Windows", "Check for and install Windows updates"),
                   self.safe_open(drivers.open_windows_update), style="secondary")
        action_row(card, tr("➕  เปิด Optional updates", "➕  Open Optional updates"),
                   tr("ดูไดรเวอร์เสริมที่ Windows ไม่ได้ลงให้อัตโนมัติ (ติ๊กแล้วกด Download & install)",
                      "Extra drivers Windows doesn't install automatically (tick them, then Download & install)"),
                   self.safe_open(drivers.open_optional_updates), style="secondary")
        spacer(card)

    def on_show(self):
        """เปิดหน้าครั้งแรกให้ตรวจไดรเวอร์เลย"""
        if not self.loaded:
            self.loaded = True
            self.load()

    def load(self):
        """อ่านข้อมูลการ์ดจอ ยี่ห้อ และอุปกรณ์ที่มีปัญหาใน thread แยก แล้วเติมลงการ์ด"""
        for box in (self.gpu_box, self.brand_box, self.problem_box):
            clear(box)
            label(box, tr("กำลังตรวจ...", "Checking..."), "small", "muted").pack(fill="x", padx=22)

        def work():
            return drivers.get_gpus(), drivers.get_system_brand(), drivers.get_problem_devices()

        def done(result, error):
            for box in (self.gpu_box, self.brand_box, self.problem_box):
                clear(box)
            if error:
                label(self.gpu_box, tr(f"ตรวจไม่สำเร็จ: {error}", f"Check failed: {error}"), "small", "error").pack(fill="x", padx=22)
                return
            gpus, brand, problems = result
            self._fill_gpus(gpus)
            self._fill_brand(brand)
            self._fill_problems(problems, brand)

        self.app.run_task(tr("ตรวจไดรเวอร์", "Checking drivers"), work, on_done=done, button=self.refresh_btn)

    def _fill_gpus(self, gpus):
        """แสดงการ์ดจอแต่ละตัว + ปุ่มไปหน้าโหลดไดรเวอร์ของค่ายนั้น เตือนถ้ายังเป็น Basic Display Adapter"""
        if not gpus:
            label(self.gpu_box, tr("ไม่พบการ์ดจอ", "No graphics card found"), "small", "muted").pack(fill="x", padx=22)
            return
        shown = set()
        for gpu in gpus:
            label(self.gpu_box, tr(f"{gpu['name']}   (ไดรเวอร์เวอร์ชัน {gpu['driver_version']})",
                                   f"{gpu['name']}   (driver version {gpu['driver_version']})"), "body").pack(fill="x", padx=22, pady=(4, 0))
            if gpu["no_driver"]:
                label(self.gpu_box, tr("⚠ การ์ดจอยังไม่มีไดรเวอร์ ภาพจะช้าและเล่นเกมไม่ได้ ควรลงไดรเวอร์ทันที",
                                       "⚠ No graphics driver: graphics are slow and games won't run. Install a driver now"),
                      "small", "error").pack(fill="x", padx=22)
            vendor = gpu["vendor"]
            if vendor in drivers.GPU_DRIVER_URLS and vendor not in shown:
                shown.add(vendor)
                name = drivers.GPU_DRIVER_URLS[vendor][0]
                action_row(self.gpu_box, tr(f"⬇  โหลดไดรเวอร์ {name}", f"⬇  Get {name} driver"),
                           tr(f"เปิดเว็บทางการของ {name} ในเบราว์เซอร์", f"Opens {name}'s official website in your browser"),
                           self.safe_open(lambda v=vendor: drivers.open_gpu_driver_page(v)))

    def _fill_brand(self, brand):
        """แสดงยี่ห้อเครื่อง/เมนบอร์ด และปุ่มไปเว็บซัพพอร์ต (ถ้ารู้จักยี่ห้อ)"""
        kind = tr("โน้ตบุ๊ก", "a laptop") if brand["is_laptop"] else tr("PC ตั้งโต๊ะ/ประกอบเอง", "a desktop/custom PC")
        what = tr("ยี่ห้อเครื่อง", "Brand") if brand["is_laptop"] else tr("เมนบอร์ด", "Motherboard")
        label(self.brand_box, tr(f"เครื่องนี้เป็น {kind}   •   {what}: {brand['maker']} {brand['model']}",
                                 f"This PC is {kind}   •   {what}: {brand['maker']} {brand['model']}"), "body").pack(fill="x", padx=22, pady=(0, 4))
        if brand["url"]:
            action_row(self.brand_box, tr(f"🌐  ไปเว็บซัพพอร์ต {brand['brand']}", f"🌐  {brand['brand']} support site"),
                       (tr(f"เปิดหน้าโหลดไดรเวอร์ของรุ่น \"{brand['model']}\" โดยตรง (ชิปเซ็ต เสียง แลน Wi-Fi)",
                           f"Opens the driver download page for \"{brand['model']}\" directly (chipset, audio, LAN, Wi-Fi)")
                        if "supportonly" in brand["url"] else
                        tr(f"เปิดเว็บ {brand['brand']} แล้วพิมพ์รุ่น \"{brand['model']}\" ในช่องค้นหาเพื่อโหลดไดรเวอร์ที่ตรงรุ่น",
                           f"Opens {brand['brand']}'s site. Search for \"{brand['model']}\" to get drivers for your exact model")),
                       self.safe_open(lambda: open_url(brand["url"])))
        else:
            label(self.brand_box, tr("ไม่รู้จักยี่ห้อนี้ ให้ค้นหาชื่อรุ่นด้านบนแล้วเข้าเว็บของผู้ผลิตโดยตรง",
                                     "Unknown brand. Search for the model above and go to the manufacturer's own site"),
                  "small", "muted").pack(fill="x", padx=22)

    def _fill_problems(self, problems, brand):
        """แสดงอุปกรณ์ที่มีปัญหาแบบ "บอกวิธีแก้พร้อมลิงก์โหลด":
        ด้านบนเป็นการ์ดแนะนำ (จัดกลุ่มอุปกรณ์ที่แก้ด้วยไดรเวอร์ตัวเดียวกัน + ปุ่มโหลดจากเว็บผู้ผลิต)
        ด้านล่างเป็นรายการอุปกรณ์ทีละตัว พร้อมปุ่มค้นหาไดรเวอร์ตัวนั้นใน Microsoft Update Catalog
        ถ้าไม่มีปัญหาให้ขึ้นข้อความสีเขียว"""
        if not problems:
            label(self.problem_box, tr("✓ ไม่มีอุปกรณ์ที่มีปัญหา", "✓ No devices with problems"), "body", "ok").pack(fill="x", padx=22, pady=(0, 6))
            return

        for fix in drivers.driver_fixes(problems, brand):
            box = ctk.CTkFrame(self.problem_box, fg_color=C["nav_active"], corner_radius=12, border_width=1, border_color=C["chip_border"])
            box.pack(fill="x", padx=22, pady=(0, 10))
            heading(box, tr(f"⬇ แนะนำ: {fix['title']}", f"⬇ Recommended: {fix['title']}"), "h3", 20, wraplength=760).pack(fill="x", padx=16, pady=(14, 2))
            label(box, fix["why"], "small", "muted", wraplength=780).pack(fill="x", padx=16, pady=(0, 6))
            for i, (text, url, desc) in enumerate(fix["links"]):
                action_row(box, text, desc, self.safe_open(lambda u=url: open_url(u)),
                           style="primary" if i == 0 else "secondary", width=250)
            spacer(box, 8)

        label(self.problem_box, tr("รายการอุปกรณ์ (ปุ่ม \"หาไดรเวอร์ตัวนี้\" ค้นด้วยรหัสอุปกรณ์ใน Microsoft Update Catalog ซึ่งเป็นเว็บทางการของ Microsoft)",
                                   "Devices (\"Find this driver\" searches the device ID on Microsoft Update Catalog, Microsoft's official site)"),
              "tiny", "muted").pack(fill="x", padx=22, pady=(2, 4))
        for d in problems:
            row = ctk.CTkFrame(self.problem_box, fg_color=C["card_alt"], corner_radius=10)
            row.pack(fill="x", padx=22, pady=2)
            text_box = ctk.CTkFrame(row, fg_color="transparent")
            text_box.pack(side="left", fill="x", expand=True, padx=12, pady=6)
            color = "error" if d["missing_driver"] else "warn"
            label(text_box, f"{d['name']}  —  {d['problem']}", "small", color, wraplength=560).pack(fill="x")
            label(text_box, d["hwid"], "tiny", "faint", wraplength=560).pack(fill="x")
            if d.get("catalog_url"):
                make_button(row, tr("🔍  หาไดรเวอร์ตัวนี้", "🔍  Find this driver"), self.safe_open(lambda u=d["catalog_url"]: open_url(u)),
                            style="secondary", width=150, height=32, font="small").pack(side="right", padx=10)


# ================================================================
# 5) ล้างเครื่อง
# ================================================================

class CleanPage(Page):
    """หน้าล้างเครื่อง: สแกนไฟล์ขยะแยกหมวด ให้ติ๊กเลือกก่อนลบ และปุ่มคืน RAM"""
    title = ("🧹 ล้างเครื่อง", "🧹 Clean up")
    subtitle = ("ลบเฉพาะไฟล์ชั่วคราวและแคช ไฟล์ส่วนตัว (เอกสาร รูป วิดีโอ) ไม่ถูกแตะ ไฟล์ที่โปรแกรมอื่นใช้อยู่จะถูกข้ามไป",
                "Only temp files and caches are deleted. Personal files (documents, photos, videos) are never touched; files in use are skipped")

    def build(self):
        """สร้างการ์ดไฟล์ขยะ (checkbox + ขนาดของแต่ละหมวด) และการ์ดคืน RAM"""
        card = make_card(self, tr("🗑 ไฟล์ขยะ", "🗑 Junk files"),
                         tr("กดสแกนก่อนเพื่อดูว่าแต่ละหมวดกินพื้นที่เท่าไร แล้วติ๊กเลือกหมวดที่จะลบ",
                            "Scan first to see how much space each category uses, then tick what to delete"))
        self.vars, self.size_labels = {}, {}
        for cat in cleaner.CATEGORIES:
            row = ctk.CTkFrame(card, fg_color=C["card_alt"], corner_radius=12)
            row.pack(fill="x", padx=22, pady=3)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(9, 0))
            var = ctk.BooleanVar(value=cat["default"])
            ctk.CTkCheckBox(top, text=tx(cat["name"]), variable=var, font=FONTS["body"], fg_color=C["primary"],
                            hover_color=C["primary_hover"], checkbox_width=22, checkbox_height=22,
                            corner_radius=6, cursor="hand2").pack(side="left")
            size = label(top, "–", "body", "muted", wraplength=0)
            size.pack(side="right")
            label(row, tx(cat["desc"]), "tiny", "muted").pack(fill="x", padx=46, pady=(0, 9))
            self.vars[cat["key"]] = var
            self.size_labels[cat["key"]] = size

        self.scan_btn = action_row(card, tr("🔍  สแกน", "🔍  Scan"), tr("นับขนาดไฟล์ขยะของทุกหมวด (ยังไม่ลบอะไร)", "Measure every category (nothing is deleted)"),
                                   self.scan, style="secondary")
        self.clean_btn = action_row(card, tr("🧹  ลบที่เลือก", "🧹  Delete selected"),
                                    tr("ลบไฟล์ในหมวดที่ติ๊กไว้ ไฟล์ในหมวดพวกนี้ Windows/โปรแกรมจะสร้างใหม่เองเมื่อต้องใช้",
                                       "Deletes files in the ticked categories. Windows/apps recreate them when needed"),
                                    self.clean)
        self.clean_btn.configure(state="disabled")
        self.result_label = label(card, "", "body", "muted")
        self.result_label.pack(fill="x", padx=22, pady=(4, 16))

        card = make_card(self, tr("🧠 คืน RAM", "🧠 Free up RAM"),
                         tr("สั่งให้ทุกโปรแกรมปล่อย RAM ที่ไม่ได้ใช้ และล้างแคชไฟล์ใน RAM ช่วยได้ตอน RAM ใกล้เต็ม "
                            "(ผลเป็นแค่ชั่วคราว โปรแกรมจะดึงกลับไปใช้เมื่อต้องการ)",
                            "Asks every program to release unused RAM and clears the file cache. Helps when RAM is nearly full "
                            "(the effect is temporary; programs take RAM back when they need it)"))
        self.ram_btn = action_row(card, tr("🧠  คืน RAM", "🧠  Free up RAM"), tr("ใช้เวลาไม่กี่วินาที ไม่มีโปรแกรมไหนถูกปิด", "Takes a few seconds, no program is closed"),
                                  lambda: self.app.run_action("clear_ram", self.ram_btn), style="secondary")
        spacer(card)

    def on_show(self):
        """เปิดหน้าครั้งแรกให้สแกนเลย ผู้ใช้จะเห็นขนาดทันที"""
        if not self.loaded:
            self.loaded = True
            self.scan()

    def scan(self):
        """สแกนทุกหมวดใน thread แยก แล้วอัปเดตขนาดข้างชื่อหมวด"""
        for size_label in self.size_labels.values():
            size_label.configure(text=tr("กำลังสแกน...", "Scanning..."), text_color=C["muted"])

        def work():
            return cleaner.scan(progress=lambda name: self.app.ui(
                self.app.set_status, tr(f"กำลังสแกน {tx(name)}...", f"Scanning {tx(name)}..."), "busy"))

        def done(result, error):
            if error:
                return
            total = 0
            for key, (size, count) in result.items():
                total += size if self.vars[key].get() else 0
                self.size_labels[key].configure(text=tr(f"{format_size(size)}  ({count:,} ไฟล์)", f"{format_size(size)}  ({count:,} files)"),
                                                text_color=C["text"] if size else C["muted"])
            self.clean_btn.configure(state="normal")
            self.result_label.configure(text=tr(f"หมวดที่ติ๊กไว้ลบได้ประมาณ {format_size(total)}", f"About {format_size(total)} can be freed in the ticked categories"),
                                        text_color=C["text"])
            self.app.set_status(tr("สแกนเสร็จแล้ว", "Scan finished"), "ok")

        self.app.run_task(tr("สแกนไฟล์ขยะ", "Scanning junk"), work, on_done=done, button=self.scan_btn)

    def clean(self):
        """ลบไฟล์ในหมวดที่ติ๊ก (ถ้าติ๊กถังขยะจะถามยืนยันก่อน เพราะกู้คืนไม่ได้) เสร็จแล้วสแกนใหม่ให้เห็นผล"""
        keys = [k for k, var in self.vars.items() if var.get()]
        if not keys:
            self.app.set_status(tr("ยังไม่ได้ติ๊กหมวดที่จะลบ", "Nothing ticked"), "error")
            return
        if "recycle_bin" in keys and not messagebox.askyesno(
                tr("ล้างถังขยะ", "Empty Recycle Bin"),
                tr("ไฟล์ในถังขยะจะถูกลบถาวร กู้คืนไม่ได้อีก\nแน่ใจไหม?", "Files in the Recycle Bin will be deleted permanently.\nAre you sure?")):
            return

        def work():
            r = cleaner.clean(keys, progress=lambda name: self.app.ui(
                self.app.set_status, tr(f"กำลังลบ {tx(name)}...", f"Deleting {tx(name)}..."), "busy"))
            return True, tr(f"ลบเสร็จ ได้พื้นที่คืน {format_size(r['freed'])} ({r['deleted']:,} ไฟล์) ข้ามไฟล์ที่กำลังใช้อยู่ {r['skipped']:,} ไฟล์",
                            f"Done. Freed {format_size(r['freed'])} ({r['deleted']:,} files), skipped {r['skipped']:,} files in use")

        def done(result, error):
            if not error:
                self.result_label.configure(text=result[1], text_color=C["ok"])
                self.after(300, self.scan)

        self.app.run_task(tr("ลบไฟล์ขยะ", "Deleting junk"), work, on_done=done, button=self.clean_btn)


# ================================================================
# 6) ปรับเล่นเกม
# ================================================================

class GamePage(Page):
    """หน้าปรับเล่นเกม: สวิตช์เปิด/ปิด 3 ตัว และเลือกแผนพลังงาน"""
    title = ("🎮 ปรับเล่นเกม", "🎮 Gaming")
    subtitle = ("ทุกอย่างเป็นสวิตช์ กดซ้ำเพื่อเปลี่ยนกลับได้เสมอ ไม่แตะ Windows Defender, Windows Update หรือ Services ของระบบ",
                "Everything is a switch you can flip back. Windows Defender, Windows Update and system services are never touched")

    def build(self):
        """สร้างการ์ดสวิตช์ปรับแต่งและการ์ดแผนพลังงาน"""
        card = make_card(self, tr("🕹 การตั้งค่าเกม", "🕹 Game settings"))
        self.switch_vars = {}
        for tweak in game_tweaks.TWEAKS:
            row = ctk.CTkFrame(card, fg_color=C["card_alt"], corner_radius=12)
            row.pack(fill="x", padx=22, pady=4)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 0))
            var = ctk.BooleanVar(value=False)
            ctk.CTkSwitch(top, text=tx(tweak["name"]), variable=var, onvalue=True, offvalue=False, font=FONTS["body"],
                          progress_color=C["primary"], switch_width=44, switch_height=22, cursor="hand2",
                          command=lambda t=tweak, v=var: self.toggle(t, v)).pack(side="left")
            rec = tr("เปิด", "On") if tweak["recommended"] else tr("ปิด", "Off")
            label(top, tr(f"แนะนำ: {rec}", f"Recommended: {rec}"), "small", "ok", wraplength=0).pack(side="right")
            label(row, tx(tweak["desc"]), "tiny", "muted").pack(fill="x", padx=12, pady=(2, 10))
            self.switch_vars[tweak["key"]] = var
        self.recommend_btn = action_row(card, tr("⭐  ใช้ค่าที่แนะนำทั้งหมด", "⭐  Use all recommended"),
                                        tr("ตั้งสวิตช์ทุกตัวตามคำแนะนำในครั้งเดียว", "Set every switch to the recommended value at once"),
                                        self.apply_recommended)
        spacer(card)

        card = make_card(self, tr("⚡ แผนพลังงาน (Power plan)", "⚡ Power plan"),
                         tr("แผนแรง ๆ ทำให้ CPU ไม่ลดความเร็วลง เกมลื่นขึ้น แต่กินไฟและโน้ตบุ๊กจะแบตหมดเร็วขึ้น ถ้าใช้โน้ตบุ๊กแบบไม่เสียบสาย แนะนำ Balanced",
                            "Performance plans keep the CPU at full speed for smoother games but use more power. On a laptop running on battery, Balanced is best"))
        self.plan_var = ctk.StringVar(value="")
        self.plan_box = ctk.CTkFrame(card, fg_color="transparent")
        self.plan_box.pack(fill="x", padx=22, pady=(0, 6))
        self.ultimate_btn = action_row(card, tr("🚀  เพิ่ม Ultimate Performance", "🚀  Add Ultimate Performance"),
                                       tr("เพิ่มแผนแรงสุดที่ Windows ซ่อนไว้ เข้ามาในรายการให้เลือก", "Adds Windows' hidden top-performance plan to the list"),
                                       self.add_ultimate, style="secondary")
        self.plan_refresh_btn = action_row(card, tr("🔄  โหลดรายการใหม่", "🔄  Reload list"),
                                           tr("อ่านรายการแผนพลังงานจาก Windows อีกครั้ง", "Read the power plan list from Windows again"),
                                           self.load_plans, style="secondary")
        spacer(card)

    def on_show(self):
        """ทุกครั้งที่เปิดหน้า อ่านสถานะจริงจาก registry ใหม่ (เผื่อผู้ใช้ไปเปลี่ยนใน Settings ของ Windows)"""
        self.load_switches()
        if not self.loaded:
            self.loaded = True
            self.load_plans()

    def load_switches(self):
        """อ่านสถานะปัจจุบันของสวิตช์ทุกตัว (อ่าน registry เร็วมาก ทำใน main thread ได้)"""
        for tweak in game_tweaks.TWEAKS:
            try:
                self.switch_vars[tweak["key"]].set(bool(tweak["get"]()))
            except Exception as e:
                self.app.report_error(e, tr(f"อ่านค่า {tx(tweak['name'])} ไม่ได้", f"Couldn't read {tx(tweak['name'])}"))

    def toggle(self, tweak, var):
        """ผู้ใช้กดสวิตช์: เขียนค่าใหม่ใน thread แยก ถ้าไม่สำเร็จให้สวิตช์เด้งกลับที่เดิม"""
        value = bool(var.get())
        name = tx(tweak["name"])

        def work():
            tweak["set"](value)
            return True, tr(f"{'เปิด' if value else 'ปิด'} {name} แล้ว", f"{name} turned {'on' if value else 'off'}")

        def done(_result, error):
            if error:
                var.set(not value)

        self.app.run_task(tr(f"ตั้งค่า {name}", f"Setting {name}"), work, on_done=done)

    def apply_recommended(self):
        """ตั้งทุกสวิตช์ตามค่าแนะนำ แล้วอ่านสถานะมาแสดงใหม่"""
        self.app.run_task(tr("ปรับค่าเล่นเกม", "Applying gaming tweaks"), game_tweaks.apply_recommended,
                          on_done=lambda _r, _e: self.load_switches(), button=self.recommend_btn)

    def load_plans(self):
        """อ่านรายการแผนพลังงานจาก powercfg /list แล้วสร้างปุ่มตัวเลือก (radio) ให้กดเปลี่ยน"""
        def done(plans, error):
            clear(self.plan_box)
            if error:
                label(self.plan_box, tr("อ่านรายการแผนพลังงานไม่ได้", "Couldn't read power plans"), "small", "error").pack(fill="x")
                return
            for plan in plans:
                if plan["active"]:
                    self.plan_var.set(plan["guid"])
                ctk.CTkRadioButton(self.plan_box, text=plan["name"] + (tr("   (ใช้อยู่)", "   (active)") if plan["active"] else ""),
                                   variable=self.plan_var, value=plan["guid"], font=FONTS["body"],
                                   fg_color=C["primary"], hover_color=C["primary_hover"], cursor="hand2",
                                   command=self.change_plan).pack(fill="x", pady=4)
            self.app.set_status(tr("โหลดรายการแผนพลังงานแล้ว", "Power plans loaded"), "ok")

        self.app.run_task(tr("อ่านแผนพลังงาน", "Reading power plans"), game_tweaks.list_power_plans, on_done=done,
                          button=self.plan_refresh_btn)

    def change_plan(self):
        """ผู้ใช้เลือกแผนพลังงานใหม่ สั่ง powercfg /setactive แล้วโหลดรายการใหม่ให้เห็นว่าเปลี่ยนแล้ว"""
        guid = self.plan_var.get()
        self.app.run_task(tr("เปลี่ยนแผนพลังงาน", "Changing power plan"), lambda: game_tweaks.set_power_plan(guid),
                          on_done=lambda _r, _e: self.load_plans())

    def add_ultimate(self):
        """เพิ่มแผน Ultimate Performance แล้วจำ GUID ไว้ใน config กันสร้างซ้ำ"""
        def work():
            ok, msg, guid = game_tweaks.add_ultimate_performance(self.app.config_data.get("ultimate_plan_guid", ""))
            if ok and guid:
                self.app.config_data = config.save_config({"ultimate_plan_guid": guid})
            return ok, msg + (tr(" กดเลือกในรายการเพื่อใช้งาน", " Select it in the list to use it") if ok else "")

        self.app.run_task(tr("เพิ่มแผน Ultimate Performance", "Adding Ultimate Performance"), work,
                          on_done=lambda _r, _e: self.load_plans(), button=self.ultimate_btn)


# ================================================================
# 7) โปรแกรมเปิดพร้อมเครื่อง
# ================================================================

class StartupPage(Page):
    """หน้าโปรแกรมเปิดพร้อมเครื่อง: สวิตช์เปิด/ปิดแต่ละโปรแกรม (วิธีเดียวกับ Task Manager)"""
    title = ("🚀 โปรแกรมเปิดพร้อมเครื่อง", "🚀 Startup apps")
    subtitle = ("ยิ่งเปิดพร้อมเครื่องเยอะ เครื่องยิ่งบูตช้าและกิน RAM ปิดตัวที่ไม่ได้ใช้ทุกวันได้ ปิดแล้วโปรแกรมยังอยู่ แค่ไม่เปิดเองตอนเปิดเครื่อง",
                "The more apps start with Windows, the slower the boot. Turn off ones you don't use daily; they stay installed, they just don't auto-start")

    def build(self):
        """สร้างการ์ดปุ่มโหลดใหม่และการ์ดรายการโปรแกรม"""
        card = make_card(self, None)
        self.refresh_btn = action_row(card, tr("🔄  โหลดรายการใหม่", "🔄  Reload list"),
                                      tr("อ่านรายการโปรแกรมเปิดพร้อมเครื่องอีกครั้ง", "Read the startup app list again"),
                                      self.load, style="secondary")
        label(card, tr("คำแนะนำ: ไม่ควรปิดโปรแกรมของการ์ดจอ เสียง ทัชแพด หรือแอนติไวรัส ถ้าไม่แน่ใจว่าตัวไหนคืออะไร ปล่อยไว้ก่อน",
                       "Tip: don't disable graphics, audio, touchpad or antivirus software. If you're not sure what something is, leave it on"),
              "tiny", "muted").pack(fill="x", padx=22, pady=(0, 12))
        self.list_card = make_card(self, tr("📋 รายการ", "📋 List"))
        self.list_box = ctk.CTkFrame(self.list_card, fg_color="transparent")
        self.list_box.pack(fill="x", padx=22, pady=(0, 14))

    def on_show(self):
        """เปิดหน้าแล้วโหลดรายการทุกครั้ง (อาจมีโปรแกรมใหม่เพิ่มเข้ามา)"""
        self.load()

    def load(self):
        """อ่าน Run key จาก registry ใน thread แยก แล้วสร้างสวิตช์ของแต่ละโปรแกรม"""
        def done(items, error):
            clear(self.list_box)
            if error:
                label(self.list_box, tr("อ่านรายการไม่ได้", "Couldn't read the list"), "small", "error").pack(fill="x")
                return
            if not items:
                label(self.list_box, tr("ไม่มีโปรแกรมเปิดพร้อมเครื่อง", "No startup apps"), "body", "muted").pack(fill="x")
                return
            enabled = sum(1 for i in items if i["enabled"])
            label(self.list_box, tr(f"เปิดอยู่ {enabled} จาก {len(items)} โปรแกรม", f"{enabled} of {len(items)} apps enabled"),
                  "small", "muted").pack(fill="x", pady=(0, 6))
            for item in items:
                row = ctk.CTkFrame(self.list_box, fg_color=C["card_alt"], corner_radius=12)
                row.pack(fill="x", pady=3)
                top = ctk.CTkFrame(row, fg_color="transparent")
                top.pack(fill="x", padx=12, pady=(9, 0))
                var = ctk.BooleanVar(value=item["enabled"])
                ctk.CTkSwitch(top, text=item["name"], variable=var, onvalue=True, offvalue=False, font=FONTS["body"],
                              progress_color=C["primary"], switch_width=44, switch_height=22, cursor="hand2",
                              command=lambda it=item, v=var: self.toggle(it, v)).pack(side="left")
                label(top, tx(item["scope"]), "tiny", "muted", wraplength=0).pack(side="right")
                command = item["command"] if len(item["command"]) <= 110 else item["command"][:107] + "..."
                label(row, command, "tiny", "faint").pack(fill="x", padx=12, pady=(0, 9))

        self.app.run_task(tr("อ่านโปรแกรมเปิดพร้อมเครื่อง", "Reading startup apps"), startup.list_startup, on_done=done,
                          button=self.refresh_btn)

    def toggle(self, item, var):
        """ผู้ใช้กดสวิตช์: เขียนสถานะใหม่ลง StartupApproved ถ้าไม่สำเร็จสวิตช์จะเด้งกลับ"""
        value = bool(var.get())

        def work():
            startup.set_enabled(item, value)
            # จดไว้ว่าตัวไหน Polo Optimizer เป็นคนปิด ตอนกด "คืนค่าเริ่มต้น" จะได้เปิดกลับเฉพาะตัวพวกนี้
            entry = [item["source"], item["name"]]
            disabled = [e for e in self.app.config_data.get("startup_disabled", []) if e != entry]
            if not value:
                disabled.append(entry)
            self.app.config_data = config.save_config({"startup_disabled": disabled})
            return True, tr(f"{'เปิด' if value else 'ปิด'} {item['name']} ตอนเปิดเครื่องแล้ว (มีผลครั้งหน้าที่เปิดเครื่อง)",
                            f"{item['name']} will {'now' if value else 'no longer'} start with Windows (from next boot)")

        def done(_result, error):
            if error:
                var.set(not value)

        self.app.run_task(tr(f"ตั้งค่า {item['name']}", f"Setting {item['name']}"), work, on_done=done)


# ================================================================
# 8) แก้ปัญหา
# ================================================================

class TroublePage(Page):
    """หน้าแก้ปัญหา: แต่ละการ์ดบอกอาการที่ใช้แก้ไว้ด้วย"""
    title = ("🩺 แก้ปัญหา", "🩺 Troubleshoot")
    subtitle = ("เลือกตามอาการที่เจอ ถ้าไม่แน่ใจ ลองถามผู้ช่วย AI ก่อนได้", "Pick the one that matches your problem. Not sure? Ask the AI assistant first")

    def build(self):
        """สร้างการ์ด 4 ใบ: ซ่อมไฟล์ระบบ, รีเซ็ตเน็ต, รีสตาร์ททาสก์บาร์, สุขภาพดิสก์"""
        card = make_card(self, tr("🛠 ซ่อมไฟล์ระบบ", "🛠 Repair system files"),
                         tr("ใช้เมื่อ: จอฟ้าบ่อย, โปรแกรมของ Windows เปิดไม่ขึ้น, Settings ค้าง, อัปเดต Windows ไม่ผ่าน",
                            "Use when: frequent blue screens, Windows apps won't open, Settings freezes, updates keep failing"))
        self.repair_btn = action_row(card, tr("🛠  ซ่อมไฟล์ระบบ", "🛠  Repair system files"),
                                     tr("เปิดหน้าต่างดำรัน DISM แล้วตามด้วย SFC ใช้เวลา 15-30 นาที ห้ามปิดหน้าต่างระหว่างทำ",
                                        "Opens a window that runs DISM then SFC. Takes 15-30 minutes, don't close it midway"),
                                     lambda: self.app.run_action("repair_windows", self.repair_btn))
        spacer(card)

        card = make_card(self, tr("🌐 รีเซ็ตอินเทอร์เน็ต", "🌐 Reset network"),
                         tr("ใช้เมื่อ: เครื่องอื่นในบ้านเล่นเน็ตได้แต่เครื่องนี้ไม่ได้, เข้าเว็บไม่ได้, Wi-Fi ต่อติดแต่ไม่มีเน็ต",
                            "Use when: other devices at home have internet but this one doesn't, websites won't load, Wi-Fi connected but no internet"))
        self.net_btn = action_row(card, tr("🌐  รีเซ็ตอินเทอร์เน็ต", "🌐  Reset network"),
                                  tr("ล้าง DNS, ขอ IP ใหม่, รีเซ็ต Winsock และ TCP/IP เน็ตจะหลุดสักครู่ แล้วควรรีสตาร์ทเครื่อง",
                                     "Flush DNS, renew IP, reset Winsock and TCP/IP. Internet drops briefly; restart afterwards"),
                                  self.reset_network)
        spacer(card)

        card = make_card(self, tr("📌 รีสตาร์ททาสก์บาร์", "📌 Restart taskbar"),
                         tr("ใช้เมื่อ: ทาสก์บาร์ค้าง, กดปุ่ม Start ไม่ได้, ไอคอนหาย, File Explorer ค้าง",
                            "Use when: the taskbar is frozen, Start won't open, icons are missing, File Explorer hangs"))
        self.explorer_btn = action_row(card, tr("📌  รีสตาร์ททาสก์บาร์", "📌  Restart taskbar"),
                                       tr("ปิดแล้วเปิด explorer.exe ใหม่ จอจะกระพริบ 2-3 วินาที โปรแกรมที่เปิดอยู่ไม่หาย",
                                          "Restarts explorer.exe. The screen flickers for 2-3 seconds; open programs stay open"),
                                       lambda: self.app.run_action("restart_explorer", self.explorer_btn))
        spacer(card)

        card = make_card(self, tr("🚑 Windows มีปัญหาหนัก / อยากเริ่มใหม่", "🚑 Windows badly broken / start over"),
                         tr("เรียงจากเบาไปหนัก ลองทีละข้อจากบนลงล่าง ข้อแรกไม่ทำให้อะไรหาย ข้อสุดท้ายคือลง Windows ใหม่ (เลือกเก็บไฟล์ส่วนตัวไว้ได้)",
                            "Ordered from lightest to heaviest. Try them top to bottom: the first changes nothing personal, the last reinstalls Windows (you can keep your files)"))
        self.defaults_btn = action_row(card, tr("↩  คืนค่าเริ่มต้น Windows", "↩  Restore Windows defaults"),
                                       tr("ใช้เมื่อปรับเครื่องด้วยโปรแกรมนี้แล้วรู้สึกแปลก: คืน Game Mode, เมาส์, การอัดวิดีโอ, แผนพลังงาน Balanced "
                                          "และเปิดโปรแกรมเปิดพร้อมเครื่องที่โปรแกรมนี้เคยปิดกลับมา",
                                          "Use if things feel off after tuning: restores Game Mode, mouse, recording, the Balanced power plan, "
                                          "and re-enables startup apps this app turned off"),
                                       lambda: self.app.confirm_action("restore_defaults", self.defaults_btn), style="secondary")
        action_row(card, tr("⏪  ย้อนกลับไปจุดคืนค่า", "⏪  Go back to a restore point"),
                   tr("เปิด System Restore ให้เลือกวันที่เครื่องยังดีอยู่ ไฟล์ส่วนตัวไม่หาย แต่โปรแกรม/ไดรเวอร์ที่ลงหลังวันนั้นจะถูกย้อน",
                      "Opens System Restore to pick a day the PC worked. Personal files stay; apps/drivers installed after that day are undone"),
                   lambda: self.app.run_action("open_system_restore"), style="secondary")
        action_row(card, tr("🔁  Reset this PC (ลง Windows ใหม่)", "🔁  Reset this PC (reinstall)"),
                   tr("ทางสุดท้าย: เปิดหน้า Recovery ของ Windows แล้วกด Reset PC เลือก 'Keep my files' จะเก็บไฟล์ส่วนตัวไว้ แต่แอปต้องลงใหม่ทั้งหมด",
                      "Last resort: opens Windows Recovery. Press Reset PC and choose 'Keep my files' to keep personal files; apps must be reinstalled"),
                   self.reset_pc, style="danger")
        spacer(card)

        card = make_card(self, tr("💽 สุขภาพดิสก์", "💽 Disk health"),
                         tr("ใช้เมื่อ: เครื่องค้างนาน ๆ ตอนเปิดไฟล์, มีเสียงแปลก ๆ จากเครื่อง, ไฟล์เปิดไม่ได้เป็นบางไฟล์",
                            "Use when: long freezes opening files, strange noises from the PC, some files won't open"))
        self.disk_btn = action_row(card, tr("💽  ตรวจสุขภาพดิสก์", "💽  Check disk health"),
                                   tr("ถามสถานะจากตัวดิสก์เอง ถ้าไม่ปกติจะเตือนเป็นสีแดง", "Asks the disks for their status and warns in red if something's wrong"),
                                   self.check_disks, style="secondary")
        self.disk_box = ctk.CTkFrame(card, fg_color="transparent", height=1)
        self.disk_box.pack(fill="x", padx=22, pady=(4, 14))

        card = make_card(self, tr("📋 แจ้งปัญหาให้ผู้พัฒนา", "📋 Report a problem to the developer"),
                         tr("ถ้าโปรแกรมทำงานผิดพลาด โปรแกรมจะจดรายละเอียดไว้ในไฟล์ error.log ส่งไฟล์นี้ให้ผู้พัฒนาจะช่วยหาสาเหตุได้เร็วขึ้น "
                            "(ในไฟล์มีแค่รายละเอียดข้อผิดพลาดของโปรแกรม ไม่มีไฟล์ส่วนตัว)",
                            "When something goes wrong, details are written to error.log. Sending that file to the developer helps find the cause faster "
                            "(it only contains the app's error details, no personal files)"))
        action_row(card, tr("📂  เปิดโฟลเดอร์ไฟล์บันทึก", "📂  Open log folder"),
                   tr(f"เปิดโฟลเดอร์ {config.APP_DIR} ที่มี error.log และไฟล์ตั้งค่า", f"Opens {config.APP_DIR}, which holds error.log and settings"),
                   self.open_log_folder, style="secondary")
        spacer(card)

    def reset_network(self):
        """ถามยืนยันก่อน (เพราะเน็ตจะหลุด) แล้วรีเซ็ตเน็ตใน thread แยก"""
        if messagebox.askyesno(tr("รีเซ็ตอินเทอร์เน็ต", "Reset network"),
                               tr("ระหว่างรีเซ็ตเน็ตจะหลุดสักครู่ และควรรีสตาร์ทเครื่องหลังทำเสร็จ\nทำต่อไหม?",
                                  "The internet will drop briefly and you should restart afterwards.\nContinue?")):
            self.app.run_action("fix_network", self.net_btn)

    def open_log_folder(self):
        """เปิดโฟลเดอร์ที่เก็บ error.log และไฟล์ตั้งค่า (สร้างให้ก่อนถ้ายังไม่มี)"""
        try:
            os.makedirs(config.APP_DIR, exist_ok=True)
            os.startfile(config.APP_DIR)
            self.app.set_status(tr("เปิดโฟลเดอร์แล้ว ถ้ามีไฟล์ error.log ส่งไฟล์นั้นให้ผู้พัฒนาได้เลย", "Folder opened. If error.log is there, send it to the developer"), "ok")
        except Exception as e:
            self.app.report_error(e, tr("เปิดโฟลเดอร์ไม่ได้", "Couldn't open the folder"))

    def reset_pc(self):
        """ถามยืนยันก่อนพาไปหน้า Reset this PC เพราะเป็นทางที่หนักที่สุด"""
        if messagebox.askyesno(tr("Reset this PC", "Reset this PC"),
                               tr("Reset this PC คือการลง Windows ใหม่ แอปที่ลงไว้จะหายหมด (ถ้าเลือก Keep my files ไฟล์ส่วนตัวจะยังอยู่)\n"
                                  "ควรลองซ่อมไฟล์ระบบและย้อนกลับไปจุดคืนค่าก่อน\n\nเปิดหน้า Recovery ไหม?",
                                  "Reset this PC reinstalls Windows and removes your apps (choose Keep my files to keep personal files).\n"
                                  "Try repairing system files and System Restore first.\n\nOpen Recovery settings?")):
            try:
                ok, msg = troubleshoot.open_reset_pc()
                self.app.set_status(msg, "ok")
            except Exception as e:
                self.app.report_error(e, tr("เปิดไม่ได้", "Couldn't open"))

    def check_disks(self):
        """อ่านสุขภาพดิสก์ทุกลูก แสดงสีเขียวถ้าปกติ สีแดงพร้อมคำเตือนถ้ามีปัญหา"""
        def done(disks, error):
            clear(self.disk_box)
            if error:
                return
            if not disks:
                label(self.disk_box, tr("อ่านข้อมูลดิสก์ไม่ได้", "Couldn't read disk info"), "small", "muted").pack(fill="x")
                return
            for d in disks:
                if d["healthy"]:
                    label(self.disk_box, f"✓ {d['name']} ({d['size']}) — {d['health_text']}", "body", "ok").pack(fill="x", pady=2)
                else:
                    label(self.disk_box, f"✗ {d['name']} ({d['size']}) — {d['health_text']} ({d['health']})", "body", "error").pack(fill="x", pady=2)
                    label(self.disk_box, tr("⚠ ดิสก์นี้อาจเสียเร็ว ๆ นี้ ควรสำรองไฟล์สำคัญไปไว้ที่อื่น (แฟลชไดรฟ์, Google Drive) ทันที แล้วเอาเครื่องไปให้ร้านตรวจ",
                                            "⚠ This disk may fail soon. Back up important files elsewhere (USB drive, Google Drive) now and have the PC checked"),
                          "small", "error").pack(fill="x", pady=(0, 4))

        self.app.run_task(tr("ตรวจสุขภาพดิสก์", "Checking disk health"), troubleshoot.disk_health, on_done=done, button=self.disk_btn)


# ================================================================
# หน้าต่างหลัก
# ================================================================

# (key, ชื่อในเมนู, คำอธิบายใต้ชื่อ, คลาสของหน้า)
PAGES = [
    ("welcome", ("✨ เริ่มต้น", "✨ Welcome"), ("รู้จักโปรแกรมและวิธีใช้", "About and how to use"), WelcomePage),
    ("home", ("🏠 หน้าแรก", "🏠 Home"), ("สเปกและดูแลเครื่อง", "Specs and PC care"), HomePage),
    ("ai", ("🤖 ผู้ช่วย AI", "🤖 AI assistant"), ("เล่าอาการ แล้วให้ช่วยแก้", "Describe a problem, get help"), AIPage),
    ("install", ("📦 ติดตั้งแอป", "📦 Install apps"), ("ลงแอปหลายตัวในคลิกเดียว", "Many apps in one click"), InstallPage),
    ("drivers", ("🔧 ไดรเวอร์", "🔧 Drivers"), ("หาไดรเวอร์ที่ขาด", "Find missing drivers"), DriversPage),
    ("clean", ("🧹 ล้างเครื่อง", "🧹 Clean up"), ("ลบไฟล์ขยะ คืน RAM", "Junk files and RAM"), CleanPage),
    ("game", ("🎮 ปรับเล่นเกม", "🎮 Gaming"), ("ตั้งค่าให้เกมลื่นขึ้น", "Smoother games"), GamePage),
    ("startup", ("🚀 เปิดพร้อมเครื่อง", "🚀 Startup apps"), ("ปิดโปรแกรมที่ไม่จำเป็น", "Disable what you don't need"), StartupPage),
    ("trouble", ("🩺 แก้ปัญหา", "🩺 Troubleshoot"), ("เน็ตหลุด ทาสก์บาร์ค้าง ฯลฯ", "Network, taskbar and more"), TroublePage),
]


class App(ctk.CTk):
    """หน้าต่างหลัก: เมนูซ้าย + พื้นที่เนื้อหาขวา + แถบสถานะล่าง และตัวจัดการงานเบื้องหลังทั้งหมด"""

    def __init__(self, admin=True, splash=False):
        """สร้างหน้าต่าง ฟอนต์ ตั้งตัวจับ error ทุกแบบ แล้วสร้างหน้าจอตามภาษาที่บันทึกไว้
        splash=True จะซ่อนหน้าต่างหลักไว้ก่อน แล้วโชว์หน้าโหลดสวย ๆ ระหว่างสร้างหน้าจอ"""
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title(APP_NAME)
        self._fit_to_screen()
        self.configure(fg_color=C["bg"])
        self.admin = admin
        self._set_icon()
        init_fonts()

        self.config_data = config.load_config()
        i18n.set_language(self.config_data.get("language", "th"))
        self._ui_queue = queue.Queue()
        self._busy = 0
        # เลขรุ่นของหน้าจอ เพิ่มขึ้นทุกครั้งที่สร้างหน้าจอใหม่ (เปลี่ยนภาษา)
        # งานเบื้องหลังที่เริ่มก่อนเปลี่ยนภาษา พอเสร็จจะไม่ไปแตะหน้าจอเก่าที่ถูกลบไปแล้ว
        self._generation = 0

        # จับ error ทุกช่องทาง ให้ไปแสดงที่แถบสถานะแทนการเด้งปิด
        self.report_callback_exception = lambda exc, val, tb: self.report_error(val, tb=tb)
        threading.excepthook = lambda args: self.ui(self.report_error, args.exc_value, tb=args.exc_traceback)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ครั้งแรกที่เปิดโปรแกรมให้เริ่มที่หน้าแนะนำโปรแกรม ครั้งต่อ ๆ ไปเริ่มที่หน้าแรกเลย
        start = "home" if self.config_data.get("welcome_seen") else "welcome"
        if not self.config_data.get("welcome_seen"):
            try:
                self.config_data = config.save_config({"welcome_seen": True})
            except Exception:
                pass
        if splash:
            self.withdraw()
            self._show_splash(lambda: self._build_ui(start))
        else:
            self._build_ui(start)
        self.after(50, self._process_ui_queue)
        self.after(300, self._set_icon)

    def _fit_to_screen(self):
        """ตั้งขนาดหน้าต่างให้พอดีจอของแต่ละเครื่อง (เครื่องคนอื่นอาจเป็นโน้ตบุ๊กจอ 1366x768 ที่ขยาย 125%)
        อ่านพื้นที่ใช้งานจริงของจอ (ไม่รวมทาสก์บาร์) แล้วหารด้วยค่าขยายจอของ Windows ให้เป็นหน่วยเดียวกับ customtkinter
        จอเตี้ยกว่า 800 จะใช้เมนูแบบย่อ และความกว้างข้อความปรับตามความกว้างหน้าต่าง"""
        try:
            scale = self._get_window_scaling()
        except Exception:
            scale = 1.0
        try:
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rect), 0)  # 0x30 = SPI_GETWORKAREA
            avail_w, avail_h = (rect.right - rect.left) / scale, (rect.bottom - rect.top) / scale
        except Exception:
            avail_w, avail_h = self.winfo_screenwidth() / scale, self.winfo_screenheight() / scale - 48
        width = int(min(1260, avail_w - 16))
        height = int(min(820, avail_h - 40))  # เผื่อแถบชื่อหน้าต่าง
        self.compact = avail_h < 800
        x, y = max(0, int((avail_w - width) / 2)), max(0, int((avail_h - height - 32) / 2))
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min(900, width), min(560, height))
        set_text_width(width - 360)

    # ---------- หน้าโหลดตอนเปิดโปรแกรม ----------

    def _show_splash(self, build):
        """โชว์หน้าโหลด (โลโก้ + ชื่อโปรแกรม + แถบโหลด) ประมาณ 2 วินาที ระหว่างนั้นสร้างหน้าจอหลักไปด้วย แล้วค่อยโชว์หน้าต่างหลัก
        ใช้สีพิเศษ #010203 เป็นสีโปร่งใสของหน้าต่าง มุมของหน้าโหลดจะได้โค้งแบบในรูปตัวอย่าง
        ถ้าสร้างหน้าโหลดไม่ได้ จะข้ามไปเปิดหน้าต่างหลักเลย"""
        try:
            w, h = 540, 380
            key = "#010203"
            splash = ctk.CTkToplevel(self)
            splash.overrideredirect(True)
            splash.geometry(f"{w}x{h}+{(self.winfo_screenwidth() - w) // 2}+{(self.winfo_screenheight() - h) // 2}")
            splash.configure(fg_color=key)
            splash.attributes("-transparentcolor", key)
            splash.attributes("-topmost", True)
            image = splash_image(w, h)
            ctk.CTkLabel(splash, text="", image=image, fg_color=key).place(x=0, y=0)
            # สีพื้นใต้แถบโหลด อ่านจากภาพจริงตรงตำแหน่งนั้น ขอบแถบจะได้กลืนกับภาพพอดี
            r, g, b = image._light_image.getpixel((w, int(h * 2 * 0.84)))[:3]
            under = f"#{r:02x}{g:02x}{b:02x}"
            bar = ctk.CTkProgressBar(splash, width=300, height=6, corner_radius=3, progress_color=C["primary"],
                                     fg_color="#14223d", bg_color=under)
            bar.set(0)
            bar.place(relx=0.5, rely=0.84, anchor="center")
            r, g, b = image._light_image.getpixel((w, int(h * 2 * 0.91)))[:3]
            under = f"#{r:02x}{g:02x}{b:02x}"
            percent = ctk.CTkLabel(splash, text="LOADING 0%", font=FONTS["tiny"], text_color="#8fa9d6",
                                   fg_color=under, bg_color=under)
            percent.place(relx=0.5, rely=0.91, anchor="center")
        except Exception:
            build()
            return

        state = {"step": 0, "built": False}
        steps = 60  # 60 ขั้น x 30 ms ≈ 1.8 วินาที

        def tick():
            state["step"] += 1
            if state["step"] == 8 and not state["built"]:
                state["built"] = True
                try:
                    build()  # สร้างหน้าจอหลักระหว่างที่หน้าโหลดยังแสดงอยู่
                except Exception as e:
                    self.report_error(e)
            progress = min(state["step"] / steps, 1.0)
            try:
                bar.set(progress)
                percent.configure(text=f"LOADING {int(progress * 100)}%")
            except Exception:
                pass
            if state["step"] < steps:
                self.after(30, tick)
            else:
                try:
                    splash.destroy()
                except Exception:
                    pass
                self.deiconify()
                self.lift()
                self.focus_force()

        self.after(60, tick)

    # ---------- ส่วนประกอบหน้าต่าง ----------

    def _build_ui(self, start_page="home"):
        """สร้างเมนู แถบค้นหาด้านบน พื้นที่เนื้อหา และแถบสถานะ (เรียกใหม่ทุกครั้งที่เปลี่ยนภาษา)"""
        self.pages = {}
        self.current = None
        self._build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew", padx=(18, 12), pady=(12, 6))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)
        self._build_topbar()
        self.page_host = ctk.CTkFrame(self.content, fg_color=C["bg"], corner_radius=0)
        self.page_host.grid(row=1, column=0, sticky="nsew")
        self.page_host.grid_columnconfigure(0, weight=1)
        self.page_host.grid_rowconfigure(0, weight=1)
        self._build_statusbar()
        self.show_page(start_page)
        if self.admin:
            self.set_status(tr("พร้อมใช้งาน", "Ready"), "ok")
        else:
            self.set_status(tr("ไม่ได้เปิดด้วยสิทธิ์ Admin บางปุ่มจะใช้ไม่ได้ ปิดโปรแกรมแล้วคลิกขวา > Run as administrator",
                               "Not running as Admin, some buttons won't work. Close and right-click > Run as administrator"), "error")

    def _build_sidebar(self):
        """สร้างเมนูด้านซ้าย: โลโก้ + ชื่อโปรแกรม, ปุ่มเมนู 8 หน้า และด้านล่างเป็นปุ่มเปลี่ยนภาษา สิทธิ์ Admin และเวอร์ชัน"""
        side = ctk.CTkFrame(self, fg_color=C["sidebar"], corner_radius=0, width=250)
        side.grid(row=0, column=0, rowspan=2, sticky="nsw")
        side.grid_propagate(False)
        self.sidebar = side

        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.pack(fill="x", padx=18, pady=(14, 10) if self.compact else (22, 18))
        logo = load_logo(44)
        if logo:
            ctk.CTkLabel(brand, text="", image=logo).pack(side="left", padx=(0, 10))
        names = ctk.CTkFrame(brand, fg_color="transparent")
        names.pack(side="left", fill="x")
        ctk.CTkLabel(names, text=APP_NAME, font=FONTS["logo"], text_color=C["text"], anchor="w").pack(fill="x")
        ctk.CTkLabel(names, text=tr("ดูแลคอมให้จบในโปรแกรมเดียว", "Your all-in-one PC helper"), font=FONTS["tiny"],
                     text_color=C["muted"], anchor="w").pack(fill="x")

        self.nav_items = {}
        for key, title, desc, _cls in PAGES:
            item = NavItem(side, tx(title), tx(desc), lambda k=key: self.show_page(k), compact=self.compact)
            item.pack(fill="x", padx=10, pady=1)
            self.nav_items[key] = item

        foot = ctk.CTkFrame(side, fg_color="transparent")
        foot.pack(side="bottom", fill="x", padx=18, pady=12)
        badge_text, badge_color = ((tr("● สิทธิ์ Admin พร้อมใช้งาน", "● Running as Admin"), C["ok"]) if self.admin
                                   else (tr("● ไม่มีสิทธิ์ Admin", "● Not running as Admin"), C["warn"]))
        ctk.CTkLabel(foot, text=badge_text, font=FONTS["tiny"], text_color=badge_color, anchor="w").pack(fill="x")
        ctk.CTkLabel(foot, text=f"{APP_NAME} v{APP_VERSION}", font=FONTS["tiny"], text_color=C["faint"], anchor="w").pack(fill="x")

    def _build_statusbar(self):
        """สร้างแถบสถานะด้านล่าง: ข้อความบอกว่ากำลังทำอะไร + แถบวิ่งตอนมีงานทำอยู่"""
        bar = ctk.CTkFrame(self, fg_color=C["sidebar"], corner_radius=0, height=38)
        bar.grid(row=1, column=1, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(0, weight=1)
        self.statusbar = bar
        self.status_label = WrapLabel(bar, text="", wrap=0, font=FONTS["small"], text_color=C["muted"], anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=16, pady=6)
        self.busy_bar = ctk.CTkProgressBar(bar, width=140, height=6, mode="indeterminate",
                                           progress_color=C["primary"], fg_color=C["card_alt"])
        if self._busy > 0:
            self._update_busy(force=True)

    # ---------- แถบค้นหาด้านบน ----------

    def _build_topbar(self):
        """แถบด้านบน: ช่องค้นหา (ค้นได้ทั้งหน้า ฟีเจอร์ และแอป ถ้าไม่เจอส่งเป็นคำถามให้ AI) + ป้ายสถานะ พร้อม/กำลังทำงาน"""
        bar = ctk.CTkFrame(self.content, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        bar.grid_columnconfigure(0, weight=1)
        self.search_entry = ctk.CTkEntry(bar, height=44, font=FONTS["body"], corner_radius=22, border_width=1,
                                         fg_color=C["card"], border_color=C["border"],
                                         placeholder_text=tr("🔍  ค้นหาฟีเจอร์ แอป หรือพิมพ์ปัญหาแล้วกด Enter เพื่อถาม AI  (Ctrl+K)",
                                                             "🔍  Search features and apps, or type a problem and press Enter to ask the AI  (Ctrl+K)"))
        self.search_entry.grid(row=0, column=0, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        self.search_entry.bind("<Return>", lambda _e: self._run_search_result(0))
        self.search_entry.bind("<Escape>", lambda _e: self.hide_search())
        self.search_entry.bind("<FocusOut>", lambda _e: self.after(200, self._hide_if_unfocused))
        self.bind_all("<Control-k>", lambda _e: self.search_entry.focus_set())
        self.state_pill = ctk.CTkLabel(bar, text=tr("  ● พร้อม  ", "  ● READY  "), font=FONTS["small"], text_color=C["ok"],
                                       fg_color=C["card"], corner_radius=15, height=30)
        self.state_pill.grid(row=0, column=1, padx=(12, 0))
        # ปุ่มเปลี่ยนภาษา ไทย / EN (อยู่มุมขวาบน เห็นง่าย)
        self.lang_switch = ctk.CTkSegmentedButton(bar, values=["ไทย", "EN"], command=self._on_language,
                                                  font=FONTS["small"], height=34, corner_radius=17, width=110,
                                                  selected_color=C["primary"], selected_hover_color=C["primary_hover"],
                                                  unselected_color=C["card"], unselected_hover_color=C["secondary_hover"])
        self.lang_switch.set("EN" if i18n.get_language() == "en" else "ไทย")
        self.lang_switch.grid(row=0, column=2, padx=(10, 0))
        self.search_popup = None
        self.search_results = []

    def _search_index(self):
        """รวบรวมทุกอย่างที่ค้นหาได้ (ทั้งสองภาษา เพื่อให้ค้นด้วยภาษาไหนก็เจอ):
        หน้าในเมนู, งานที่กดทำได้ (ล้างขยะ คืน RAM ฯลฯ) และแอปในหน้าติดตั้ง
        คืน list ของ dict {icon, title, kind, text (ไว้ค้น), run (ฟังก์ชันที่ทำเมื่อกด)}"""
        items = []
        for key, title, desc, _cls in PAGES:
            icon, name = split_icon(tx(title))
            items.append({"icon": icon, "title": name, "kind": tr("หน้า", "Page"),
                          "text": " ".join(title + desc), "run": lambda k=key: self.show_page(k)})
        extra = {"clean_junk": "ขยะ temp cache junk ล้าง", "clear_ram": "แรม ram memory", "game_tweaks": "เกม game fps mouse เมาส์",
                 "high_performance": "พลังงาน power plan แรง", "restore_point": "คืนค่า restore backup",
                 "repair_windows": "ซ่อม sfc dism windows พัง", "fix_network": "เน็ต wifi internet dns",
                 "restart_explorer": "ทาสก์บาร์ taskbar explorer start", "open_taskmgr": "task manager โปรแกรมค้าง",
                 "open_security": "ไวรัส virus defender สแกน", "open_sound": "เสียง sound ลำโพง ไมค์",
                 "open_windows_update": "อัปเดต update",
                 "restore_defaults": "รีเซ็ต reset ค่าเดิม ค่าเริ่มต้น default undo ย้อน",
                 "open_system_restore": "ย้อนกลับ system restore วินพัง windows broken"}
        for action, (name, desc) in ai_assistant.ALLOWED_ACTIONS.items():
            if action in ("open_drivers", "open_startup"):
                continue
            items.append({"icon": "⚡", "title": tx(name), "kind": tr("ทำเลย", "Action"),
                          "text": " ".join(name + desc) + " " + extra.get(action, ""), "run": lambda a=action: self.confirm_action(a)})
        for app in installer.all_apps():
            items.append({"icon": "📦", "title": tx(app["name"]), "kind": tr("แอป", "App"), "app_id": app["id"],
                          "text": " ".join([app["id"], *[str(x) for x in (app["name"], app["desc"])]]),
                          "run": lambda a=app: self._open_app_in_install(a)})
        return items

    def _on_search_key(self, event):
        """พิมพ์ในช่องค้นหา: หาของที่ตรง แล้วแสดงผลลัพธ์ใต้ช่อง (ปุ่ม Enter/Escape มีงานของมันเองเลยข้าม)"""
        if event.keysym in ("Return", "Escape"):
            return
        query = self.search_entry.get().strip()
        if not query:
            self.hide_search()
            return
        q = query.lower()
        words = q.split()
        scored = []
        for item in self._search_index():
            hay = f"{item['title']} {item['text']}".lower()
            if all(w in hay for w in words):
                title = item["title"].lower()
                scored.append((0 if title.startswith(q) else 1 if q in title else 2, item))
        scored.sort(key=lambda x: x[0])
        results = [item for _s, item in scored[:6]]
        results.append({"icon": "🤖", "title": tr(f"ถามผู้ช่วย AI: \"{query}\"", f"Ask the AI: \"{query}\""), "kind": "AI",
                        "run": lambda: self._ask_ai(query)})
        self._show_results(results)

    def _show_results(self, results):
        """แสดงกล่องผลลัพธ์ลอยใต้ช่องค้นหา (ผลแรกถูกไฮไลต์ กด Enter = เลือกผลแรก)"""
        self.search_results = results
        if self.search_popup is None or not self.search_popup.winfo_exists():
            self.search_popup = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=14, border_width=1, border_color=C["primary"])
        popup = self.search_popup
        clear(popup)
        for i, item in enumerate(results):
            row = ctk.CTkFrame(popup, fg_color=C["nav_active"] if i == 0 else "transparent", corner_radius=10, cursor="hand2")
            row.pack(fill="x", padx=6, pady=(6 if i == 0 else 0, 6 if i == len(results) - 1 else 2))
            widgets = [row]
            image = app_icon(item["app_id"], item["title"], 24) if item.get("app_id") else (emoji_image(item["icon"], 22) if item.get("icon") else None)
            if image:
                widgets.append(ctk.CTkLabel(row, text="", image=image, cursor="hand2"))
                widgets[-1].pack(side="left", padx=(10, 8), pady=6)
            widgets.append(label(row, item["title"], "body", wraplength=600, cursor="hand2"))
            widgets[-1].pack(side="left", pady=6)
            widgets.append(badge(row, item["kind"], "store" if item["kind"] == "AI" else "info"))
            widgets[-1].pack(side="right", padx=10)
            for w in widgets:
                w.bind("<Button-1>", lambda _e, n=i: self._run_search_result(n))
                w.bind("<Enter>", lambda _e, r=row: r.configure(fg_color=C["nav_active"]))
                w.bind("<Leave>", lambda _e, r=row, first=(i == 0): r.configure(fg_color=C["nav_active"] if first else "transparent"))
        popup.place(in_=self.search_entry, relx=0, rely=1, y=6, relwidth=1)
        popup.lift()

    def _run_search_result(self, index):
        """ทำตามผลลัพธ์ที่เลือก (เปิดหน้า / ทำงาน / เปิดแอปในหน้าติดตั้ง / ถาม AI) แล้วล้างช่องค้นหา"""
        if not self.search_entry.get().strip():
            return
        if not self.search_results:
            self._on_search_key(type("E", (), {"keysym": "x"})())
        if index >= len(self.search_results):
            return
        item = self.search_results[index]
        self.search_entry.delete(0, "end")
        self.hide_search()
        self.focus_set()
        try:
            item["run"]()
        except Exception as e:
            self.report_error(e)

    def _hide_if_unfocused(self):
        """ซ่อนผลค้นหาเมื่อช่องค้นหาไม่ได้โฟกัสแล้ว (หน่วงเวลานิดหน่อยให้การคลิกผลลัพธ์ทำงานก่อน)"""
        try:
            if self.focus_get() is not self.search_entry._entry:
                self.hide_search()
        except Exception:
            self.hide_search()

    def hide_search(self):
        """ซ่อนกล่องผลลัพธ์การค้นหา"""
        self.search_results = []
        if getattr(self, "search_popup", None) is not None:
            try:
                self.search_popup.place_forget()
            except Exception:
                pass

    def _ask_ai(self, question):
        """ส่งข้อความจากช่องค้นหาไปเป็นคำถามในหน้าผู้ช่วย AI"""
        self.show_page("ai")
        self.pages["ai"].send(question)

    def _open_app_in_install(self, app):
        """เปิดหน้าติดตั้งแอป แล้วกรองให้เห็นเฉพาะแอปที่ค้นหา (ยังไม่ติดตั้งจนกว่าผู้ใช้จะกดเอง)"""
        self.show_page("install")
        self.pages["install"].set_filter(tx(app["name"]))

    def confirm_action(self, action, button=None, on_done=None):
        """ทำ action หลังถามยืนยัน (เฉพาะงานที่ทำให้เน็ตหลุด) ใช้กับผลค้นหาและปุ่ม "ทำเลย" ของ AI"""
        if action == "fix_network" and not messagebox.askyesno(
                tr("รีเซ็ตอินเทอร์เน็ต", "Reset network"),
                tr("ระหว่างรีเซ็ตเน็ตจะหลุดสักครู่ และควรรีสตาร์ทเครื่องหลังทำเสร็จ\nทำต่อไหม?",
                   "The internet will drop briefly and you should restart afterwards.\nContinue?")):
            return
        if action == "restore_defaults" and not messagebox.askyesno(
                tr("คืนค่าเริ่มต้น Windows", "Restore Windows defaults"),
                tr("จะคืนค่า Game Mode, เมาส์, การอัดวิดีโอเบื้องหลัง, แผนพลังงาน (Balanced) และเปิดโปรแกรมเปิดพร้อมเครื่องที่โปรแกรมนี้เคยปิดกลับมา\n"
                   "ไฟล์และแอปไม่ถูกแตะ ทำต่อไหม?",
                   "This restores Game Mode, mouse, background recording, the Balanced power plan, and re-enables startup apps this app turned off.\n"
                   "Files and apps are untouched. Continue?")):
            return
        self.run_action(action, button, on_done=on_done)

    def _set_icon(self):
        """ใส่ไอคอนหน้าต่าง (เรียกซ้ำหลัง customtkinter ใส่ไอคอนของมันเองเสร็จ ไม่งั้นจะโดนทับ)"""
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

    def _on_language(self, value):
        """ผู้ใช้กดเปลี่ยนภาษา: บันทึกลง config แล้วสร้างหน้าจอใหม่ทั้งหมดด้วยภาษาใหม่ (กลับมาหน้าเดิม)
        ถ้ามีงานทำอยู่ (เช่นติดตั้งแอป) จะไม่ให้เปลี่ยน เพราะหน้าจอที่แสดงความคืบหน้าจะหายไป"""
        lang = "en" if value == "EN" else "th"
        if lang == i18n.get_language():
            return
        if self._busy > 0:
            self.lang_switch.set("EN" if i18n.get_language() == "en" else "ไทย")
            self.set_status(tr("รอให้งานที่ทำอยู่เสร็จก่อน แล้วค่อยเปลี่ยนภาษา", "Wait for the current task to finish before changing language"), "error")
            return
        try:
            i18n.set_language(lang)
            self.config_data = config.save_config({"language": lang})
        except Exception as e:
            self.report_error(e)
        page = self.current or "home"
        self._generation += 1
        for widget in (self.sidebar, self.content, self.statusbar, self.search_popup):
            if widget is not None:
                widget.destroy()
        self._build_ui(start_page=page)

    def show_page(self, key):
        """เปลี่ยนหน้า: สร้างหน้าตอนเปิดครั้งแรก (โปรแกรมจะเปิดเร็วขึ้น) แล้วซ่อนหน้าเก่า แสดงหน้าใหม่"""
        try:
            self.hide_search()
            if key not in self.pages:
                cls = next(c for k, _t, _d, c in PAGES if k == key)
                self.pages[key] = cls(self.page_host, self)
            if self.current and self.current != key:
                self.pages[self.current].grid_forget()
            self.pages[key].grid(row=0, column=0, sticky="nsew")
            for k, item in self.nav_items.items():
                item.set_active(k == key)
            self.current = key
            self.pages[key].on_show()
        except Exception as e:
            self.report_error(e, tr("เปิดหน้านี้ไม่ได้", "Couldn't open this page"))

    # ---------- แถบสถานะและ error ----------

    def set_status(self, text, kind="info"):
        """เปลี่ยนข้อความแถบสถานะ kind = info / busy / ok / error (แต่ละแบบมีสีและไอคอนต่างกัน)"""
        icon, color = {"info": ("", C["muted"]), "busy": ("⏳ ", C["text"]),
                       "ok": ("✓ ", C["ok"]), "error": ("⚠ ", C["error"])}.get(kind, ("", C["muted"]))
        self.status_label.configure(text=icon + str(text).replace("\n", "  "), text_color=color)

    def _update_busy(self, force=False):
        """แสดงแถบวิ่งด้านขวาของแถบสถานะเมื่อมีงานเบื้องหลังทำอยู่ ซ่อนเมื่อเสร็จหมด"""
        if self._busy > 0:
            if force or not self.busy_bar.winfo_ismapped():
                self.busy_bar.grid(row=0, column=1, padx=16)
                self.busy_bar.start()
            self.state_pill.configure(text=tr("  ● กำลังทำงาน  ", "  ● WORKING  "), text_color=C["warn"], fg_color=C["card"])
        else:
            self.busy_bar.stop()
            self.busy_bar.grid_forget()
            self.state_pill.configure(text=tr("  ● พร้อม  ", "  ● READY  "), text_color=C["ok"], fg_color=C["card"])

    def report_error(self, error, prefix=None, tb=None):
        """แสดง error ที่แถบสถานะ (สีแดง) และเก็บรายละเอียดลงไฟล์ error.log ไว้ดูทีหลัง โปรแกรมทำงานต่อได้"""
        try:
            self.set_status(f"{prefix or tr('เกิดข้อผิดพลาด', 'Error')}: {error}", "error")
            os.makedirs(config.APP_DIR, exist_ok=True)
            with open(os.path.join(config.APP_DIR, "error.log"), "a", encoding="utf-8") as f:
                f.write("".join(traceback.format_exception(type(error), error, tb or error.__traceback__)) + "\n")
        except Exception:
            pass

    # ---------- งานเบื้องหลัง ----------

    def ui(self, func, *args, **kwargs):
        """ฝากงานแก้หน้าจอจาก thread อื่นไว้ในคิว (thread อื่นแตะ widget ตรง ๆ ไม่ได้)
        จำเลขรุ่นหน้าจอไว้ด้วย ถ้าหน้าจอถูกสร้างใหม่ไปแล้ว (เปลี่ยนภาษา) งานนี้จะถูกข้าม"""
        self._ui_queue.put((self._generation, func, args, kwargs))

    def _process_ui_queue(self):
        """main thread ดึงงานจากคิวมาทำทีละอัน แล้วนัดตัวเองให้มาเช็กใหม่ในอีก 50 มิลลิวินาทีด้วย .after()"""
        try:
            while True:
                generation, func, args, kwargs = self._ui_queue.get_nowait()
                if generation != self._generation:
                    continue
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    self.report_error(e)
        except queue.Empty:
            pass
        self.after(50, self._process_ui_queue)

    def run_task(self, name, work, on_done=None, button=None):
        """รัน work() ใน thread แยก ระหว่างนั้นปิดปุ่มไว้กันกดซ้ำ และแถบสถานะขึ้นว่า "กำลัง..."
        เสร็จแล้วเรียก on_done(ผลลัพธ์, error) ใน main thread
        ถ้า work คืน (True/False, ข้อความ) จะเอาข้อความนั้นไปแสดงที่แถบสถานะให้อัตโนมัติ"""
        if button is not None:
            try:
                button.configure(state="disabled")
            except Exception:
                pass
        self._busy += 1
        self._update_busy()
        self.set_status(tr(f"กำลัง{name}...", f"{name}..."), "busy")
        generation = self._generation

        def finish(result, error):
            self._busy = max(0, self._busy - 1)
            self._update_busy()
            if button is not None:
                try:
                    button.configure(state="normal")
                except Exception:
                    pass
            if error is not None:
                self.report_error(error, tr(f"{name}ไม่สำเร็จ", f"{name} failed"))
            elif isinstance(result, tuple) and len(result) >= 2 and isinstance(result[0], bool):
                self.set_status(result[1], "ok" if result[0] else "error")
            else:
                self.set_status(tr(f"{name}เสร็จแล้ว", f"{name}: done"), "ok")
            if on_done:
                try:
                    on_done(result, error)
                except Exception as e:
                    self.report_error(e)

        def worker():
            try:
                result = work()
                error = None
            except Exception as e:
                result, error = None, e
            # ใส่คิวตรง ๆ พร้อมเลขรุ่นตอนเริ่มงาน ถ้าเปลี่ยนภาษาไปแล้ว ผลลัพธ์จะถูกข้าม (แต่ตัวนับงานต้องลดลงเสมอ)
            self._ui_queue.put((self._generation, self._finish_task, (finish, generation, result, error), {}))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_task(self, finish, generation, result, error):
        """จบงานเบื้องหลัง: ถ้าหน้าจอยังเป็นรุ่นเดิมก็เรียก finish ตามปกติ ถ้าเปลี่ยนภาษาไปแล้วแค่ลดตัวนับงาน"""
        if generation == self._generation:
            finish(result, error)
        else:
            self._busy = max(0, self._busy - 1)
            self._update_busy()

    # ---------- งานที่หลายหน้าใช้ร่วมกัน (รวมถึงปุ่ม "ทำเลย" ของ AI) ----------

    def task_clean_default(self):
        """ลบไฟล์ขยะทุกหมวดที่ติ๊กไว้ตั้งแต่แรก (ไม่รวมถังขยะ) คืน (สำเร็จ, ข้อความ)"""
        r = cleaner.clean(cleaner.default_keys())
        return True, tr(f"ลบไฟล์ขยะแล้ว ได้พื้นที่คืน {format_size(r['freed'])} ({r['deleted']:,} ไฟล์)",
                        f"Junk cleaned: {format_size(r['freed'])} freed ({r['deleted']:,} files)")

    def task_restore_defaults(self):
        """คืนค่าทุกอย่างที่ Polo Optimizer เคยปรับกลับเป็นค่าเริ่มต้นของ Windows:
        ค่าเกม/เมาส์/อัดวิดีโอ/แผนพลังงาน (game_tweaks) และเปิดโปรแกรมเปิดพร้อมเครื่องที่โปรแกรมนี้เคยปิดกลับมา
        (ไม่ไปยุ่งกับตัวที่ผู้ใช้ปิดเองใน Task Manager) คืน (สำเร็จ, ข้อความสรุป)"""
        ok, done, failed = game_tweaks.restore_windows_defaults(self.config_data.get("ultimate_plan_guid", ""))
        wanted = [tuple(e) for e in self.config_data.get("startup_disabled", [])]
        reenabled = 0
        for item in startup.list_startup():
            if (item["source"], item["name"]) in wanted and not item["enabled"]:
                try:
                    startup.set_enabled(item, True)
                    reenabled += 1
                except OSError:
                    failed.append(item["name"])
        if reenabled:
            done.append(tr(f"เปิดโปรแกรมเปิดพร้อมเครื่องกลับ {reenabled} ตัว", f"Re-enabled {reenabled} startup app(s)"))
        self.config_data = config.save_config({"ultimate_plan_guid": "", "startup_disabled": []})
        text = tr("คืนค่าเริ่มต้นแล้ว: ", "Defaults restored: ") + ", ".join(done)
        if failed:
            text += tr("  (ทำไม่สำเร็จ: ", "  (failed: ") + ", ".join(failed) + ")"
        return not failed, text

    def task_high_performance(self):
        """เปลี่ยนเป็นแผนพลังงานแรงสุด ถ้าต้องสร้าง Ultimate ใหม่ก็จำ GUID ไว้ใน config"""
        ok, msg, guid = game_tweaks.use_high_performance(self.config_data.get("ultimate_plan_guid", ""))
        if guid:
            self.config_data = config.save_config({"ultimate_plan_guid": guid})
        return ok, msg

    def run_action(self, action, button=None, on_done=None):
        """ทำ action ตามรหัส (ใช้กับปุ่ม "ทำเลย" ของ AI และปุ่มในหน้าต่าง ๆ)
        รหัสที่เป็นการเปลี่ยนหน้า/เปิดหน้าต่างของ Windows ทำทันที ส่วนงานที่ใช้เวลาจะรันใน thread แยก
        รหัสที่ไม่อยู่ในรายการอนุญาตจะไม่ถูกทำเด็ดขาด"""
        if action not in ai_assistant.ALLOWED_ACTIONS and not action.startswith("install:"):
            self.set_status(tr(f"ไม่รู้จักคำสั่ง {action}", f"Unknown action {action}"), "error")
            return
        pages = {"open_drivers": "drivers", "open_startup": "startup"}
        if action in pages:
            self.show_page(pages[action])
            return
        openers = {
            "open_taskmgr": lambda: open_system_tool("taskmgr.exe"),
            "open_security": lambda: open_url("windowsdefender:"),
            "open_sound": lambda: open_url("ms-settings:sound"),
            "open_windows_update": drivers.open_windows_update,
            "open_system_restore": troubleshoot.open_system_restore,
        }
        if action in openers:
            try:
                openers[action]()
                self.set_status(tr("เปิดให้แล้ว", "Opened"), "ok")
                if on_done:
                    on_done((True, ""), None)
            except Exception as e:
                self.report_error(e, tr("เปิดไม่ได้", "Couldn't open"))
            return
        if action.startswith("install:"):
            app_id = action.split(":", 1)[1]
            if app_id not in installer.allowed_ids():
                self.set_status(tr("แอปนี้ไม่อยู่ในรายการที่อนุญาต", "This app isn't in the allowed list"), "error")
                return
            self.show_page("install")
            self.pages["install"].install_ids([app_id])
            return
        works = {
            "clean_junk": self.task_clean_default,
            "clear_ram": ram.clear_ram,
            "game_tweaks": game_tweaks.apply_recommended,
            "high_performance": self.task_high_performance,
            "restore_point": restore_point.create_restore_point,
            "repair_windows": troubleshoot.repair_windows,
            "fix_network": lambda: troubleshoot.reset_network(
                progress=lambda step: self.ui(self.set_status, tr(f"กำลังรีเซ็ตเน็ต {step}...", f"Resetting network {step}..."), "busy")),
            "restart_explorer": troubleshoot.restart_explorer,
            "restore_defaults": self.task_restore_defaults,
        }
        name = ai_assistant.action_label(action)[0]
        self.run_task(name, works[action], on_done=on_done, button=button)


def main():
    """จุดเริ่มโปรแกรม: เช็กสิทธิ์ Admin (ถ้ายังไม่มีให้ขอ) แล้วเปิดหน้าต่างหลัก"""
    admin = is_admin()
    if not admin and "--no-elevate" not in sys.argv:
        if relaunch_as_admin():
            sys.exit(0)
    try:
        # บอก Windows ว่าเป็นแอปของเราเอง ไอคอนบนทาสก์บาร์จะเป็นโลโก้ Polo ไม่ใช่ไอคอนของ Python
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Polo.Optimizer")
    except Exception:
        pass
    try:
        app = App(admin=admin, splash="--no-splash" not in sys.argv)
        app.mainloop()
    except Exception as e:
        # error ตอนเปิดโปรแกรมยังไม่มีแถบสถานะให้แสดง เลยใช้หน้าต่างแจ้งเตือนแทน
        try:
            messagebox.showerror(APP_NAME, f"{tr('เปิดโปรแกรมไม่สำเร็จ', 'Failed to start')}\n{e}")
        except Exception:
            pass


if __name__ == "__main__":
    main()

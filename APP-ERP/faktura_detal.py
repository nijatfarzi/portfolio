# faktura_detal.py — müasir CTk görünüşü + etibarlı PDF
from email.mime import base
import customtkinter as ctk
import sqlite3, os, sys, subprocess
from tkinter import ttk, messagebox
from datetime import datetime
from single_instance import is_claimed, bring_to_front

# ---- PDF (ReportLab) ----
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# >>> Tema & şriftləri ayarlardan tətbiq et:
try:
    from ui_theme import apply_theme_global
    apply_theme_global()
except Exception:
    pass

from ui_theme import PDF_FONT_PATH
if PDF_FONT_PATH:
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", PDF_FONT_PATH))
        PDF_BASE_FONT = "DejaVu"
    except Exception:
        PDF_BASE_FONT = "Helvetica"
else:
    PDF_BASE_FONT = "Helvetica"

# ---- Tema (əgər varsa istifadə et) ----
try:
    from ui_theme import (
        COLOR_PRIMARY, COLOR_PRIMARY_HOVER, COLOR_SUCCESS, COLOR_BG_SOFT,
        FONT_BOLD, FONT_NORMAL, enable_windows_chrome, logger
    )
except Exception:
    COLOR_PRIMARY = "#2563eb"
    COLOR_PRIMARY_HOVER = "#1d4ed8"
    COLOR_SUCCESS = "#16a34a"
    COLOR_BG_SOFT = "#f1f5f9"
    FONT_BOLD = ("Segoe UI", 14, "bold")
    FONT_NORMAL = ("Segoe UI", 12, "normal")
    enable_windows_chrome = None

# ---- PDF şrift qeydiyyatı (DejaVu varsa istifadə et) ----
def _register_pdf_font():    
    base_dir = os.path.dirname(__file__)
    dj = os.path.join(base_dir, "DejaVuSans.ttf")
    if os.path.exists(dj):
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", dj))
            return "DejaVu"
        except Exception:
            pass
    # Windows sistem şriftini yoxla
    win_dejavu = r"C:\Windows\Fonts\DejaVuSans.ttf"
    if os.path.exists(win_dejavu):
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", win_dejavu))
            return "DejaVu"
        except Exception:
            pass
    return "Helvetica"

PDF_BASE_FONT = _register_pdf_font()


class FakturaDetalPenceresi(ctk.CTk):
    def __init__(self, faktura_identifier, master=None):
        super().__init__()
        if enable_windows_chrome:
            try: enable_windows_chrome(self)
            except Exception: pass

        from ui_theme import COLOR_BG_SOFT, FONT_BOLD, FONT_NORMAL, COLOR_PRIMARY, COLOR_PRIMARY_HOVER, COLOR_SUCCESS, button_style

        self.identifier = str(faktura_identifier or "").strip()
        self.title(f"📄 Faktura Detalı — {self.identifier or 'Seçim'}")
        self.geometry("1200x720")

        logger.info("Faktura detalı pəncərəsi başladılır...")
        # arxa fon tema rəngi
        try:
            self.configure(fg_color=COLOR_BG_SOFT)
        except Exception:
            pass

        # grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ------- BAŞLIQ (kart) -------
        header = ctk.CTkFrame(self, corner_radius=12, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)

        # başlıq şrift temadan
        title = ctk.CTkLabel(header, text="Faktura", font=FONT_BOLD)
        title.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))

        self.info_line = ctk.CTkLabel(header, text="Yüklənir...", font=FONT_NORMAL)
        self.info_line.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))

        # ------- DÜYMƏ PANELİ -------
        btnbar = ctk.CTkFrame(self, fg_color="transparent")
        btnbar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 6))
        btnbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(btnbar, text="").grid(row=0, column=0, sticky="w")  # sol boşluq

        # PDF ÇIXARIŞ — temadan rəng/hündürlük (size="lg"), height= vermirik
        self.btn_pdf = ctk.CTkButton(
            btnbar, text="PDF ÇIXARIŞ",
            **button_style("success", size="lg"),
            command=self.print_faktura
        )
        self.btn_pdf.grid(row=0, column=2, sticky="e", padx=(8, 0))

        # Fakturalar — temadan
        self.btn_fakturalar = ctk.CTkButton(
            btnbar, text="Fakturalar",
            **button_style("primary", size="lg"),
            command=self._open_fakturalar
        )
        self.btn_fakturalar.grid(row=0, column=3, sticky="e", padx=(8, 0))

        # ------- CƏDVƏL -------
        table_wrap = ctk.CTkFrame(self, corner_radius=12, fg_color="transparent")
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        self.scr_y = ctk.CTkScrollbar(table_wrap)
        self.scr_y.grid(row=0, column=1, sticky="ns")

        self.tree = ttk.Treeview(
            table_wrap,
            columns=("kod", "ad", "olcu", "cins", "say", "alis", "satis", "mebleg"),
            show="headings", yscrollcommand=self.scr_y.set, selectmode="browse"
        )
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        self.scr_y.configure(command=self.tree.yview)

        # Excel-vari stil (tema şrift/rəng)
        sty = ttk.Style(self)
        try: sty.theme_use("clam")
        except Exception: pass
        sty.configure(
            "Treeview",
            background="#ffffff", foreground="#000000",
            fieldbackground="#ffffff",
            rowheight=32, font=FONT_NORMAL,
            borderwidth=1, relief="solid"
        )
        sty.configure(
            "Treeview.Heading",
            background=COLOR_PRIMARY, foreground="white",
            font=FONT_BOLD, borderwidth=1, relief="solid"
        )
        sty.map(
            "Treeview",
            background=[("selected", COLOR_SUCCESS)],
            foreground=[("selected", "white")]
        )

        # sütun başlıqları + enlər
        heads = [("kod", "KOD", 110), ("ad", "AD", 320), ("olcu", "ÖLÇÜ", 95),
                ("cins", "CİNS", 95), ("say", "SAY", 70),
                ("alis", "ALİŞ", 90), ("satis", "SATIŞ", 90), ("mebleg", "MƏBLƏĞ", 110)]
        for cid, text, w in heads:
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=w, anchor="center")
        self.tree.column("ad", anchor="w")

        # zebra
        self.tree.tag_configure("odd", background="#f8fafc")
        self.tree.tag_configure("even", background="#ffffff")

        # məlumatlar
        self.faktura_info = None
        self.rows = []
        self._load_data()

    # ---------------- MƏLUMAT ----------------
    def _load_data(self):
        """Faktura başlığı və sətirləri yüklə (ayar temalı)."""
        logger.info("Faktura məlumatı yüklənir...")
        base = os.path.dirname(__file__)
        p1 = os.path.join(base, "erp.db")
        p2 = os.path.join(os.getcwd(), "erp.db")
        dbp = p1 if os.path.exists(p1) else p2
        conn = sqlite3.connect(dbp)

        try:
            cur = conn.cursor()
            ident = str(self.identifier or "").strip()
            if ident and ident.isdigit():
                cur.execute("""
                    SELECT f.faktura_no, f.tarix, f.tur, m.ad, m.telefon, f.id
                    FROM fakturalar f
                    JOIN musteriler m ON m.id=f.musteri_id
                    WHERE f.id=?
                """, (int(ident),))
            else:
                cur.execute("""
                    SELECT f.faktura_no, f.tarix, f.tur, m.ad, m.telefon, f.id
                    FROM fakturalar f
                    JOIN musteriler m ON m.id=f.musteri_id
                    WHERE f.faktura_no=?
                """, (ident,))
            r = cur.fetchone()
            if not r:
                self.info_line.configure(text="Qeyd tapılmadı")
                conn.close(); return

            self.faktura_info = {
                "faktura_no": r[0], "tarix": r[1], "tur": r[2],
                "musteri": r[3], "telefon": r[4] or "", "id": r[5],
            }

            gunluk = self._fmt_date(self.faktura_info["tarix"])
            tur = "ALİŞ" if (self.faktura_info["tur"] == "alis") else "SATIŞ"
            self.info_line.configure(
                text=f"No: {self.faktura_info['faktura_no']}   |   Tarix: {gunluk}   |   Növ: {tur}   |   Müştəri: {self.faktura_info['musteri']}"
            )

            # detallar
            cur.execute("""
                SELECT u.kod,
                    IFNULL(u.ad,''), IFNULL(u.olcu,''), IFNULL(u.cins,''),
                    IFNULL(fd.say,0),
                    IFNULL(fd.alis_qiymet,0),
                    IFNULL(fd.satis_qiymet,0),
                    IFNULL(fd.mebleg,0)
                FROM faktura_detal fd
                LEFT JOIN mehsullar u
                        ON u.kod = fd.mehsul_kod
                        AND IFNULL(u.cins,'') = IFNULL(fd.mehsul_cins,'')
                WHERE fd.faktura_id=?
            ORDER BY fd.id
            """, (self.faktura_info["id"],))
            self.rows = cur.fetchall()
            conn.close()

            # cədvələ əlavə et (zebra)
            for i, row in enumerate(self.rows):
                self.tree.insert("", "end", values=row, tags=("odd" if i%2 else "even",))
        except Exception as e:
            logger.error("Faktura məlumatı yüklənmədi: %s", e)
            self.info_line.configure(text=f"Səhv: {e}")

    def _fmt_date(self, s):
        logger.info("Tarix formatlanır...")
        # "YYYY-MM-DD" və ya "YYYY-MM-DD HH:MM" -> "dd.mm.yyyy" və ya "... HH:MM"
        try:
            if len(s) > 10:
                dt = datetime.strptime(s[:16], "%Y-%m-%d %H:%M")
                return dt.strftime("%d.%m.%Y %H:%M")
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except Exception:
            return s

    # ---------------- PDF ----------------
    def print_faktura(self):
        """Ayarlar > Faktura PDF qovluğuna müasir PDF yarat."""
        logger.info("Faktura çap olunur...")
        if not getattr(self, "faktura_info", None):
            from tkinter import messagebox
            messagebox.showwarning("Məlumat", "Faktura tapılmadı.")
            return

        fakt_no = self.faktura_info["faktura_no"]

        # PDF yolunu ayarlardan al
        try:
            from ui_theme import invoice_pdf_path, load_app_settings
            out_path = invoice_pdf_path(fakt_no, load_app_settings())
        except Exception:
            import os
            out_path = os.path.join(os.getcwd(), f"{fakt_no}.pdf")

        # DejaVu qeydiyyatı (əgər varsa)
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import os
            base_dir = os.path.dirname(__file__)
            dj = os.path.join(base_dir, "DejaVuSans.ttf")
            if os.path.exists(dj):
                pdfmetrics.registerFont(TTFont("DejaVu", dj))
                base_font = "DejaVu"
            elif os.path.exists(r"C:\Windows\Fonts\DejaVuSans.ttf"):
                pdfmetrics.registerFont(TTFont("DejaVu", r"C:\Windows\Fonts\DejaVuSans.ttf"))
                base_font = "DejaVu"
            else:
                base_font = "Helvetica"
        except Exception:
            base_font = "Helvetica"

        # PDF çəkilişi
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        c = canvas.Canvas(out_path, pagesize=A4)
        W, H = A4

        # Başlıq
        c.setFont(base_font, 18); c.drawCentredString(W/2, H-30*mm, "FAKTURA")
        c.setFont(base_font, 11)
        info = self.faktura_info
        left_x, right_x, y = 20*mm, 110*mm, H-45*mm
        c.drawString(left_x,  y,     f"FAKTURA NO : {info['faktura_no']}")
        c.drawString(left_x,  y-6*mm, f"MÜŞTƏRİ   : {info['musteri']}")
        c.drawString(right_x, y,     f"TARİX     : {self._fmt_date(info['tarix'])}")
        c.drawString(right_x, y-6*mm, f"TEL       : {info['telefon']}")

        # Cədvəl
        y = y - 14*mm
        headers = ["KOD","AD","ÖLÇÜ","CİNS","SAY","ALİŞ","SATIŞ","MƏBLƏĞ"]
        widths  = [22*mm, 62*mm, 18*mm, 18*mm, 14*mm, 22*mm, 22*mm, 26*mm]
        x = 10*mm
        c.setFont(base_font, 10)
        for h, w in zip(headers, widths):
            c.rect(x, y-6*mm, w, 7*mm, stroke=1, fill=0)
            c.drawString(x+2*mm, y-4.5*mm, h)
            x += w
        y -= 7*mm

        toplam = 0.0
        for row in self.rows:
            if y < 20*mm:  # yeni səhifə
                c.showPage()
                c.setFont(base_font, 10)
                y = H-20*mm
            x = 10*mm
            for val, w in zip(row, widths):
                c.rect(x, y-6*mm, w, 7*mm, stroke=1, fill=0)
                c.drawString(x+2*mm, y-4.5*mm, f"{val}")
                x += w
            try:
                toplam += float(row[-1] or 0)
            except Exception:
                pass
            y -= 7*mm

        # Toplam
        y -= 4*mm
        c.setFont(base_font, 11)
        c.drawRightString(W-12*mm, y, "CƏMİ:")
        c.drawRightString(W-10*mm, y, f"{toplam:,.2f} ₼")

        c.save()

        # Aç / bildir
        try:
            if os.name == "nt":
                os.startfile(out_path)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", out_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        from tkinter import messagebox
        logger.info("PDF saxlanıldı məlumatı göstərilir...")
        messagebox.showinfo("Məlumat", f"PDF saxlanıldı:\n{out_path}")

    def _export_pdf(self, filename):
        # ==== Hazırlıq ====
        logger.info("PDF ixrac olunur...")
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase.pdfmetrics import stringWidth
        import os

        base_font = PDF_BASE_FONT  # (DejaVu və ya Helvetica)
        bold_font = base_font
        # Bold şrift varsa qeyd et (DejaVuSans-Bold.ttf)
        for cand in [
            os.path.join(os.path.dirname(__file__), "DejaVuSans-Bold.ttf"),
            r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
        ]:
            try:
                if os.path.exists(cand):
                    pdfmetrics.registerFont(TTFont("DejaVu-Bold", cand))
                    bold_font = "DejaVu-Bold"
                    break
            except Exception:
                pass

        c = canvas.Canvas(filename, pagesize=A4)
        w, h = A4
        margin = 36
        inner_w = w - 2 * margin
        y = h - margin

        # --- köməkçi: mətn sığdır (lazım olsa kiçilt / ellipsis) ---
        def fit_text(txt, font_name, size, max_w, min_size=8):
            logger.info("Mətn sığdırılır: %s", txt)
            txt = "" if txt is None else str(txt)
            s = size
            while stringWidth(txt, font_name, s) > max_w and s > min_size:
                s -= 0.5
            if stringWidth(txt, font_name, s) <= max_w:
                return txt, s
            # hələ də sığmırsa ellipsis
            t = txt
            while stringWidth(t + "…", font_name, s) > max_w and len(t) > 1:
                t = t[:-1]
            return (t + "…"), s

        # --- sətr yazıcı ---
        def draw_kv(left_label, left_value, right_label, right_value, line_gap=18, size=11):
            logger.info("Açar-dəyər cütü çəkilir: %s=%s, %s=%s", left_label, left_value, right_label, right_value)
            nonlocal y
            # sol blok
            c.setFont(base_font, size); c.drawString(margin, y, left_label)
            val, s = fit_text(left_value, base_font, size, inner_w * 0.45)
            c.setFont(base_font, s); c.drawString(margin + 90, y, val)
            # sağ blok (sağa düzülmüş etiket, dəyər etiketdən sonra)
            right_x = margin + inner_w * 0.55
            c.setFont(base_font, size); c.drawRightString(right_x + 90, y, right_label)
            val2, s2 = fit_text(right_value, base_font, size, inner_w * 0.35)
            c.setFont(base_font, s2); c.drawString(right_x + 100, y, val2)
            y -= line_gap

        # ==== Başlıq ====
        title = "ALİŞ FAKTURASI" if self.faktura_info["tur"] == "alis" else "SATIŞ FAKTURASI"
        c.setFont(bold_font, 20)
        title_w = stringWidth(title, bold_font, 20)
        c.drawString((w - title_w) / 2.0, y, title)   # ORTADA
        y -= 28

        # ==== Üst məlumatlar (solda: Faktura No, Müştəri | sağda: Tel, Tarix) ====
        fakt_no = self.faktura_info["faktura_no"]
        musteri = self.faktura_info["musteri"]
        tel = self.faktura_info.get("telefon") or ""
        tarix = self._fmt_date(self.faktura_info["tarix"])

        draw_kv("FAKTURA NO:", fakt_no, "TEL:", tel, line_gap=18, size=12)
        draw_kv("MÜŞTƏRİ:", musteri, "TARİX:", tarix, line_gap=18, size=12)

        y -= 8  # kiçik boşluq

        # ==== Cədvəl ====
        # Kolon təyini
        headers = ["KOD", "AD", "ÖLÇÜ", "CİNS", "SAY", "ALİŞ", "SATIŞ", "MƏBLƏĞ"]
        weights = [1, 3, 1, 1, 1, 1, 1, 1]  # cəmi 10
        col_w = [inner_w * wgt / sum(weights) for wgt in weights]
        row_h = 18
        pad_x = 4

        def new_page_with_header():
            nonlocal y
            c.showPage()
            y = h - margin
            # başlıq təkrarı
            c.setFont(bold_font, 20)
            tw = stringWidth(title, bold_font, 20)
            c.drawString((w - tw) / 2.0, y, title)
            y -= 28
            draw_kv("FAKTURA NO:", fakt_no, "TEL:", tel, line_gap=18, size=12)
            draw_kv("MÜŞTƏRİ:", musteri, "TARİX:", tarix, line_gap=18, size=12)
            y -= 8

        def ensure_space(rows_needed=1):
            logger.info("Sətirlər üçün yer yoxlanılır: %d...", rows_needed)
            nonlocal y
            need = rows_needed * row_h + 40  # alt cəmi və s. üçün pay
            if y - need < margin:
                new_page_with_header()

        # --- başlıq çək ---
        ensure_space(2)
        c.setLineWidth(1.2)
        x = margin
        c.setFont(bold_font, 12)  # BAŞLIQ BOLD
        for i, head in enumerate(headers):
            cw = col_w[i]
            c.rect(x, y - row_h, cw, row_h, stroke=1, fill=0)
            txt, s = fit_text(head, bold_font, 12, cw - 2 * pad_x)
            c.setFont(bold_font, s)
            c.drawString(x + pad_x, y - row_h + 4, txt)
            x += cw
        y -= row_h

        # --- sətirlər ---
        toplam = 0.0
        c.setFont(base_font, 11)
        for r in self.rows:
            ensure_space(1)
            kod, ad, olcu, cins, say, alis, satis, mebleg = r
            toplam += float(mebleg or 0)

            vals = [
                kod,
                ad,
                olcu,
                cins,
                f"{float(say or 0):.0f}",
                f"{float(alis or 0):.2f}",
                f"{float(satis or 0):.2f}",
                f"{float(mebleg or 0):.2f}",
            ]
            x = margin
            for i, v in enumerate(vals):
                cw = col_w[i]
                c.rect(x, y - row_h, cw, row_h, stroke=1, fill=0)
                txt, s = fit_text(v, base_font, 11, cw - 2 * pad_x)
                c.setFont(base_font, s)
                c.drawString(x + pad_x, y - row_h + 4, txt)
                x += cw
            y -= row_h

        # --- CƏMİ (eyni cədvəldə ən altda, BOLD) ---
        ensure_space(1)
        x = margin
        for i, cw in enumerate(col_w):
            c.rect(x, y - row_h, cw, row_h, stroke=1, fill=0)
            if i == len(col_w) - 2:
                # "CƏMİ" etiketi
                txt, s = fit_text("CƏMİ", bold_font, 12, cw - 2 * pad_x)
                c.setFont(bold_font, s)  # BOLD
                c.drawString(x + pad_x, y - row_h + 4, txt)
            elif i == len(col_w) - 1:
                # dəyər
                val = f"{toplam:.2f}"
                txt, s = fit_text(val, bold_font, 12, cw - 2 * pad_x)
                c.setFont(bold_font, s)  # BOLD
                c.drawString(x + pad_x, y - row_h + 4, txt)
            x += cw
        y -= row_h

        c.save()

    def _open_fakturalar(self):
        logger.info("Fakturalar açılır...")
        path = os.path.join(os.path.dirname(__file__), "fakturalar.py")
        if is_claimed("fakturalar"):
            # Açıqsa yeni nüsxə açma; mövcud siyahını önə gətir
            bring_to_front("Fakturalar")
            return
        # Bağlıdırsa aç
        try:
            if os.name == "nt":
                q = lambda s: f'"{s}"'
                cmd = " ".join([q(sys.executable), q(path)])
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen([sys.executable, path], shell=False)
        except Exception as e:
            logger.error("Fakturalar pəncərəsi açıla bilmədi: %s", e)
            messagebox.showerror("Səhv", f"Fakturalar açıla bilmədi:\n{e}")


if __name__ == "__main__":    
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    app = FakturaDetalPenceresi(faktura_identifier=arg or "")
    app.mainloop()

# fakturalar.py — Fakturalar siyahısı (Hamısı/Alış/Satış filtri, sütun filtrləri,
# Excel-grid görünüşü, böyük şriftli düymələr, tarix/vaxt ağıllı göstərim)
import customtkinter as ctk
import sqlite3
from tkinter import ttk, messagebox
import os, sys, subprocess
from single_instance import claim, is_claimed, bring_to_front
from ui_theme import (
    APP_TITLE, APPEARANCE_MODE, COLOR_THEME,
    COLOR_PRIMARY, COLOR_PRIMARY_HOVER,
    COLOR_BG_SOFT, COLOR_ACCENT, COLOR_ACCENT_DARK,
    COLOR_SUCCESS, COLOR_WARNING,
    FONT_H1, FONT_H2, FONT_BOLD, FONT_NORMAL,
    button_style, enable_windows_chrome, logger, log_call
)

# >>> Tema və şriftləri ayarlardan tətbiq et:
try:
    from ui_theme import apply_theme_global
    apply_theme_global()
except Exception:
    pass

class FakturalarPenceresi(ctk.CTk):
    def __init__(self):
        super().__init__()
        if enable_windows_chrome:
            try:
                enable_windows_chrome(self)
            except Exception:
                pass

        self.title(f"{APP_TITLE} — Fakturalar")
        self.geometry("1280x720")
        self.minsize(1100, 600)
        self.configure(fg_color=COLOR_BG_SOFT)

        # ---- filtr vəziyyətləri
        self.tur_filter = "Hamısı"      # "Hamısı" | "Alış" | "Satış"
        self.q_no = ctk.StringVar()
        self.q_musteri = ctk.StringVar()
        self.q_tarih = ctk.StringVar()
        self._sort_col = "TARİX"   # default olaraq tarix
        self._sort_desc = True     # default: yeni tarix yuxarıda (desc)
        logger.info("FakturalarPenceresi init: tur_filter=%s", self.tur_filter)

        # ---- UI
        self._build_ui()
        self._load_and_fill()

        # qısa yol
        self.bind("<F5>", lambda _e: self._load_and_fill())

    # ================= UI =================
    def _build_ui(self):
        # YUXARI PANEL
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(top, text="🧾 Fakturalar", font=FONT_H1).pack(side="left")

        # Sağ tərəfə "Hamısı / Alış / Satış" filtri (default Hamısı)
        self.filter_combo = ctk.CTkComboBox(
            top, values=["Hamısı", "Alış", "Satış"],
            command=lambda _v: self._on_tur_change(),
            width=120, font=FONT_BOLD
        )
        self.filter_combo.set("Hamısı")
        self.filter_combo.pack(side="right", padx=(10, 0))

        # Yenilə (tema/stil ui_theme-dən; ölçü üçün size="lg")
        ctk.CTkButton(
            top, text="Yenilə (F5)",
            **button_style("primary", size="lg"),
            width=130,
            command=self._load_and_fill
        ).pack(side="right", padx=(8, 4))

        # Əsas Menyu (tamamilə temadan; override yoxdur)
        ctk.CTkButton(
            top, text="ƏSAS MENYU",
            **button_style("accent", size="lg"),
            width=130,
            command=self._open_mainmenu
        ).pack(side="right", padx=(4, 8))

        # SÜTUN FİLTR PANELİ (başlıq üstü)
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(filter_bar, text="🔎 No:", font=FONT_NORMAL).pack(side="left")
        ctk.CTkEntry(filter_bar, width=150, textvariable=self.q_no, font=FONT_NORMAL)\
            .pack(side="left", padx=(4, 14))

        ctk.CTkLabel(filter_bar, text="🔎 Müştəri:", font=FONT_NORMAL).pack(side="left")
        ctk.CTkEntry(filter_bar, width=230, textvariable=self.q_musteri, font=FONT_NORMAL)\
            .pack(side="left", padx=(4, 14))

        ctk.CTkLabel(filter_bar, text="🔎 Tarix (gg.aa.yyyy):", font=FONT_NORMAL).pack(side="left")
        ctk.CTkEntry(filter_bar, width=150, textvariable=self.q_tarih, font=FONT_NORMAL)\
            .pack(side="left", padx=(4, 0))

        # dəyişəndə cədvəli yenilə
        for v in (self.q_no, self.q_musteri, self.q_tarih):
            v.trace_add("write", lambda *_: self._load_and_fill())

        # CƏDVƏL ÇƏRÇİVƏSİ
        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        self.scroll_y = ctk.CTkScrollbar(table_frame)
        self.scroll_y.pack(side="right", fill="y")

        self.scroll_x = ctk.CTkScrollbar(table_frame, orientation="horizontal")
        self.scroll_x.pack(side="bottom", fill="x")

        columns = ("NO", "TARİX", "NÖV", "MÜŞTƏRİ", "CƏMİ")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set,
            selectmode="browse"
        )
        self.tree.pack(fill="both", expand=True)
        self.scroll_y.configure(command=self.tree.yview)
        self.scroll_x.configure(command=self.tree.xview)

        # İki dəfə klikləmə ilə detal aç
        self.tree.bind("<Double-1>", lambda e: self._open_selected_invoice())

        # Excel-vari grid stili
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#ffffff", foreground="#000000",   # qara yazı
            fieldbackground="#ffffff",
            rowheight=32, font=FONT_NORMAL,
            borderwidth=1, relief="solid"
        )
        style.configure(
            "Treeview.Heading",
            background=COLOR_PRIMARY, foreground="white",
            font=FONT_BOLD, borderwidth=1, relief="solid"
        )
        style.map(
            "Treeview",
            background=[("selected", COLOR_SUCCESS)],  # yaşıl arxa fon
            foreground=[("selected", "white")]         # ağ yazı
        )

        headings = {
            "NO": "NO",
            "TARİX": "TARİX",
            "NÖV": "NÖV",
            "MÜŞTƏRİ": "MÜŞTƏRİ",
            "CƏMİ": "CƏMİ"
        }
        widths = {"NO":160, "TARİX":160, "NÖV":90, "MÜŞTƏRİ":360, "CƏMİ":140}
        anchors = {"NO":"w", "TARİX":"center", "NÖV":"center", "MÜŞTƏRİ":"w", "CƏMİ":"e"}

        for c in columns:
            # başlığa klikləyəndə sıralama dəyişsin
            self.tree.heading(c, text=f"{headings[c]} ⇅", command=lambda col=c: self._toggle_sort(col))
            self.tree.column(c, width=widths[c], anchor=anchors[c])

        # zebra
        self.tree.tag_configure("odd", background="#f8fafc")
        self.tree.tag_configure("even", background="#ffffff")

        # ALT DÜYMƏ PANELİ
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(0, 12))

        left_box = ctk.CTkFrame(bottom, fg_color="transparent")
        left_box.pack(side="left")

        right_box = ctk.CTkFrame(bottom, fg_color="transparent")
        right_box.pack(side="right")

        # Sol: ANBAR (Stok)
        ctk.CTkButton(
            left_box, text="📦 ANBAR",
            **button_style("primary", size="lg"),
            width=160,
            command=self._open_stok
        ).pack(side="left", padx=6)

        # Sağ: FAKTURANI AÇ
        ctk.CTkButton(
            right_box, text="FAKTURANI AÇ",
            **button_style("success", size="lg"),
            width=160,
            command=self._open_selected_invoice
        ).pack(side="right", padx=6)


# -----------------------------------
    def _set_heading_icons(self):
        """Aktiv sütunda ▲/▼, digərlərində ⇅ göstər."""
        for col in ("NO","TARİX","NÖV","MÜŞTƏRİ","CƏMİ"):
            base = col
            if col == self._sort_col:
                arrow = "▼" if self._sort_desc else "▲"
                text = f"{base} {arrow}"
            else:
                text = f"{base} ⇅"
            self.tree.heading(col, text=text, command=lambda c=col: self._toggle_sort(c))

    def _toggle_sort(self, col):
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = False
        # cədvəli yenidən dolduranda sıralayacağıq
        self._load_and_fill()

    def _apply_sort(self, rows):
        """
        rows: [ (no, gtarix, nov, musteri, cemi_str) ]  # ekrana çıxacaq hallar
        Sütuna görə açar yaradıb sıralayır.
        """
        col = self._sort_col
        idx = {"NO":0, "TARİX":1, "NÖV":2, "MÜŞTƏRİ":3, "CƏMİ":4}[col]

        def parse_date(s):
            # "dd.mm.yyyy" və ya "dd.mm.yyyy HH:MM"
            try:
                parts = s.split(" ")
                d = parts[0]
                dd, mm, yyyy = d.split(".")
                if len(parts) > 1:
                    hh, mi = parts[1].split(":")
                else:
                    hh, mi = "00", "00"
                # İl-öncəli tuple, düzgün xronoloji sıralama verir
                return (int(yyyy), int(mm), int(dd), int(hh), int(mi))
            except:
                return (0,0,0,0,0)

        def keyfunc(r):
            v = r[idx]
            if col == "CƏMİ":
                # "1 234.56 ₼" → ədədi
                try:
                    return float(str(v).replace("₼","").replace(" ", "").replace("\xa0",""))
                except:
                    return -1e18
            if col == "TARİX":
                return parse_date(str(v))
            # string sütunlar: böyük/kiçik fərqsiz
            return str(v or "").casefold()

        return sorted(rows, key=keyfunc, reverse=self._sort_desc)

    # ================ DATA / SORĞU =================
    def _connect(self):
        return sqlite3.connect("erp.db")

    def _on_tur_change(self):
        self.tur_filter = self.filter_combo.get()
        self._load_and_fill()


    def _build_where(self):
        """Filtr paneli və növ combobox-una görə WHERE və parametrləri qaytarır."""
        where = []
        params = []

        # Növ filtri
        if self.tur_filter == "Alış":
            where.append("f.tur='alis'")
        elif self.tur_filter == "Satış":
            where.append("f.tur='satis'")

        # No filtri
        qno = (self.q_no.get() or "").strip()
        if qno:
            where.append("f.faktura_no LIKE ?")
            params.append(f"%{qno}%")

        # Müştəri filtri
        qmus = (self.q_musteri.get() or "").strip()
        if qmus:
            where.append("m.ad LIKE ?")
            params.append(f"%{qmus}%")

        # Tarix filtri (gg.aa.yyyy tam bərabər)
        qtar = (self.q_tarih.get() or "").strip()
        if qtar:
            # f.tarix TEXT ola bilər; vaxt yoxdursa yalnız tarixi, varsa tarix+vaxt var
            where.append("""
                CASE 
                    WHEN length(f.tarix) > 10 THEN strftime('%d.%m.%Y', f.tarix)
                    ELSE strftime('%d.%m.%Y', f.tarix)
                END = ?
            """)
            params.append(qtar)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        return where_sql, params

    def _load_and_fill(self):
        # cədvəli təmizlə
        for i in self.tree.get_children():
            self.tree.delete(i)

        where_sql, params = self._build_where()

        try:
            conn = self._connect()
            cur = conn.cursor()
            # Tarix göstərimi: vaxt varsa "gg.aa.yyyy SS:DD", yoxdursa "gg.aa.yyyy"
            cur.execute(f"""
                SELECT 
                    f.faktura_no AS no,
                    CASE 
                        WHEN length(f.tarix) > 10 
                            THEN strftime('%d.%m.%Y %H:%M', f.tarix)
                        ELSE strftime('%d.%m.%Y', f.tarix)
                    END AS g_tarix,
                    CASE f.tur WHEN 'alis' THEN 'ALIŞ' ELSE 'SATIŞ' END AS nov,
                    IFNULL(m.ad,'') AS musteri,
                    IFNULL(SUM(fd.mebleg),0.0) AS cemi
                FROM fakturalar f
                LEFT JOIN musteriler m ON m.id = f.musteri_id
                LEFT JOIN faktura_detal fd ON fd.faktura_id = f.id
                {where_sql}
                GROUP BY f.id
                ORDER BY f.tarix DESC
            """, params)
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            print("Faktura siyahısı xətası:", e)
            rows = []

        # ekrana çıxacaq hallar
        to_display = [
            (no, gtarix, nov, musteri, f"{float(cemi):.2f} ₼")
            for (no, gtarix, nov, musteri, cemi) in rows
        ]

        # 1) aktiv sütuna görə sırala
        to_display = self._apply_sort(to_display)

        # 2) başlıq ikonlarını yenilə
        self._set_heading_icons()

        # 3) yaz
        for i, row in enumerate(to_display):
            tag = "odd" if i % 2 else "even"
            self.tree.insert("", "end", values=row, tags=(tag,))


    # ============ ƏMƏLİYYATLAR ============
    def _open_mainmenu(self):
        path = os.path.join(os.path.dirname(__file__), "ana_menu.py")
        logger.info("ƏSAS MENYU açılır...")
        try:
            if os.name == "nt":
                q = lambda s: f'"{s}"'
                subprocess.Popen(" ".join([q(sys.executable), q(path)]), shell=True)
            else:
                subprocess.Popen([sys.executable, path], shell=False)
        except Exception as e:
            messagebox.showerror("Xəta", f"ƏSAS MENYU açıla bilmədi:\n{e}")
            logger.error("ƏSAS MENYU açma xətası: %s", e)
            return
        self.after(50, self.destroy)   
    
    def _open_stok(self):
        path = os.path.join(os.path.dirname(__file__), "stok.py")
        logger.info("Anbar idarəetməsi açılır...")
        try:
            if os.name == "nt":
                q = lambda s: f'"{s}"'
                subprocess.Popen(" ".join([q(sys.executable), q(path)]), shell=True)
            else:
                subprocess.Popen([sys.executable, path], shell=False)
        except Exception as e:
            messagebox.showerror("Xəta", f"Anbar açıla bilmədi:\n{e}")
            logger.error("Anbar açma xətası: %s", e)
            return
        self.after(50, self.destroy)   # <-- os._exit(0) əvəzinə



    def _open_selected_invoice(self):
        item = self.tree.focus()
        if not item:
            messagebox.showinfo("Məlumat", "Zəhmət olmasa bir faktura seçin."); 
            logger.warning("Heç bir faktura seçilməyib.")
            return

        no = self.tree.item(item, "values")[0]  # birinci sütun: faktura no

        # Detal pəncərəsi artıq açıqdırsa yeni nüsxə açma, önə gətir
        if is_claimed("detal"):
            bring_to_front("Faktura Detalı")
            return

        # Deyilsə yeni faktura pəncərəsi başlat (no parametri ilə)
        path = os.path.join(os.path.dirname(__file__), "faktura_detal.py")
        logger.info("Faktura pəncərəsi açılır...")
        try:
            if os.name == "nt":
                q = lambda s: f'"{s}"'
                cmd = " ".join([q(sys.executable), q(path), q(no)])
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen([sys.executable, path, no], shell=False)
        except Exception as e:
            messagebox.showerror("Xəta", f"Detal açıla bilmədi:\n{e}")
            logger.error("Detal açma xətası: %s", e)

# ================= İCRA =================
if __name__ == "__main__":
    if not claim("fakturalar"):
        sys.exit(0)

    ctk.set_appearance_mode(APPEARANCE_MODE)
    ctk.set_default_color_theme(COLOR_THEME)
    app = FakturalarPenceresi()
    app.mainloop()

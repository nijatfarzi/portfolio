# stok.py — Anbar (Əsas Menyu / Faktura ver düymələri, başlıqda sıralama ikonları,
# "excel-vari" grid görünüşü, az stok < 50)
import customtkinter as ctk
import sqlite3
from tkinter import ttk
import subprocess, sys, os
from tkinter import messagebox
from ui_theme import (
    FONT_H1, FONT_NORMAL, FONT_BOLD,
    COLOR_PRIMARY, COLOR_PRIMARY_HOVER,
    COLOR_ACCENT, COLOR_ACCENT_DARK, COLOR_BG_SOFT, COLOR_SUCCESS, COLOR_WARNING, 
    button_style, logger
)
from single_instance import is_claimed, bring_to_front

# Standart Windows başlıq çubuğu (əgər varsa)
try:
    from ui_theme import enable_windows_chrome
except Exception:
    enable_windows_chrome = None

# >>> Tema və şriftləri ayarlardan tətbiq et:
try:    
    from ui_theme import apply_theme_global
    apply_theme_global()
except Exception:
    pass


# ====== AYARLAR ======
LOW_STOCK_THRESHOLD = 50  # az stok həddi (50-dən az)

# Cədvəl sütunları və ədədi sütunlar
COLUMNS = ("KOD","AD","ÖLÇÜ","CİNS","STOK","ALIŞ","SATIŞ","MƏBLƏĞ")
NUMERIC_COLS = {"STOK","ALIŞ","SATIŞ","MƏBLƏĞ"}


class StokPenceresi(ctk.CTk):  # CTkToplevel -> CTk (əsas pəncərə)
    def __init__(self):
        super().__init__()
        if enable_windows_chrome:
            try:
                enable_windows_chrome(self)
            except Exception:
                pass

        self.title("📦 Anbar")
        self.geometry("1380x740")
        self.configure(fg_color=COLOR_BG_SOFT)

        logger.info("Anbar pəncərəsi yaradıldı.")

        # filter vəziyyətləri
        self.q_text = ctk.StringVar()
        self.q_cins = ctk.StringVar(value="")
        self.q_hide_zero = ctk.BooleanVar(value=False)
        self.q_max_stock = ctk.StringVar(value="")

        # başlıq sıralama vəziyyəti
        self._sort_col = "AD"
        self._sort_desc = False

        self._build_ui()
        self._load_kpis_and_table()
        # qısa yollar
        self.bind("<F5>", lambda _e: self._load_kpis_and_table())
        self.bind("<Return>", self._open_detail_process)  # Enter: detalları aç
        self.bind("<Control-f>", lambda _e: self.search_entry.focus_set())

    # ---------- UI ----------
    def _build_ui(self):
        # BAŞLIQ
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(header, text="📦 ANBAR", font=FONT_H1).pack(side="left")

        btns = ctk.CTkFrame(header, fg_color="transparent")
        btns.pack(side="right")

        # ƏSAS MENYU / YENİLƏ  → hamısı temadan, height vermirik
        ctk.CTkButton(
            btns, text="ƏSAS MENYU",
            **button_style("accent", size="lg"),
            width=150,
            command=self._open_mainmenu_process
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btns, text="YENİLƏ (F5)",
            **button_style("primary", size="lg"),
            width=150,
            command=self._load_kpis_and_table
        ).pack(side="left", padx=6)

        # KPI KARTLARI (dəyər şriftini eyni saxladım; istəsən ui_theme-ə böyük rəqəm şrifti əlavə edərik)
        kpi_bar = ctk.CTkFrame(self)
        kpi_bar.pack(fill="x", padx=14, pady=(0, 8))
        self.card_items = self._make_card(kpi_bar, "MAL NÖVÜ", "0")
        self.card_stock = self._make_card(kpi_bar, "ÜMUMİ STOK", "0")
        self.card_value = self._make_card(kpi_bar, "ÜMUMİ DƏYƏR", "0.00 ₼")
        self.card_low = self._make_card(kpi_bar, f"AZ STOK (<{LOW_STOCK_THRESHOLD})", "0", warn=True)

        # FİLTER BAR
        filter_bar = ctk.CTkFrame(self)
        filter_bar.pack(fill="x", padx=14, pady=(2, 8))

        self.search_entry = ctk.CTkEntry(
            filter_bar, width=380, placeholder_text="Kod / Ad axtar…",
            textvariable=self.q_text, font=FONT_NORMAL
        )
        self.search_entry.pack(side="left", padx=(10, 6), pady=8)
        self.search_entry.bind("<KeyRelease>", lambda _e: self._refresh_table())

        ctk.CTkLabel(filter_bar, text="Cins:", font=FONT_NORMAL).pack(side="left", padx=(10, 4))
        self.cins_combo = ctk.CTkComboBox(
            filter_bar, values=["", "kişi", "qadın"], width=120,
            variable=self.q_cins, command=lambda _v: self._refresh_table()
        )
        self.cins_combo.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(filter_bar, text="Stok ≤", font=FONT_NORMAL).pack(side="left", padx=(10, 4))
        e_max = ctk.CTkEntry(filter_bar, width=80, textvariable=self.q_max_stock, placeholder_text="məs. 50", font=FONT_NORMAL)
        e_max.pack(side="left", padx=(0, 8))
        e_max.bind("<KeyRelease>", lambda _e: self._refresh_table())

        cb = ctk.CTkCheckBox(filter_bar, text="Sıfır stokları gizlət",
                            variable=self.q_hide_zero, command=self._refresh_table)
        cb.pack(side="left", padx=(10, 8))

        # CƏDVƏL
        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=14, pady=(2, 12))

        self.scroll = ctk.CTkScrollbar(table_frame)
        self.scroll.pack(side="right", fill="y")

        self.tree = ttk.Treeview(
            table_frame, columns=COLUMNS, show="headings",
            yscrollcommand=self.scroll.set, selectmode="browse"
        )
        self.tree.pack(fill="both", expand=True)
        self.scroll.configure(command=self.tree.yview)

        widths = {"KOD":110,"AD":300,"ÖLÇÜ":110,"CİNS":110,"STOK":90,"ALIŞ":120,"SATIŞ":120,"MƏBLƏĞ":140}
        for c, w in widths.items():
            self.tree.heading(c, text=f"{c} ⇅", command=lambda col=c: self._toggle_sort(col))
            anchor = "w" if c=="AD" else ("e" if c in ("ALIŞ","SATIŞ","MƏBLƏĞ","STOK") else "center")
            self.tree.column(c, width=w, anchor=anchor)

        # grid + zebra + SEÇİM YAŞIL (əvvəl hover mavisi idi)
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except: pass
        style.configure("Treeview",
                        background="#ffffff", foreground="#0f172a",
                        fieldbackground="#ffffff",
                        rowheight=32, font=FONT_NORMAL,
                        borderwidth=1, relief="solid")
        style.configure("Treeview.Heading",
                        background=COLOR_PRIMARY, foreground="white",
                        font=FONT_BOLD,
                        borderwidth=1, relief="solid")
        style.map("Treeview",
                background=[("selected", COLOR_SUCCESS)],
                foreground=[("selected", "white")])

        self.tree.tag_configure("low", background="#fff7ed")   # açıq narıncı
        self.tree.tag_configure("zero", background="#fee2e2")  # açıq qırmızı
        self.tree.bind("<Double-1>", self._open_detail_process)

        # ALT DÜYMƏ ÇUBUĞU
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(pady=(0, 10))

        ctk.CTkButton(
            bottom, text="Zibil Qutusu",
            **button_style("warning", size="lg"),
            command=self._open_trash
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            bottom, text="Detalı Aç (Enter)",
            **button_style("success", size="lg"),
            command=self._open_detail_process
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            bottom, text="Faktura ver",
            **button_style("accent", size="lg"),
            width=150,
            command=self._open_faktura_process
        ).pack(side="left", padx=6)


    def _make_card(self, parent, title, value, warn=False):
        logger.info("Kart yaradılır: %s", title)
        card = ctk.CTkFrame(parent, fg_color="#ffffff", corner_radius=10)
        card.pack(side="left", expand=True, fill="x", padx=8, pady=8)
        ctk.CTkLabel(card, text=title, font=FONT_BOLD,
                     text_color=("#7c8494" if not warn else COLOR_WARNING)).pack(anchor="w", padx=16, pady=(14, 2))
        lbl = ctk.CTkLabel(card, text=value, font=("Segoe UI", 22, "bold"))
        lbl.pack(anchor="w", padx=16, pady=(0, 14))
        return lbl

    # ---------- DATA ----------
    def _connect(self):
        logger.info("Verilənlər bazasına qoşulur...")
        return sqlite3.connect("erp.db")

    def _load_kpis_and_table(self):
        # KPI-lar
        logger.info("KPI və cədvəl yüklənir...")
        try:
            conn = self._connect(); cur = conn.cursor()
            cur.execute("""
                SELECT
                COUNT(*),
                IFNULL(SUM(IFNULL(stok,0)), 0),
                IFNULL(SUM(IFNULL(stok,0) * IFNULL(alis_qiymet,0)), 0)
                FROM mehsullar
            """)

            items, total_stock, total_value = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM mehsullar WHERE IFNULL(stok,0) < ?", (LOW_STOCK_THRESHOLD,))
            low = cur.fetchone()[0]
            conn.close()
        except Exception:
            items = total_stock = low = 0; total_value = 0.0

        self.card_items.configure(text=f"{items:,}")
        self.card_stock.configure(text=f"{int(total_stock):,}")
        self.card_value.configure(text=f"{total_value:,.2f} ₼")
        self.card_low.configure(text=f"{low:,}")

        # Cədvəl
        self._refresh_table()

    def _build_where(self):
        # filtrləri SQL-ə çevir
        logger.info("WHERE şərti qurulur...")
        parts = []; params = []

        q = self.q_text.get().strip()
        if q:
            parts.append("(kod LIKE ? OR ad LIKE ?)")
            like = f"%{q}%"
            params += [like, like]

        cins = self.q_cins.get().strip()
        if cins:
            parts.append("IFNULL(cins,'') = ?")
            params.append(cins)

        if self.q_hide_zero.get():
            parts.append("IFNULL(stok,0) <> 0")

        max_s = self.q_max_stock.get().strip()
        if max_s.isdigit():
            parts.append("IFNULL(stok,0) <= ?")
            params.append(int(max_s))

        where = (" WHERE " + " AND ".join(parts)) if parts else ""
        return where, params

    def _apply_sort(self, rows):
        logger.info("Sıralama tətbiq olunur...")
        col = self._sort_col
        idx = COLUMNS.index(col)

        def key(row):
            v = row[idx]
            if col in NUMERIC_COLS:
                try:
                    return float(v)
                except:
                    return -1e18
            return str(v or "").casefold()

        return sorted(rows, key=key, reverse=self._sort_desc)

    def _set_heading_icons(self):
        # bütün başlıqlarda "⇅", aktiv olanda ▲/▼
        logger.info("Başlıq ikonları qurulur...")
        for col in COLUMNS:
            text = f"{col} ⇅"
            if col == self._sort_col:
                text = f"{col} {'▼' if self._sort_desc else '▲'}"
            self.tree.heading(col, text=text, command=lambda c=col: self._toggle_sort(c))

    def _toggle_sort(self, col):
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = False
        self._refresh_table()

    def _refresh_table(self):
        logger.info("Cədvəl yenilənir...")
        for i in self.tree.get_children():
            self.tree.delete(i)

        where, params = self._build_where()
        try:
            conn = self._connect(); cur = conn.cursor()
            cur.execute(f"""
                SELECT kod, ad, IFNULL(olcu,''), IFNULL(cins,''), IFNULL(stok,0),
                       IFNULL(alis_qiymet,0), IFNULL(satis_qiymet,0),
                       IFNULL(stok,0)*IFNULL(alis_qiymet,0)
                FROM mehsullar
                {where}
            """, params)
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            rows = []
            print("anbar siyahısı:", e)

        # başlıq sıralaması tətbiq et
        rows = self._apply_sort(rows)
        self._set_heading_icons()

        for r in rows:
            tags = []
            stok = r[4]
            if stok == 0:
                tags.append("zero")
            elif stok < LOW_STOCK_THRESHOLD:
                tags.append("low")
            self.tree.insert("", "end", values=(
                r[0], r[1], r[2], r[3],
                int(stok) if float(stok).is_integer() else stok,
                f"{float(r[5]):.2f} ₼", f"{float(r[6]):.2f} ₼",
                f"{float(r[7]):.2f} ₼"
            ), tags=tags)

    # ---------- ACTIONS ----------
    
    def _open_faktura_process(self):
        """Əsas Menyu-nu yeni prosesdə aç və bu pəncərəni bağla (tək pəncərə axını)."""
        logger.info("Faktura prosesi açılır...")
        path = os.path.join(os.path.dirname(__file__), "faktura.py")
        try:
            if os.name == "nt":
                # Windows: boşluqlu yollar üçün dırnaqlayıb shell=True
                q = lambda s: f'"{s}"'
                cmd = " ".join([q(sys.executable), q(path)])
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen([sys.executable, path], shell=False)
        except Exception as e:
            logger.error("Faktura açıla bilmədi: %s", e)
            messagebox.showerror("Xəta", f"Faktura açıla bilmədi:\n{e}")
            return
        os._exit(0)  # cari faktura pəncərəsini bağla

    def _open_mainmenu_process(self):
        """Əsas Menyu-nu yeni prosesdə aç və bu pəncərəni bağla (tək pəncərə axını)."""
        logger.info("Əsas menyu prosesi açılır...")
        path = os.path.join(os.path.dirname(__file__), "ana_menu.py")
        try:
            if os.name == "nt":
                # Windows: boşluqlu yollar üçün dırnaqlayıb shell=True
                q = lambda s: f'"{s}"'
                cmd = " ".join([q(sys.executable), q(path)])
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen([sys.executable, path], shell=False)
        except Exception as e:
            logger.error("Əsas Menyu açıla bilmədi: %s", e)
            messagebox.showerror("Xəta", f"Əsas Menyu açıla bilmədi:\n{e}")
            return
        os._exit(0)  # cari faktura pəncərəsini bağla

    def _open_trash(self):
        logger.info("Zibil qutusu açılır...")
        path = os.path.join(os.path.dirname(__file__), "trash.py")
        if is_claimed("trash"):
            bring_to_front("Məhsul Zibil Qutusu")   # mövcud pəncərəni önə gətir
            return
        subprocess.Popen([sys.executable, path], close_fds=True)

    def _open_detail_process(self, _e=None):
        logger.info("Detallı proses açılır...")
        sel = self.tree.focus()
        if not sel:
            return
        v = self.tree.item(sel)["values"]
        if not v:
            return
        kod = str(v[0]); cins = str(v[3] or "")
        script = os.path.join(os.path.dirname(__file__), "mehsul_detal.py")
        try:
            subprocess.Popen([sys.executable, script, kod, cins], close_fds=True)
        except Exception as exc:
            logger.error("Məhsul detalı açılarkən xəta: %s", exc)
            print("Məhsul detalı açılarkən xəta:", exc)


if __name__ == "__main__":
    import traceback, tkinter as tk
    from tkinter import messagebox
    try:
        from ui_theme import APPEARANCE_MODE, COLOR_THEME
        ctk.set_appearance_mode(APPEARANCE_MODE)
        ctk.set_default_color_theme(COLOR_THEME)

        app = StokPenceresi()
        app.mainloop()
    except Exception as e:
        # Konsola yaz + fayla qeyd et + msgbox göstər
        logger.error("Anbar pəncərəsi açılarkən xəta: %s", e)
        tb = traceback.format_exc()
        print(tb)
        try:
            with open("error_log_stok.txt", "w", encoding="utf-8") as f:
                f.write(tb)
        except:
            pass
        try:
            root = tk.Tk(); root.withdraw()
            logger.error("Anbar pəncərəsi açılarkən xəta: %s", e)
            messagebox.showerror("Xəta", f"Anbar pəncərəsi açılarkən xəta:\n\n{tb}")
        except:
            pass
        raise


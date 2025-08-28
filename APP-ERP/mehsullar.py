#   mehsullar.py — MƏHSULLAR (AD %20 qısalt, stok sətrini sola çək, tək "Filtrlə" altda,
# başlıqlarda həmişə ⇅ ikonu; aktivdə ▲/▼)
from email import header
import customtkinter as ctk
from tkinter import ttk, messagebox
import sqlite3, os, sys, subprocess
from single_instance import bring_to_front, claim, is_claimed
from ui_theme import (
    FONT_H1, FONT_BOLD, FONT_NORMAL,
    COLOR_PRIMARY, COLOR_PRIMARY_HOVER,
    COLOR_BG_SOFT, COLOR_SUCCESS, button_style, logger
)

# >>> Tema & şriftləri ayarlardan tətbiq et:
try:
    from ui_theme import apply_theme_global
    apply_theme_global()
except Exception:
    pass

# Tema / başlıq
try:
    from ui_theme import (
        FONT_H1, FONT_BOLD, FONT_NORMAL,
        COLOR_PRIMARY, COLOR_PRIMARY_HOVER,
        COLOR_BG_SOFT
    )
    from ui_theme import enable_windows_chrome
except Exception:
    FONT_H1 = ("Segoe UI", 22, "bold")
    FONT_BOLD = ("Segoe UI", 12, "bold")
    FONT_NORMAL = ("Segoe UI", 12)
    COLOR_PRIMARY = "#2563eb"
    COLOR_PRIMARY_HOVER = "#62d81d"
    COLOR_BG_SOFT = "#f1f5f9"
    def enable_windows_chrome(*_a, **_k): pass

LABEL_FONT = ("Segoe UI", 13)
ENTRY_FONT = ("Segoe UI", 13)
TREE_FONT  = ("Segoe UI", 13)
CTRL_H = 32
ROW_H  = 34

COLUMNS = ("KOD","AD","ÖLÇÜ","CİNS","STOK","ALİŞ","SATIŞ")
NUMERIC_COLS = {"STOK","ALİŞ","SATIŞ"}  # rəqəm sıralama

class MehsullarPenceresi(ctk.CTk):
    def __init__(self):
        super().__init__()
        try: enable_windows_chrome(self)
        except Exception: pass

        self.title("📦 Məhsullar")
        self.geometry("1120x660")
        self.configure(fg_color=COLOR_BG_SOFT)

        logger.info("Məhsul siyahısı pəncərəsi yaradıldı.")

        # ---- filter state ----
        self.q_text = ctk.StringVar(value="")
        self.q_cins = ctk.StringVar(value="")
        self.q_olcu = ctk.StringVar(value="")
        self.q_stok_min = ctk.StringVar(value="")
        self.q_stok_max = ctk.StringVar(value="")
        self.q_al_min = ctk.StringVar(value="")
        self.q_al_max = ctk.StringVar(value="")
        self.q_sat_min = ctk.StringVar(value="")
        self.q_sat_max = ctk.StringVar(value="")
        self.q_hide_zero = ctk.BooleanVar(value=False)

        # sütun sıralama vəziyyəti
        self._sort_col = "AD"
        self._sort_desc = False

        self._olcu_values = [""]
        self._refresh_olcu_values()

        self._build_ui()
        self._refresh_table()

    # ---------- UI ----------
    def _build_ui(self):
        logger.info("İnterfeys qurulur...")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # BAŞLIQ
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        ctk.CTkLabel(header, text="📦 MƏHSULLAR", font=FONT_H1).pack(side="left")

        ctk.CTkButton(
            header, text="ƏSAS MENYU",
            **button_style("accent", size="lg"),
            command=self._open_mainmenu
        ).pack(side="right")  # tam sağ

        # === YUXARI SƏTR (axtarış / cins / ölçü / sıfırları gizlət) ===
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 2))
        for i in range(10): top.grid_columnconfigure(i, weight=0)
        top.grid_columnconfigure(0, weight=2, minsize=420)

        self.e_search = ctk.CTkEntry(
            top, height=CTRL_H, font=FONT_NORMAL,
            placeholder_text="Kod / Ad axtar…", textvariable=self.q_text
        )
        self.e_search.grid(row=0, column=0, sticky="ew", padx=(0,8), pady=(2,2))
        self.e_search.bind("<KeyRelease>", lambda _e: self._refresh_table())

        ctk.CTkLabel(top, text="Cins:", font=FONT_NORMAL)\
            .grid(row=0, column=1, sticky="e", padx=(0,4))
        self.cb_cins = ctk.CTkComboBox(
            top, values=["","kişi","qadın"], height=CTRL_H, width=150,
            variable=self.q_cins, command=lambda _v: self._refresh_table()
        )
        self.cb_cins.grid(row=0, column=2, sticky="w")

        ctk.CTkLabel(top, text="Ölçü:", font=FONT_NORMAL)\
            .grid(row=0, column=3, sticky="e", padx=(10,4))
        self.cb_olcu = ctk.CTkComboBox(
            top, values=self._olcu_values, height=CTRL_H, width=160,
            variable=self.q_olcu, command=lambda _v: self._refresh_table()
        )
        self.cb_olcu.grid(row=0, column=4, sticky="w")

        self.cb_hide = ctk.CTkCheckBox(
            top, text="Sıfır stokları gizlət",
            variable=self.q_hide_zero, command=self._refresh_table
        )
        self.cb_hide.grid(row=0, column=5, sticky="w", padx=(12,0))

        # === ALT SƏTR (stok/alış/satış aralıqları + tək "Filtrlə") ===
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 6))
        for i in range(12): bottom.grid_columnconfigure(i, weight=0)
        bottom.grid_columnconfigure(11, weight=1)

        def add_range(lbl, vmin, vmax, start_col):
            ctk.CTkLabel(bottom, text=lbl, font=FONT_NORMAL)\
                .grid(row=0, column=start_col, sticky="e", padx=(0,4))
            e1 = ctk.CTkEntry(bottom, width=110, height=CTRL_H, textvariable=vmin,
                            placeholder_text="min", font=FONT_NORMAL)
            e2 = ctk.CTkEntry(bottom, width=110, height=CTRL_H, textvariable=vmax,
                            placeholder_text="maks", font=FONT_NORMAL)
            e1.grid(row=0, column=start_col+1, sticky="w")
            e2.grid(row=0, column=start_col+2, sticky="w", padx=(6,12))
            e1.bind("<KeyRelease>", lambda _e: self._refresh_table())
            e2.bind("<KeyRelease>", lambda _e: self._refresh_table())

        add_range("Stok:",   self.q_stok_min, self.q_stok_max, 0)
        add_range("Alış ₼:", self.q_al_min,   self.q_al_max,   3)
        add_range("Satış ₼:",self.q_sat_min,  self.q_sat_max,  6)

        ctk.CTkButton(
            bottom, text="Filtrlə",
            **button_style("primary", size="lg"),
            width=110,
            command=self._filter_button
        ).grid(row=0, column=10, padx=(8,0))

        # === CƏDVƏL ===
        table = ctk.CTkFrame(self)
        table.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0,12))
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollbar(table); self.scroll.grid(row=0, column=1, sticky="ns")

        self.tree = ttk.Treeview(
            table, columns=COLUMNS, show="headings",
            yscrollcommand=self.scroll.set, selectmode="browse"
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.scroll.configure(command=self.tree.yview)

        # ALT PANEL: [Zibil Qutusu] [Yenilə] [Detala Bax]
        bottom2 = ctk.CTkFrame(self, fg_color="transparent")
        bottom2.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 12))
        bottom2.grid_columnconfigure(0, weight=1)
        bottom2.grid_columnconfigure(1, weight=1)
        bottom2.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(
            bottom2, text="Zibil Qutusu",
            **button_style("warning", size="lg"),
            command=self._open_trash
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            bottom2, text="Yenilə",
            **button_style("primary", size="lg"),
            width=140,
            command=self._reload_olcu_and_refresh
        ).grid(row=0, column=1)

        ctk.CTkButton(
            bottom2, text="Detala Bax",
            **button_style("success", size="lg"),
            command=self._open_detail_process
        ).grid(row=0, column=2, sticky="e")

        # Sütun başlıqları / genişlik / sıralama ikonları
        widths = {"KOD":100, "AD":200, "ÖLÇÜ":100, "CİNS":100, "STOK":100, "ALİŞ":100, "SATIŞ":100}
        for c,w in widths.items():
            self.tree.heading(c, text=f"{c} ⇅", command=lambda col=c: self._toggle_sort(col))
            anchor = "w" if c=="AD" else ("e" if c in ("ALİŞ","SATIŞ","STOK") else "center")
            self.tree.column(c, width=w, anchor=anchor)

        # grid görünüşü + yaşıl seçim
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except: pass
        style.configure("Treeview",
                        background="#ffffff", foreground="#0f172a",
                        fieldbackground="#ffffff",
                        rowheight=ROW_H, font=FONT_NORMAL,
                        borderwidth=1, relief="solid")
        style.configure("Treeview.Heading",
                        background=COLOR_PRIMARY, foreground="white",
                        font=FONT_BOLD,
                        borderwidth=1, relief="solid")
        style.map("Treeview",
                background=[("selected", COLOR_SUCCESS)],
                foreground=[("selected","white")])

        self.tree.tag_configure("odd", background="#f8fafc")
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.bind("<Double-1>", self._open_detail_process)

    # ---------- DB ----------
    def _conn(self):
        logger.info("Verilənlər bazasına qoşulur...")
        base = os.path.dirname(__file__)
        p1 = os.path.join(base, "erp.db")
        p2 = os.path.join(os.getcwd(), "erp.db")
        return sqlite3.connect(p1 if os.path.exists(p1) else p2)

    def _refresh_olcu_values(self):
        logger.info("Ölçü dəyərləri yenilənir...")
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT DISTINCT IFNULL(olcu,'') FROM mehsullar ORDER BY olcu")
                vals = [r[0] for r in cur.fetchall() if r and r[0]]
            self._olcu_values = [""] + vals
        except Exception as e:
            logger.error("Ölçü dəyərləri yenilənmədi: %s", e)
            print("Ölçü dəyərləri oxunmadı:", e)
            self._olcu_values = [""]

    def _reload_olcu_and_refresh(self):
        logger.info("Ölçü dəyərləri yenidən yüklənir...")
        sel = self.q_olcu.get()
        self._refresh_olcu_values()
        try: self.cb_olcu.configure(values=self._olcu_values)
        except Exception: pass
        if sel not in self._olcu_values: sel = ""
        self.q_olcu.set(sel); self.cb_olcu.set(sel)
        self._refresh_table()

    # ---------- Yardımçılar ----------
    def _num(self, s):
        logger.info("Sətir rəqəmə çevrilir...")
        try: return float(str(s).replace(",", "."))
        except: return None

    def _build_where(self):
        logger.info("WHERE şərti qurulur...")
        parts, params = [], []

        q = self.q_text.get().strip()
        if q:
            like = f"%{q}%"
            parts.append("(u.kod LIKE ? OR IFNULL(u.ad,'') LIKE ?)")
            params += [like, like]

        cins = self.q_cins.get().strip()
        if cins:
            parts.append("IFNULL(u.cins,'') = ?"); params.append(cins)

        olcu = self.q_olcu.get().strip()
        if olcu:
            parts.append("IFNULL(u.olcu,'') = ?"); params.append(olcu)

        smin = self._num(self.q_stok_min.get()); smax = self._num(self.q_stok_max.get())
        if smin is not None: parts.append("IFNULL(u.stok,0) >= ?"); params.append(smin)
        if smax is not None: parts.append("IFNULL(u.stok,0) <= ?"); params.append(smax)

        almin = self._num(self.q_al_min.get()); almax = self._num(self.q_al_max.get())
        if almin is not None: parts.append("IFNULL(u.alis_qiymet,0) >= ?"); params.append(almin)
        if almax is not None: parts.append("IFNULL(u.alis_qiymet,0) <= ?"); params.append(almax)

        samin = self._num(self.q_sat_min.get()); samax = self._num(self.q_sat_max.get())
        if samin is not None: parts.append("IFNULL(u.satis_qiymet,0) >= ?"); params.append(samin)
        if samax is not None: parts.append("IFNULL(u.satis_qiymet,0) <= ?"); params.append(samax)

        if self.q_hide_zero.get():
            parts.append("IFNULL(u.stok,0) <> 0")

        where = ("WHERE " + " AND ".join(parts)) if parts else ""
        return where, params

    # başlıq kliklənməsi
    def _toggle_sort(self, col):
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = False
        self._refresh_table()

    def _apply_sort(self, rows):
        col = self._sort_col
        idx = COLUMNS.index(col)
        def key(row):
            v = row[idx]
            if col in NUMERIC_COLS:
                try: return float(v)
                except: return -1e18
            return str(v or "").casefold()
        return sorted(rows, key=key, reverse=self._sort_desc)

    def _set_heading_icons(self):
        # bütün başlıqlarda "⇅", aktivdə ▲/▼
        for col in COLUMNS:
            text = f"{col} ⇅"
            if col == self._sort_col:
                text = f"{col} {'▼' if self._sort_desc else '▲'}"
            self.tree.heading(col, text=text, command=lambda c=col: self._toggle_sort(c))

    # ---------- Məlumat doldurma ----------
    def _refresh_table(self):
        logger.info("Məhsul cədvəli yenilənir...")
        for i in self.tree.get_children(): self.tree.delete(i)

        where, params = self._build_where()
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    SELECT u.kod, IFNULL(u.ad,''), IFNULL(u.olcu,''), IFNULL(u.cins,''),
                           IFNULL(u.stok,0), IFNULL(u.alis_qiymet,0), IFNULL(u.satis_qiymet,0)
                    FROM mehsullar u
                    {where}
                """, params)
                rows = cur.fetchall()
        except Exception as e:
            logger.error("Məhsullar alınmadı: %s", e)
            messagebox.showerror("Xəta", f"Məhsullar yüklənmədi:\n{e}")
            rows = []

        rows = self._apply_sort(rows)
        self._set_heading_icons()

        tag = "even"
        for kod, ad, olcu, cins, stok, alis, satis in rows:
            tag = "odd" if tag == "even" else "even"
            stok_disp = int(stok) if float(stok).is_integer() else stok
            self.tree.insert("", "end", values=(
                kod, ad, olcu, cins, stok_disp,
                f"{float(alis):.2f} ₼", f"{float(satis):.2f} ₼"
            ), tags=(tag,))

    # alt sətrdəki "Filtrlə" həm ölçüləri oxuyur, həm cədvəli yeniləyir
    def _filter_button(self):
        self._reload_olcu_and_refresh()

    # ---------- Əməliyyatlar ----------
    def _open_mainmenu(self):
        logger.info("Əsas menyu açılır...")
        script = os.path.join(os.path.dirname(__file__), "ana_menu.py")
        try:
            subprocess.Popen([sys.executable, script], close_fds=True)
        except Exception as e:
            logger.error("Əsas menyu açıla bilmədi: %s", e)
            messagebox.showerror("Xəta", f"Əsas menyu açıla bilmədi:\n{e}")
        else:
            self.destroy()

    def _open_detail_process(self, _e=None):
        logger.info("Məhsul detalı açılır...")
        sel = self.tree.focus()
        if not sel: return
        vals = self.tree.item(sel)["values"]
        if not vals: return
        kod = str(vals[0]); cins = str(vals[3] or "")
        script = os.path.join(os.path.dirname(__file__), "mehsul_detal.py")
        try:
            subprocess.Popen([sys.executable, script, kod, cins], close_fds=True)
        except Exception as exc:
            logger.error("Məhsul detal pəncərəsi açıla bilmədi: %s", exc)
            print("Məhsul detal açma xətası:", exc)

    def _open_trash(self):
        logger.info("Zibil qutusu açılır...")
        path = os.path.join(os.path.dirname(__file__), "trash.py")
        if is_claimed("trash"):
            bring_to_front("Məhsul Zibil Qutusu")   # mövcud pəncərəni önə gətir
            return
        subprocess.Popen([sys.executable, path], close_fds=True)


if __name__ == "__main__":
    if not claim("mehsullar"):  # artıq açıqsa bu proses çıxır
        sys.exit(0)
        
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = MehsullarPenceresi()
    app.mainloop()

import customtkinter as ctk
from tkinter import ttk, messagebox
import sqlite3, sys, os, subprocess
from datetime import datetime

from ui_theme import (
    FONT_H1, FONT_NORMAL, FONT_BOLD,
    COLOR_PRIMARY, COLOR_SUCCESS,
    COLOR_BG_SOFT, button_style, logger
)

# >>> Tema & fontları ayarlardan uygula:
try:
    from ui_theme import apply_theme_global
    apply_theme_global()
except Exception:
    pass

try:
    from ui_theme import enable_windows_chrome
except Exception:
    enable_windows_chrome = None

class MehsulDetalPenceresi(ctk.CTk):
    def __init__(self, kod: str, cins: str = ""):
        super().__init__()
        if enable_windows_chrome:
            try: enable_windows_chrome(self)
            except Exception: pass

        self.kod = kod
        self.cins = cins or ""
        self.title(f"🧩 Məhsul Detalı – {self.kod} {('('+self.cins+')' if self.cins else '')}")
        self.geometry("1120x660")
        self.configure(fg_color=COLOR_BG_SOFT)

        logger.info("Məhsul detalı pəncərəsi yaradıldı.")

        # vəziyyət
        self.v_ad    = ctk.StringVar()
        self.v_olcu  = ctk.StringVar()
        self.v_cins  = ctk.StringVar(value=self.cins)
        self.v_stok  = ctk.StringVar()
        self.v_al    = ctk.StringVar()
        self.v_sat   = ctk.StringVar()
        self.v_delta = ctk.StringVar(value="1")
        self.v_apply_history = ctk.BooleanVar(value=False)

        self._dirty = False
        self._original = {}
        self._base_stok = 0.0
        self._pending_stock_delta = 0
        self._history_rows = []

        self._build_ui()
        self._load_product()
        self._load_history()
        self.protocol("WM_DELETE_WINDOW", self._confirm_close)

    # ---------- DB köməkçiləri ----------
    def _conn(self): 
        logger.info("Verilənlər bazasına qoşulur...")
        return sqlite3.connect("erp.db")

    def _ensure_stok_log_table(self, cur):
        logger.info("Stok log cədvəlinin mövcudluğunu yoxlayır...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stok_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_no   TEXT UNIQUE,
                tarix    TEXT DEFAULT (datetime('now')),
                mehsul_kod TEXT NOT NULL,
                mehsul_cins TEXT,
                delta    INTEGER NOT NULL,
                aciqlama TEXT
            )
        """)
        cur.execute("PRAGMA table_info(stok_log)")
        cols = {r[1] for r in cur.fetchall()}
        if "alis_qiymet" not in cols:
            cur.execute("ALTER TABLE stok_log ADD COLUMN alis_qiymet REAL")
        if "satis_qiymet" not in cols:
            cur.execute("ALTER TABLE stok_log ADD COLUMN satis_qiymet REAL")
        if "mebleg" not in cols:
            cur.execute("ALTER TABLE stok_log ADD COLUMN mebleg REAL")

    def _next_log_no(self, cur, is_add: bool):
        logger.info("Növbəti log nömrəsi alınır...")
        today = datetime.now().strftime("%Y%m%d")
        prefix = ("LA" if is_add else "LS") + f"-{today}-"
        cur.execute("SELECT COUNT(*) FROM stok_log WHERE log_no LIKE ?", (prefix + "%",))
        n = (cur.fetchone()[0] or 0) + 1
        return f"{prefix}{n:03d}"

    # ---------- UI (tam grid) ----------
    def _build_ui(self):
        logger.info("İnterfeys qurulur...")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        ctk.CTkLabel(header, text="🧩 MƏHSUL DETALI", font=FONT_H1).pack(side="left")

        area = ctk.CTkFrame(self, fg_color="transparent")
        area.grid(row=1, column=0, sticky="nsew", padx=14, pady=(4, 10))
        area.grid_columnconfigure(0, weight=0, minsize=330)
        area.grid_columnconfigure(1, weight=1)
        area.grid_rowconfigure(0, weight=1)

        # Sol panel
        left = ctk.CTkFrame(area, fg_color="#ffffff", corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0,10), pady=6)
        left.grid_columnconfigure(0, minsize=95)
        left.grid_columnconfigure(1, weight=1)

        r = 0
        def add_row(lbl, w):
            nonlocal r
            ctk.CTkLabel(left, text=lbl, font=FONT_NORMAL, anchor="e")\
                .grid(row=r, column=0, sticky="e", padx=(12,6), pady=(4,2))
            w.grid(row=r, column=1, sticky="ew", padx=(0,12), pady=(4,2))
            r += 1
            return w

        self.e_kod = add_row("Kod",  ctk.CTkEntry(left, state="readonly"))
        self.e_ad  = add_row("Ad",   ctk.CTkEntry(left, textvariable=self.v_ad))
        self.e_olc = add_row("Ölçü", ctk.CTkEntry(left, textvariable=self.v_olcu))
        self.cb_cins = add_row("Cins", ctk.CTkComboBox(
            left, values=["","kişi","qadın"], state="readonly", variable=self.v_cins, width=160
        ))
        self.e_stok = add_row("Stok", ctk.CTkEntry(left, state="readonly", textvariable=self.v_stok))
        self.e_al   = add_row("Alış ₼",  ctk.CTkEntry(left, textvariable=self.v_al))
        self.e_sat  = add_row("Satış ₼", ctk.CTkEntry(left, textvariable=self.v_sat))

        ctk.CTkLabel(left, text="Sürətli stok ±", font=FONT_BOLD, anchor="e")\
            .grid(row=r, column=0, sticky="e", padx=(12,6), pady=(6,2))
        ctk.CTkEntry(left, width=80, textvariable=self.v_delta)\
            .grid(row=r, column=1, sticky="w", padx=(0,12), pady=(6,2))
        r += 1

        act = ctk.CTkFrame(left, fg_color="transparent")
        act.grid(row=r, column=0, columnspan=2, sticky="ew", padx=16, pady=(0,2))
        act.grid_columnconfigure((0,1), weight=1)
        ctk.CTkButton(act, text="+ Əlavə et", **button_style("success"),
                    command=lambda: self._adjust_stock(True))\
            .grid(row=0, column=0, padx=(0,4), sticky="ew")
        ctk.CTkButton(act, text="− Çıxar", **button_style("warning"),
                    command=lambda: self._adjust_stock(False))\
            .grid(row=0, column=1, padx=(4,0), sticky="ew")
        r += 1

        self._lbl_pending = ctk.CTkLabel(left, text="", text_color="#6b7280", anchor="w")
        self._lbl_pending.grid(row=r, column=0, columnspan=2, sticky="ew", padx=14, pady=(0,6))
        r += 1

        ctk.CTkCheckBox(left, text="Keçmişi yenilə", variable=self.v_apply_history)\
            .grid(row=r, column=0, columnspan=2, sticky="w", padx=16, pady=(4,0)); r+=1
        info = ("Yadda saxlayanda köhnə dəyərlərin ÜSTÜNƏ YAZILACAQ.\n"
                "Keçmişi yeniləsəniz bu məhsulun bütün hərəkətlərində qiymətlər yeni dəyərlərə çəkiləcək "
                "və MƏBLƏĞ yenidən hesablanacaq.")
        ctk.CTkLabel(left, text=info, font=FONT_NORMAL,
                    text_color="#6b7280", justify="left", wraplength=290)\
            .grid(row=r, column=0, columnspan=2, sticky="ew", padx=12, pady=(2,4)); r+=1

        left.grid_rowconfigure(r, weight=1); r+=1
        btm = ctk.CTkFrame(left, fg_color="transparent")
        btm.grid(row=r, column=0, columnspan=2, sticky="ew", padx=12, pady=(6,10))
        btm.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(btm, text="Yadda saxla", **button_style("primary"),
                    command=self._save_confirm).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(btm, text="Məhsulu Sil", **button_style("danger"),
                    command=self._delete_product_confirm).grid(row=0, column=1, sticky="e", padx=(8,0))

        # Sağ panel
        right = ctk.CTkFrame(area, fg_color="#ffffff", corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(10,0), pady=6)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(right, text="Hərəkət Keçmişi (iki dəfə kliklə faktura/logu aç)", font=FONT_BOLD)\
            .grid(row=0, column=0, sticky="w", padx=12, pady=(12,4))

        filt = ctk.CTkFrame(right, fg_color="transparent")
        filt.grid(row=1, column=0, sticky="ew", padx=12, pady=(0,6))
        filt.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(filt, text="Növ:", width=40, anchor="e", font=FONT_NORMAL)\
            .grid(row=0, column=0, padx=(0,4))
        self.cmb_tur = ctk.CTkComboBox(filt, values=["Hamısı","ALIS","SATIS","ƏLAVƏ","ÇIXAR"],
                                    state="readonly", width=120, height=42)
        self.cmb_tur.set("Hamısı"); self.cmb_tur.grid(row=0, column=1, padx=(0,10))
        self.e_fno = ctk.CTkEntry(filt, placeholder_text="F.No / Log No axtar", width=220, height=42, font=FONT_NORMAL)
        self.e_fno.grid(row=0, column=2, padx=(0,10))

        ctk.CTkButton(filt, text="Filtrlə", **button_style("primary"),
                    command=self._render_history).grid(row=0, column=3)
        ctk.CTkButton(filt, text="Yenilə", **button_style("accent"),
                    command=self._load_history).grid(row=0, column=4, padx=(10,0))

        self.cmb_tur.bind("<<ComboboxSelected>>", lambda *_: self._render_history())
        self.e_fno.bind("<KeyRelease>", lambda *_: self._render_history())

        self.scroll = ctk.CTkScrollbar(right); self.scroll.grid(row=2, column=1, sticky="ns", padx=(0,10), pady=(0,10))
        cols = ("TARİX","NÖV","SAY","ALIS","SATIS","MƏBLƏĞ","F.NO")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", yscrollcommand=self.scroll.set, selectmode="browse")
        self.tree.grid(row=2, column=0, sticky="nsew", padx=(10,0), pady=(0,10))
        self.scroll.configure(command=self.tree.yview)

        widths = {"TARİX":160, "NÖV":80, "SAY":80, "ALIS":90, "SATIS":90, "MƏBLƏĞ":120, "F.NO":200}
        for c,w in widths.items():
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor=("e" if c in ("SAY","ALIS","SATIS","MƏBLƏĞ") else "center"))
        st = ttk.Style(self); st.theme_use("clam")
        st.configure("Treeview", background="#ffffff", foreground="#0f172a",
                    fieldbackground="#ffffff", rowheight=28, font=FONT_NORMAL)
        st.configure("Treeview.Heading", background=COLOR_PRIMARY, foreground="white", font=FONT_BOLD)
        st.map("Treeview", background=[("selected", COLOR_SUCCESS)], foreground=[("selected","white")])

        self.tree.bind("<Double-1>", self._open_invoice_or_log)

    # ---------- Məlumat ----------
    def _load_product(self):
        logger.info("Məhsul məlumatı yüklənir...")
        try:
            conn = self._conn(); cur = conn.cursor()
            cur.execute("""SELECT ad, IFNULL(olcu,''), IFNULL(cins,''), IFNULL(stok,0),
                                  IFNULL(alis_qiymet,0), IFNULL(satis_qiymet,0)
                           FROM mehsullar WHERE kod=? AND IFNULL(cins,'')=?""",
                        (self.kod, self.cins))
            r = cur.fetchone(); conn.close()
            if not r:
                logger.warning("Məhsul tapılmadı: %s / %s", self.kod, self.cins)
                messagebox.showerror("Xəta", "Məhsul tapılmadı."); self.destroy(); return
            self.e_kod.configure(state="normal"); self.e_kod.delete(0,"end"); self.e_kod.insert(0,self.kod); self.e_kod.configure(state="readonly")
            self.v_ad.set(r[0]); self.v_olcu.set(r[1]); self.v_cins.set(r[2] or "")
            self._base_stok = float(r[3] or 0); self._update_stock_display()
            self.v_al.set(f"{float(r[4]):.2f}"); self.v_sat.set(f"{float(r[5]):.2f}")
            self._original = {"Ad":r[0] or "","Ölçü":r[1] or "","Alış ₼":f"{float(r[4]):.2f}","Satış ₼":f"{float(r[5]):.2f}"}
            self._dirty = False
            for v in (self.v_ad, self.v_olcu, self.v_al, self.v_sat):
                v.trace_add("write", lambda *_: self._mark_dirty())
        except Exception as e:
            logger.error("Xəta: %s", e)
            messagebox.showerror("Xəta", str(e))

    def _update_stock_display(self):
        logger.info("Stok göstəricisi yenilənir...")
        cur = self._base_stok + self._pending_stock_delta
        self.v_stok.set(f"{int(cur) if float(cur).is_integer() else cur}")
        self._lbl_pending.configure(
            text = (f"Gözləyən stok Δ: {'+' if self._pending_stock_delta>0 else '−'}{abs(self._pending_stock_delta)} (Yadda saxla ilə tətbiq olunur)"
                    if self._pending_stock_delta else "")
        )

    def _load_history(self):
        logger.info("Məhsul keçmişi yüklənir...")
        try:
            conn = self._conn(); cur = conn.cursor()
            # Fakturalar
            cur.execute("""
              SELECT strftime('%Y-%m-%d %H:%M', f.tarix),
                     UPPER(f.tur),
                     fd.say, fd.alis_qiymet, fd.satis_qiymet, fd.mebleg, f.faktura_no
              FROM faktura_detal fd
              JOIN fakturalar f ON f.id = fd.faktura_id
              WHERE fd.mehsul_kod=? AND IFNULL(fd.mehsul_cins,'')=?
            """, (self.kod, self.cins))
            fakturalar = cur.fetchall()

            # Loglar (alış/satış qiyməti və məbləğ artıq cədvəldədir)
            self._ensure_stok_log_table(cur)
            cur.execute("""
              SELECT strftime('%Y-%m-%d %H:%M', tarix),
                     CASE WHEN delta>=0 THEN 'ƏLAVƏ' ELSE 'ÇIXAR' END,
                     ABS(delta),
                     alis_qiymet, satis_qiymet, mebleg,
                     log_no
              FROM stok_log
              WHERE mehsul_kod=? AND IFNULL(mehsul_cins,'')=?
            """, (self.kod, self.cins))
            loglar = cur.fetchall()
            conn.close()

            rows = list(fakturalar) + list(loglar)
            rows.sort(key=lambda r: r[0] or "", reverse=True)
            self._history_rows = rows
            self._render_history()
        except Exception as e:
            logger.error("Keçmiş yüklənmədi: %s", e)
            print("keçmiş yüklənmədi:", e)
            self._history_rows = []; self._render_history()

    def _render_history(self):
        logger.info("Məhsul keçmişi göstərilir...")
        for i in self.tree.get_children(): self.tree.delete(i)
        tfilter = self.cmb_tur.get().strip()
        q = self.e_fno.get().strip().lower()
        for (tarix, tur, say, alis, satis, meb, fno) in self._history_rows:
            if tfilter != "Hamısı" and (tur or "") != tfilter: continue
            if q and fno and q not in str(fno).lower(): continue
            say_d = "" if say is None else (int(say) if float(say).is_integer() else say)
            al_d  = "" if alis is None else f"{float(alis):.2f}"
            sa_d  = "" if satis is None else f"{float(satis):.2f}"
            me_d  = "" if meb is None else f"{float(meb):.2f}"
            self.tree.insert("", "end", values=(tarix, tur, say_d, al_d, sa_d, me_d, fno))

    # ---------- Yadda saxla / Log ----------
    def _mark_dirty(self):
        logger.info("Məhsul dəyişdirildi kimi işarələndi.")
        self._dirty = True

    def _collect_current(self):
        logger.info("Cari məhsul məlumatı toplanır...")
        return {
            "Ad": self.v_ad.get().strip(),
            "Ölçü": self.v_olcu.get().strip(),
            "Alış ₼": f"{float(self.v_al.get().replace(',', '.')):.2f}",
            "Satış ₼": f"{float(self.v_sat.get().replace(',', '.')):.2f}",
        }

    def _diff_text(self):
        logger.info("Əsas və cari məhsul məlumatı müqayisə olunur...")
        cur = self._collect_current(); diffs=[]
        for k in ("Ad","Ölçü","Alış ₼","Satış ₼"):
            o,n = self._original.get(k,""), cur.get(k,"")
            if str(o)!=str(n): diffs.append(f"• {k}: {o} → {n}")
        if self._pending_stock_delta:
            b = self._base_stok; a = self._base_stok + self._pending_stock_delta
            diffs.append(f"• Stok: {int(b) if float(b).is_integer() else b} → {int(a) if float(a).is_integer() else a} ({'+' if self._pending_stock_delta>0 else ''}{self._pending_stock_delta})")
        return diffs

    def _save_confirm(self):
        logger.info("Yadda saxlanma təsdiqlənir...")
        diffs = self._diff_text()
        if not diffs and not self.v_apply_history.get():
            logger.info("Yadda saxlanacaq dəyişiklik yoxdur.")
            messagebox.showinfo("Məlumat","Yadda saxlanacaq dəyişiklik yoxdur."); return
        txt = ("\n".join(diffs) if diffs else "Sahələrdə dəyişiklik yoxdur.") + \
              "\n\nBu əməliyyat köhnə dəyərlərin ÜSTÜNƏ YAZILACAQ.\nDavam edilsin?"
        if not messagebox.askyesno("Yadda saxla", txt): return
        if not self._save_do(): return
        self._load_product(); self._load_history()
        if self.v_apply_history.get():
            logger.info("Dəyişikliklər məhsul keçmişinə tətbiq olunur...")
            if messagebox.askyesno("Keçmişi Yenilə",
                                   "Bu məhsulun BÜTÜN keçmiş hərəkətlərində qiymətlər yeni dəyərlərə yenilənsin?\n"
                                   "SATIŞ: məbləğ = say × yeni Satış ₼\n"
                                   "ALIS:  məbləğ = say × yeni Alış ₼"):
                self._apply_to_history(); self._load_history()

    def _save_do(self):
        logger.info("Məhsul məlumatı yadda saxlanır...")
        try:
            delta = int(self._pending_stock_delta)
            alis = round(float(self.v_al.get().replace(",", ".")), 2)
            satis = round(float(self.v_sat.get().replace(",", ".")), 2)

            conn = self._conn(); cur = conn.cursor()
            self._ensure_stok_log_table(cur)

            # Məhsul yenilə
            cur.execute("""UPDATE mehsullar
                           SET ad=?, olcu=?, satis_qiymet=ROUND(?,2), alis_qiymet=ROUND(?,2),
                               stok = IFNULL(stok,0) + ?
                           WHERE kod=? AND IFNULL(cins,'')=?""",
                        (self.v_ad.get().strip(), self.v_olcu.get().strip(),
                         satis, alis, delta, self.kod, self.cins))

            # Stok logu (delta != 0)
            # ...
            if delta != 0:
                is_add = delta > 0
                log_no = self._next_log_no(cur, is_add=is_add)

                # hər iki qiyməti də log-a yaz (tam məlumat)
                if is_add:
                    meb = round(abs(delta) * alis, 2)
                    cur.execute("""INSERT INTO stok_log
                                    (log_no, mehsul_kod, mehsul_cins, delta, aciqlama,
                                    alis_qiymet, satis_qiymet, mebleg)
                                VALUES (?,?,?,?,?,?,?,?)""",
                                (log_no, self.kod, self.cins, delta,
                                "Məhsul Detal əl ilə ƏLAVƏ", alis, satis, meb))
                else:
                    meb = round(abs(delta) * satis, 2)
                    cur.execute("""INSERT INTO stok_log
                                    (log_no, mehsul_kod, mehsul_cins, delta, aciqlama,
                                    alis_qiymet, satis_qiymet, mebleg)
                                VALUES (?,?,?,?,?,?,?,?)""",
                                (log_no, self.kod, self.cins, delta,
                                "Məhsul Detal əl ilə ÇIXAR", alis, satis, meb))

            conn.commit(); conn.close()
            self._pending_stock_delta = 0
            self._dirty = False
            logger.info("Məhsul uğurla yeniləndi.")
            messagebox.showinfo("Məlumat", "Məhsul yeniləndi.")
            return True
        except Exception as e:
            logger.error("Məhsul yenilənmədi: %s", e)
            messagebox.showerror("Xəta", f"Yenilənmədi: {e}")
            return False

    def _apply_to_history(self):
        logger.info("Dəyişikliklər məhsul keçmişinə tətbiq olunur...")
        try:
            new_al = float(self.v_al.get().replace(",", "."))
            new_sa = float(self.v_sat.get().replace(",", "."))
            conn = self._conn(); cur = conn.cursor()
            cur.execute("""
                UPDATE faktura_detal
                   SET satis_qiymet=ROUND(?,2),
                       mebleg=ROUND(IFNULL(say,0)*ROUND(?,2),2)
                 WHERE mehsul_kod=? AND IFNULL(mehsul_cins,'')=?
                   AND faktura_id IN (SELECT id FROM fakturalar WHERE tur='satis')
            """, (new_sa, new_sa, self.kod, self.cins))
            cur.execute("""
                UPDATE faktura_detal
                   SET alis_qiymet=ROUND(?,2),
                       mebleg=ROUND(IFNULL(say,0)*ROUND(?,2),2)
                 WHERE mehsul_kod=? AND IFNULL(mehsul_cins,'')=?
                   AND faktura_id IN (SELECT id FROM fakturalar WHERE tur='alis')
            """, (new_al, new_al, self.kod, self.cins))
            conn.commit(); conn.close()
            logger.info("Məhsul keçmişi uğurla yeniləndi.")
            messagebox.showinfo("Məlumat", "Keçmiş hərəkətlərdəki qiymətlər yeniləndi.")
        except Exception as e:
            logger.error("Keçmişə tətbiq olunmadı: %s", e)
            messagebox.showerror("Xəta", f"Keçmişə tətbiq olunmadı: {e}")

    # ---------- aç / bağla ----------
    def _adjust_stock(self, add: bool):

        logger.info("Stok tənzimlənir...")
        try:
            d = int(float(self.v_delta.get().replace(",", ".")))
        except:
            logger.error("Stok tənzimləmə dəyəri yanlışdır.")
            messagebox.showwarning("Xəbərdarlıq", "Düzgün bir ədəd daxil edin."); return
        if not add: d = -d
        self._pending_stock_delta += d
        self._mark_dirty()
        self._update_stock_display()

    def _open_invoice_or_log(self, _e=None):
        logger.info("Faktura və ya log açılır...")
        sel = self.tree.focus()
        if not sel: return
        vals = self.tree.item(sel)["values"]
        if not vals or len(vals) < 7: return
        tur, fno = vals[1], vals[6]
        if (tur in ("ƏLAVƏ","ÇIXAR")) or str(fno).startswith(("LA-","LS-")):
            try:
                conn = self._conn(); cur = conn.cursor()
                cur.execute("""SELECT strftime('%Y-%m-%d %H:%M', tarix), delta, alis_qiymet, satis_qiymet, mebleg, aciqlama
                               FROM stok_log WHERE log_no=?""", (fno,))
                r = cur.fetchone(); conn.close()
                if r:
                    tarix, delta, alis, satis, meb, acik = r
                    tip = "ƏLAVƏ" if (delta or 0) >= 0 else "ÇIXAR"
                    adet = abs(delta or 0)
                    qiymet = alis if tip=="ƏLAVƏ" else satis
                    logger.info("Stok log məlumatı göstərilir...")
                    messagebox.showinfo("Stok Logu",
                        f"Log No: {fno}\nTarix: {tarix}\nHərəkət: {tip} {adet}\n"
                        f"Qiymət: {'' if qiymet is None else f'{qiymet:.2f} ₼'}\n"
                        f"Məbləğ: {'' if meb is None else f'{meb:.2f} ₼'}\nAçıqlama: {acik or ''}")
                else:
                    logger.warning("Stok log tapılmadı: %s", fno)
                    messagebox.showinfo("Stok Logu", f"Log No: {fno}\nQeyd tapılmadı.")
            except Exception as e:
                logger.error("Faktura və ya log açıla bilmədi: %s", e)
                messagebox.showerror("Xəta", str(e))
            return

        # Faktura detalları
        script = os.path.join(os.path.dirname(__file__), "faktura_detal.py")
        try:
            subprocess.Popen([sys.executable, script, str(fno)], close_fds=True)
        except Exception as exc:
            logger.error("Faktura detal pəncərəsi açıla bilmədi: %s", exc)
            print("Faktura detal açılma xətası:", exc)

    def _ensure_trash_table(self, cur):
        logger.info("Zibil qutusu cədvəlinin mövcudluğunu yoxlayır...")
        # Silinən məhsulları saxlayacağımız zibil qutusu
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mehsullar_trash (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deleted_at TEXT DEFAULT (datetime('now')),
                kod TEXT, ad TEXT, olcu TEXT, cins TEXT,
                stok REAL, alis_qiymet REAL, satis_qiymet REAL,
                note TEXT
            )
        """)

    def _delete_product_confirm(self):
        logger.info("Məhsulun silinməsi təsdiqlənir...")
        try:
            conn = self._conn(); cur = conn.cursor()
            # məhsulu və stok məlumatını oxu
            cur.execute("""SELECT kod, IFNULL(ad,''), IFNULL(olcu,''), IFNULL(cins,''),
                                IFNULL(stok,0), IFNULL(alis_qiymet,0), IFNULL(satis_qiymet,0)
                        FROM mehsullar WHERE kod=? AND IFNULL(cins,'')=?""",
                        (self.kod, self.cins))
            row = cur.fetchone()
            if not row:
                logger.warning("Məhsul tapılmadı: %s, %s", self.kod, self.cins)
                messagebox.showerror("Xəta", "Məhsul tapılmadı."); conn.close(); return

            kod, ad, olcu, cins, stok, alis, satis = row
            # istifadəçini xəbərdar et
            txt = (f"Bu məhsulu silmək üzrəsiniz:\n"
                f"• Kod: {kod}\n• Ad: {ad}\n• Cins: {cins}\n• Mövcud stok: {int(stok) if float(stok).is_integer() else stok}\n\n"
                "Məhsul, daimi silinmədən əvvəl ZİBİL QUTUSU’na köçürüləcək.\nDavam edilsin?")
            if not messagebox.askyesno("Məhsulu Sil", txt):
                conn.close(); return

            # zibil qutusu cədvəlini təmin et
            self._ensure_trash_table(cur)

            # zibil qutusuna kopyala
            cur.execute("""INSERT INTO mehsullar_trash
                            (kod, ad, olcu, cins, stok, alis_qiymet, satis_qiymet, note)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (kod, ad, olcu, cins, stok, alis, satis, "mehsul_detal üzərindən silindi"))

            # əsas cədvəldən sil
            cur.execute("DELETE FROM mehsullar WHERE kod=? AND IFNULL(cins,'')=?", (kod, cins))
            conn.commit(); conn.close()

            logger.info("Məhsul silindi və zibil qutusuna köçürüldü.")
            messagebox.showinfo("Məlumat", "Məhsul silindi və zibil qutusuna köçürüldü.")
            self.destroy()
        except Exception as e:
            logger.error("Məhsul silinmədi: %s", e)
            messagebox.showerror("Xəta", f"Silinmədi:\n{e}")

    def _confirm_close(self):
        logger.info("Bağlanma təsdiqlənir...")
        if not self._dirty and self._pending_stock_delta == 0:
            self.destroy(); return
        resp = messagebox.askyesnocancel("Yadda saxlanmamış dəyişikliklər",
                                         "Dəyişikliklər yadda saxlanılsın?\n"
                                         "Bəli: Yadda saxla və bağla\nXeyr: Yadda saxlamadan bağla\nİmtina: Geri dön")
        if resp is None: return
        if resp is True:
            if self._save_do(): self.destroy()
        else:
            self.destroy()

if __name__ == "__main__":
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    kod = sys.argv[1] if len(sys.argv) > 1 else ""
    cins = sys.argv[2] if len(sys.argv) > 2 else ""
    if not kod:
        logger.error("Məhsul kodu verilməyib.")
        messagebox = __import__("tkinter").messagebox
        messagebox.showerror("Xəta", "Məhsul kodu verilməyib."); sys.exit(1)
    app = MehsulDetalPenceresi(kod=kod, cins=cins)
    app.mainloop()

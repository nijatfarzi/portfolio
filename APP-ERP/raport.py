# raport.py — Hesabatlar (Məhsul üzrə / Faktura üzrə)
# - Məhsul üzrə: ALIŞ/SATIŞ ayrı; STOK sütunu
# - Faktura üzrə: satış siyahısı (dövrüyyə/məhsul dəyəri/qazanc)
# - Məhsul dəyəri: COALESCE(fd.alis_qiymet, u.alis_qiymet, 0) * COALESCE(fd.say,0)
# - PDF çıxış: DejaVu şriftləri ilə tam Azərbaycan dili dəstəyi
# - Tema: ui_theme.py

import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import sqlite3, os, sys, csv
import subprocess
from datetime import datetime, timedelta

from ui_theme import (
    FONT_H1, FONT_BOLD, FONT_NORMAL,
    COLOR_PRIMARY, COLOR_PRIMARY_HOVER,
    COLOR_BG_SOFT, COLOR_SUCCESS,
    enable_windows_chrome, button_style, logger
)
from single_instance import bring_to_front

# --- Varsayılan klasör yardımcıları -----------------------------------------

def _app_dir_name():
    """
    Tətbiq qovluğunun adı.
    ui_theme.py içində APP_DIR_NAME varsa onu istifadə edir, yoxdursa 'Avanqard ERP'.
    """
    try:
        from ui_theme import APP_DIR_NAME
        return APP_DIR_NAME or "Avanqard ERP"
    except Exception:
        return "Avanqard ERP"


def _default_reports_dir():
    """
    Sənədlər\<APP_DIR_NAME>\Hesabatlar qovluğunu təmin edir.
    Yaradılmazsa istifadəçi qovluğunda ‘Hesabatlar’ açır.
    """
    logger.info("Defolt hesabat qovluğu təyin edilir...")
    import os
    base = os.path.join(os.path.expanduser("~"), "Documents", _app_dir_name())
    reports = os.path.join(base, "Hesabatlar")
    try:
        os.makedirs(reports, exist_ok=True)
    except Exception:
        reports = os.path.join(os.path.expanduser("~"), "Hesabatlar")
        os.makedirs(reports, exist_ok=True)
    return reports


# ---------- tarix köməkçiləri ----------
def today(): return datetime.now().date()
def start_of_week(d): return d - timedelta(days=d.weekday())
def start_of_month(d): return d.replace(day=1)
def start_of_quarter(d):
    m = ((d.month - 1)//3)*3 + 1
    return d.replace(month=m, day=1)
def start_of_year(d): return d.replace(month=1, day=1)
def dstr(d): return d.strftime("%Y-%m-%d")


class RaporlarPenceresi(ctk.CTk):
    def __init__(self):
        super().__init__()
        try: enable_windows_chrome(self)
        except: pass

        self.title("📊 Hesabatlar")
        self.geometry("1280x800")
        self.minsize(1100, 680)
        self.configure(fg_color=COLOR_BG_SOFT)
        logger.info("Hesabatlar pəncərəsi yaradıldı.")

        # Defolt: Aylıq, Məhsul üzrə
        self.periyot = ctk.StringVar(value="Aylıq")
        self.tarih1 = ctk.StringVar(value=dstr(start_of_month(today())))
        self.tarih2 = ctk.StringVar(value=dstr(today()))
        self.top_n = ctk.StringVar(value="10")
        self.report_mode = ctk.StringVar(value="Məhsul üzrə")  # "Məhsul üzrə" | "Faktura üzrə"

        self._build_ui()
        self._apply_period_default()
        self._run()

    # ---------- UI ----------
    def _build_ui(self):
        # Üst bar
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(top, text="📊 HESABATLAR", font=FONT_H1).pack(side="left")

        # Sağ: Əsas Menyu
        ctk.CTkButton(
            top, text="ƏSAS MENYU",
            **button_style("success", size="lg"),
            command=self._open_mainmenu
        ).pack(side="right")

        # Filtr barı
        fb = ctk.CTkFrame(self, fg_color="transparent")
        fb.pack(fill="x", padx=14, pady=(0, 8))

        # Hesabat tipi seçici
        self.seg_mode = ctk.CTkSegmentedButton(
            fb, values=["Məhsul üzrə", "Faktura üzrə"],
            variable=self.report_mode, command=lambda _=None: self._switch_mode()
        )
        self.seg_mode.pack(side="left", padx=(0, 12))

        # Dövr
        self.cmb = ctk.CTkComboBox(
            fb, values=["Gündəlik","Həftəlik","Aylıq","Rüblük","İllik","Xüsusi"],
            width=140, command=lambda _v: self._apply_period_default()
        ); self.cmb.set(self.periyot.get())
        self.cmb.pack(side="left", padx=(0, 10))

        self.e1 = ctk.CTkEntry(fb, width=120, placeholder_text="YYYY-MM-DD", textvariable=self.tarih1, font=FONT_NORMAL)
        self.e2 = ctk.CTkEntry(fb, width=120, placeholder_text="YYYY-MM-DD", textvariable=self.tarih2, font=FONT_NORMAL)
        self.e1.pack(side="left", padx=4); self.e2.pack(side="left", padx=(4, 10))

        ctk.CTkLabel(fb, text="Top N:", font=FONT_NORMAL).pack(side="left")
        self.cmb_topn = ctk.CTkComboBox(fb, values=["5","10","20","50"], width=70, variable=self.top_n)
        self.cmb_topn.pack(side="left", padx=(4, 10))

        ctk.CTkButton(
            fb, text="İcra et",
            **button_style("primary", size="lg"),
            width=120, command=self._run
        ).pack(side="left")

        ctk.CTkButton(
            fb, text="PDF Çıxış",
            **button_style("primary", size="lg"),
            width=120, command=self._export_pdf
        ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            fb, text="CSV",
            **button_style("accent", size="lg"),
            width=90, command=self._export_all
        ).pack(side="left", padx=(8, 0))

        # KPI zolağı
        kpi = ctk.CTkFrame(self, fg_color="transparent")
        kpi.pack(fill="x", padx=14, pady=(0, 8))
        self.kpi_orders = self._kpi_card(kpi, "Faktura (Satış)", "0")
        self.kpi_rev    = self._kpi_card(kpi, "SATIŞ Dövrüyyəsi", "0.00")
        self.kpi_cost   = self._kpi_card(kpi, "Məhsul dəyəri (COGS)", "0.00")
        self.kpi_profit = self._kpi_card(kpi, "QAZANC", "0.00")
        self.kpi_avg    = self._kpi_card(kpi, "Ort. Səbət", "0.00")

        # Orta sahə: 2 görünüş
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        # Məhsul üzrə (tab + grid)
        self.tabs = ctk.CTkTabview(center)
        self.tab_top   = self.tabs.add("Ən çox satılan")
        self.tab_least = self.tabs.add("Ən az satılan")
        self.tab_prof  = self.tabs.add("Ən gəlirli")
        self.tab_worst = self.tabs.add("Ən az gəlirli")

        cols_prod = ("KOD","AD","ÖLÇÜ","CİNS","STOK","SATIŞ SAY","ORT. ALIŞ","ORT. SATIŞ","SATIŞ MƏBLƏĞİ","QAZANC")
        self.tree_top   = self._make_tree(self.tab_top, cols_prod)
        self.tree_least = self._make_tree(self.tab_least, cols_prod)
        self.tree_prof  = self._make_tree(self.tab_prof, cols_prod)
        self.tree_worst = self._make_tree(self.tab_worst, cols_prod)

        # Faktura üzrə (tək grid)
        self.invoice_wrap = ctk.CTkFrame(center)
        cols_inv = ("NO","TARİX","MÜŞTƏRİ","SATIŞ SAY","SATIŞ MƏBLƏĞİ","MƏHSUL DƏYƏRİ","QAZANC")
        self.tree_invoice = self._make_tree(self.invoice_wrap, cols_inv)

        # defolt görünüş: Məhsul üzrə
        self.tabs.pack(fill="both", expand=True)

        # Alt bar
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(0, 16))
        ctk.CTkButton(bottom, text="Bağla",
                    **button_style("accent", size="lg"),
                    width=140, command=self.destroy).pack(side="right")

    def _switch_mode(self):
        logger.info("Hesabat rejimi dəyişdirilir...")
        # Görünüşlər arasında keçid
        if self.report_mode.get() == "Məhsul üzrə":
            self.invoice_wrap.pack_forget()
            self.tabs.pack(fill="both", expand=True)
        else:
            self.tabs.pack_forget()
            self.invoice_wrap.pack(fill="both", expand=True)
        self._run()
    
    # raport.py (sinifin içi)

    def _get_range(self):
        from datetime import datetime
        try:
            s = datetime.strptime(self.tarih1.get(), "%Y-%m-%d").date()
        except Exception:
            s = today()
        try:
            e = datetime.strptime(self.tarih2.get(), "%Y-%m-%d").date()
        except Exception:
            e = today()
        return dstr(s), dstr(e)

    def _clear_trees(self):
        for t in (getattr(self, "tree_top", None),
                getattr(self, "tree_least", None),
                getattr(self, "tree_prof", None),
                getattr(self, "tree_worst", None),
                getattr(self, "tree_invoice", None)):
            if t:
                for iid in t.get_children():
                    t.delete(iid)

    def _run(self, *_):
        """
        Hesabatı yenilə: tarix aralığını oxu, KPI-ları və cədvəlləri doldur.
        Rejimlər:
        - "Məhsul üzrə": Top/Least/Profit/Worst tabları
        - "Faktura üzrə": Faktura xülasəsi
        """
        try:
            s, e = self._get_range()
            topn = int(self.top_n.get() or 10)
        except Exception:
            s, e, topn = "1970-01-01", "2100-12-31", 10

        # Ekranı təmizlə
        self._clear_trees()
        try: self.kpi_orders.configure(text="0")
        except Exception: pass
        for lbl in (getattr(self, "kpi_rev", None),
                    getattr(self, "kpi_cost", None),
                    getattr(self, "kpi_profit", None),
                    getattr(self, "kpi_avg", None)):
            if lbl: lbl.configure(text="0.00")

        def _fmt_money(x):
            try:
                return f"{float(x or 0):.2f}"
            except Exception:
                return "0.00"

        def _fmt_int(x):
            try:
                return f"{int(x or 0)}"
            except Exception:
                return "0"

        try:
            con = self._conn()
            cur = con.cursor()
        except Exception as ex:
            # DB açılmırsa sakitcə çıx
            try:
                from tkinter import messagebox
                messagebox.showerror("Xəta", f"Verilənlər bazasına qoşulmaq olmur:\n{ex}", parent=self)
            except Exception:
                pass
            return

        try:
            if self.report_mode.get() == "Məhsul üzrə":
                # ---------- KPI (satış fakturaları) ----------
                cur.execute("""
                    SELECT
                        COUNT(DISTINCT f.id)                                                    AS orders,
                        SUM(COALESCE(fd.mebleg, COALESCE(fd.satis_qiymet,0)*COALESCE(fd.say,0))) AS revenue,
                        SUM(COALESCE(fd.alis_qiymet, COALESCE(m.alis_qiymet,0)) * COALESCE(fd.say,0)) AS cost
                    FROM fakturalar f
                    JOIN faktura_detal fd ON fd.faktura_id = f.id
                    LEFT JOIN mehsullar m ON m.kod = fd.mehsul_kod AND m.cins = fd.mehsul_cins
                    WHERE (f.tur='SATIŞ' OR f.tur='SATIS' OR f.tur='SATICI' OR f.tur='SAT')  -- elastik
                    AND date(f.tarix) BETWEEN ? AND ?
                """, (s, e))
                orders, revenue, cost = cur.fetchone() or (0, 0, 0)
                profit = (revenue or 0) - (cost or 0)
                avg_basket = (revenue or 0) / orders if orders else 0

                # KPI göstər
                self.kpi_orders.configure(text=_fmt_int(orders))
                self.kpi_rev.configure(text=_fmt_money(revenue))
                self.kpi_cost.configure(text=_fmt_money(cost))
                self.kpi_profit.configure(text=_fmt_money(profit))
                self.kpi_avg.configure(text=_fmt_money(avg_basket))

                # ---------- Məhsul üzrə toplulaşdırma (CTE) ----------
                # qty, revenue, cost, profit + stok və məhsul məlumatları
                PROD_SQL = """
                WITH S AS (
                    SELECT
                        fd.mehsul_kod AS kod,
                        fd.mehsul_cins AS cins,
                        SUM(COALESCE(fd.say,0)) AS qty,
                        SUM(COALESCE(fd.mebleg, COALESCE(fd.satis_qiymet,0)*COALESCE(fd.say,0))) AS revenue,
                        SUM(COALESCE(fd.alis_qiymet, COALESCE(m.alis_qiymet,0)) * COALESCE(fd.say,0)) AS cost
                    FROM fakturalar f
                    JOIN faktura_detal fd ON fd.faktura_id = f.id
                    LEFT JOIN mehsullar m ON m.kod = fd.mehsul_kod AND m.cins = fd.mehsul_cins
                    WHERE (f.tur='SATIŞ' OR f.tur='SATIS' OR f.tur='SATICI' OR f.tur='SAT')
                    AND date(f.tarix) BETWEEN ? AND ?
                    GROUP BY fd.mehsul_kod, fd.mehsul_cins
                )
                SELECT
                    s.kod,
                    COALESCE(mm.ad,'') AS ad,
                    COALESCE(mm.olcu,'') AS olcu,
                    s.cins,
                    COALESCE(mm.stok,0) AS stok,
                    s.qty,
                    CASE WHEN s.qty=0 THEN 0 ELSE (s.cost/s.qty) END  AS ort_alis,
                    CASE WHEN s.qty=0 THEN 0 ELSE (s.revenue/s.qty) END AS ort_satis,
                    s.revenue,
                    (s.revenue - s.cost) AS profit
                FROM S s
                LEFT JOIN mehsullar mm ON mm.kod=s.kod AND mm.cins=s.cins
                """

                def fill_tree(tree, order_by, limit):
                    cur.execute(PROD_SQL + f" ORDER BY {order_by} LIMIT ?", (s, e, limit))
                    for kod, ad, olcu, cins, stok, qty, oa, os_, rev, prof in cur.fetchall():
                        tree.insert("", "end", values=(
                            kod, ad, olcu, cins,
                            _fmt_int(stok),
                            _fmt_int(qty),
                            _fmt_money(oa),
                            _fmt_money(os_),
                            _fmt_money(rev),
                            _fmt_money(prof),
                        ))

                # Ən çox / ən az satılan, ən gəlirli / ən az gəlirli
                fill_tree(self.tree_top,   "qty DESC, revenue DESC", topn)
                fill_tree(self.tree_least, "qty ASC, revenue ASC",   topn)
                fill_tree(self.tree_prof,  "profit DESC, revenue DESC", topn)
                fill_tree(self.tree_worst, "profit ASC, revenue ASC",   topn)

            else:
                # ---------- Faktura üzrə ----------
                # KPI
                cur.execute("""
                    SELECT
                        COUNT(DISTINCT f.id)                                                    AS orders,
                        SUM(COALESCE(fd.mebleg, COALESCE(fd.satis_qiymet,0)*COALESCE(fd.say,0))) AS revenue,
                        SUM(COALESCE(fd.alis_qiymet, COALESCE(m.alis_qiymet,0)) * COALESCE(fd.say,0)) AS cost
                    FROM fakturalar f
                    JOIN faktura_detal fd ON fd.faktura_id = f.id
                    LEFT JOIN mehsullar m ON m.kod = fd.mehsul_kod AND m.cins = fd.mehsul_cins
                    WHERE (f.tur='SATIŞ' OR f.tur='SATIS' OR f.tur='SATICI' OR f.tur='SAT')
                    AND date(f.tarix) BETWEEN ? AND ?
                """, (s, e))
                orders, revenue, cost = cur.fetchone() or (0, 0, 0)
                profit = (revenue or 0) - (cost or 0)
                avg_basket = (revenue or 0) / orders if orders else 0

                self.kpi_orders.configure(text=_fmt_int(orders))
                self.kpi_rev.configure(text=_fmt_money(revenue))
                self.kpi_cost.configure(text=_fmt_money(cost))
                self.kpi_profit.configure(text=_fmt_money(profit))
                self.kpi_avg.configure(text=_fmt_money(avg_basket))

                # Cədvəl
                cur.execute("""
                    SELECT
                        f.faktura_no                                   AS no,
                        f.tarix                                        AS tarix,
                        COALESCE(m.ad, '')                              AS musteri,
                        SUM(COALESCE(fd.say,0))                         AS qty,
                        SUM(COALESCE(fd.mebleg, COALESCE(fd.satis_qiymet,0)*COALESCE(fd.say,0))) AS revenue,
                        SUM(COALESCE(fd.alis_qiymet, COALESCE(ms.alis_qiymet,0)) * COALESCE(fd.say,0)) AS cost,
                        SUM(COALESCE(fd.mebleg, COALESCE(fd.satis_qiymet,0)*COALESCE(fd.say,0))) -
                        SUM(COALESCE(fd.alis_qiymet, COALESCE(ms.alis_qiymet,0)) * COALESCE(fd.say,0)) AS profit
                    FROM fakturalar f
                    JOIN faktura_detal fd ON fd.faktura_id = f.id
                    LEFT JOIN musteriler m ON m.id = f.musteri_id
                    LEFT JOIN mehsullar  ms ON ms.kod = fd.mehsul_kod AND ms.cins = fd.mehsul_cins
                    WHERE (f.tur='SATIŞ' OR f.tur='SATIS' OR f.tur='SATICI' OR f.tur='SAT')
                    AND date(f.tarix) BETWEEN ? AND ?
                    GROUP BY f.id
                    ORDER BY date(f.tarix) DESC, f.faktura_no DESC
                    LIMIT ?
                """, (s, e, 1000))
                for no, tarix, musteri, qty, rev, cst, prof in cur.fetchall():
                    self.tree_invoice.insert("", "end", values=(
                        no, tarix, musteri,
                        _fmt_int(qty),
                        _fmt_money(rev),
                        _fmt_money(cst),
                        _fmt_money(prof),
                    ))

        except Exception as e:
            # hər hansı SQL və ya doldurma xətası
            try:
                from tkinter import messagebox
                messagebox.showerror("Xəta", f"Hesabat icra edilə bilmədi:\n{e}", parent=self)
            except Exception:
                pass
        finally:
            try: con.close()
            except Exception: pass

    def _open_mainmenu(self):
        """Əsas Menyu’nu yeni prosesdə aç və bu pəncərəni bağla (tək pəncərə axını)."""
        logger.info("ƏSAS MENYUYA KEÇİD FakturaForm-dan")
        path = os.path.join(os.path.dirname(__file__), "ana_menu.py")
        try:
            if os.name == "nt":
                # Windows: boşluqlu yollar üçün dırnaqla və shell=True
                q = lambda s: f'"{s}"'
                cmd = " ".join([q(sys.executable), q(path)])
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen([sys.executable, path], shell=False)
        except Exception as e:
            messagebox.showerror("Xəta", f"Əsas Menyu açıla bilmədi:\n{e}")
            logger.error("Əsas Menyu açılma xətası: %s", e)
            return
        os._exit(0)  # cari faktura pəncərəsini bağla


    def _kpi_card(self, parent, title, val):
        logger.info("KPI kartı yaradılır: %s", title)
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.pack(side="left", expand=True, fill="x", padx=8, pady=8)
        ctk.CTkLabel(card, text=title, font=FONT_BOLD, text_color="#64748b").pack(
            anchor="w", padx=14, pady=(12,2)
        )
        lbl = ctk.CTkLabel(card, text=val, font=("Segoe UI", 22, "bold"))
        lbl.pack(anchor="w", padx=14, pady=(0, 12))
        return lbl

    def _make_tree(self, parent, cols):
        logger.info("Ağac görünüşü yaradılır...")
        wrap = ctk.CTkFrame(parent); wrap.pack(fill="both", expand=True, padx=8, pady=8)
        scroll = ctk.CTkScrollbar(wrap); scroll.pack(side="right", fill="y")
        tree = ttk.Treeview(wrap, columns=cols, show="headings",
                            yscrollcommand=scroll.set, selectmode="browse")
        tree.pack(fill="both", expand=True); scroll.configure(command=tree.yview)

        # Sütun genişlikləri
        widths = {c:110 for c in cols}
        widths.update({"AD":320, "ÖLÇÜ":90, "CİNS":100, "STOK":80, "TARİX":110, "MÜŞTƏRİ":220})
        for c in cols:
            tree.heading(c, text=c)
            if c in ("AD","MÜŞTƏRİ"): anchor = "w"
            elif c in ("SATIŞ MƏBLƏĞİ","MƏHSUL DƏYƏRİ","QAZANC","ORT. ALIŞ","ORT. SATIŞ"): anchor = "e"
            else: anchor = "center"
            tree.column(c, width=widths.get(c,110), anchor=anchor)

        st = ttk.Style(self)
        try: st.theme_use("clam")
        except: pass
        st.configure("Treeview", background="#ffffff", foreground="#0f172a",
                     fieldbackground="#ffffff", rowheight=32, font=FONT_NORMAL,
                     borderwidth=1, relief="solid")
        st.configure("Treeview.Heading", background=COLOR_PRIMARY, foreground="white",
                     font=FONT_BOLD, borderwidth=1, relief="solid")
        st.map("Treeview", background=[("selected", COLOR_PRIMARY_HOVER)], foreground=[("selected","white")])
        return tree

    # ---------- tarix / filtr ----------
    def _apply_period_default(self):
        logger.info("Defolt dövr tətbiq edilir...")
        self.periyot.set(self.cmb.get())
        d = today()
        p = self.periyot.get()
        if p == "Gündəlik":   s, e = d, d
        elif p == "Həftəlik": s, e = start_of_week(d), d
        elif p == "Aylıq":    s, e = start_of_month(d), d
        elif p == "Rüblük":   s, e = start_of_quarter(d), d
        elif p == "İllik":    s, e = start_of_year(d), d
        else:
            try:
                s = datetime.strptime(self.tarih1.get(), "%Y-%m-%d").date()
                e = datetime.strptime(self.tarih2.get(), "%Y-%m-%d").date()
            except: s, e = d, d
        self.tarih1.set(dstr(s)); self.tarih2.set(dstr(e))


    # ---------- DB ----------
    def _conn(self):
        logger.info("Verilənlər bazasına qoşulur...")
        base = os.path.dirname(__file__)
        p1 = os.path.join(base, "erp.db")
        p2 = os.path.join(os.getcwd(), "erp.db")
        return sqlite3.connect(p1 if os.path.exists(p1) else p2)

    # ---------- SORĞULAR ----------
    # ... (burada SQL və kod dəyişməz, yalnız mesajlar və başlıqlar dəyişir) ...

    # ---------- icra et ----------
    # ... (yalnız mesajlar və başlıqlar dəyişir) ...

    def _export_all(self):
        """Bütün məlumatı CSV kimi ixrac edir."""
        logger.info("Bütün məlumat ixrac olunur...")
        s, e = self._get_range()
        initialdir = _default_reports_dir()
        initialfile = f"hesabat_{s}_{e}.csv"

        dlg = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV faylları", "*.csv")],
            initialdir=initialdir,
            initialfile=initialfile,
            title="Hesabatı CSV kimi yadda saxla"
        )
        if not dlg:
            return

        try:
            if self.report_mode.get() == "Məhsul üzrə":
                orders, revenue, cost, profit, avg, top, least, prof, worst = self._query_product(limit=1_000_000)
                with open(dlg, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["Hesabat Aralığı", s, e])
                    w.writerow(["Hesabat Tipi", "Məhsul üzrə"])
                    w.writerow([])
                    w.writerow(["KPI"])
                    w.writerow(["Satış Faktura Sayı", orders])
                    w.writerow(["SATIŞ Dövrüyyəsi", revenue])
                    w.writerow(["Məhsul dəyəri (COGS)", cost])
                    w.writerow(["QAZANC", profit])
                    w.writerow(["Ort. Səbət", avg])

                    def dump(title, rows):
                        w.writerow([]); w.writerow([title])
                        w.writerow(["KOD","AD","ÖLÇÜ","CİNS","STOK","SATIŞ_SAY","ORT_ALIŞ","ORT_SATIŞ","SATIŞ_MƏBLƏĞİ","QAZANC"])
                        for r in rows:
                            w.writerow([
                                r[0], r[1], r[2], r[3], int(r[4] or 0), int(r[5] or 0),
                                round(float(r[6] or 0), 2), round(float(r[7] or 0), 2),
                                round(float(r[8] or 0), 2), round(float(r[9] or 0), 2),
                            ])
                    dump("Ən çox satılan", top)
                    dump("Ən az satılan", least)
                    dump("Ən gəlirli", prof)
                    dump("Ən az gəlirli", worst)

            else:
                orders, revenue, cost, profit, avg, rows = self._query_invoice(limit=1_000_000)
                with open(dlg, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["Hesabat Aralığı", s, e])
                    w.writerow(["Hesabat Tipi", "Faktura üzrə"])
                    w.writerow([])
                    w.writerow(["KPI"])
                    w.writerow(["Satış Faktura Sayı", orders])
                    w.writerow(["SATIŞ Dövrüyyəsi", revenue])
                    w.writerow(["Məhsul dəyəri (COGS)", cost])
                    w.writerow(["QAZANC", profit])
                    w.writerow(["Ort. Səbət", avg])
                    w.writerow([])
                    w.writerow(["NO","TARİX","MÜŞTƏRİ","SATIŞ_SAY","SATIŞ_MƏBLƏĞİ","MƏHSUL_DƏYƏRİ","QAZANC"])
                    for no, d, musteri, qty, rev, c, p in rows:
                        w.writerow([no, d, musteri, int(qty or 0),
                                    round(float(rev or 0), 2),
                                    round(float(c or 0), 2),
                                    round(float(p or 0), 2)])

            logger.info("CSV yadda saxlanıldı: %s", dlg)
            messagebox.showinfo("Hesabat yadda saxlanıldı", f"CSV uğurla yadda saxlanıldı:\n{dlg}")

        except PermissionError:
            logger.error("CSV yadda saxlanıla bilmədi: %s", dlg)
            messagebox.showerror(
                "İcazə Xətası",
                "Seçdiyiniz yerə yazıla bilmədi.\n\n"
                "• Fayl açıq ola bilər.\n"
                "• Qovluq üçün yazma icazəniz olmaya bilər.\n\n"
                "Zəhmət olmasa başqa qovluq seçin (məs. Sənədlər)."
            )
        except Exception as e:
            logger.error("CSV yazıla bilmədi: %s", e)
            messagebox.showerror("Xəta", f"CSV yazıla bilmədi:\n{e}")

    #     def _export_pdf(self):
        """Ekrandakı hesabatı sadə PDF kimi ixrac edir."""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except Exception as e:
            messagebox.showerror("Xəta", f"ReportLab tapılmadı:\n{e}", parent=self)
            return

        # Şrift (DejaVu varsa, Azərbaycan dili tam dəstək)
        base_font = "Helvetica"
        try:
            import os
            # layihə qovluğunda DejaVuSans.ttf varsa qeydiyyatdan keçir
            dj = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
            if os.path.exists(dj):
                pdfmetrics.registerFont(TTFont("DejaVu", dj))
                base_font = "DejaVu"
        except Exception:
            pass

        # Fayl yolu dialoqu
        s, e = self._get_range()
        initialdir = _default_reports_dir()
        initialfile = f"hesabat_{s}_{e}.pdf"
        out_path = filedialog.asksaveasfilename(
            title="Hesabatı PDF kimi yadda saxla",
            defaultextension=".pdf",
            filetypes=[("PDF faylları", "*.pdf")],
            initialdir=initialdir,
            initialfile=initialfile
        )
        if not out_path:
            return

        # Səhifə oriyentasiyası: məhsul üzrə (10 sütun) üçün landscape rahatdır
        page = landscape(A4) if self.report_mode.get() == "Məhsul üzrə" else A4
        c = canvas.Canvas(out_path, pagesize=page)
        W, H = page
        margin = 12 * mm
        inner_w = W - 2 * margin
        y = H - margin

        def write_title(txt, size=14):
            nonlocal y
            c.setFont(base_font, size)
            c.drawString(margin, y, txt)
            y -= 8 * mm

        def write_kpis():
            nonlocal y
            c.setFont(base_font, 10)
            lines = [
                f"Faktura (Satış): {getattr(self.kpi_orders, 'cget', lambda k: '0')('text')}",
                f"SATIŞ Dövrüyyəsi: {getattr(self.kpi_rev, 'cget', lambda k: '0.00')('text')}",
                f"Məhsul dəyəri (COGS): {getattr(self.kpi_cost, 'cget', lambda k: '0.00')('text')}",
                f"Qazanc: {getattr(self.kpi_profit, 'cget', lambda k: '0.00')('text')}",
                f"Ort. Səbət: {getattr(self.kpi_avg, 'cget', lambda k: '0.00')('text')}",
            ]
            for line in lines:
                c.drawString(margin, y, line); y -= 6 * mm
            y -= 2 * mm

        def emit_table(title, tree, max_rows=100):
            """Treeview-i cədvəl kimi çək."""
            nonlocal y
            if tree is None: 
                return
            cols = tree["columns"]
            items = tree.get_children()
            if not cols:
                return

            # Yeni səhifə ehtiyacı
            def ensure_header():
                nonlocal y
                if y < 30 * mm:
                    c.showPage()
                    c.setFont(base_font, 10)
                    y = H - margin

            # Başlıq
            ensure_header()
            c.setFont(base_font, 12)
            c.drawString(margin, y, title)
            y -= 6 * mm

            # Sütun enləri (bərabər payla)
            col_w = inner_w / len(cols)

            # Header sətri
            c.setFont(base_font, 10)
            for i, htxt in enumerate(cols):
                x = margin + i * col_w
                c.rect(x, y - 6 * mm, col_w, 7 * mm, stroke=1, fill=0)
                c.drawString(x + 2 * mm, y - 4.5 * mm, str(htxt))
            y -= 7 * mm

            # Sətirlər
            c.setFont(base_font, 9)
            written = 0
            for iid in items:
                vals = tree.item(iid, "values")
                ensure_header()
                if y < 20 * mm:
                    c.showPage()
                    c.setFont(base_font, 9)
                    y = H - margin
                    # header-i yenidən çək
                    for i, htxt in enumerate(cols):
                        x = margin + i * col_w
                        c.rect(x, y - 6 * mm, col_w, 7 * mm, stroke=1, fill=0)
                        c.drawString(x + 2 * mm, y - 4.5 * mm, str(htxt))
                    y -= 7 * mm

                for i, val in enumerate(vals[:len(cols)]):
                    x = margin + i * col_w
                    c.rect(x, y - 6 * mm, col_w, 7 * mm, stroke=1, fill=0)
                    c.drawString(x + 2 * mm, y - 4.5 * mm, str(val))
                y -= 7 * mm
                written += 1
                if written >= max_rows:
                    break

            y -= 4 * mm  # bölücü boşluq

        # Başlıq + KPI
        write_title(f"Hesabat — {s}  →  {e}  ({self.report_mode.get()})")
        write_kpis()

        # Cədvəllər
        if self.report_mode.get() == "Məhsul üzrə":
            emit_table("Ən çox satılan", self.tree_top)
            emit_table("Ən az satılan", self.tree_least)
            emit_table("Ən gəlirli", self.tree_prof)
            emit_table("Ən az gəlirli", self.tree_worst)
        else:
            emit_table("Fakturalar (satış)", self.tree_invoice)

        # Yadda saxla və aç
        try:
            c.save()
            try:
                if os.name == "nt":
                    os.startfile(out_path)
                else:
                    import subprocess, sys
                    subprocess.Popen(["xdg-open", out_path],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            messagebox.showinfo("Məlumat", f"PDF saxlanıldı:\n{out_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Xəta", f"PDF saxlanma xətası:\n{e}", parent=self)

    def _export_pdf(self):
        """Ekrandakı hesabatı sadə PDF kimi ixrac edir."""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except Exception as e:
            messagebox.showerror("Xəta", f"ReportLab tapılmadı:\n{e}", parent=self)
            return

        # Şrift (DejaVu varsa, Azərbaycan dili tam dəstək)
        base_font = "Helvetica"
        try:
            import os
            # layihə qovluğunda DejaVuSans.ttf varsa qeydiyyatdan keçir
            dj = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
            if os.path.exists(dj):
                pdfmetrics.registerFont(TTFont("DejaVu", dj))
                base_font = "DejaVu"
        except Exception:
            pass

        # Fayl yolu dialoqu
        s, e = self._get_range()
        initialdir = _default_reports_dir()
        initialfile = f"hesabat_{s}_{e}.pdf"
        out_path = filedialog.asksaveasfilename(
            title="Hesabatı PDF kimi yadda saxla",
            defaultextension=".pdf",
            filetypes=[("PDF faylları", "*.pdf")],
            initialdir=initialdir,
            initialfile=initialfile
        )
        if not out_path:
            return

        # Səhifə oriyentasiyası: məhsul üzrə (10 sütun) üçün landscape rahatdır
        page = landscape(A4) if self.report_mode.get() == "Məhsul üzrə" else A4
        c = canvas.Canvas(out_path, pagesize=page)
        W, H = page
        margin = 12 * mm
        inner_w = W - 2 * margin
        y = H - margin

        def write_title(txt, size=14):
            nonlocal y
            c.setFont(base_font, size)
            c.drawString(margin, y, txt)
            y -= 8 * mm

        def write_kpis():
            nonlocal y
            c.setFont(base_font, 10)
            lines = [
                f"Faktura (Satış): {getattr(self.kpi_orders, 'cget', lambda k: '0')('text')}",
                f"SATIŞ Dövrüyyəsi: {getattr(self.kpi_rev, 'cget', lambda k: '0.00')('text')}",
                f"Məhsul dəyəri (COGS): {getattr(self.kpi_cost, 'cget', lambda k: '0.00')('text')}",
                f"Qazanc: {getattr(self.kpi_profit, 'cget', lambda k: '0.00')('text')}",
                f"Ort. Səbət: {getattr(self.kpi_avg, 'cget', lambda k: '0.00')('text')}",
            ]
            for line in lines:
                c.drawString(margin, y, line); y -= 6 * mm
            y -= 2 * mm

        def emit_table(title, tree, max_rows=100):
            """Treeview-i cədvəl kimi çək."""
            nonlocal y
            if tree is None: 
                return
            cols = tree["columns"]
            items = tree.get_children()
            if not cols:
                return

            # Yeni səhifə ehtiyacı
            def ensure_header():
                nonlocal y
                if y < 30 * mm:
                    c.showPage()
                    c.setFont(base_font, 10)
                    y = H - margin

            # Başlıq
            ensure_header()
            c.setFont(base_font, 12)
            c.drawString(margin, y, title)
            y -= 6 * mm

            # Sütun enləri (bərabər payla)
            col_w = inner_w / len(cols)

            # Header sətri
            c.setFont(base_font, 10)
            for i, htxt in enumerate(cols):
                x = margin + i * col_w
                c.rect(x, y - 6 * mm, col_w, 7 * mm, stroke=1, fill=0)
                c.drawString(x + 2 * mm, y - 4.5 * mm, str(htxt))
            y -= 7 * mm

            # Sətirlər
            c.setFont(base_font, 9)
            written = 0
            for iid in items:
                vals = tree.item(iid, "values")
                ensure_header()
                if y < 20 * mm:
                    c.showPage()
                    c.setFont(base_font, 9)
                    y = H - margin
                    # header-i yenidən çək
                    for i, htxt in enumerate(cols):
                        x = margin + i * col_w
                        c.rect(x, y - 6 * mm, col_w, 7 * mm, stroke=1, fill=0)
                        c.drawString(x + 2 * mm, y - 4.5 * mm, str(htxt))
                    y -= 7 * mm

                for i, val in enumerate(vals[:len(cols)]):
                    x = margin + i * col_w
                    c.rect(x, y - 6 * mm, col_w, 7 * mm, stroke=1, fill=0)
                    c.drawString(x + 2 * mm, y - 4.5 * mm, str(val))
                y -= 7 * mm
                written += 1
                if written >= max_rows:
                    break

            y -= 4 * mm  # bölücü boşluq

        # Başlıq + KPI
        write_title(f"Hesabat — {s}  →  {e}  ({self.report_mode.get()})")
        write_kpis()

        # Cədvəllər
        if self.report_mode.get() == "Məhsul üzrə":
            emit_table("Ən çox satılan", self.tree_top)
            emit_table("Ən az satılan", self.tree_least)
            emit_table("Ən gəlirli", self.tree_prof)
            emit_table("Ən az gəlirli", self.tree_worst)
        else:
            emit_table("Fakturalar (satış)", self.tree_invoice)

        # Yadda saxla və aç
        try:
            c.save()
            try:
                if os.name == "nt":
                    os.startfile(out_path)
                else:
                    import subprocess, sys
                    subprocess.Popen(["xdg-open", out_path],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            messagebox.showinfo("Məlumat", f"PDF saxlanıldı:\n{out_path}", parent=self)
        except Exception as e:
            messagebox.showerror("Xəta", f"PDF saxlanma xətası:\n{e}", parent=self)


if __name__ == "__main__":
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = RaporlarPenceresi()
    try:
        from single_instance import bring_to_front
        bring_to_front("Hesabatlar")  # və ya pəncərənin tam başlığı
    except Exception:
        pass
    app.mainloop()

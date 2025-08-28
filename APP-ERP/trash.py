# trash.py — Məhsul Zibil Qutusu (filtrli siyahı, bərpa et, daimi sil, məhsullara qayıt)
import customtkinter as ctk
import sqlite3, os, sys, subprocess
from tkinter import ttk, messagebox
from single_instance import claim, is_claimed, bring_to_front
from ui_theme import (
    APP_TITLE, APPEARANCE_MODE, COLOR_THEME,
    COLOR_PRIMARY, COLOR_PRIMARY_HOVER, COLOR_SUCCESS, COLOR_BG_SOFT,
    FONT_H1, FONT_BOLD, FONT_NORMAL,
    button_style, enable_windows_chrome, logger
)

DB_PATH = "erp.db"

class TrashPenceresi(ctk.CTk):
    def __init__(self):
        super().__init__()
        if enable_windows_chrome:
            try: enable_windows_chrome(self)
            except Exception: pass

        self.title(f"{APP_TITLE} — Məhsul Zibil Qutusu")
        self.geometry("1200x720")
        self.minsize(1000, 600)
        self.configure(fg_color=COLOR_BG_SOFT)

        logger.info("Zibil qutusu pəncərəsi yaradıldı.")

        # filtr vəziyyətləri
        self.q_kod   = ctk.StringVar()
        self.q_ad    = ctk.StringVar()
        self.q_cins  = ctk.StringVar()
        self.q_note  = ctk.StringVar()

        self._build_ui()
        self._refresh()

    # -------------------- UI --------------------
    def _build_ui(self):
        # YUXARI PANEL (başlıq + Məhsullara qayıt)
        logger.info("İstifadəçi interfeysi qurulur...")
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(top, text="🗑️ MƏHSUL ZİBİL QUTUSU", font=FONT_H1).pack(side="left")

        ctk.CTkButton(
            top, text="Məhsullar",
            **button_style("success", size="lg"),
            command=self._open_mehsullar
        ).pack(side="right", padx=(8, 0))

        # FİLTR PANELİ
        fb = ctk.CTkFrame(self, fg_color="transparent")
        fb.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(fb, text="Kod:", font=FONT_NORMAL).pack(side="left")
        ctk.CTkEntry(fb, width=160, textvariable=self.q_kod, font=FONT_NORMAL).pack(side="left", padx=(4, 12))

        ctk.CTkLabel(fb, text="Ad:", font=FONT_NORMAL).pack(side="left")
        ctk.CTkEntry(fb, width=260, textvariable=self.q_ad, font=FONT_NORMAL).pack(side="left", padx=(4, 12))

        ctk.CTkLabel(fb, text="Cins:", font=FONT_NORMAL).pack(side="left")
        ctk.CTkEntry(fb, width=140, textvariable=self.q_cins, font=FONT_NORMAL).pack(side="left", padx=(4, 12))

        ctk.CTkLabel(fb, text="Qeyd:", font=FONT_NORMAL).pack(side="left")
        ctk.CTkEntry(fb, width=260, textvariable=self.q_note, font=FONT_NORMAL).pack(side="left", padx=(4, 0))

        for v in (self.q_kod, self.q_ad, self.q_cins, self.q_note):
            v.trace_add("write", lambda *_: self._refresh())

        # CƏDVƏL
        table_wrap = ctk.CTkFrame(self, corner_radius=12)
        table_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        self.scroll_y = ctk.CTkScrollbar(table_wrap); self.scroll_y.pack(side="right", fill="y")

        columns = ("DELETED_AT","KOD","AD","ÖLÇÜ","CİNS","STOK","ALIŞ","SATIŞ","QEYD")
        self.tree = ttk.Treeview(
            table_wrap, columns=columns, show="headings",
            yscrollcommand=self.scroll_y.set, selectmode="browse"
        )
        self.tree.pack(fill="both", expand=True, padx=(6, 0), pady=6)
        self.scroll_y.configure(command=self.tree.yview)

        # Excel cədvəli + yaşıl seçim
        st = ttk.Style(self); st.theme_use("clam")
        st.configure("Treeview",
                    background="#ffffff", foreground="#000000",
                    fieldbackground="#ffffff", rowheight=32, font=FONT_NORMAL,
                    borderwidth=1, relief="solid")
        st.configure("Treeview.Heading",
                    background=COLOR_PRIMARY, foreground="white",
                    font=FONT_BOLD, borderwidth=1, relief="solid")
        st.map("Treeview",
            background=[("selected", COLOR_SUCCESS)],
            foreground=[("selected", "white")])

        widths = {"DELETED_AT":180, "KOD":120, "AD":320, "ÖLÇÜ":90, "CİNS":90,
                "STOK":90, "ALIŞ":90, "SATIŞ":90, "QEYD":260}
        anchors= {"DELETED_AT":"center","KOD":"w","AD":"w","ÖLÇÜ":"center","CİNS":"center",
                "STOK":"e","ALIŞ":"e","SATIŞ":"e","QEYD":"w"}
        for c in columns:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=widths[c], anchor=anchors[c])

        # ALT DÜYMƏLƏR
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(0, 12))

        left_box = ctk.CTkFrame(bottom, fg_color="transparent"); left_box.pack(side="left")
        right_box= ctk.CTkFrame(bottom, fg_color="transparent"); right_box.pack(side="right")

        ctk.CTkButton(
            left_box, text="Yenilə",
            **button_style("primary", size="lg"),
            command=self._refresh
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            right_box, text="Daimi Sil",
            **button_style("danger", size="lg"),
            command=self._permanent_delete_selected
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            right_box, text="Bərpa Et",
            **button_style("success", size="lg"),
            command=self._restore_selected
        ).pack(side="right", padx=(8, 8))

    # -------------------- DATA --------------------
    def _connect(self):
        logger.info("Verilənlər bazasına qoşulur...")
        return sqlite3.connect(DB_PATH)

    def _ensure_trash_table(self, cur):
        logger.info("Zibil cədvəlinin mövcudluğu yoxlanılır...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mehsullar_trash (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deleted_at TEXT DEFAULT (datetime('now')),
                kod TEXT, ad TEXT, olcu TEXT, cins TEXT,
                stok REAL, alis_qiymet REAL, satis_qiymet REAL,
                note TEXT
            )
        """)

    def _build_where(self):
        logger.info("WHERE şərti qurulur...")
        where = []; params = []
        if self.q_kod.get().strip():
            where.append("kod LIKE ?"); params.append(f"%{self.q_kod.get().strip()}%")
        if self.q_ad.get().strip():
            where.append("ad LIKE ?"); params.append(f"%{self.q_ad.get().strip()}%")
        if self.q_cins.get().strip():
            where.append("IFNULL(cins,'') LIKE ?"); params.append(f"%{self.q_cins.get().strip()}%")
        if self.q_note.get().strip():
            where.append("IFNULL(note,'') LIKE ?"); params.append(f"%{self.q_note.get().strip()}%")
        return (("WHERE " + " AND ".join(where)) if where else ""), params

    def _refresh(self):
        logger.info("Cədvəl yenilənir...")
        # cədvəli təmizlə
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            conn = self._connect(); cur = conn.cursor()
            self._ensure_trash_table(cur)
            where_sql, params = self._build_where()
            cur.execute(f"""
                SELECT deleted_at, kod, IFNULL(ad,''), IFNULL(olcu,''), IFNULL(cins,''),
                       IFNULL(stok,0.0), IFNULL(alis_qiymet,0.0), IFNULL(satis_qiymet,0.0),
                       IFNULL(note,'')
                FROM mehsullar_trash
                {where_sql}
                ORDER BY deleted_at DESC
            """, params)
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            logger.error("Siyahı alına bilmədi: %s", e)
            messagebox.showerror("Xəta", f"Siyahı alına bilmədi:\n{e}")
            return

        for i, r in enumerate(rows):
            tag = "odd" if i % 2 else "even"
            # ədədi sahələri sağa düzülmüş göstərmək üçün string format
            r = list(r)
            r[5] = f"{float(r[5]):.0f}" if float(r[5]).is_integer() else f"{float(r[5]):.2f}"
            r[6] = f"{float(r[6]):.2f}"
            r[7] = f"{float(r[7]):.2f}"
            self.tree.insert("", "end", values=r, tags=(tag,))

    # -------------------- ACTIONS --------------------
    def _selected_values(self):
        logger.info("Seçilmiş dəyərlər alınır...")
        item = self.tree.focus()
        if not item:
            logger.warning("Heç bir sətir seçilməyib.")
            messagebox.showinfo("Məlumat", "Zəhmət olmasa bir qeyd seçin.")
            return None
        return self.tree.item(item, "values")

    def _restore_selected(self):
        logger.info("Seçilmiş qeyd bərpa olunur...")
        vals = self._selected_values()
        if not vals: return
        deleted_at, kod, ad, olcu, cins, stok, alis, satis, note = vals

        try:
            conn = self._connect(); cur = conn.cursor()
            self._ensure_trash_table(cur)

            # zibil qeydini tam gətir (tip uyğunluqları)
            cur.execute("""
                SELECT id, kod, ad, olcu, IFNULL(cins,''), IFNULL(stok,0.0),
                       IFNULL(alis_qiymet,0.0), IFNULL(satis_qiymet,0.0), IFNULL(note,'')
                FROM mehsullar_trash
                WHERE kod=? AND IFNULL(cins,'')=? AND deleted_at=?
            """, (kod, cins, deleted_at))
            tr = cur.fetchone()
            if not tr:
                conn.close(); messagebox.showerror("Xəta","Qeyd tapılmadı."); return

            trash_id, kod, ad, olcu, cins, stok, alis, satis, note = tr

            # mövcuddur?
            cur.execute("SELECT COUNT(1) FROM mehsullar WHERE kod=? AND IFNULL(cins,'')=?", (kod, cins))
            exists = cur.fetchone()[0] > 0

            if exists:
                logger.warning("Qeyd artıq mövcuddur: %s / %s", kod, cins)
                if not messagebox.askyesno(
                    "Bərpa Et",
                    f"'{kod} / {cins}' artıq mövcuddur.\n"
                    "Zibil qutusundakı məlumatlarla ÜZƏRİNƏ YAZILSIN?"
                ):
                    conn.close(); return
                cur.execute("""
                    UPDATE mehsullar
                       SET ad=?, olcu=?, cins=?, stok=?, alis_qiymet=?, satis_qiymet=?
                     WHERE kod=? AND IFNULL(cins,'')=?
                """, (ad, olcu, cins, stok, alis, satis, kod, cins))
            else:
                cur.execute("""
                    INSERT INTO mehsullar (kod, ad, olcu, cins, stok, alis_qiymet, satis_qiymet)
                    VALUES (?,?,?,?,?,?,?)
                """, (kod, ad, olcu, cins, stok, alis, satis))

            # zibil qeydini sil
            cur.execute("DELETE FROM mehsullar_trash WHERE id=?", (trash_id,))
            conn.commit(); conn.close()
            logger.info("Seçilmiş qeyd bərpa olundu.")
            messagebox.showinfo("Məlumat", "Qeyd bərpa olundu.")
            self._refresh()
        except Exception as e:
            logger.error("Bərpa olunmadı: %s", e)
            messagebox.showerror("Xəta", f"Bərpa olunmadı:\n{e}")

    def _permanent_delete_selected(self):
        logger.info("Seçilmiş qeyd daimi silinir...")
        vals = self._selected_values()
        if not vals: return
        deleted_at, kod, ad, olcu, cins, *_ = vals

        if not messagebox.askyesno(
            "Daimi Sil",
            f"Bu qeyd DAİMİ olaraq silinəcək:\n• {kod} / {cins}\n\nDavam edilsin?"
        ):
            logger.info("Daimi silmə ləğv edildi.")
            return
        try:
            logger.info("Verilənlər bazasına qoşulur...")
            conn = self._connect(); cur = conn.cursor()
            self._ensure_trash_table(cur)
            cur.execute("""
                DELETE FROM mehsullar_trash
                 WHERE kod=? AND IFNULL(cins,'')=? AND deleted_at=?
            """, (kod, cins, deleted_at))
            conn.commit(); conn.close()
            self._refresh()
            logger.info("Seçilmiş qeyd daimi silindi.")
        except Exception as e:
            logger.error("Silmək mümkün olmadı: %s", e)
            messagebox.showerror("Xəta", f"Silmək mümkün olmadı:\n{e}")

    def _open_mehsullar(self):
        logger.info("Məhsullar pəncərəsi açılır...")
        path = os.path.join(os.path.dirname(__file__), "mehsullar.py")
        if is_claimed("mehsullar"):
            bring_to_front("Məhsullar")           # mövcud Məhsullar pəncərəsini önə gətir
            return
        subprocess.Popen([sys.executable, path], close_fds=True)
       


if __name__ == "__main__":
    if not claim("trash"): sys.exit(0)
    ctk.set_appearance_mode(APPEARANCE_MODE)
    ctk.set_default_color_theme(COLOR_THEME)
    app = TrashPenceresi()
    app.mainloop()

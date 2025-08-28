import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import sqlite3, re, tempfile, time
from contextlib import closing
import os, sys, subprocess       
from single_instance import claim, is_claimed, bring_to_front
from ui_theme import (
    COLOR_PRIMARY, COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS, COLOR_WARNING,
    FONT_BOLD, FONT_NORMAL, enable_windows_chrome,
    load_app_settings, button_style, logger, log_call
)

# Printer (isteğe bağlı, pywin32) – dinamik import
try:
    import importlib
    win32print = importlib.import_module("win32print")  # type: ignore[assignment]
except Exception:
    win32print = None

# >>> Tema və şriftləri ayarlardan tətbiq et:
try:
    from ui_theme import apply_theme_global
    apply_theme_global()
except Exception:
    pass

ROW_HEIGHT_PX = 34
BASE_HEADER_PX = 48  # Cədvəl başlığı üçün hündürlük (piksel)
INIT_SCREEN_RATIO = (0.62, 0.66)
MAX_SCREEN_RATIO = 0.92  # Yenidən ölçüləndirmə üçün maksimum ekran hündürlüyü nisbəti
KOD_REGEX = re.compile(r'^[A-Z]+[0-9]{2,}$')

import sys
def except_hook(exctype, value, traceback):
    import tkinter.messagebox as mb
    mb.showerror("Tkinter Xətası", f"{exctype.__name__}: {value}")
    sys.__excepthook__(exctype, value, traceback)
sys.excepthook = except_hook

class FakturaForm(ctk.CTk):  # <-- CTkToplevel əvəzinə CTk (əsas pəncərə)
    def __init__(self, master=None, force_mode=None):
        super().__init__()

        # Windows-un standart başlıq çubuğu (min/max/close) üçün:
        if enable_windows_chrome:
            try:
                enable_windows_chrome(self)
            except Exception:
                pass  # yoxdursa normal davam

        self.title("Faktura")
        self._apply_initial_size()
        logger.info("PƏNCƏRƏ AÇILDI: FakturaForm mode=%s", force_mode)

        self.is_alis = True if force_mode in (None, "alis") else False
        self.db_path = os.path.join(os.path.dirname(__file__), "erp.db")
        self.phone_prefix = "+994 "
        self.fullscreen = False

        self._active_row = None
        self._focus_bounce = False
        self._tip = None
        self._tip_after = None
        self._tip_key = None
        self._tip_lock_until = 0.0

        # >>> ENLİK AYARLARI <<<
        self.column_weights = {
            "KOD *": 1, "AD": 7, "ÖLÇÜ": 1, "CİNS": 1,
            "SAY *": 1, "ALIŞ ₼ *": 2, "SATIŞ ₼ *": 2, "MEBLEG": 2
        }
        self.column_mins = {
            "KOD *": 90, "AD": 320, "ÖLÇÜ": 90, "CİNS": 110,
            "SAY *": 80, "ALIŞ ₼ *": 120, "SATIŞ ₼ *": 120, "MEBLEG": 120
        }
        self.column_pref = {
            "KOD *": 100, "AD": 360, "ÖLÇÜ": 110, "CİNS": 120,
            "SAY *": 90, "ALIŞ ₼ *": 130, "SATIŞ ₼ *": 130, "MEBLEG": 130
        }
        db_same_dir = os.path.join(os.path.dirname(__file__), "erp.db")
        db_cwd      = os.path.join(os.getcwd(), "erp.db")
        self.db_path = db_same_dir if os.path.exists(db_same_dir) else db_cwd
        
        self.settings = load_app_settings()

        self._apply_initial_size()
        self._check_database()
        self._ensure_schema()
        self._create_widgets()
        self._setup_table()
        self.bind("<F11>", lambda _e: self.toggle_fullscreen())
        self.protocol("WM_DELETE_WINDOW", self._confirm_close)
    
    # ---------------- pəncərə / ölçü ----------------
    def _apply_initial_size(self):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = int(sw * INIT_SCREEN_RATIO[0]); h = int(sh * INIT_SCREEN_RATIO[1])
        x = int((sw - w)//2); y = int((sh - h)//2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(880, 560)

    def _maybe_resize_window(self):
        try:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            max_h = int(sh * MAX_SCREEN_RATIO)
            row_count = len(getattr(self, "table_rows", []))
            desired_h = BASE_HEADER_PX + (row_count * ROW_HEIGHT_PX)
            self.update_idletasks()
            cur_w, cur_h = map(int, self.geometry().split("+")[0].split("x"))
            new_h = min(max(desired_h, cur_h), max_h)
            if new_h != cur_h and not self.fullscreen:
                x = int((sw - cur_w)//2); y = int((sh - new_h)//2)
                self.geometry(f"{cur_w}x{new_h}+{x}+{y}")
        except: pass

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        try: self.attributes("-fullscreen", self.fullscreen)
        except: self.state("zoomed" if self.fullscreen else "normal")

    def _is_form_dirty(self) -> bool:
        """Formda istifadəçi girişi varmı? Boşdursa False qaytarır."""
        # Başlıq sahələri
        if (self.musteri_entry.get().strip()
            or self._phone_digits()):  # telefon rəqəm varsa doludur
            return True

        # Sətirlərdə hər hansı giriş varmı?
        for row in getattr(self, "table_rows", []):
            if self._row_has_any_input(row):
                return True

        # Toplam 0.00 deyilsə də dolu saymaq olar (istəyə bağlı)
        # if self.toplam_label.cget("text") != "TOPLAM: 0.00":
        #     return True

        return False

    def _confirm_close(self):
        """Yalnız form doludursa xəbərdarlıq et; boşdursa birbaşa bağla."""
        logger.info("BAĞLAMA SORĞUSU: FakturaForm dirty=%s", self._is_form_dirty())
        from tkinter import messagebox
        if not self._is_form_dirty():
            self.destroy()
            return
        if messagebox.askyesno("Bağla", "Yadda saxlanmamış məlumatlar var. Yenə də bağlansın?"):
            self.destroy()
        logger.info("PƏNCƏRƏ BAĞLANDI: FakturaForm")

    # ---------------- DB / sxem ----------------
    @log_call()
    def _check_database(self):
        if not os.path.exists(self.db_path):
            messagebox.showerror(
                "Xəta",
                f"Verilənlər bazası tapılmadı:\n{self.db_path}\n\n"
                "Zəhmət olmasa 'erp.db' faylını tətbiq qovluğuna yerləşdirin."
            )
            return  # self.destroy() YOX
    @log_call()
    def _ensure_schema(self):
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                c = conn.cursor()
                c.execute("PRAGMA table_info(fakturalar)")
                if "toplam" not in {r[1] for r in c.fetchall()}:
                    c.execute("ALTER TABLE fakturalar ADD COLUMN toplam REAL DEFAULT 0")
                    conn.commit()
                c.execute("PRAGMA table_info(faktura_detal)")
                if "toplam" not in {r[1] for r in c.fetchall()}:
                    c.execute("ALTER TABLE faktura_detal ADD COLUMN toplam REAL")
                    conn.commit()
        except Exception as e:
            print("sxem təminatı:", e)

    def _fakturalar_has_toplam(self, conn):
        try:
            c = conn.cursor()
            c.execute("PRAGMA table_info(fakturalar)")
            return "toplam" in {r[1] for r in c.fetchall()}
        except:
            return False

    # ---------------- tək ipucu (titrəyişsiz) ----------------
    def _place_tip(self, widget):
        self.update_idletasks()
        x = widget.winfo_rootx() - self.winfo_rootx() + widget.winfo_width() + 8
        y = widget.winfo_rooty() - self.winfo_rooty() - 4
        if x + self._tip.winfo_reqwidth() > self.winfo_width() - 10:
            x = widget.winfo_rootx() - self.winfo_rootx() - self._tip.winfo_reqwidth() - 8
        if y + self._tip.winfo_reqheight() > self.winfo_height() - 10:
            y = widget.winfo_rooty() - self.winfo_rooty() + widget.winfo_height() + 4
        self._tip.place(x=x, y=y); self._tip.lift()

    def _show_tip(self, widget, text: str):
        """Qısa müddətli ipucu etiketi (tema rəngi/şrift)."""
        try:
            if hasattr(self, "_tip") and self._tip is not None:
                self._tip.destroy()
        except Exception:
            pass

        from ui_theme import COLOR_WARNING, FONT_BOLD
        self._tip = ctk.CTkLabel(
            self, text=text, fg_color=COLOR_WARNING,
            text_color="white", font=FONT_BOLD, corner_radius=8
        )
        try:
            x = widget.winfo_rootx() - self.winfo_rootx()
            y = widget.winfo_rooty() - self.winfo_rooty() - 36
            self._tip.place(x=x, y=y)
            self.after(2000, lambda: (self._tip.destroy() if getattr(self, "_tip", None) else None))
        except Exception:
            # yerləşdirmə xətası olarsa ortada göstər
            self._tip.pack(pady=6)
            self.after(2000, lambda: (self._tip.destroy() if getattr(self, "_tip", None) else None))

    def _extend_tip(self, extra_ms):
        if self._tip and self._tip.winfo_exists():
            if self._tip_after:
                try: self.after_cancel(self._tip_after)
                except: pass
            self._tip_after = self.after(extra_ms, self._hide_tip)

    def _hide_tip(self):
        if self._tip and self._tip.winfo_exists(): self._tip.place_forget()
        self._tip_after = None

    # ---------------- UI ----------------
    def _theme_mode_button(self):
        """ALlŞ/SATlŞ mod düyməsinin stilini (rəng/şrift) temadan tətbiq et."""
        from ui_theme import button_style
        try:
            self.mode_button.configure(
                text="ALlŞ" if self.is_alis else "SATlŞ",
                **button_style("success" if self.is_alis else "primary")
            )
        except Exception:
            pass

    def _create_widgets(self):
        top = ctk.CTkFrame(self, fg_color="transparent"); top.pack(fill="x", padx=10, pady=(10,5))
        # ... _create_widgets içində, mode_button yaradılan yeri TAMAMİLƏ bununla əvəz et:
        self.mode_button = ctk.CTkButton(
            top,
            text="ALlŞ" if self.is_alis else "SATlŞ",
            **button_style("success" if self.is_alis else "primary", size="lg"),  # hündürlük temadan
            width=150,                                  # height PARAMETRİ YOX!
            command=self.toggle_mode
        )
        self.mode_button.pack(pady=(0, 10))

        info = ctk.CTkFrame(top, fg_color="transparent"); info.pack(fill="x")
        left = ctk.CTkFrame(info, fg_color="transparent"); left.pack(side="left", padx=20, anchor="n")
        ctk.CTkLabel(left, text="Müştəri Adı", font=FONT_NORMAL).pack(anchor="w")
        self.musteri_entry = ctk.CTkEntry(left, width=260); self.musteri_entry.pack(anchor="w", pady=(0,6))
        self.musteri_entry.bind("<KeyRelease>", lambda e: self._upper_on_type(e.widget))
        ctk.CTkLabel(left, text="Telefon", font=FONT_NORMAL).pack(anchor="w")
        self.telefon_entry = ctk.CTkEntry(left, width=170, placeholder_text="(55) 123 45 67")
        self.telefon_entry.pack(anchor="w")
        self.telefon_entry.bind("<KeyRelease>", self._phone_live_format)
        self.telefon_entry.bind("<FocusOut>", self._phone_validate)

        right = ctk.CTkFrame(info, fg_color="transparent"); right.pack(side="right", padx=20, anchor="n")
        ctk.CTkLabel(right, text="Faktura №", font=FONT_NORMAL).pack(anchor="w")
        self.faktura_no_entry = ctk.CTkEntry(right, width=180)
        self.faktura_no_entry.insert(0, self._generate_invoice_no())
        self.faktura_no_entry.configure(state="readonly"); self.faktura_no_entry.pack(anchor="w", pady=(0,6))
        ctk.CTkLabel(right, text="Tarix", font=FONT_NORMAL).pack(anchor="w")
        self.tarix_entry = ctk.CTkEntry(right, width=140)
        self.tarix_entry.insert(0, datetime.now().strftime("%Y-%m-%d")); self.tarix_entry.pack(anchor="w")

        self.table_outer = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.table_outer.pack(fill="both", expand=True, padx=10, pady=(6,0))
        self.table_frame = ctk.CTkFrame(self.table_outer, fg_color="transparent"); self.table_frame.pack(fill="both", expand=True)

        self.toplam_label = ctk.CTkLabel(self.table_outer, text="CƏMİ: 0.00", font=FONT_BOLD)
        self.toplam_label.pack(anchor="w", padx=2, pady=(8,8))

        bottom = ctk.CTkFrame(self, fg_color="transparent"); bottom.pack(fill="x", padx=10, pady=8)
        self._create_bottom_buttons(bottom)

        self._apply_theme_fonts()

    # ---------------- köməkçilər ----------------
    def _visible_headers(self):
        headers = ["KOD *","AD","ÖLÇÜ","CİNS","SAY *","ALIŞ ₼ *","SATIŞ ₼ *","MEBLEG"]
        return [h for h in headers if not (not self.is_alis and h=="ALIŞ ₼ *")]

    def _upper_on_type(self, w):
        pos = w.index(tk.INSERT); txt = w.get(); up = txt.upper()
        if up != txt:
            w.delete(0, tk.END); w.insert(0, up)
            try: w.icursor(pos)
            except: pass

    def _row_has_any_input(self, row):
        for k, w in row.items():
            if k=="MEBLEG": continue
            if isinstance(w, ctk.CTkComboBox):
                if w.get().strip(): return True
            else:
                if w.get().strip(): return True
        return False

    def _price_header(self): return "ALIŞ ₼ *" if self.is_alis else "SATIŞ ₼ *"

    def _apply_theme_fonts(self):
        """Formdakı girişlərin şriftini bir dəfəlik temaya bağla."""
        from ui_theme import FONT_NORMAL
        # Üst sahələr
        for ent in (getattr(self, "musteri_entry", None),
                    getattr(self, "telefon_entry", None),
                    getattr(self, "faktura_no_entry", None),
                    getattr(self, "tarix_entry", None)):
            try:
                if ent: ent.configure(font=FONT_NORMAL)
            except Exception:
                pass

        # Sətir hüceyrələri (varsa)
        for row in getattr(self, "table_rows", []):
            for key in ("KOD *","AD *","ÖLÇÜ","CİNS","SAY *","ALIŞ ₼ *","SATIŞ ₼ *","MƏBLƏĞ","MEBLEG"):
                w = row.get(key)
                try:
                    if hasattr(w, "configure"):
                        w.configure(font=FONT_NORMAL)
                except Exception:
                    pass

    def _first_missing_required(self, row):
        if not self._row_has_any_input(row): return None
        for h in ["KOD *","SAY *", self._price_header()]:
            if h in row and not row[h].get().strip(): return row[h]
        return None

    # ---------------- telefon ----------------
    def _phone_digits(self): return re.sub(r"\D", "", self.telefon_entry.get())

    def _format_phone_string(self, digits):
        d = digits[:9]
        if not d: return ""
        if len(d)<=2: return f"({d}"
        out = f"({d[:2]}) "
        if len(d)<=5: return out + d[2:]
        out += d[2:5] + " "
        if len(d)<=7: return out + d[5:]
        return out + d[5:7] + " " + d[7:]

    def _phone_live_format(self, _e=None):
        digits = self._phone_digits(); new = self._format_phone_string(digits)
        if new != self.telefon_entry.get():
            cur = self.telefon_entry.index(tk.INSERT)
            self.telefon_entry.delete(0, tk.END); self.telefon_entry.insert(0, new)
            try: self.telefon_entry.icursor(min(cur+1, len(new)))
            except: pass

    def _phone_validate(self, _e=None):
        s = self._phone_digits()
        if s and len(s)!=9:
            self._show_tip(self.telefon_entry, "Telefon 9 rəqəm olmalıdır. Məs: (55) 123 45 67")

    # ---------------- sahə yoxlamaları ----------------
    def _format_olcu(self, w):
        raw = w.get().strip()
        if raw=="": return True
        if re.fullmatch(r"\d{2}", raw): return True
        if re.fullmatch(r"\d{2}-\d{2}", raw): return True
        if re.fullmatch(r"\d{4}", raw):
            w.delete(0, tk.END); w.insert(0, f"{raw[:2]}-{raw[2:]}"); return True
        self._show_tip(w, "Ölçü 'nn' və ya 'nn-nn' olmalıdır. Məs: 40 və ya 40-45.")
        return True

    def _format_price(self, w, row):
        txt = w.get().strip()
        if txt=="":
            return True
        try:
            n = float(txt.replace(",", "."))
            w.delete(0, tk.END); w.insert(0, f"{n:.2f}")
            return True
        except:
            self._show_tip(w, "Düzgün qiymət daxil et (məs: 12.50).")
            return True

    def _validate_say_and_stock(self, row):
        say_w = row["SAY *"]; txt = say_w.get().strip()
        if txt=="":
            return True
        if not re.fullmatch(r"\d+", txt):
            self._show_tip(say_w, "SAY tam ədəd olmalıdır (məs: 3).")
            return True
        if not self.is_alis:
            kod = row["KOD *"].get().strip().upper()
            cins = row["CİNS"].get().strip()
            if not kod: return True
            try:
                with closing(sqlite3.connect(self.db_path)) as conn:
                    c = conn.cursor()
                    c.execute("SELECT IFNULL(stok,0) FROM mehsullar WHERE kod=? AND cins=?", (kod, cins))
                    s = c.fetchone(); mevcut = int(s[0]) if s else 0
                    if int(say_w.get()) > mevcut:
                        self._show_tip(say_w, f"Anbarda kifayət qədər yoxdur! Mövcud: {mevcut}")
            except Exception as e:
                print("stok:", e)
        return True

    def _price_guard(self, row):
        try:
            al = float(row.get("ALIŞ ₼ *").get().replace(",", ".")) if self.is_alis and "ALIŞ ₼ *" in row else None
            sa = float(row.get("SATIŞ ₼ *").get().replace(",", ".")) if "SATIŞ ₼ *" in row else None
            if al is not None and sa is not None and sa < al:
                self._show_tip(row["SATIŞ ₼ *"], "Diqqət: Satış qiyməti alışdan aşağıdır.")
        except: pass

    def _handle_focus_in(self, new_row_idx):
        if self._focus_bounce:
            self._focus_bounce = False; self._active_row = new_row_idx; return
        prev = self._active_row
        if prev is None or new_row_idx==prev:
            self._active_row = new_row_idx; return
        if new_row_idx < prev:
            self._active_row = new_row_idx; return
        prev_row = self.table_rows[prev]
        miss = self._first_missing_required(prev_row)
        if miss:
            self._show_tip(miss, f"{prev+1}. sətr: KOD, SAY və QİYMƏT vacibdir.")
            self._focus_bounce = True
            self.after_idle(lambda w=miss: w.focus_set())
            return
        self._active_row = new_row_idx

    # ---------------- kod + auto doldurma ----------------
    def _validate_kod_and_autofill(self, row):
        kod_w = row["KOD *"]; self._upper_on_type(kod_w)
        kod = kod_w.get().strip()
        if kod=="": return True
        if not KOD_REGEX.match(kod):
            self._show_tip(kod_w, "Kod formatı: A001, AB01 (ən azı 1 hərf + 2 rəqəm).")
            return True
        cins = row["CİNS"].get().strip() if "CİNS" in row else ""
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                c = conn.cursor()
                if cins:
                    c.execute("""SELECT ad, olcu, IFNULL(satis_qiymet,0), IFNULL(stok,0)
                                 FROM mehsullar WHERE kod=? AND cins=?""", (kod, cins))
                else:
                    c.execute("""SELECT ad, olcu, IFNULL(satis_qiymet,0), IFNULL(stok,0)
                                 FROM mehsullar WHERE kod=? ORDER BY stok DESC LIMIT 1""", (kod,))
                srow = c.fetchone()
                if srow:
                    ad, olcu, s_fiyat, _ = srow
                    if ad and not row["AD"].get().strip(): row["AD"].insert(0, ad)
                    if olcu and not row["ÖLÇÜ"].get().strip(): row["ÖLÇÜ"].insert(0, olcu)
                    if "SATIŞ ₼ *" in row and not row["SATIŞ ₼ *"].get().strip():
                        row["SATISI ₼ *"].insert(0, f"{float(s_fiyat):.2f}")
                if self.is_alis and "ALIŞ ₼ *" in row and not row["ALIŞ ₼ *"].get().strip():
                    c.execute("""SELECT alis_qiymet FROM faktura_detal
                                 WHERE mehsul_kod=? AND (?='' OR mehsul_cins=?)
                                 AND alis_qiymet IS NOT NULL
                                 ORDER BY id DESC LIMIT 1""", (kod, cins, cins))
                    last_al = c.fetchone()
                    if last_al and last_al[0] is not None:
                        row["ALIŞ ₼ *"].insert(0, f"{float(last_al[0]):.2f}")
        except Exception as e:
            print("auto doldurma:", e)
        return True

    # ---------------- cədvəl ----------------
    def _setup_table(self):
        for w in self.table_frame.winfo_children():
            w.destroy()
        self.table_rows = []
        self._active_row = None

        visible = self._visible_headers()

        for i, h in enumerate(visible):
            self.table_frame.grid_columnconfigure(
                i,
                weight=self.column_weights.get(h, 1),
                minsize=self.column_mins.get(h, 80)
            )

        for c, h in enumerate(visible):
            hdr = ctk.CTkLabel(self.table_frame, text=h, fg_color="#e2e8f0",
                               font=("Segoe UI", 12, "bold"), corner_radius=4)
            hdr.grid(row=0, column=c, sticky="nsew", padx=2, pady=2)

        for _ in range(3):
            self._add_row()
        self._maybe_resize_window()
   
    def _make_combobox_readonly(self, combo: ctk.CTkComboBox):
        combo.bind("<Key>", lambda e: "break")
        combo.bind("<<Paste>>", lambda e: "break")
        combo.bind("<Control-v>", lambda e: "break")
        combo.bind("<Control-V>", lambda e: "break")

    def _add_row(self):
        visible = self._visible_headers()
        row_idx = len(self.table_rows)
        grid_r = row_idx + 1

        row_widgets = {}
        for c, h in enumerate(visible):
            pref_w = self.column_pref.get(h, 100)
            if h == "CİNS":
                w = ctk.CTkComboBox(self.table_frame, values=["", "kişi", "qadın"], width=pref_w)
                w.set("")
                self._make_combobox_readonly(w)
                w.configure(command=lambda _ch, rr=row_widgets:
                            (rr.get("KOD *") and rr["KOD *"].get().strip()) and
                            self._validate_kod_and_autofill(rr))
            elif h in ["SAY *", "ALIŞ ₼ *", "SATIŞ ₼ *"]:
                w = ctk.CTkEntry(self.table_frame, width=pref_w)
                w.bind("<KeyRelease>", lambda _e: self._calculate_totals())
            elif h == "KOD *":
                w = ctk.CTkEntry(self.table_frame, width=pref_w)
                w.bind("<KeyRelease>", lambda e: self._upper_on_type(e.widget))
                w.bind("<FocusOut>", lambda _e, rr=row_widgets:
                       [self._validate_kod_and_autofill(rr), self._check_add_row()])
            elif h == "MEBLEG":
                w = ctk.CTkEntry(self.table_frame, state="readonly", width=pref_w)
            elif h == "ÖLÇÜ":
                w = ctk.CTkEntry(self.table_frame, width=pref_w)
                w.bind("<FocusOut>", lambda e: self._format_olcu(e.widget))
            else:
                w = ctk.CTkEntry(self.table_frame, width=pref_w)

            w._row_idx = row_idx
            w.grid(row=grid_r, column=c, sticky="nsew", padx=2, pady=2)
            w.bind("<FocusIn>", lambda _e, idx=row_idx: self._handle_focus_in(idx), add=True)
            row_widgets[h] = w

        if "SAY *" in row_widgets:
            row_widgets["SAY *"].bind("<FocusOut>", lambda _e, rr=row_widgets:
                                      [self._validate_say_and_stock(rr), self._calculate_totals()], add=True)
        if "ALIŞ ₼ *" in row_widgets:
            row_widgets["ALIŞ ₼ *"].bind("<FocusOut>", lambda e, rr=row_widgets:
                                         [self._format_price(e.widget, rr), self._price_guard(rr), self._calculate_totals()], add=True)
        if "SATIŞ ₼ *" in row_widgets:
            row_widgets["SATIŞ ₼ *"].bind("<FocusOut>", lambda e, rr=row_widgets:
                                          [self._format_price(e.widget, rr), self._price_guard(rr), self._calculate_totals()], add=True)

        self.table_rows.append(row_widgets)
        self._maybe_resize_window()
        self._check_add_row()

    def _last_row_has_kod(self): return bool(self.table_rows and self.table_rows[-1]["KOD *"].get().strip())
    def _check_add_row(self):
        if self._last_row_has_kod():
            self._add_row()

    def _calculate_totals(self):
        toplam = 0.0
        for row in self.table_rows:
            if not row["KOD *"].get().strip(): continue
            try:
                say = float(row["SAY *"].get().replace(",", "."))
                fiyat = float((row["ALIŞ ₼ *"].get() if self.is_alis else row["SATIŞ ₼ *"].get()).replace(",", "."))
                meb = say * fiyat
                row["MEBLEG"].configure(state="normal")
                row["MEBLEG"].delete(0, tk.END); row["MEBLEG"].insert(0, f"{meb:.2f}")
                row["MEBLEG"].configure(state="readonly")
                toplam += meb
            except: pass
        self.toplam_label.configure(text=f"CƏMİ: {toplam:.2f}")

    def toggle_mode(self):
        """ALlŞ ↔ SATlŞ keçidi — düymə stili temadan gəlsin, nömrə/cədvəl yenilənsin."""
        from ui_theme import button_style
        self.is_alis = not self.is_alis

        # Mod düyməsi mətn + rəng (ui_theme.button_style)
        self.mode_button.configure(
            text="ALlŞ" if self.is_alis else "SATlŞ",
            **button_style("success" if self.is_alis else "primary")
        )

        # Faktura nömrəsini yenilə
        try:
            self.faktura_no_entry.configure(state="normal")
            self.faktura_no_entry.delete(0, tk.END)
            self.faktura_no_entry.insert(0, self._generate_invoice_no())
            self.faktura_no_entry.configure(state="readonly")
        except Exception:
            pass

        # Cədvəl sütun dəstini yenidən qur (ALlŞ/SATlŞ fərqli sütunlar)
        try:
            self._setup_table()
        except Exception:
            pass

    # ---------------- başlıq yoxlaması ----------------
    def _validate_header(self):
        ok = True
        if not self.musteri_entry.get().strip():
            self._show_tip(self.musteri_entry, "Müştəri adı vacibdir."); ok = False
        if not self.tarix_entry.get().strip():
            self._show_tip(self.tarix_entry, "Tarix vacibdir."); ok = False
        return ok

    # ---------------- yadda saxla / pdf ----------------
    def _generate_invoice_no(self):
        prefix = "AL" if self.is_alis else "SA"; today = datetime.now().strftime("%Y%m%d")
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM fakturalar WHERE faktura_no LIKE ?", (f"{prefix}-{today}%",))
                count = c.fetchone()[0] + 1
                return f"{prefix}-{today}-{count:03d}"
        except:
            return f"{prefix}-{today}-001"

    def _validate_inputs(self):
        for i, row in enumerate(self.table_rows, start=1):
            if not self._row_has_any_input(row): continue
            miss = self._first_missing_required(row)
            if miss:
                self._show_tip(miss, f"{i}. sətr: KOD, SAY və QİYMƏT vacibdir.")
                return False
            k = row["KOD *"].get().strip().upper()
            if not KOD_REGEX.match(k):
                self._show_tip(row["KOD *"], f"{i}. sətr: Kod formatı səhvdir (məs: A001, AB01).")
                logger.warning("Yanlış KOD formatı %d-ci sətrdə: %s", i, k)
                return False
        return True

    def _safe_float(self, s, default=None):
        try: return float(str(s).replace(",", "."))
        except: return default

    def _safe_int(self, s, default=None):
        try: return int(float(str(s).replace(",", ".")))
        except: return default

    def _go_mainmenu(self):
        """Əsas Menyu-nu yeni prosesdə aç və bu pəncərəni bağla (tək pəncərə axını)."""
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

    @log_call()
    def yadda_saxla(self, silent: bool = False, clear: bool = True):
        if not self._validate_header(): return
        if not self._validate_inputs(): return
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                c = conn.cursor()
                musteri = self.musteri_entry.get().strip()
                tel_digits = self._phone_digits()
                tel_db = f"{self.phone_prefix}{tel_digits}" if tel_digits else None
                if tel_digits and len(tel_digits) != 9:
                    self._show_tip(self.telefon_entry, "Telefon 9 rəqəm olmalıdır, yenə də yadda saxlanılır.")

                c.execute("""INSERT INTO musteriler (ad, telefon)
                             VALUES (?,?)
                             ON CONFLICT(ad) DO UPDATE SET telefon=excluded.telefon""",
                          (musteri, tel_db))
                mid = c.execute("SELECT id FROM musteriler WHERE ad=?", (musteri,)).fetchone()[0]

                c.execute("""INSERT INTO fakturalar (faktura_no, tarix, musteri_id, tur)
                             VALUES (?,?,?,?)""",
                          (self.faktura_no_entry.get(), self.tarix_entry.get(), mid,
                           "alis" if self.is_alis else "satis"))
                fid = c.lastrowid

                price_h = self._price_header()
                for row in self.table_rows:
                    if not self._row_has_any_input(row): continue
                    kod = row["KOD *"].get().strip().upper()
                    say_txt = row["SAY *"].get().strip()
                    fiyat_txt = row[price_h].get().strip()
                    if not (kod and say_txt and fiyat_txt): continue

                    ad   = (row["AD"].get().strip() or kod)
                    olcu = row["ÖLÇÜ"].get().strip()
                    cins = row["CİNS"].get().strip()
                    say  = self._safe_int(say_txt, 0)
                    alis = self._safe_float(row.get("ALIŞ ₼ *").get()) if self.is_alis and "ALIŞ ₼ *" in row else None
                    satis= self._safe_float(row.get("SATIŞ ₼ *").get()) if "SATIŞ ₼ *" in row else None
                    meb  = self._safe_float(row["MEBLEG"].get(), 0.0)

                    c.execute("""INSERT INTO faktura_detal
                                 (faktura_id, mehsul_kod, mehsul_cins, say, alis_qiymet, satis_qiymet, mebleg)
                                 VALUES (?,?,?,?,?,?,?)""",
                              (fid, kod, cins, say, alis, satis, meb))

                    stok_deg = say if self.is_alis else -say
                    c.execute("""INSERT INTO mehsullar (kod, cins, ad, olcu, stok, alis_qiymet, satis_qiymet)
                                 VALUES (?,?,?,?,?,?,?)
                                 ON CONFLICT(kod,cins) DO UPDATE SET
                                   ad=excluded.ad,
                                   olcu=excluded.olcu,
                                   stok=mehsullar.stok + excluded.stok,
                                   alis_qiymet=COALESCE(excluded.alis_qiymet, mehsullar.alis_qiymet),
                                   satis_qiymet=COALESCE(excluded.satis_qiymet, mehsullar.satis_qiymet)
                               """,
                              (kod, cins, ad, olcu, stok_deg,
                               alis if self.is_alis else None, satis))

                toplam = self._safe_float(self.toplam_label.cget("text").replace("CƏMİ: ", ""), 0.0)
                if self._fakturalar_has_toplam(conn):
                    c.execute("UPDATE fakturalar SET toplam=? WHERE id=?", (toplam, fid))
                conn.commit()

                if not silent:
                    messagebox.showinfo("Uğurlu", "Faktura yadda saxlanıldı.")
                    logger.info("Faktura uğurla yadda saxlanıldı.")
                if clear:
                    self.temizle()
                return True

        except sqlite3.IntegrityError as e:
            messagebox.showerror("Xəta", f"SQL (unikal) xətası: {e}")
            return False
        except Exception as e:
            messagebox.showerror("Xəta", str(e))
            logger.error(f"Faktura yadda saxla xətası: {e}")
            return False

    def temizle(self):
        self._hide_tip()
        self.musteri_entry.delete(0, tk.END)
        self.telefon_entry.delete(0, tk.END)
        self.faktura_no_entry.configure(state="normal")
        self.faktura_no_entry.delete(0, tk.END)
        self.faktura_no_entry.insert(0, self._generate_invoice_no())
        self.faktura_no_entry.configure(state="readonly")
        self.tarix_entry.delete(0, tk.END)
        self.tarix_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self._setup_table()
        self.toplam_label.configure(text="CƏMİ: 0.00")

    def _create_bottom_buttons(self, parent):
        """Aşağı düymə paneli — bütün düymələr ui_theme.button_style ilə temaya bağlıdır."""
        from ui_theme import button_style

        # SOL: TƏMİZLƏ, ANA MENYU
        ctk.CTkButton(
            parent, text="TƏMİZLƏ",
            **button_style("warning", size="lg"),
            width=120,
            command=self.temizle
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            parent, text="ƏSAS MENYU",
            **button_style("accent", size="lg"),
            width=110,
            command=self._go_mainmenu
        ).pack(side="left", padx=5)

        # SAĞ: YADDA SAXLA, ÇAP ET (PDF)
        ctk.CTkButton(
            parent, text="YADDA SAXLA",
            **button_style("primary", size="lg"),
            width=150,
            command=self.yadda_saxla
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            parent, text="ÇAP ET (PDF)",
            **button_style("success", size="lg"),
            command=self.cap_et
        ).pack(side="right", padx=5)

    # ---------------- PDF ixrac ----------------
    def _save_and_open_invoice_pdf(self, pdf, fakt_no: str):
        """
        FPDF `pdf` sənədini ayarlardakı Faktura qovluğuna saxlayır və açır/çap edir.
        Yeni düzəndə ui_theme.invoice_pdf_path istifadə olunur; yoxdursa köhnə pdf_path_for_invoice-a,
        o da yoxdursa işçi qovluğa yazılır.
        """
        import os
        from tkinter import messagebox
        logger.info("Faktura PDF saxlanılır...")

        # 1) Hədəf fayl yolu
        out = None
        try:
            from ui_theme import invoice_pdf_path, load_app_settings
            out = invoice_pdf_path(fakt_no, load_app_settings())
        except Exception:
            try:
                # geriyə uyğunluq (köhnə ad)
                from ui_theme import pdf_path_for_invoice, load_app_settings
                out = pdf_path_for_invoice(fakt_no, load_app_settings())
            except Exception:
                out = os.path.join(os.getcwd(), f"{fakt_no}.pdf")

        # 2) Saxla
        try:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            pdf.output(out)
        except Exception as e:
            messagebox.showerror("Xəta", f"PDF saxlanma xətası:\n{e}")
            logger.error(f"PDF save error: {e}")
            return

        # 3) Aç / Çap et (Windows-da əsas printer real printerdirsə əvvəlcə çap)
        printed_or_opened = False
        try:
            if os.name == "nt":
                try:
                    import importlib
                    w = importlib.import_module("win32print")
                    name = str(w.GetDefaultPrinter() or "")
                    if name and not any(x in name.lower() for x in ("pdf", "xps", "onenote", "fax")):
                        try:
                            os.startfile(out, "print")
                            printed_or_opened = True
                        except Exception:
                            printed_or_opened = False
                except Exception:
                    pass
                if not printed_or_opened:
                    os.startfile(out)
                    printed_or_opened = True
            else:
                import subprocess
                subprocess.Popen(["xdg-open", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                printed_or_opened = True
        except Exception:
            pass

        # 4) Məlumatlandır
        messagebox.showinfo(
            "Məlumat",
            f"PDF saxlanıldı:\n{out}\n" + ("Çap üçün göndərildi." if printed_or_opened else "Baxış üçün açıldı.")
        )
        logger.info("PDF uğurla açıldı/çap olundu.")

    def cap_et(self):
        """DB-ə qeyd et + PDF yarat + (mümkünsə) aç/çap et."""
        logger.info("ÇAP ET: %s", self.faktura_no_entry.get())
        # 1) Form yoxlamaları
        if not self._validate_header(): return
        if not self._validate_inputs(): return

        # 2) Əvvəlcə DB-ə qeyd et (səssiz, formu təmizləmə)
        ok = self.yadda_saxla(silent=True, clear=False)
        if not ok:
            return

        # 3) PDF kitabxanası
        try:
            from fpdf import FPDF
        except Exception:
            messagebox.showerror("Xəta", "PDF üçün 'fpdf2' lazımdır:\n  pip install fpdf2")
            logger.error("PDF kitabxanası import xətası.")
            return
        logger.info("PDF kitabxanası uğurla import olundu.")

        # 4) Ayarlar (istəyə bağlı: hazırda yalnız şrift üçün oxuyuruq)
        try:
            from ui_theme import load_app_settings
            cfg = getattr(self, "settings", None) or load_app_settings()

        except Exception:
            cfg = None

        # 5) DejaVu (varsa) / Helvetica (əvəzedici)
        import os
        base_dir = os.path.dirname(__file__)
        dj  = os.path.join(base_dir, "DejaVuSansCondensed.ttf")
        djb = os.path.join(base_dir, "DejaVuSansCondensed-Bold.ttf")
        use_dejavu = os.path.exists(dj) and os.path.exists(djb)

        pdf = FPDF()
        pdf.add_page()

        if use_dejavu:
            pdf.add_font('DejaVu','',  dj,  uni=True)
            pdf.add_font('DejaVuB','', djb, uni=True)
            header_font       = ('DejaVu','',14)
            text_font         = ('DejaVu','',11)
            cell_font         = ('DejaVu','',10)
            table_header_font = ('DejaVuB','',10)   # sütun başlıqları
            total_bold_font   = ('DejaVuB','',11)   # cəmi etiketi
            bold_font         = ('DejaVuB','',12)
        else:
            header_font       = ('Helvetica','',14)
            text_font         = ('Helvetica','',11)
            cell_font         = ('Helvetica','',10)
            table_header_font = ('Helvetica','B',10)
            total_bold_font   = ('Helvetica','B',11)
            bold_font         = ('Helvetica','B',12)

        # 6) Başlıq
        pdf.set_font(*header_font)
        pdf.cell(0, 10, f"{'ALlŞ' if self.is_alis else 'SATlŞ'} FAKTURASI", ln=1, align="C")

        fakt_no = (self.faktura_no_entry.get() or "").strip()
        tel_raw = self.telefon_entry.get().strip()
        tel_txt = f"{self.phone_prefix}{self._phone_digits()}" if tel_raw else ""
        musteri = self.musteri_entry.get() or "ÜMUMİ"
        tarih   = self.tarix_entry.get()

        # İki sütunlu başlıq: sol=55%, sağ=45%
        avail_w = pdf.w - pdf.l_margin - pdf.r_margin
        left_w  = avail_w * 0.55
        right_w = avail_w - left_w

        # Sətir 1: № — Telefon
        pdf.set_font(*bold_font)
        pdf.cell(left_w,  8, f"№: {fakt_no}", border=0, align="L")
        pdf.set_font(*text_font)
        pdf.cell(right_w, 8, f"Telefon: {tel_txt}" if tel_txt else "", border=0, ln=1, align="R")

        # Sətir 2: Müştəri — Tarix
        pdf.set_font(*text_font)
        pdf.cell(left_w,  8, f"Müştəri: {musteri}", border=0, align="L")
        pdf.cell(right_w, 8, f"Tarix: {tarih}",     border=0, ln=1, align="R")

        pdf.ln(4)

        # 7) Cədvəl sütunları
        headers = ["KOD *","AD *","ÖLÇÜ","CİNS","SAY *"]
        if self.is_alis:
            headers += ["ALIŞ ₼ *","SATIŞ ₼ *","MƏBLƏĞ"]
        else:
            headers += ["SATIŞ ₼ *","MƏBLƏĞ"]

        # Genişlik çəkiləri (daha oxunaqlı cədvəl)
        weights_map = {
            "KOD *": 1.2, "AD *": 3.2, "ÖLÇÜ": 0.9, "CİNS": 1.0, "SAY *": 0.9,
            "ALIŞ ₼ *": 1.2, "SATIŞ ₼ *": 1.2, "MƏBLƏĞ": 1.4
        }
        weights = [weights_map.get(h, 1) for h in headers]
        total_w = sum(weights) or 1
        col_ws  = [avail_w * w / total_w for w in weights]

        # 8) Sütun başlıqları (qalın)
        pdf.set_font(*table_header_font)
        for h, w in zip(headers, col_ws):
            pdf.cell(w, 8, h.replace(" ₼ *","").replace("*","").strip(), 1, align="C")
        pdf.ln()

        # 9) Sətirlər
        pdf.set_font(*cell_font)
        for row in self.table_rows:
            if not self._row_has_any_input(row):
                continue
            kod   = row["KOD *"].get().strip()
            ad    = row["AD *"].get().strip()
            olcu  = row["ÖLÇÜ"].get().strip()
            cins  = row["CİNS"].get().strip()
            say   = row["SAY *"].get().strip()
            alis  = row.get("ALIŞ ₼ *")
            satis = row.get("SATIŞ ₼ *")
            alis_v  = (alis.get().strip()  if (alis and self.is_alis) else "")
            satis_v = (satis.get().strip() if satis else "")
            mebleg_e = (row.get("MƏBLƏĞ") or row.get("MEBLEG"))
            mebleg = mebleg_e.get().strip() if mebleg_e else ""

            cells = [kod, ad, olcu, cins, say]
            if self.is_alis:
                cells += [alis_v, satis_v, mebleg]
            else:
                cells += [satis_v, mebleg]

            for c, w in zip(cells, col_ws):
                pdf.cell(w, 8, str(c), 1)
            pdf.ln()

        # 10) Cəmi (qalın)
        toplam_txt = self.toplam_label.cget("text").replace("CƏMİ: ", "")
        pdf.set_font(*total_bold_font)
        if len(col_ws) >= 2:
            pdf.cell(sum(col_ws[:-1]), 8, "CƏMİ", 1, align="R")
            pdf.cell(col_ws[-1],       8, toplam_txt, 1, align="R")
        else:
            pdf.cell(0, 8, f"CƏMİ: {toplam_txt}", 1, align="R")

        # 11) Saxla + aç/çap et
        self._save_and_open_invoice_pdf(pdf, fakt_no)

if __name__ == "__main__":
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    app = FakturaForm(force_mode=arg)   # force_mode = "satis" və ya "alis"
    app.mainloop()

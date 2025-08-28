# hesab.py — Giriş / Qeydiyyat (referans kodlu) / Hesab (şifrə dəyiş, çıxış)
import os, sys, re
import customtkinter as ctk
from tkinter import messagebox
from ui_theme import (
    APP_TITLE, APPEARANCE_MODE, COLOR_THEME,
    FONT_H1, FONT_BOLD, FONT_NORMAL,
    COLOR_PRIMARY, COLOR_PRIMARY_HOVER, COLOR_SUCCESS, COLOR_BG_SOFT,
    enable_windows_chrome,
    load_app_settings,
    ensure_auth_tables, create_user, get_user, verify_password,
    start_session, end_session, get_active_session, user_count,
    hash_password, _conn, button_style, logger, log_call
)

USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,32}$")
NAME_RE     = re.compile(r"^[A-Za-zÇĞİÖŞÜçğıöşü\s'\-]{2,}$")

def valid_password(p: str) -> bool:
    if len(p) < 6: return False
    if not re.search(r"[A-Z]", p): return False
    if not re.search(r"[a-z]", p): return False
    if not re.search(r"\d",   p): return False
    return True

class HesabPenceresi(ctk.CTk):
    def __init__(self, mode: str = "login"):
        super().__init__()
        try: ctk.set_appearance_mode(APPEARANCE_MODE); ctk.set_default_color_theme(COLOR_THEME)
        except Exception: pass
        enable_windows_chrome(self)
        self.title(f"{APP_TITLE} — Hesab")
        self.geometry("560x640")
        self.minsize(560, 600)
        self.configure(fg_color=COLOR_BG_SOFT)

        logger.info("HesabPenceresi initialized.")

        # Pəncərə bağlanma hadisəsini tut
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # ESC düyməsi ilə çıxış
        self.bind("<Escape>", lambda e: self._on_close())
        
        ensure_auth_tables()
        self.cfg = load_app_settings()
        self.active = get_active_session()   # (username, expires_at) | None
        self._lock_register = bool(self.active)  # sessiya açıqsa qeydiyyat kilidli

        self._build_ui(mode)

    def _build_ui(self, mode: str):
        wrap = ctk.CTkFrame(self, corner_radius=12); wrap.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(wrap, text="🔐 Hesab / Giriş", font=FONT_H1).pack(anchor="w", padx=12, pady=(12, 8))

        self.tabs = ctk.CTkTabview(
            wrap,
            segmented_button_selected_color=COLOR_PRIMARY,
            segmented_button_selected_hover_color=COLOR_PRIMARY_HOVER
        )
        self.tabs.pack(fill="both", expand=True, padx=12, pady=8)

        t_login = self.tabs.add("Giriş")
        t_reg   = self.tabs.add("Qeydiyyat")
        t_acc   = self.tabs.add("Hesab")

        # === GİRİŞ ===
        self.v_user = ctk.StringVar()
        self.v_pass = ctk.StringVar()

        fr = ctk.CTkFrame(t_login, fg_color="transparent"); fr.pack(fill="x", padx=6, pady=8)
        ctk.CTkLabel(fr, text="İstifadəçi adı", font=FONT_BOLD).pack(anchor="w", pady=(6,2))
        self.e_login_user = ctk.CTkEntry(fr, textvariable=self.v_user, font=FONT_NORMAL); self.e_login_user.pack(fill="x")

        ctk.CTkLabel(fr, text="Şifrə", font=FONT_BOLD).pack(anchor="w", pady=(10,2))
        self.e_login_pass = ctk.CTkEntry(fr, textvariable=self.v_pass, show="●", font=FONT_NORMAL); self.e_login_pass.pack(fill="x")

        self.btn_login = ctk.CTkButton(
            fr, text="Daxil ol",
            **button_style("primary", size="lg"),
            command=self._do_login
        )
        self.btn_login.pack(fill="x", pady=(14,6))
        self.btn_forgot = ctk.CTkButton(
            fr, text="Şifrəmi Unutdum",
            **button_style("info"),
            command=self.open_recover_password   
        )
        self.btn_forgot.pack(anchor="w")

        # === QEYDİYYAT ===
        self.rv_user = ctk.StringVar(); self.rv_name = ctk.StringVar(); self.rv_surn = ctk.StringVar()
        self.rv_p1   = ctk.StringVar(); self.rv_p2   = ctk.StringVar(); self.rv_ref  = ctk.StringVar()

        fr2 = ctk.CTkFrame(t_reg, fg_color="transparent"); fr2.pack(fill="x", padx=2, pady=4)

        info_txt = "Qeydiyyat üçün əvvəlcə çıxış edin." if self.active else "Zəhmət olmasa formu doldurun."
        ctk.CTkLabel(fr2, text=info_txt, font=FONT_NORMAL, text_color="#64748b").pack(anchor="w", pady=(0,6))

        ctk.CTkLabel(fr2, text="İstifadəçi adı", font=FONT_BOLD).pack(anchor="w", pady=(6,2))
        self.e_reg_user = ctk.CTkEntry(fr2, textvariable=self.rv_user, font=FONT_NORMAL); self.e_reg_user.pack(fill="x")

        ctk.CTkLabel(fr2, text="Ad", font=FONT_BOLD).pack(anchor="w", pady=(6,2))
        self.e_reg_name = ctk.CTkEntry(fr2, textvariable=self.rv_name, font=FONT_NORMAL); self.e_reg_name.pack(fill="x")

        ctk.CTkLabel(fr2, text="Soyad", font=FONT_BOLD).pack(anchor="w", pady=(6,2))
        self.e_reg_surn = ctk.CTkEntry(fr2, textvariable=self.rv_surn, font=FONT_NORMAL); self.e_reg_surn.pack(fill="x")

        ctk.CTkLabel(fr2, text="Şifrə", font=FONT_BOLD).pack(anchor="w", pady=(6,2))
        self.e_reg_p1 = ctk.CTkEntry(fr2, textvariable=self.rv_p1, show="●", font=FONT_NORMAL); self.e_reg_p1.pack(fill="x")

        ctk.CTkLabel(fr2, text="Şifrə (təkrar)", font=FONT_BOLD).pack(anchor="w", pady=(6,2))
        self.e_reg_p2 = ctk.CTkEntry(fr2, textvariable=self.rv_p2, show="●", font=FONT_NORMAL); self.e_reg_p2.pack(fill="x")

        ctk.CTkLabel(fr2, text="Referans Kodu", font=FONT_BOLD).pack(anchor="w", pady=(6,2))
        self.e_reg_ref = ctk.CTkEntry(fr2, textvariable=self.rv_ref, font=FONT_NORMAL); self.e_reg_ref.pack(fill="x")

        self.btn_register = ctk.CTkButton(
            fr2, text="Qeydiyyatdan keç",
            **button_style("success", size="lg"),
            command=self._do_register
        )
        self.btn_register.pack(fill="x", pady=(14,6))

        # === HESAB ===
        acc = ctk.CTkFrame(t_acc, fg_color="transparent"); acc.pack(fill="both", expand=True, padx=6, pady=8)
        self.lbl_active = ctk.CTkLabel(acc, text="", font=FONT_NORMAL); self.lbl_active.pack(anchor="w", pady=(6,8))

        self.btn_pwchange = ctk.CTkButton(acc, text="Şifrəni dəyiş",
                                  **button_style("info", size="lg"),
                                  command=self._change_password_dialog)
        self.btn_pwchange.pack(anchor="w", pady=(0,6))

        self.btn_logout = ctk.CTkButton(acc, text="Sessiyanı bağla",
                                        **button_style("danger", size="lg"),
                                        command=self._logout)
        self.btn_logout.pack(anchor="w")


        # Alt bar: Əsas Menyu
        bar = ctk.CTkFrame(wrap, fg_color="transparent"); bar.pack(fill="x", padx=6, pady=(8, 4))
        ctk.CTkButton(bar, text="ƏSAS MENYU",
                    **button_style("accent", size="lg"),
                    command=lambda: self.show_main(close_self=True)).pack(side="right")

        # Tab seçimi məntiqi
        if mode == "account" and self.active:
            self.tabs.set("Hesab")
        elif user_count() == 0:
            self.tabs.set("Qeydiyyat")
        else:
            self.tabs.set("Giriş")

        # Etiketləri/hesab qutusunu və kilidi tətbiq et
        self._refresh_account_box()
        self._apply_auth_locks()

    # ---- Əməliyyatlar ----

    def _apply_auth_locks(self):
        """Sessiya açıqsa Giriş və Qeydiyyat formalarını passiv et; bağlıysa aktiv et.
        Həmçinin Hesab tabında 'Şifrəni dəyiş' və 'Sessiyanı bağla' düymələri:
        sessiya yoxdursa PASSİV."""
        logger.info("Applying auth locks...")
        locked = bool(self.active)

        # GİRİŞ
        for w in (getattr(self, "e_login_user", None),
                getattr(self, "e_login_pass", None),
                getattr(self, "btn_login", None),
                getattr(self, "btn_forgot", None)):
            try:
                if w: w.configure(state=("disabled" if locked else "normal"))
            except Exception:
                pass

        # QEYDİYYAT
        for w in (getattr(self, "e_reg_user", None),
                getattr(self, "e_reg_name", None),
                getattr(self, "e_reg_surn", None),
                getattr(self, "e_reg_p1", None),
                getattr(self, "e_reg_p2", None),
                getattr(self, "e_reg_ref", None),
                getattr(self, "btn_register", None)):
            try:
                if w: w.configure(state=("disabled" if locked else "normal"))
            except Exception:
                pass

        # HESAB TAB — sessiya yoxdursa şifrəni dəyiş / çıxış PASSİV
        for w in (getattr(self, "btn_pwchange", None),
                getattr(self, "btn_logout", None)):
            try:
                if w: w.configure(state=("normal" if locked else "disabled"))
            except Exception:
                pass

    def _clear_session_persisted(self):
        """
        Aktiv sessiyanı daimi saxlanmadan sil:
        - ui_theme.end_session() → sessions cədvəlini sıfırlayır (ƏSAS MƏNBƏ)
        - ayar faylındakı 'active_user' sahəsini boşaldır
        - mühit dəyişənini təmizləyir
        """
        logger.info("Clearing session data...")
        cleared = False

        # --- Əsas təmizləmə: sessions cədvəli ---
        try:
            end_session()           # ui_theme-dən; Əsas Menyu gözətçisi bunu oxuyur
            cleared = True
        except Exception:
            pass

        # --- Ayar faylı (ui_theme settings) ---
        try:
            from ui_theme import load_app_settings, save_app_settings
            cfg = load_app_settings()
            if cfg.get("active_user"):
                cfg["active_user"] = ""
                save_app_settings(cfg)
                cleared = True
        except Exception:
            pass

        # --- Mühit dəyişəni (informativ) ---
        logger.info("Clearing environment variables...")
        try:
            import os as _os
            _os.environ.pop("AVANQARD_ACTIVE_USER", None)
        except Exception:
            pass

        return cleared

    def _do_login(self):
        """Daxil ol: istifadəçi yoxdur / şifrə səhv mesajları və düzgün yoxlama."""
        logger.info("Attempting login...")
        from tkinter import messagebox

        u = (self.v_user.get() or "").strip().lower()
        p = self.v_pass.get() or ""

        if not u or not p:
            messagebox.showwarning("Xəbərdarlıq", "İstifadəçi adı və şifrə tələb olunur.", parent=self)
            logger.warning("Login attempt failed: missing username or password.")
            return

        # Qeyd oxu (tuple/dict ola bilər)
        try:
            rec = get_user(u)
        except Exception:
            rec = None

        if not rec:
            messagebox.showerror("Xəta", "İstifadəçi adı tapılmadı.", parent=self)
            logger.error("Login attempt failed: user not found.")
            return

        # Şifrə hash-i təhlükəsiz götür
        pwd_hash = None
        try:
            pwd_hash = rec[3]  # (id, username, full_name, password, ...)
        except Exception:
            try:
                pwd_hash = rec.get("password")
            except Exception:
                pwd_hash = None

        if not pwd_hash:
            messagebox.showerror("Xəta", "İstifadəçi qeydində şifrə sahəsi yoxdur (sxem fərqi).", parent=self)
            logger.error("Login attempt failed: password field missing in user record.")
            return

        # Şifrəni yoxla

        ok_pw = False
        try:
            ok_pw = verify_password(p, pwd_hash)
        except Exception:
            ok_pw = False

        if not ok_pw:
            messagebox.showerror("Xəta", "Şifrə səhvdir.", parent=self)
            logger.error("Login attempt failed: incorrect password.")
            return

        # Uğurlu giriş → sessiyanı daimi yaz (DB + settings + env)
        try:            
            self._persist_session(u)   # içində start_session(...) çağırışı var
            logger.info("Session persisted successfully.")
        except Exception as e:
            logger.error("Session persistence failed: %s", e)

        self.active = u
        self._lock_register = True

        # UI yenilə
        try: self._refresh_account_box()
        except: pass
        try:
            self._apply_auth_locks()
            self.after(0, self._apply_auth_locks)
        except: pass

        # Mesaj + Əsas Menyu
        try:
            messagebox.showinfo("Məlumat", "Giriş uğurludur. Əsas Menyu açılır…", parent=self)
            logger.info("Opening main menu...")
        except Exception as e:
            logger.error("Əsas Menyu açma xətası: %s", e)

        try: self.v_pass.set("")
        except Exception: pass

        # İKİNCİ MENYUYA MANE OL: varsa qabağa gətir, yoxdursa aç; sonra Hesabı bağla
        self.show_main(close_self=True)

    def _build_recover_password_window(self):
        logger.info("Building recover password window...")
        from tkinter import messagebox
        win = ctk.CTkToplevel(self)
        self._recover_win = win
        try: enable_windows_chrome(win)
        except Exception: pass
        win.title("Şifrəni Bərpa Et")
        win.geometry("420x360")
        win.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, "_recover_win", None), win.destroy()))

        # Sahələr (referans kodu AVTOMATİK DOLMUR!)
        v_user = ctk.StringVar(value=(self.v_user.get() or ""))
        v_ref  = ctk.StringVar()       # ← boş
        v_p1   = ctk.StringVar()
        v_p2   = ctk.StringVar()

        frm = ctk.CTkFrame(win, fg_color="transparent"); frm.pack(fill="both", expand=True, padx=14, pady=12)

        ctk.CTkLabel(frm, text="İstifadəçi adı", font=FONT_BOLD).pack(anchor="w", pady=(0,2))
        e_user = ctk.CTkEntry(frm, textvariable=v_user, font=FONT_NORMAL, placeholder_text="istifadəçi adı")
        e_user.pack(fill="x")

        ctk.CTkLabel(frm, text="Referans kodu", font=FONT_BOLD).pack(anchor="w", pady=(10,2))
        e_ref = ctk.CTkEntry(frm, textvariable=v_ref, font=FONT_NORMAL, placeholder_text="məs. AVQ-2025")
        e_ref.pack(fill="x")

        ctk.CTkLabel(frm, text="Yeni şifrə", font=FONT_BOLD).pack(anchor="w", pady=(10,2))
        e_p1 = ctk.CTkEntry(frm, textvariable=v_p1, show="●", font=FONT_NORMAL); e_p1.pack(fill="x")

        ctk.CTkLabel(frm, text="Yeni şifrə (təkrar)", font=FONT_BOLD).pack(anchor="w", pady=(10,2))
        e_p2 = ctk.CTkEntry(frm, textvariable=v_p2, show="●", font=FONT_NORMAL); e_p2.pack(fill="x")

        # Doğrulayıcılar (qeydiyyat qaydaları ilə uyğun)
        def _valid_username(u: str) -> bool:
            return bool(USERNAME_RE.fullmatch(u))

        def _valid_password(p: str) -> bool:
            try:
                from ui_theme import valid_password
                return valid_password(p)
            except Exception:
                import re
                return len(p) >= 6 and re.search(r"[A-Z]", p) and re.search(r"[a-z]", p) and re.search(r"\d", p)

        # Yadda saxla
        def _save():
            u   = (v_user.get() or "").strip().lower()
            ref = (v_ref.get()  or "").strip()
            p1  = v_p1.get() or ""
            p2  = v_p2.get() or ""

            if not u or not ref or not p1 or not p2:
                messagebox.showwarning("Xəbərdarlıq", "Bütün sahələri doldurun.", parent=win); return
                logger.warning("Password recovery failed: all fields are required.")
            if not _valid_username(u):
                messagebox.showwarning("Xəbərdarlıq", "Düzgün istifadəçi adı daxil edin (3–32; hərf/rəqəm/._-).", parent=win); return
            if p1 != p2:
                messagebox.showwarning("Xəbərdarlıq", "Şifrələr uyğun deyil.", parent=win); return
            if not _valid_password(p1):
                messagebox.showwarning("Xəbərdarlıq", "Şifrə ən azı 6 simvol; ən azı 1 böyük, 1 kiçik hərf və 1 rəqəm olmalıdır.", parent=win); return

            # Referans kodunu AYARLARDAN oxu və tam uyğunluq yoxla
            try:
                from ui_theme import load_app_settings
                expected = str(load_app_settings().get("invite_code", "AVQ-2025"))
            except Exception:
                expected = "AVQ-2025"
            if ref.strip() != expected.strip():
                messagebox.showerror("Xəta", "Referans kodu səhvdir.", parent=win); return
            logger.info("Referans kodu təsdiqləndi.")

            # İstifadəçi var?
            try:
                rec = get_user(u)
            except Exception:
                rec = None
            if not rec:
                messagebox.showerror("Xəta", "İstifadəçi adı tapılmadı.", parent=win)
                logger.error("Password recovery failed: user not found.")
                return

            # Şifrəni yenilə
            try:
                from ui_theme import _conn, hash_password
                with _conn() as conn:
                    cur = conn.cursor()
                    newhash = hash_password(p1)
                    cur.execute("UPDATE users SET password=? WHERE username=?", (newhash, u))
                    if cur.rowcount == 0:  # sxem fərqi üçün fallback
                        cur.execute("UPDATE users SET password_hash=? WHERE username=?", (newhash, u))
                    conn.commit()
            except Exception as e:
                logger.error("Password recovery failed: %s", e)
                messagebox.showerror("Xəta", f"Yenilənmədi:\n{e}", parent=win); return

            logger.info("Password for user '%s' has been reset.", u)
            messagebox.showinfo("Məlumat", "Şifrə sıfırlandı. İndi daxil ola bilərsiniz.", parent=win)
            try:
                self.tabs.set("Giriş"); self.v_user.set(u); self.v_pass.set(""); self.e_login_user.focus_set()
            except Exception:
                pass
            setattr(self, "_recover_win", None)
            win.destroy()

        # Düymələr
        btnbar = ctk.CTkFrame(frm, fg_color="transparent"); btnbar.pack(fill="x", pady=(12,0))
        ctk.CTkButton(btnbar, text="İmtina", **button_style("accent"),
                    command=lambda: (setattr(self, "_recover_win", None), win.destroy())).pack(side="right", padx=(6,0))
        ctk.CTkButton(btnbar, text="Bərpa et", **button_style("primary"), command=_save).pack(side="right")

        # Enter ilə yadda saxla, ilk fokus
        for w in (e_user, e_ref, e_p1, e_p2):
            w.bind("<Return>", lambda _e: _save())
        try:
            (e_user if not v_user.get() else e_ref).focus_set()
        except Exception:
            pass

    
    def open_recover_password(self):
        """Şifrəni Bərpa Et pəncərəsi: açıqsa qabağa gətir, yoxdursa yarat."""
        logger.info("Opening password recovery window...")
        # Əvvəl açılıbsa — göstər & fokus et
        if getattr(self, "_recover_win", None) and self._recover_win.winfo_exists():
            try:
                self._recover_win.deiconify()
                self._recover_win.lift()
                self._recover_win.focus_force()
            except Exception:
                pass
            return
        # Yoxdursa yarat
        logger.info("Building recover password window...")
        self._build_recover_password_window()

    def _do_register(self):
        if self._lock_register:
            logger.warning("Registration attempt failed: user is logged in.")
            messagebox.showwarning("Xəbərdarlıq", "Aktiv sessiya zamanı qeydiyyatdan keçə bilməzsiniz. Zəhmət olmasa çıxış edin.")
            return

        u = (self.rv_user.get() or "").strip().lower()
        n = (self.rv_name.get() or "").strip()
        s = (self.rv_surn.get() or "").strip()
        p1 = self.rv_p1.get() or ""
        p2 = self.rv_p2.get() or ""
        ref= (self.rv_ref.get() or "").strip()

        # Yoxlama
        if not USERNAME_RE.match(u):
            logger.warning("Registration attempt failed: invalid username.")
            messagebox.showwarning("Xəbərdarlıq",
                "İstifadəçi adı 3–32 simvol olmalıdır; yalnız kiçik hərf, rəqəm, nöqtə, alt xətt, tire.")
            return
        if not NAME_RE.match(n) or not NAME_RE.match(s):
            logger.warning("Registration attempt failed: invalid name or surname.")
            messagebox.showwarning("Xəbərdarlıq", "Ad/Soyad ən azı 2 hərf olmalıdır; yalnız hərf, boşluq, - və ' ola bilər.")
            return
        if p1 != p2:
            logger.warning("Registration attempt failed: passwords do not match.")
            messagebox.showwarning("Xəbərdarlıq", "Şifrələr uyğun deyil."); return
        if not valid_password(p1):
            logger.warning("Registration attempt failed: invalid password.")
            messagebox.showwarning("Xəbərdarlıq",
                "Şifrə ən azı 6 simvol olmalıdır; ən azı 1 böyük, 1 kiçik hərf və 1 rəqəm olmalıdır.")
            return
        if ref != str(self.cfg.get("invite_code","AVQ-2025")).strip():
            logger.warning("Registration attempt failed: invalid invite code.")
            messagebox.showerror("Xəta", "Referans kodu yanlışdır."); return

        full_name = f"{n} {s}".strip()
        ok = create_user(u, p1, full_name)
        if not ok:
            logger.error("Registration attempt failed: username already exists.")
            messagebox.showerror("Xəta", "Bu istifadəçi adı artıq mövcuddur."); return

        messagebox.showinfo("Məlumat", "Qeydiyyat tamamlandı. İndi daxil ola bilərsiniz.")
        logger.info("User '%s' registered successfully.", u)
        self.tabs.set("Giriş")
        self.v_user.set(u); self.v_pass.set("")

    def _change_password_dialog(self):
        sess = get_active_session()
        if not sess:
            logger.warning("Password change attempt failed: no active session.")
            messagebox.showwarning("Xəbərdarlıq", "Aktiv sessiya tapılmadı."); return
        username = sess[0]

        win = ctk.CTkToplevel(self); enable_windows_chrome(win)
        win.title("Şifrəni dəyiş"); win.geometry("360x260")
        ctk.CTkLabel(win, text=f"İstifadəçi: {username}", font=FONT_BOLD).pack(anchor="w", padx=12, pady=(12,6))
        v_old = ctk.StringVar(); v_new = ctk.StringVar(); v_rep = ctk.StringVar()
        ctk.CTkLabel(win, text="Cari şifrə", font=FONT_NORMAL).pack(anchor="w", padx=12)
        ctk.CTkEntry(win, textvariable=v_old, show="●").pack(fill="x", padx=12, pady=(0,6))
        ctk.CTkLabel(win, text="Yeni şifrə", font=FONT_NORMAL).pack(anchor="w", padx=12)
        ctk.CTkEntry(win, textvariable=v_new, show="●").pack(fill="x", padx=12, pady=(0,6))
        ctk.CTkLabel(win, text="Yeni şifrə (təkrar)", font=FONT_NORMAL).pack(anchor="w", padx=12)
        ctk.CTkEntry(win, textvariable=v_rep, show="●").pack(fill="x", padx=12, pady=(0,10))
        def _ok():
            rec = get_user(username)
            if not rec or not verify_password(v_old.get(), rec[3]):
                logger.error("Password change attempt failed: incorrect current password.")
                messagebox.showerror("Xəta", "Cari şifrə səhvdir."); return
            if v_new.get() != v_rep.get():
                logger.warning("Password change attempt failed: new passwords do not match.")
                messagebox.showwarning("Xəbərdarlıq", "Yeni şifrələr uyğun deyil."); return
            if not valid_password(v_new.get()):
                logger.warning("Password change attempt failed: invalid new password.")
                messagebox.showwarning("Xəbərdarlıq",
                    "Şifrə ən azı 6 simvol; ən azı 1 böyük, 1 kiçik hərf və 1 rəqəm olmalıdır.")
                return
            try:
                with _conn() as conn:
                    cur = conn.cursor()
                    cur.execute("UPDATE users SET password=? WHERE username=?",
                                (hash_password(v_new.get()), username))
                    conn.commit()
                logger.info("Password for user '%s' has been updated.", username)
                messagebox.showinfo("Məlumat", "Şifrə yeniləndi.")
                win.destroy()
            except Exception as e:
                logger.error("Password change attempt failed: %s", e)
                messagebox.showerror("Xəta", f"Yenilənmədi:\n{e}")
        ctk.CTkButton(win, text="Yadda saxla", fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
                      command=_ok).pack(side="right", padx=12, pady=12)

    def _logout(self):
        """Sessiyanı bağla: daimi sessiyanı sil, UI-ni dərhal 'Giriş' vəziyyətinə gətir."""
        logger.info("Logging out user...")
        from tkinter import messagebox

        # Artıq sessiya yoxdursa nəzakətlə məlumat ver və giriş formasını aç
        if not get_active_session():
            self.active = None
            self._lock_register = False
            self._refresh_account_box(); self._apply_auth_locks()
            self.tabs.set("Giriş")
            try: self.e_login_user.focus_set()
            except: pass
            logger.warning("Logout attempt failed: no active session.")
            messagebox.showinfo("Məlumat", "Artıq aktiv sessiya yoxdur.")
            return

        # 1) SESSİYANI HƏQİQƏTƏN BAĞLA (sessions cədvəli + ayarlar)
        try:
            logger.info("Closing user session...")
            self._clear_session_persisted()
        except Exception as e:
            logger.error("Session clear error: %s", e)
            print("Session clear error:", e)

        # 2) Lokal vəziyyəti sıfırla
        self.active = None
        self._lock_register = False

        for v in (getattr(self, "v_user", None),
                getattr(self, "v_pass", None),
                getattr(self, "rv_user", None),
                getattr(self, "rv_name", None),
                getattr(self, "rv_surn", None),
                getattr(self, "rv_p1", None),
                getattr(self, "rv_p2", None),
                getattr(self, "rv_ref", None)):
            try:
                if v is not None: v.set("")
            except Exception:
                pass

        # 3) UI-ni 'Giriş' moduna al
        try: self._refresh_account_box()
        except Exception: pass
        try:
            self._apply_auth_locks()
            self.after(0, self._apply_auth_locks)
        except Exception: pass

        try: self.tabs.set("Giriş")
        except Exception: pass
        try: self.e_login_user.focus_set()
        except Exception: pass

        # 4) Məlumat ver — Əsas Menyu gözətçisi 1 san. ərzində sessiyanın bağlandığını görüb menyunu kilidləyəcək
        try:
            messagebox.showinfo("Məlumat", "Sessiya bağlandı. Zəhmət olmasa yenidən daxil olun.", parent=self)
        except Exception:
            pass

    def _persist_session(self, username: str):
        """Aktiv sessiyanı daimi saxlanmaya yaz (DB + settings + env)."""
        logger.info("Persisting session for user '%s'...", username)
        wrote = False
        try:
            # ƏSAS: əsas mənbə — sessions cədvəlinə yazır
            from ui_theme import start_session
            start_session(username)   # timeout, ayarlardakı 'session_timeout_min' ilə
            wrote = True
        except Exception:
            pass

        # İkincili (informativ) qeydlər:
        try:
            from ui_theme import load_app_settings, save_app_settings
            cfg = load_app_settings()
            cfg["active_user"] = username
            save_app_settings(cfg)
            wrote = True
        except Exception:
            pass

        try:
            import os as _os
            _os.environ["AVANQARD_ACTIVE_USER"] = username
            wrote = True
        except Exception:
            pass

        return wrote

    def _refresh_account_box(self):
        """Hesab tabındakı etiketi (parol xaric) dolu-dolu göstər."""
        sess = get_active_session()
        if sess:
            u, exp = sess[0], sess[1]
            # Varsayılan sətirlər
            lines = [ "Aktiv sessiya:", f" • İstifadəçi adı: {u}" ]
            # İstifadəçi qeydini çək (parolu göstərmədən)
            try:
                rec = get_user(u)  # (id, username, full_name, password, role, created_at)
                if rec:
                    uid, uname, full_name, _pwd, role, created = rec
                    if uid is not None:       lines.append(f" • ID: {uid}")
                    if full_name:             lines.append(f" • Ad Soyad: {full_name}")
                    if role:                  lines.append(f" • Rol: {role}")
                    if created:               lines.append(f" • Qeydiyyat: {created}")
            except Exception:
                pass
            if exp: lines.append(f" • Sessiya bitmə: {exp}")
            # Etiket
            try:
                self.lbl_active.configure(text="\n".join(lines), justify="left")
            except Exception:
                self.lbl_active.configure(text="\n".join(lines))
        else:
            self.lbl_active.configure(text="Aktiv sessiya yoxdur.")
        # düymə vəziyyətləri
        try: self._apply_auth_locks()
        except Exception: pass


    def show_main(self, close_self: bool = False):
        """Ana Menyu: açıqsa qabağa gətir; bağlıdırsa aç. İstəsəniz bu pəncərəni bağla."""
        logger.info("Ana menyu göstərilir...")
        shown = False

        # 1) Varsa qabağa gətir (başlıq variantlarını genişlet)
        try:
            from single_instance import bring_to_front
            for title in (
                "Əsas Menyu", "Ana Menyu",
                "Avanqard ERP — Əsas Menyu", "Avanqard ERP — Ana Menyu",
            ):
                try:
                    if bring_to_front(title):
                        shown = True
                        break
                except Exception:
                    pass
        except Exception:
            pass

        # 2) Yoxdursa başlat
        if not shown:
            try:
                import os, sys, subprocess
                script = os.path.join(os.path.dirname(__file__), "ana_menu.py")
                subprocess.Popen([sys.executable, script], close_fds=True)
                shown = True
            except Exception as e:
                from tkinter import messagebox
                logger.error("Ana Menyu açıla bilmədi: %s", e)
                messagebox.showerror("Xəta", f"Ana Menyu açıla bilmədi:\n{e}", parent=self)
                return False

        # 3) Click-through’u engelle: önce gizle, sonra küçük gecikmeyle kapat
        if close_self:
            try:
                self.attributes("-disabled", True)  # event kaçmasını önlemeye yardım eder
            except Exception:
                pass
            self.withdraw()
            self.after(180, self.destroy)

        return True

    
    def _on_close(self):
        """Pəncərə bağlananda çıxışı təsdiqlə"""
        logger.info("Close event triggered.")
        if messagebox.askyesno("Çıxış", "Hesab pencərəsini bağlamaq istədiyinizə əminsiniz?", parent=self):
            logger.info("User confirmed exit.")
            self.destroy()
            # Əgər əsas tətbiqdirsə tam bağla
            if self == self.winfo_toplevel():
                import os
                os._exit(0)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "login"
    app = HesabPenceresi(mode=mode)
    app.mainloop()

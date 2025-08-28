# ui_theme.py — Tema / Parametrlər / PDF qovluqları / Auth + Session / DB yeri
# ------------------------------------------------------------------------------------
import sys, os, json, logging, shutil, subprocess,re,sqlite3, hashlib, base64
import functools
import customtkinter as ctk
from logging.handlers import RotatingFileHandler
from tkinter import messagebox, filedialog as fd

APP_TITLE = "Avanqard ERP"

APP_BASE_DIR  = os.path.dirname(__file__)                                # modul qovluğu (MEIPASS içi)
APP_RUN_DIR   = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                 else APP_BASE_DIR)                                       # real iş qovluğu (exe yanında)
ASSETS_DIR    = os.path.join(APP_BASE_DIR, "assets")
FONTS_DIR     = os.path.join(APP_BASE_DIR, "fonts")
LOGS_DIR      = os.path.join(APP_RUN_DIR,  "logs")                        # --> bütün loglar bura
os.makedirs(LOGS_DIR, exist_ok=True)

def resource_path(rel: str) -> str:
    """PyInstaller içindəki daxili resurslar üçün (assets/fonts)."""
    # rel: "assets/app.ico" və ya "fonts/DejaVuSans.ttf"
    # Əvvəlcə APP_BASE_DIR altında axtar (MEIPASS); yoxdursa RUN_DIR-ə bax
    p = os.path.join(APP_BASE_DIR, rel)
    return p if os.path.exists(p) else os.path.join(APP_RUN_DIR, rel)

def init_logging() -> logging.Logger:
    """Bütün modulların istifadə edəcəyi ümumi logger."""
    logger = logging.getLogger("avanqard")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")

    fh = RotatingFileHandler(os.path.join(LOGS_DIR, "app.log"), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt); fh.setLevel(logging.INFO)
    eh = RotatingFileHandler(os.path.join(LOGS_DIR, "error.log"), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    eh.setFormatter(fmt); eh.setLevel(logging.ERROR)

    logger.addHandler(fh); logger.addHandler(eh)

    # stdout/stderr-i də fayla yönləndir (istəyə bağlı):
    class _StreamToLog:
        def __init__(self, level): self.level = level
        def write(self, b):
            s = b if isinstance(b, str) else b.decode("utf-8", "replace")
            for line in s.rstrip().splitlines(): logger.log(self.level, line)
        def flush(self): pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.stdout = _StreamToLog(logging.INFO)
    sys.stderr = _StreamToLog(logging.ERROR)

    def _exhook(exctype, value, tb):
        logger.exception("UNCAUGHT: %s: %s", exctype.__name__, value)
        try: messagebox.showerror("Xəta", f"{exctype.__name__}: {value}")
        except Exception: pass
    sys.excepthook = _exhook

    logger.info("Loglama başladıldı. RUN_DIR=%s", APP_RUN_DIR)
    return logger

logger = init_logging()
def log_call(name=None, level=logging.INFO):
    """Metodu çağırış/səhv ilə birlikdə loglayır."""
    def deco(fn):
        tag = name or fn.__qualname__
        @functools.wraps(fn)
        def wrap(*a, **k):
            logger.log(level, "CALL %s", tag)
            try:
                r = fn(*a, **k)
                logger.log(level, "OK   %s", tag)
                return r
            except Exception:
                logger.exception("ERR  %s", tag)
                raise
        return wrap
    return deco


# Bu iki dəyər config-dən oxunub apply_theme_global ilə yenilənir:
APPEARANCE_MODE = "light"          # "light" | "dark" | "system"
COLOR_THEME     = "blue"           # "blue" | "green" | "dark-blue"

# ========================= RƏNG PALETİ =========================
COLOR_PRIMARY = "#2563eb"
COLOR_PRIMARY_HOVER = "#1d4ed8"
COLOR_SUCCESS = "#16a34a"
COLOR_DANGER  = "#dc2626"
COLOR_WARNING = "#f59e0b"
COLOR_INFO    = "#0ea5e9"
COLOR_BG_SOFT = "#f1f5f9"
COLOR_CARD    = "#ffffff"
COLOR_ACCENT      = "#6366f1"
COLOR_ACCENT_DARK = "#4f46e5"

# ========================= ŞRİFTLƏR =========================
FONT_TITLE  = ("Segoe UI", 28, "bold")
FONT_H1     = ("Segoe UI", 24, "bold")
FONT_H2     = ("Segoe UI", 20, "bold")
FONT_NORMAL = ("Segoe UI", 14)
FONT_BOLD   = ("Segoe UI", 18, "bold")

# ========================= PDF ŞRİFT =========================
# Fayl tapılmazsa PDF_FONT_PATH boş qalır; modullar Helvetica-ya keçir.
PDF_FONT_NAME = "DejaVuSans"

def _find_pdf_font_path() -> str:
    candidates = [
        os.path.join(APP_BASE_DIR, "DejaVuSans.ttf"),
        os.path.join(APP_BASE_DIR, "fonts", "DejaVuSans.ttf"),
        os.path.join(APP_BASE_DIR, "assets", "DejaVuSans.ttf"),
        os.path.join(APP_BASE_DIR, "static", "DejaVuSans.ttf"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""  # tapılmazsa boş burax

PDF_FONT_PATH = _find_pdf_font_path()


# ========================= DÜYMƏ STİLİ =========================
def button_style(kind="primary", size=None):
    """
    Temadan düymə stili qaytarır.
    kind: primary | success | danger | warning | accent | info
    size: None(md=42) | "sm"(36) | "lg"(48) | "xl"(58)
    """
    base = {"corner_radius": 8, "height": 42, "font": FONT_BOLD}

    # Ölçü
    if size == "sm":
        base["height"] = 36
    elif size == "lg":
        base["height"] = 48
    elif size == "xl":
        base["height"] = 58
        base["corner_radius"] = 12

    # Rəng variantı
    if kind == "primary":
        base |= {"fg_color": COLOR_PRIMARY, "hover_color": COLOR_PRIMARY_HOVER}
    elif kind == "success":
        base |= {"fg_color": COLOR_SUCCESS, "hover_color": "#15803d"}
    elif kind == "danger":
        base |= {"fg_color": COLOR_DANGER, "hover_color": "#b91c1c"}
    elif kind == "warning":
        base |= {"fg_color": COLOR_WARNING, "hover_color": "#d97706"}
    elif kind == "accent":
        base |= {"fg_color": COLOR_ACCENT, "hover_color": COLOR_ACCENT_DARK}
    elif kind == "info":
        base |= {"fg_color": COLOR_INFO, "hover_color": "#0284c7"}
    else:
        # naməlum növ → primary-ə keçir
        base |= {"fg_color": COLOR_PRIMARY, "hover_color": COLOR_PRIMARY_HOVER}

    return base


# ========================= BAŞLIQ ÇUBUĞU =========================
def enable_windows_chrome(win, allow_maximize=True):
    """CTk/CTkToplevel pəncərədə OS başlığını aktiv saxla (— ☐ ✕)."""
    def _set():
        try:
            if hasattr(win, 'overrideredirect'): win.overrideredirect(False)
            if hasattr(win, 'resizable'):        win.resizable(bool(allow_maximize), bool(allow_maximize))
            if hasattr(win, 'attributes'):       win.attributes("-toolwindow", False)
        except Exception as e:
            print(f"Windows başlıq ayarlanarkən xəta: {e}")
    try:
        win.after(100, _set)
    except:
        _set()

# ========================= DAİMİ PARAMETRLƏR =========================
CONFIG_PATH = os.path.join(APP_BASE_DIR, "erp_config.json")

def _user_root() -> str:
    """Standart kök: Sənədlər/Avanqard ERP (yoxdursa layihə qovluğu)."""
    docs = os.path.join(os.path.expanduser("~"), "Documents", "Avanqard ERP")
    try:
        os.makedirs(docs, exist_ok=True)
        return docs
    except Exception:
        return os.path.join(APP_BASE_DIR, "Avanqard ERP")

def load_app_settings() -> dict:
    """Parametrləri oxu; yoxdursa standartlarla doldur və qovluqları yarat."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}

    root = _user_root()

    # Qaimə & Hesabat qovluqları
    inv_dir = cfg.get("invoice_dir") or os.path.join(root, "Qaimələr")
    rep_dir = cfg.get("report_dir")  or os.path.join(root, "Hesabatlar")
    os.makedirs(inv_dir, exist_ok=True)
    os.makedirs(rep_dir, exist_ok=True)
    cfg["invoice_dir"] = inv_dir
    cfg["report_dir"]  = rep_dir

    # Data qovluğu & DB
    data_dir = cfg.get("data_dir") or os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)
    cfg["data_dir"] = data_dir
    _migrate_db_to_data_dir(data_dir)

    # Sessiya vaxtı (dəq) və referans kodu
    cfg.setdefault("session_timeout_min", 30)
    cfg.setdefault("invite_code", "AVQ-2025")

    # Görünüş
    cfg.setdefault("appearance", "light")
    cfg.setdefault("color_theme", "blue")

    # Yadda saxla (yarandısa)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return cfg

def save_app_settings(cfg: dict) -> bool:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        try: messagebox.showerror("Xəta", f"Parametrlər yadda saxlanılmadı:\n{e}")
        except Exception: pass
        return False

# ---- Qovluq seçicilər
def select_invoice_dir(cfg: dict = None, parent=None) -> str:
    if cfg is None: cfg = load_app_settings()
    cur = cfg.get("invoice_dir", _user_root())
    newdir = fd.askdirectory(initialdir=cur, title="Qaimə PDF qovluğu", parent=parent)
    if newdir:
        os.makedirs(newdir, exist_ok=True)
        cfg["invoice_dir"] = newdir
        save_app_settings(cfg)
        try: messagebox.showinfo("Məlumat", f"Qaimə qovluğu yeniləndi:\n{newdir}")
        except Exception: pass
    return cfg["invoice_dir"]

def select_report_dir(cfg: dict = None, parent=None) -> str:
    if cfg is None: cfg = load_app_settings()
    cur = cfg.get("report_dir", _user_root())
    newdir = fd.askdirectory(initialdir=cur, title="Hesabat PDF qovluğu", parent=parent)
    if newdir:
        os.makedirs(newdir, exist_ok=True)
        cfg["report_dir"] = newdir
        save_app_settings(cfg)
        try: messagebox.showinfo("Məlumat", f"Hesabat qovluğu yeniləndi:\n{newdir}")
        except Exception: pass
    return cfg["report_dir"]

# ---- PDF yol köməkçiləri
def invoice_pdf_path(filename: str, cfg: dict = None) -> str:
    if cfg is None: cfg = load_app_settings()
    safe = re.sub(r"[^\w\-]+", "_", (filename or "QAİMƏ").strip())
    return os.path.join(cfg["invoice_dir"], f"{safe}.pdf")

def report_pdf_path(filename: str, cfg: dict = None) -> str:
    if cfg is None: cfg = load_app_settings()
    safe = re.sub(r"[^\w\-]+", "_", (filename or "HESABAT").strip())
    # filename 'hesabat_...' ilə gəlirsə .pdf daxil deyil deyə qəbul edirik:
    if not safe.lower().endswith(".pdf"):
        safe = f"{safe}"
    return os.path.join(cfg["report_dir"], safe)

# ---- Geri uyğunluq (köhnə adlar):
def pdf_path_for_invoice(filename: str, cfg: dict = None) -> str:
    """KÖHNƏ ad — yeni invoice_pdf_path-a yönləndirir."""
    return invoice_pdf_path(filename, cfg)

def select_pdf_dir(cfg: dict = None, parent=None) -> str:
    """KÖHNƏ ad — yeni select_invoice_dir-ə yönləndirir."""
    return select_invoice_dir(cfg, parent)

# --------- İlk Başlatma Sihri (qovluq və qısayollar) ---------
def _create_shortcut_desktop(name="Avanqard ERP", icon_rel="assets/app.ico"):
    """PyWin32 qurmadan PowerShell ilə masaüstü .lnk yaradılır."""
    if os.name != "nt": return False
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    os.makedirs(desktop, exist_ok=True)
    lnk = os.path.join(desktop, f"{name}.lnk")
    target = sys.executable
    icon = resource_path(icon_rel)
    ps = (
      "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{}');"
      "$s.TargetPath='{}';$s.IconLocation='{}';$s.WorkingDirectory='{}';$s.Save()"
    ).format(lnk.replace("\\","\\\\"), target.replace("\\","\\\\"), icon.replace("\\","\\\\"), APP_RUN_DIR.replace("\\","\\\\"))
    try:
        subprocess.run(["powershell","-NoProfile","-Command", ps], check=True, creationflags=0x08000000)
        logger.info("Masaüstü qısayol yaradıldı: %s", lnk)
        return True
    except Exception as e:
        logger.error("Qısayol yaradılmadı: %s", e); return False

def ensure_first_run_setup():
    """Quraşdırma sualları (PDF qovluqları) + masaüstü qısayolu (bir dəfə)."""
    try:
        cfg = load_app_settings()
        marker = os.path.join(cfg.get("data_dir", APP_RUN_DIR), ".first_run_done")
        if os.path.exists(marker): return

        # PDF qovluqlarını istifadəçiyə soruş (standartlar hazır):
        inv = fd.askdirectory(initialdir=cfg["invoice_dir"], title="Qaimə PDF qovluğunu seçin")
        rep = fd.askdirectory(initialdir=cfg["report_dir"],  title="Hesabat PDF qovluğunu seçin")
        if inv: cfg["invoice_dir"] = inv
        if rep: cfg["report_dir"]  = rep
        save_app_settings(cfg)

        _create_shortcut_desktop()  # uğursuz olsa səssiz keç

        with open(marker, "w", encoding="utf-8") as f: f.write("ok")
        logger.info("İlk başlatma tamamlandı.")
    except Exception as e:
        logger.error("ilk başlatma xətası: %s", e)
        messagebox.showerror("Quraşdırma Xətası", f"Quraşdırma zamanı xəta baş verdi:\n{e}")

# ========================= AUTH / SESSION (SQLite) =========================
def _db_file_in_data_dir() -> str:
    data_dir = load_app_settings().get("data_dir")
    return os.path.join(data_dir, "erp.db")

def _migrate_db_to_data_dir(data_dir: str):
    """Layihədə/iş qovluğunda köhnə erp.db varsa data/ altına köçürür (kopyalayır)."""
    old1 = os.path.join(APP_BASE_DIR, "erp.db")
    old2 = os.path.join(os.getcwd(), "erp.db")
    newp = os.path.join(data_dir, "erp.db")
    if os.path.exists(newp):
        return
    src = old1 if os.path.exists(old1) else (old2 if os.path.exists(old2) else None)
    if src:
        try:
            shutil.copy2(src, newp)
        except Exception as e:
            print("DB köçürmə xətası:", e)

def _conn():
    """Tətbiqin SQLite bağlantısı — bütün modullar bunu istifadə etsin."""
    dbp = _db_file_in_data_dir()
    os.makedirs(os.path.dirname(dbp), exist_ok=True)
    return sqlite3.connect(dbp)

def ensure_auth_tables():
    """users + sessions cədvəllərini təmin et."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT UNIQUE NOT NULL,
                full_name TEXT,
                password  TEXT NOT NULL,    -- base64(salt)$base64(hash)
                role      TEXT DEFAULT 'user',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT NOT NULL,
                login_at  TEXT DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL
            )
        """)
        conn.commit()

# ---- Parol hash (PBKDF2-HMAC-SHA256)
def _pbkdf2(password: str, salt: bytes, iters: int = 120_000) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return base64.b64encode(dk).decode("ascii")

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    return f"{base64.b64encode(salt).decode('ascii')}${_pbkdf2(password, salt)}"

def verify_password(password: str, stored: str) -> bool:
    try:
        s, h = stored.split("$", 1)
        salt = base64.b64decode(s.encode("ascii"))
        return _pbkdf2(password, salt) == h
    except Exception:
        return False

def create_user(username: str, password: str, full_name: str = "", role: str = "user") -> bool:
    ensure_auth_tables()
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, full_name, password, role) VALUES (?,?,?,?)",
                        (username.strip().lower(), full_name.strip(), hash_password(password), role))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def user_count() -> int:
    ensure_auth_tables()
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        n = cur.fetchone()
        return int(n[0]) if n else 0

def get_user(username: str):
    ensure_auth_tables()
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, full_name, password, role, created_at FROM users WHERE username=?",
                    (username.strip().lower(),))
        return cur.fetchone()

def start_session(username: str, timeout_min: int = None):
    ensure_auth_tables()
    cfg = load_app_settings()
    tmin = int(cfg.get("session_timeout_min", 30)) if timeout_min is None else int(timeout_min)
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
        cur.execute("INSERT INTO sessions (username, expires_at) VALUES (?, datetime('now', ?))",
                    (username.strip().lower(), f'+{tmin} minutes'))
        conn.commit()

def end_session(username: str = None):
    ensure_auth_tables()
    with _conn() as conn:
        cur = conn.cursor()
        if username:
            cur.execute("DELETE FROM sessions WHERE username=?", (username.strip().lower(),))
        else:
            cur.execute("DELETE FROM sessions")
        conn.commit()

def get_active_session():
    """Aktiv (vaxtı bitməmiş) son sessiyanı qaytar (username, expires_at) və ya None."""
    ensure_auth_tables()
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT username, expires_at
              FROM sessions
             WHERE expires_at > datetime('now')
             ORDER BY id DESC LIMIT 1
        """)
        return cur.fetchone()

def require_session_or_exit(parent_script: str = "hesab.py"):
    """Sessiya yoxdursa giriş/hesab ekranını açıb prosesi bağla."""
    if get_active_session() is None:
        try:
            import subprocess
            script = os.path.join(os.path.dirname(__file__), parent_script)
            subprocess.Popen([sys.executable, script], close_fds=True)
        except Exception as e:
            try: messagebox.showerror("Xəta", f"Giriş ekranı açıla bilmədi:\n{e}")
            except Exception: pass
        os._exit(0)

# ========================= QLOBAL TEMA =========================
def apply_theme_global():
    """Config-dəki görünüşü bütün yeni pəncərələrə tətbiq et (ctk qlobal)."""
    cfg = load_app_settings()
    mode  = cfg.get("appearance", "light")
    theme = cfg.get("color_theme", "blue")
    try:
        ctk.set_appearance_mode(mode)
        ctk.set_default_color_theme(theme)
    except Exception:
        pass

# ========================= PARAMETRLƏR PƏNCƏRƏSİ =========================
_SETTINGS_WIN = None  # tək instance

def open_settings_window(parent=None):
    """Parametrlər: tək instance, modal (grab), önə gətir; tema önizləmədə bağlanmır/donmur.
    'Ana Menyu' düyməsi: açıqsa önə gətirir, bağlısa açır (ikinci nüsxəni başlatmır)."""
    import traceback, os, sys, subprocess
    global _SETTINGS_WIN

    # Artıq açıqsa: önə gətir
    if _SETTINGS_WIN is not None and _SETTINGS_WIN.winfo_exists():
        try:
            _SETTINGS_WIN.deiconify()
            _SETTINGS_WIN.lift()
            _SETTINGS_WIN.focus_force()
            _SETTINGS_WIN.attributes("-topmost", True)
            _SETTINGS_WIN.after(150, lambda: _SETTINGS_WIN.attributes("-topmost", False))
        except Exception:
            pass
        return

    cfg = load_app_settings()

    top = ctk.CTkToplevel(parent)
    _SETTINGS_WIN = top
    enable_windows_chrome(top)
    top.title(f"{APP_TITLE} — Parametrlər")
    top.geometry("700x400"); top.minsize(600, 400)

    # ---- YALNIZ grab_set ilə modal et (parent -disabled İSTİFADƏ ETMİRİK) ----
    def _ensure_modal():
        try:
            if _SETTINGS_WIN is top and top.winfo_exists():
                if top.grab_current() is not top:
                    top.grab_set()
                top.after(400, _ensure_modal)
        except Exception:
            pass

    def _release_modal_and_focus_parent():
        try:
            if top.grab_current() is top:
                top.grab_release()
        except Exception:
            pass
        try:
            if parent is not None and parent.winfo_exists():
                parent.deiconify(); parent.lift(); parent.focus_force()
        except Exception:
            pass

    try:
        if parent is not None and parent.winfo_exists():
            top.transient(parent)
    except Exception:
        pass
    try:
        top.deiconify(); top.lift(); top.focus_force()
        top.after(0, _ensure_modal)
    except Exception:
        pass

    def _on_close():
        nonlocal top
        global _SETTINGS_WIN
        try:
            _release_modal_and_focus_parent()
        finally:
            try:
                _SETTINGS_WIN = None
                if top.winfo_exists():
                    top.destroy()
            except Exception:
                pass

    top.protocol("WM_DELETE_WINDOW", _on_close)
    top.bind("<Destroy>", lambda e: _release_modal_and_focus_parent())

    # ===== UI =====
    wrap = ctk.CTkFrame(top, corner_radius=12); wrap.pack(fill="both", expand=True, padx=16, pady=16)
    ctk.CTkLabel(wrap, text="⚙️ Parametrlər", font=FONT_H1).pack(anchor="w", padx=8, pady=(0,8))

    # Görünüş
    r1 = ctk.CTkFrame(wrap, fg_color="transparent"); r1.pack(fill="x", pady=6)
    ctk.CTkLabel(r1, text="Görünüş", font=FONT_BOLD, width=160).pack(side="left")
    cb_mode  = ctk.CTkComboBox(r1, values=["light","dark","system"], width=140)
    cb_mode.set(cfg.get("appearance","light")); cb_mode.pack(side="left", padx=6)
    ctk.CTkLabel(r1, text="Tema", font=FONT_BOLD, width=60).pack(side="left", padx=(12,0))
    cb_theme = ctk.CTkComboBox(r1, values=["blue","green","dark-blue"], width=140)
    cb_theme.set(cfg.get("color_theme","blue")); cb_theme.pack(side="left", padx=6)

    # Qaimə / Hesabat qovluqları
    r2 = ctk.CTkFrame(wrap, fg_color="transparent"); r2.pack(fill="x", pady=6)
    ctk.CTkLabel(r2, text="Qaimə PDF qovluğu", font=FONT_BOLD, width=160).pack(side="left")
    lbl_inv = ctk.CTkLabel(r2, text=cfg.get("invoice_dir",""), font=FONT_NORMAL); lbl_inv.pack(side="left", padx=6)
    ctk.CTkButton(r2, text="Seç…", **button_style("accent"), width=90,
                  command=lambda: lbl_inv.configure(text=select_invoice_dir(cfg, top))).pack(side="left", padx=6)

    r3 = ctk.CTkFrame(wrap, fg_color="transparent"); r3.pack(fill="x", pady=6)
    ctk.CTkLabel(r3, text="Hesabat PDF qovluğu", font=FONT_BOLD, width=160).pack(side="left")
    lbl_rep = ctk.CTkLabel(r3, text=cfg.get("report_dir",""), font=FONT_NORMAL); lbl_rep.pack(side="left", padx=6)
    ctk.CTkButton(r3, text="Seç…", **button_style("accent"), width=90,
                  command=lambda: lbl_rep.configure(text=select_report_dir(cfg, top))).pack(side="left", padx=6)

    # ---- Canlı önizləmə: tema dəyişmədən ƏVVƏL grab-i burax, SONRA yenidən qur ----
    def _preview_theme(*_):
        # 1) modalı burax
        try:
            if top.grab_current() is top:
                top.grab_release()
        except Exception:
            pass
        # 2) temanı tətbiq et
        try:
            ctk.set_appearance_mode(cb_mode.get().strip().lower())
            ctk.set_default_color_theme(cb_theme.get().strip())
        except Exception:
            traceback.print_exc()
        # 3) pəncərəni yenidən önə gətir + yenidən modal et
        def _regrab():
            try:
                if top.winfo_exists():
                    top.deiconify(); top.lift(); top.focus_force()
                    if top.grab_current() is not top:
                        top.grab_set()
            except Exception:
                pass
        top.after(150, _regrab)

    cb_mode.configure(command=lambda _v: _preview_theme())
    cb_theme.configure(command=lambda _v: _preview_theme())

    # Alt — Sol: Ana Menyu | Sağ: Yadda saxla & Bağla / Bağla
    bottom = ctk.CTkFrame(wrap, fg_color="transparent"); bottom.pack(fill="x", pady=(10,0))

    def _go_main_menu():
        """Açıqsa önə gətir, bağlısa aç. İkinci nüsxəni başlatma."""
        brought = False
        try:
            if parent is not None and parent.winfo_exists():
                t = (parent.winfo_toplevel().title() or "").lower()
                if "ana men" in t:  # "Ana Menyu"/"Ana Menyu" və s.
                    try:
                        if top.grab_current() is top:
                            top.grab_release()
                    except Exception:
                        pass
                    parent.deiconify(); parent.lift(); parent.focus_force()
                    brought = True
        except Exception:
            brought = False

        if not brought:
            try:
                script = os.path.join(os.path.dirname(__file__), "ana_menu.py")
                subprocess.Popen([sys.executable, script], close_fds=True)
                brought = True
            except Exception as e:
                messagebox.showerror("Xəta", f"Əsas Menyu açıla bilmədi:\n{e}", parent=top)
                return

        _on_close()  # parametrləri bağla (grab sərbəst + pəncərə bağlanır)

    ctk.CTkButton(bottom, text="🏠 Əsas Menyu", **button_style("primary"), command=_go_main_menu)\
        .pack(side="left")

    def _save_and_close():
        try:
            cfg["appearance"] = cb_mode.get().strip().lower()
            cfg["color_theme"]= cb_theme.get().strip()
            if save_app_settings(cfg):
                apply_theme_global()
                _on_close()
                messagebox.showinfo("Məlumat","Parametrlər yadda saxlanıldı.", parent=parent or None)
            else:
                messagebox.showerror("Xəta","Parametrlər yadda saxlanılmadı.", parent=top)
        except Exception:
            _on_close()
            messagebox.showerror("Xəta","Parametrlər yadda saxlanılarkən xəta baş verdi.", parent=parent or None)

    ctk.CTkButton(bottom, text="Yadda saxla & Bağla", **button_style("success"), command=_save_and_close)\
        .pack(side="right")
    ctk.CTkButton(bottom, text="Bağla", **button_style("warning"), command=_on_close)\
        .pack(side="right", padx=8)

    # önə gətir
    try:
        top.deiconify(); top.lift(); top.attributes("-topmost", True)
        top.after(150, lambda: top.attributes("-topmost", False))
        top.wait_visibility(); top.focus_force()
    except Exception:
        pass


# --- modul yüklənəndə mövcud temanı tətbiq et (qlobal)
apply_theme_global()

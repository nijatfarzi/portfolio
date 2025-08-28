import os
import sys
import subprocess
import customtkinter as ctk
from tkinter import messagebox

from ui_theme import (
    FONT_H1, FONT_BOLD,
    enable_windows_chrome,
    apply_theme_global,
    button_style, logger, log_call,
    get_active_session, resource_path, ensure_first_run_setup
)

try:
    from ui_theme import open_settings_window
except Exception:
    def open_settings_window(parent=None):
        messagebox.showinfo("Ayarlar", "Ayarlar pəncərəsi əlavə edilməyib kimi görünür.")

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import shutil

def _handoff(script_name: str, *args: str):
    import os, sys, subprocess
    from tkinter import messagebox

    path = os.path.join(os.path.dirname(__file__), script_name)
    try:
        if os.name == "nt":
            q = lambda s: f'"{s}"'
            cmd = " ".join([q(sys.executable), q(path)] + [q(str(a)) for a in args])
            subprocess.Popen(cmd, shell=True)
        else:
            subprocess.Popen([sys.executable, path, *map(str, args)], shell=False)
    except Exception as e:
        messagebox.showerror("Xəta", f"Açıla bilmədi:\n{script_name}\n\n{e}")
        return

    os._exit(0)

def clean_pycache(start_path="."):
    deleted = []
    for root, dirs, _ in os.walk(start_path):
        for dir_name in dirs:
            if dir_name == "__pycache__":
                dir_path = os.path.join(root, dir_name)
                try:
                    shutil.rmtree(dir_path)
                    deleted.append(dir_path)
                except Exception as e:
                    print(f"Silinmədi: {dir_path} - {e}")
    if deleted:
        print(f"Təmizləndi: {len(deleted)} __pycache__ qovluğu")
    else:
        print("__pycache__ qovluğu tapılmadı")

class AnaMenu(ctk.CTk):
    def __init__(self):
        clean_pycache()
        super().__init__()

        apply_theme_global()
        enable_windows_chrome(self)
        self.title("Avanqard ERP — Əsas Menyu")
        self.iconbitmap(resource_path("assets/app.ico"))
        logger.info("PƏNCƏRƏ AÇILDI: AnaMenu")
        ensure_first_run_setup() 

        self.geometry("700x700")
        self.minsize(700, 520)
    
        self._closing = False
        self._watchdog_id = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ESC düyməsinə basanda çıxışı soruş
        self.bind("<Escape>", lambda e: self._on_close())
        self._build_ui()
        # Sessiya izləyicisi: əvvəlcə yoxla və periodik izləmə
        self.after(100, self._enforce_session_start)

    @log_call()
    def _spawn(self, script_name: str, *args: str):
        """
        VSCode-da işləyərkən alt pəncərələri təhlükəsiz aç.
        - cwd -> layihə qovluğu
        - Windows yaratma bayraqları -> valideyndən asılı olmasın
        - Xəta olarsa messagebox + log
        """
        try:
            base = os.path.dirname(__file__)
            script = os.path.join(base, script_name)

            # Python icraçısı
            py = sys.executable
            if py.lower().endswith("python.exe") and os.name == "nt":
                # Konsol istəmirsənsə pythonw.exe-yə keç (tapılarsa)
                pyw = py[:-len("python.exe")] + "pythonw.exe"
                if os.path.exists(pyw):
                    py = pyw

            cmd = [py, script, *map(str, args)]
            logger.info("SPAWN: %s", " ".join(cmd))

            # Windows-da ayrılmış proseslə başlat (bağlanma/fokus problemlərini önləyir)
            creationflags = 0
            if os.name == "nt":
                creationflags = 0x00000008 | 0x00000200  # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS

            subprocess.Popen(
                cmd,
                cwd=base,                 # <— VACİB: layihə kökünü CWD et
                close_fds=False,          # bəzi sistemlərdə True problem yarada bilər
                creationflags=creationflags
            )
        except Exception as e:
            logger.exception("spawn alınmadı: %s", e)
            try:
                messagebox.showerror("Xəta", f"Açıla bilmədi:\n{script_name}\n\n{e}")
            except Exception:
                pass

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 8))
        hero = ctk.CTkFrame(header, fg_color="transparent"); hero.pack()

        if HAS_PIL:
            try:
                logo_path = resource_path("assets/app.png")
                if os.path.exists(logo_path):
                    img = Image.open(logo_path).resize((140, 140))
                    self.logo_img = ctk.CTkImage(img, size=(140, 140))
                    ctk.CTkLabel(hero, image=self.logo_img, text="").pack(pady=(0, 6))
            except Exception:
                pass

        ctk.CTkLabel(hero, text="Avanqard ERP", font=FONT_H1).pack()

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="both", expand=True, padx=24, pady=(6, 12))

        def big_btn(text, cmd, kind):
            def _cmd():
                logger.info("BASILDİ: %s", text)
                try: cmd()
                except Exception:
                    logger.exception("BASMA əməliyyatı alınmadı: %s", text)
                    raise
            btn = ctk.CTkButton(
                buttons, text=text,
                **button_style(kind, size="xl"),   # hündürlük temadan (58px)
                command=_cmd
            )
            btn.pack(fill="x", pady=8)
            return btn

        self.btn_satis   = big_btn("🧾 FAKTURA VER",  lambda: self._guarded_handoff("faktura.py"),     "success")
        self.btn_anbar   = big_btn("📦 ANBAR",        lambda: self._guarded_handoff("stok.py"),         "primary")
        self.btn_list    = big_btn("📑 FAKTURALAR",   lambda: self._guarded_handoff("fakturalar.py"),   "accent")
        self.btn_mehsullar = big_btn("🏷️ MƏHSULLAR",   lambda: self._guarded_handoff("mehsullar.py"),      "warning")
        self.btn_rapor   = big_btn("📊 HESABATLAR",   lambda: self._guarded_handoff("raport.py"),       "info")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=24, pady=(4, 16))

        # 🔧 height parametri çıxarıldı; size="lg" ilə verilir
        ctk.CTkButton(
            bottom, text="⚙️ AYARLAR",
            **button_style("accent", size="lg"),
            command=lambda: open_settings_window(self)
        ).pack(side="left")

        ctk.CTkButton(
            bottom, text="👤 HESAB",
            **button_style("primary", size="lg"),
            command=self._open_login_soft 
        ).pack(side="right")

    def _open_login_soft(self):
        """Hesab pəncərəsi: açıqsa önə gətir, yoxdursa aç (menyunu kilidləmədən)."""
        try:
            from single_instance import bring_to_front
            if bring_to_front("Hesab") or bring_to_front("Hesab / Giriş"):
                return True
        except Exception:
            pass
        try:
            self._spawn("hesab.py")
            return True
        except Exception:
            return False

    def _guarded_handoff(self, script_name: str, *args: str):
        """Sessiya varsa səhifəni aç; yoxdursa nəzakətlə Hesab (Giriş) pəncərəsini aç."""
        if get_active_session():
            # mövcud _handoff/_spawn quruluşuna görə seç:
            try:
                _handoff  # varsa (bəzi menyu düymələrində istifadə olunur)
                _handoff(script_name, *args)
                return
            except Exception:
                pass
            self._spawn(script_name, *args)
        else:
            # Yalnız login pəncərəsini aç/önə gətir; menyunu KİLİDLƏMƏ!
            self._open_login_soft()

    def _open_account(self):
        """Sessiya varsa Hesab sekmesine; yoxdursa login rejimində aç və menyunu kilidlə."""
        try:
            if get_active_session():
                self._spawn("hesab.py", "account")
            else:
                self._freeze_and_prompt_login()
        except Exception:
            self._freeze_and_prompt_login()
    
    def _set_disabled(self, disabled: bool):
        """Pəncərəni kilidlə/aç (Windows-da -disabled, digərlərində səssizcə ötür)."""
        try:
            # Windows-da işləyir; digər platformalarda xəta verərsə ötür
            self.attributes("-disabled", bool(disabled))
        except Exception:
            pass

    def _bring_or_open_hesab(self):
        """Hesab pəncərəsini önə gətir; yoxdursa aç. Bağlanış zamanı heç nə etmə."""
        if getattr(self, "_closing", False):
            return False
        try:
            from single_instance import bring_to_front
            if bring_to_front("Hesab") or bring_to_front("Hesab / Giriş"):
                return True
        except Exception:
            pass
        try:
            self._spawn("hesab.py")
            return True
        except Exception:
            return False

    def _freeze_and_prompt_login(self):
        """Sessiya yoxdursa menyunu kilidlə və Hesab pəncərəsini önə gətir/aç."""
        if getattr(self, "_closing", False):
            return
        self._set_disabled(True)
        self._bring_or_open_hesab()

    def _enforce_session_start(self):
        """Yumşaq rejim: açılışda sessiya məcburi deyil."""
        return  # heç nə etmir

    def _session_watchdog(self):
        """Yumşaq rejim: periodik yoxlama edilmir."""
        return  # heç nə etmir

    def _on_close(self):
        """X düyməsinə basanda: watchdog-u ləğv et, yenidən açılmaların qarşısını al, təhlükəsiz və qəti bağlan."""
        logger.info("PƏNCƏRƏ BAĞLANIR: AnaMenu (istək)")
        self._closing = True
        try:
            if self._watchdog_id is not None:
                self.after_cancel(self._watchdog_id)
        except Exception:
            pass
        self._set_disabled(False)
        
        # İstifadəçidən çıxmaq istədiyinə əmin olub-olmadığını soruş
        if messagebox.askyesno("Çıxış", "Proqramdan çıxmaq istədiyinizə əminsiniz?", parent=self):
            try:
                self.destroy()
            finally:
                # Event loop-da qalmış tetikleyiciləri də dayandırmaq üçün sərt çıxış
                import os
                os._exit(0)
        logger.info("PƏNCƏRƏ BAĞLANDI: AnaMenu")

if __name__ == "__main__":
    apply_theme_global()
    route = sys.argv[1] if len(sys.argv) > 1 else ""

    if route == "hesab":
        mode = sys.argv[2] if len(sys.argv) > 2 else "login"
        from hesab import HesabPenceresi
        app = HesabPenceresi(mode=mode)

    elif route == "faktura":
        from faktura import FakturaForm
        app = FakturaForm()

    elif route == "fakturalar":
        from fakturalar import FakturalarPenceresi
        app = FakturalarPenceresi()

    elif route == "stok":
        from stok import StokPenceresi
        app = StokPenceresi()

    elif route == "mehsullar":
        from mehsullar import MehsullarPenceresi
        app = MehsullarPenceresi()

    elif route == "raport":
        from raport import RaporlarPenceresi
        app = RaporlarPenceresi()

    elif route == "detal":
        ident = sys.argv[2] if len(sys.argv) > 2 else ""
        from mehsul_detal import FakturaDetalPenceresi
        app = FakturaDetalPenceresi(ident)

    else:
        app = AnaMenu()

    app.mainloop()
    clean_pycache()

# single_instance.py — kiçik tək pəncərə qoruması (Windows/macOS/Linux)
import os, atexit, tempfile, time

_LOCKS = {}  # ad -> lockfile yolu

def _path(name): 
    return os.path.join(tempfile.gettempdir(), f"avq_{name}.lock")

def claim(name: str, stale_hours: int = 24) -> bool:
    """Bu proses pəncərə adını sahiblənir. Artıq açıqdırsa False qaytarır."""
    p = _path(name)
    # köhnə kilidi təmizlə
    if os.path.exists(p):
        try:
            if time.time() - os.path.getmtime(p) > stale_hours * 3600:
                os.remove(p)
        except OSError:
            pass
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        _LOCKS[name] = p
        atexit.register(lambda: os.path.exists(p) and os.remove(p))
        return True
    except FileExistsError:
        return False

def is_claimed(name: str) -> bool:
    """Qeydiyyat varmı? (Açıqdırsa True)"""
    return os.path.exists(_path(name))

# --- Windows: mövcud pəncərəni önə gətir (başlıqda uyğun ilk pəncərə) ---
def bring_to_front(title_substr: str) -> bool:
    if os.name != "nt":
        return False
    import ctypes
    import ctypes.wintypes as w

    user32 = ctypes.windll.user32
    EnumWindows           = user32.EnumWindows
    IsWindowVisible       = user32.IsWindowVisible
    GetWindowTextW        = user32.GetWindowTextW
    GetWindowTextLengthW  = user32.GetWindowTextLengthW
    SetForegroundWindow   = user32.SetForegroundWindow
    ShowWindow            = user32.ShowWindow
    SW_RESTORE = 9

    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, ctypes.c_void_p)
    def enum_proc(hwnd, lParam):
        if IsWindowVisible(hwnd):
            ln = GetWindowTextLengthW(hwnd)
            if ln:
                buf = ctypes.create_unicode_buffer(ln + 1)
                GetWindowTextW(hwnd, buf, ln + 1)
                title = buf.value
                if title_substr.lower() in title.lower():
                    found.append(hwnd)
                    return False  # dayandır
        return True

    EnumWindows(enum_proc, 0)
    if not found:
        return False
    hwnd = found[0]
    ShowWindow(hwnd, SW_RESTORE)      # minimizədən geri gətir
    SetForegroundWindow(hwnd)         # önə al
    return True

import sqlite3

conn = sqlite3.connect("erp.db")
c = conn.cursor()

# MƏHSULLAR
c.execute("""
CREATE TABLE IF NOT EXISTS mehsullar (
    kod TEXT,
    ad TEXT NOT NULL,
    olcu TEXT,
    cins TEXT,
    stok REAL DEFAULT 0,
    alis_qiymet REAL DEFAULT 0,
    satis_qiymet REAL DEFAULT 0,
    PRIMARY KEY (kod, cins)
)
""")

# MÜŞTƏRİLƏR
c.execute("""
CREATE TABLE IF NOT EXISTS musteriler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT UNIQUE,
    telefon TEXT
)
""")

# QƏBZLƏR
c.execute("""
CREATE TABLE IF NOT EXISTS fakturalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faktura_no TEXT,
    tarix TEXT,
    toplam REAL,
    musteri_id INTEGER,
    tur TEXT,  -- 'alis' / 'satis'
    FOREIGN KEY (musteri_id) REFERENCES musteriler (id)
)
""")

# QƏBZ DETALI
c.execute("""
CREATE TABLE IF NOT EXISTS faktura_detal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faktura_id INTEGER,
    mehsul_kod TEXT,
    mehsul_cins TEXT,
    say REAL,
    alis_qiymet REAL,
    satis_qiymet REAL,
    mebleg REAL,
    toplam REAL,
    FOREIGN KEY (faktura_id) REFERENCES fakturalar (id),
    FOREIGN KEY (mehsul_kod, mehsul_cins) REFERENCES mehsullar (kod, cins)
)
""")

# ANBAR LOGU (əl ilə ± hərəkətlər)
c.execute("""
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

# --- Əksik sütunlar varsa əlavə et (SQLite PRAGMA ilə yoxla) ---
c.execute("PRAGMA table_info(stok_log)")
cols = {r[1] for r in c.fetchall()}
if "alis_qiymet" not in cols:
    c.execute("ALTER TABLE stok_log ADD COLUMN alis_qiymet REAL")
if "satis_qiymet" not in cols:
    c.execute("ALTER TABLE stok_log ADD COLUMN satis_qiymet REAL")
if "mebleg" not in cols:
    c.execute("ALTER TABLE stok_log ADD COLUMN mebleg REAL")

# indekslər
c.execute("CREATE INDEX IF NOT EXISTS idx_stoklog_kodcins ON stok_log (mehsul_kod, mehsul_cins)")
c.execute("CREATE INDEX IF NOT EXISTS idx_stoklog_tarix   ON stok_log (tarix)")
c.execute("CREATE INDEX IF NOT EXISTS idx_stoklog_logno   ON stok_log (log_no)")

conn.commit()
conn.close()
print("✅ verilənlər bazası hazırdır (stok_log qiymət/məbləğ sahələri ilə)")

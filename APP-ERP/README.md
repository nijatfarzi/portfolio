# Avanqard ERP (Desktop • Python + CustomTkinter)

Axşam-axşam yığıb işlədiyim **masaüstü ERP prototipi** — stok (anbar), məhsullar, alış/satış fakturaları, faktura detalı və hesabatlar **bir yerdə**. Sadə SQLite verilənlər bazası ilə işləyir; Windows üçün PyInstaller ilə paketlənə bilir.

## Özəlliklər
### Anbar / Stok
- **Ümumi stok**, **inventar dəyəri** (stok × alış qiyməti), **az stok sayacı** (<50)
- Axtarış (kod/ad), **cins** filtri, **maksimum stok** limiti, **sıfır stokları gizlət**
- Cədvəldə vahid format: 2 onluq, ₼ işarəsi, sayılar sağa hizalı

### Məhsullar
- Sürətli axtarış və filtr
- **Məhsul detalı**: ölçü vahidi, qiymətlər, hərəkət keçmişi

### Fakturalar
- **Alış / Satış** fakturası formu
- Fakturalar siyahısı + **iki dəfə kliklə** detal pəncərəsi
- **PDF çıxış** (ReportLab)

### Hesabatlar / Analitika
- KPI-lar: **Faktura sayı, Dövriyyə, COGS, Qazanc, Orta səbət**
- Rejimlər: **Məhsul üzrə** (Top-N / Least / Profit / Worst), **Faktura üzrə**
- Tarix aralığı seçimi, **F5** ilə yeniləmə, **PDF ixrac**

### Hesab / İstifadəçi
- Qeydiyyat, giriş/çıxış, sessiya idarəsi
- Aktiv istifadəçi məlumatları (parol **xaric**): ID, ad-soyad, rol, qeydiyyat tarixi

### Tətbiq davranışı
- **Tək instans** və **bring-to-front** (ikinci proses/minimize açılmanın qarşısı)
- Toplanmış səhv idarəetməsi (excepthook → aydın mesaj qutuları)

## Quraşdırma
```bash
# Python 3.11+ tövsiyə olunur
pip install -r requirements.txt
python db_init.py   # cədvəlləri yaradır; istəyə görə demo məlumat da yaza bilərsiz
python ana_menu.py  # tətbiqi başlat
```

> **Qeyd:** Real `erp.db` fayllarınızı paylaşmayın. Repo üçün `data/erp_demo.db` (demo) istifadə edin. `ui_theme._conn()` DB yolunu layihə kökünə (`./data`) yönləndirir.

## Paketləmə (Windows – PyInstaller)
```bash
py -m pip install pyinstaller
pyinstaller --noconfirm --onefile --name AvanqardERP ^
  --add-data "DejaVuSans.ttf;." ^
  ana_menu.py
# Çıxış: dist/AvanqardERP.exe
```

## Layihə quruluşu (tövsiyə)
```
avanqard-erp/
  ana_menu.py
  mehsullar.py
  mehsul_detali.py
  fakturalar.py
  faktura.py
  faktura_detal.py
  stok.py
  raport.py
  hesab.py
  single_instance.py
  ui_theme.py
  db_init.py
  data/
    erp_demo.db        # (real müştəri məlumatı YOX!)
  assets/screenshots/
    ana-menu.png
    anbar.png
    mehsullar.png
    fakturalar.png
    faktura-detal.png
    raportlar.png
  requirements.txt
  .gitignore
  LICENSE
  README.md
```

## Ekran görüntüləri
`assets/screenshots` qovluğuna şəkillərinizi yerləşdirin və LinkedIn/GitHub üçün istifadə edin.

## Lisenziya
MIT — bax: `LICENSE`.

---

İstənilən rəy və təklifə açığam. Beta test və ya əməkdaşlıq üçün DM yazın. 🚀
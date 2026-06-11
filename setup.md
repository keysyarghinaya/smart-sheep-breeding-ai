# DombaKu – Panduan Setup Raspberry Pi
## Struktur Direktori

```
camera-app/
├── app.py
├── history.json          ← dibuat otomatis saat pertama scan
├── captures/             ← foto hasil scan tersimpan di sini
└── templates/
    ├── base.html
    ├── login.html
    ├── dashboard.html
    ├── kamera.html
    └── histori.html
```

---

## 1. Install Dependencies Python

Jalankan perintah berikut satu per satu di terminal Raspberry Pi:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install OpenCV (lebih cepat dari pip)
sudo apt install -y python3-opencv

# Install Flask
pip3 install flask

# Install EasyOCR (untuk baca ear tag)
pip3 install easyocr

# Jika easyocr butuh torch (bisa lama, ~15 menit di RPi):
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

> **Catatan:** EasyOCR akan download model ~100MB saat pertama kali dipakai.
> Pastikan Raspberry Pi terhubung internet saat pertama run.

---

## 2. Cek Kamera

```bash
# Pastikan webcam terdeteksi
ls /dev/video*
# Seharusnya muncul /dev/video0

# Test capture manual
fswebcam -r 1280x720 test.jpg
```

---

## 3. Jalankan Aplikasi

```bash
cd ~/camera-app
python3 app.py
```

Kemudian buka browser di Raspberry Pi dan akses:
```
http://localhost:5000
```

**Login demo:**
- Email    : `admin@dombaku.com`
- Password : `dombaku123`

---

## 4. Akses dari Komputer Lain (di jaringan yang sama)

Cari IP Raspberry Pi:
```bash
hostname -I
```

Lalu buka dari browser komputer/HP:
```
http://<IP-RaspberryPi>:5000
```

---

## 5. Autostart saat Boot (Opsional)

```bash
# Buat service systemd
sudo nano /etc/systemd/system/dombaku.service
```

Isi file:
```ini
[Unit]
Description=DombaKu Camera App
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/camera-app/app.py
WorkingDirectory=/home/pi/camera-app
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable dombaku
sudo systemctl start dombaku
```

---

## 6. Tips Optimasi OCR Ear Tag

Untuk hasil OCR yang lebih akurat pada ear tag domba:
- Jarak kamera ke ear tag ideal: **15–30 cm**
- Pastikan **pencahayaan cukup** (hindari backlight)
- Posisikan ear tag **tegak lurus** menghadap kamera
- Gunakan **mode capture** saat domba diam, bukan saat bergerak

---

## 7. Langkah Selanjutnya (TODO)

- [ ] Integrasi Firebase (ganti hardcode login dengan Firebase Auth)
- [ ] Kirim data hasil OCR ke Firestore
- [ ] Integrasi AI rekomendasi kawin (endpoint di `record["ai_result"]`)
- [ ] Optimasi resolusi capture untuk OCR (crop area ear tag)
- [ ] Touchscreen support (sudah finger-friendly, tinggal hubungkan kabel)

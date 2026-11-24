# Lost & Found Fasilkom UI (Backend Flask)

## Cara menjalankan
1. Pastikan Python 3.9+ terpasang.
2. Buka terminal di folder proyek ini, lalu (disarankan) buat virtual environment:
   - Windows : `python -m venv venv` lalu `venv\Scripts\activate`
   - Mac/Linux: `python3 -m venv venv` lalu `source venv/bin/activate`
3. Pasang dependensi: `pip install -r requirements.txt`
4. Jalankan: `python app.py`
5. Buka http://127.0.0.1:5000

Database `lostfound.db` dan akun admin dibuat otomatis saat pertama dijalankan.
Login admin awal: username `admin`, password `admin123` (ubah di config.py / environment variable).
Untuk mereset data, hentikan server dan hapus file `lostfound.db`.

## Struktur
- app.py          : membuat aplikasi, mendaftarkan blueprint, membuat tabel & admin awal
- config.py       : pengaturan (secret key, database, upload, admin awal)
- models.py       : tabel Item, Claim, Admin
- utils.py        : upload foto & decorator admin_required
- routes/public.py: Create, Read, Claim (mahasiswa)
- routes/admin.py : login, dashboard, Update, Delete, review klaim (admin)
- templates/      : HTML (Jinja2), templates/admin untuk halaman admin
- uploads/        : foto yang diunggah (di luar static, disajikan lewat route /photo/<id>)
- matching.py     : smart auto-matching Lost -> Found

## Daftar route
| URL | Method | Fungsi |
|---|---|---|
| / | GET | Daftar laporan + cari/filter (q, type, location, date, status) |
| /items/<id> | GET | Detail barang |
| /report | GET, POST | Buat laporan Lost/Found (kategori, apresiasi) |
| /photo/<id> | GET | Foto barang (buram untuk Dokumen/ID bagi non-admin) |
| /claim | GET, POST | Ajukan klaim |
| /admin/login, /admin/logout | GET/POST, GET | Autentikasi admin |
| /admin/ | GET | Dashboard (jumlah Pending/Published/Claimed) |
| /admin/items | GET | Kelola barang (filter ?status=) |
| /admin/items/<id>/edit | GET, POST | Edit laporan & status |
| /admin/items/<id>/status | POST | Ubah status cepat |
| /admin/items/<id>/delete | POST | Hapus laporan |
| /admin/claims | GET | Daftar klaim |
| /admin/claims/<id>/approve atau reject | POST | Tinjau klaim |

## Upgrade dari versi sebelumnya
- Kolom baru (category, priority, reward_note) ditambahkan otomatis ke lostfound.db saat app dijalankan; data lama aman (kategori lama = Lainnya).
- Folder foto pindah dari static/uploads ke uploads/. Salin foto lama ke folder uploads/ agar tetap tampil.
- Jalankan `pip install -r requirements.txt` lagi (ada tambahan Pillow).

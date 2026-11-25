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

## Struktur
- app.py          : membuat aplikasi, migrasi database otomatis, akun admin awal
- config.py       : pengaturan (secret key, database, upload, admin awal)
- models.py       : tabel Item, Claim, Admin + konstanta (kategori, lokasi, posisi barang, prioritas)
- matching.py     : smart auto-matching Lost -> Found
- utils.py        : upload foto, privacy blur, decorator admin_required
- routes/public.py: Create, Read, Claim, Photo (mahasiswa)
- routes/admin.py : login, dashboard, Update, Delete, review klaim (admin)
- templates/      : HTML (Jinja2); _macros.html berisi badge & kartu barang
- uploads/        : foto yang diunggah (disajikan lewat /photo/<id>)

## Aturan penting
- Prioritas High otomatis untuk kategori Dokumen/ID, Elektronik, Dompet (ubah di HIGH_PRIORITY_CATEGORIES, models.py).
- Foto kategori Dokumen/ID diburamkan di server untuk publik (jelas untuk admin / klaim disetujui).
- Lokasi memakai dropdown (LOCATIONS di models.py) + detail lokasi opsional.
- Posisi barang (Dipegang Penemu / Dititipkan di Pos Satpam) hanya untuk laporan Found; admin bisa mengubahnya di halaman edit.

## Upgrade dari versi sebelumnya (tanpa menghapus lostfound.db)
Saat `python app.py` dijalankan, otomatis:
- kolom baru `location_detail` dan `storage_status` ditambahkan;
- lokasi teks bebas lama diubah menjadi pilihan dropdown (teks aslinya disimpan di detail lokasi; yang tidak dikenali menjadi "Lainnya");
- laporan Found lama diberi posisi "Dipegang Penemu";
- prioritas dihitung ulang dari kategori dengan aturan baru;
- kolom lama `reward_note` dibiarkan di database (tidak dipakai, tidak menimbulkan error).

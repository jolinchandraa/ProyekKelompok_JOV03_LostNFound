"""
config.py
Berisi semua pengaturan aplikasi di satu tempat supaya mudah diubah.
"""
import os

# Folder tempat file ini berada (dipakai untuk membuat path absolut)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Kunci rahasia untuk menandatangani session (login admin) dan flash message.
    # GANTI nilai ini saat dikumpulkan/dipakai sungguhan.
    SECRET_KEY = os.environ.get("SECRET_KEY", "ganti-dengan-kunci-rahasia-kelompok")

    # Lokasi file database SQLite (akan dibuat otomatis: lostfound.db)
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "lostfound.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Pengaturan upload foto
    # Folder upload SENGAJA di luar "static" agar foto tidak bisa dibuka langsung lewat URL.
    # Semua foto disajikan lewat route /photo/<id> yang memeriksa hak akses (lihat routes/public.py).
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # batas ukuran upload: 5 MB

    # Akun admin awal (dibuat otomatis jika belum ada di database)
    DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

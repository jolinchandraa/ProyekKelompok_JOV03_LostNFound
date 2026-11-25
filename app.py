"""
app.py
Titik masuk aplikasi. Menjalankan: python app.py
"""
import os
from flask import Flask
from sqlalchemy import inspect, text
from config import Config
from models import (db, Admin, Item, LOCATIONS, TYPE_FOUND, STORAGE_FINDER,
                    priority_for_category, split_legacy_location)
from utils import photo_is_blurred


def add_missing_columns():
    """
    Migrasi otomatis bagian 1: menambahkan kolom baru ke tabel 'items' jika database lama
    belum memilikinya. db.create_all() hanya membuat tabel BARU, tidak menambah kolom ke
    tabel yang sudah ada, jadi kita lakukan ALTER TABLE sendiri.

    Catatan: kolom lama 'reward_note' (fitur apresiasi yang sudah dihapus) SENGAJA dibiarkan
    di database. Kolom itu bersifat nullable dan tidak lagi dipakai model, jadi tidak
    menimbulkan error, dan data lama tetap aman (tidak ada DROP COLUMN).
    """
    existing = {col["name"] for col in inspect(db.engine).get_columns("items")}
    new_columns = {
        "category": "VARCHAR(30) NOT NULL DEFAULT 'Lainnya'",
        "priority": "VARCHAR(10) NOT NULL DEFAULT 'normal'",
        "location_detail": "VARCHAR(150)",
        "storage_status": "VARCHAR(20)",
    }
    with db.engine.begin() as conn:
        for name, definition in new_columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE items ADD COLUMN {name} {definition}"))


def sync_legacy_data():
    """
    Migrasi otomatis bagian 2: menyesuaikan ISI data lama dengan aturan terbaru.
    Aman dijalankan berulang kali (hasilnya sama, tidak merusak data):
      - lokasi teks bebas -> pilihan dropdown + detail (teks asli disimpan di detail)
      - laporan Found tanpa posisi penyimpanan -> 'Dipegang Penemu'; laporan Lost -> kosong
      - prioritas dihitung ulang dari kategori (aturan High: Dokumen/ID, Elektronik, Dompet)
    """
    for item in Item.query.all():
        if item.location not in LOCATIONS:
            item.location, detail = split_legacy_location(item.location)
            if detail and not item.location_detail:
                item.location_detail = detail

        if item.report_type == TYPE_FOUND:
            if not item.storage_status:
                item.storage_status = STORAGE_FINDER
        else:
            item.storage_status = None

        item.priority = priority_for_category(item.category)
    db.session.commit()


def create_app():
    """Application factory: membuat dan mengatur objek Flask."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Pastikan folder upload ada
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Hubungkan SQLAlchemy ke aplikasi
    db.init_app(app)

    # Daftarkan fungsi bantu agar bisa dipanggil langsung di template Jinja
    app.jinja_env.globals["photo_is_blurred"] = photo_is_blurred

    # Daftarkan blueprint (kumpulan route)
    from routes.public import public_bp
    from routes.admin import admin_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    # Buat tabel, migrasi database lama, dan buat akun admin awal
    with app.app_context():
        db.create_all()
        add_missing_columns()
        sync_legacy_data()
        if not Admin.query.filter_by(username=app.config["DEFAULT_ADMIN_USERNAME"]).first():
            admin = Admin(username=app.config["DEFAULT_ADMIN_USERNAME"])
            admin.set_password(app.config["DEFAULT_ADMIN_PASSWORD"])
            db.session.add(admin)
            db.session.commit()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)  # debug=True hanya untuk pengembangan

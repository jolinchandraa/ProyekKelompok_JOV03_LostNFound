"""
app.py
Titik masuk aplikasi. Menjalankan: python app.py
"""
import os
from flask import Flask
from sqlalchemy import inspect, text
from config import Config
from models import db, Admin
from utils import photo_is_blurred


def add_missing_columns():
    """
    Migrasi sederhana: menambahkan kolom baru ke tabel 'items' jika database lama
    (dibuat sebelum fitur kategori/prioritas/apresiasi) belum memilikinya.
    db.create_all() hanya membuat tabel BARU, tidak menambah kolom ke tabel yang sudah ada,
    jadi kita lakukan ALTER TABLE sendiri. Data lama tetap aman.
    """
    existing = {col["name"] for col in inspect(db.engine).get_columns("items")}
    new_columns = {
        "category": "VARCHAR(30) NOT NULL DEFAULT 'Lainnya'",
        "priority": "VARCHAR(10) NOT NULL DEFAULT 'normal'",
        "reward_note": "VARCHAR(50)",
    }
    with db.engine.begin() as conn:
        for name, definition in new_columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE items ADD COLUMN {name} {definition}"))


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

    # Buat tabel, tambahkan kolom baru bila perlu, dan buat akun admin awal
    with app.app_context():
        db.create_all()
        add_missing_columns()
        if not Admin.query.filter_by(username=app.config["DEFAULT_ADMIN_USERNAME"]).first():
            admin = Admin(username=app.config["DEFAULT_ADMIN_USERNAME"])
            admin.set_password(app.config["DEFAULT_ADMIN_PASSWORD"])
            db.session.add(admin)
            db.session.commit()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)  # debug=True hanya untuk pengembangan

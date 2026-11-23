"""
app.py
Titik masuk aplikasi. Menjalankan: python app.py
"""
import os
from flask import Flask
from config import Config
from models import db, Admin


def create_app():
    """Application factory: membuat dan mengatur objek Flask."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Pastikan folder upload ada
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Hubungkan SQLAlchemy ke aplikasi
    db.init_app(app)

    # Daftarkan blueprint (kumpulan route)
    from routes.public import public_bp
    from routes.admin import admin_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    # Buat semua tabel + akun admin awal jika belum ada
    with app.app_context():
        db.create_all()
        if not Admin.query.filter_by(username=app.config["DEFAULT_ADMIN_USERNAME"]).first():
            admin = Admin(username=app.config["DEFAULT_ADMIN_USERNAME"])
            admin.set_password(app.config["DEFAULT_ADMIN_PASSWORD"])
            db.session.add(admin)
            db.session.commit()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)  # debug=True hanya untuk pengembangan

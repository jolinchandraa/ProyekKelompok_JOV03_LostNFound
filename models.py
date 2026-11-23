"""
models.py
Definisi tabel database memakai SQLAlchemy (ORM).
Satu class = satu tabel. Satu atribut db.Column = satu kolom.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Objek db dibuat di sini, lalu dihubungkan ke aplikasi di app.py (db.init_app)
db = SQLAlchemy()

# Konstanta supaya tidak salah ketik string di banyak tempat
STATUS_PENDING = "pending"      # baru dilaporkan, menunggu persetujuan admin
STATUS_PUBLISHED = "published"  # sudah disetujui, tampil untuk publik
STATUS_CLAIMED = "claimed"      # sudah diklaim & dikembalikan ke pemilik
ALL_STATUSES = [STATUS_PENDING, STATUS_PUBLISHED, STATUS_CLAIMED]

TYPE_LOST = "lost"    # laporan barang hilang
TYPE_FOUND = "found"  # laporan barang ditemukan


class Item(db.Model):
    """Tabel laporan barang (Lost maupun Found)."""
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(10), nullable=False)       # 'lost' / 'found'
    name = db.Column(db.String(120), nullable=False)             # nama barang
    description = db.Column(db.Text, nullable=False)             # deskripsi barang
    location = db.Column(db.String(150), nullable=False)         # lokasi terakhir terlihat / ditemukan
    event_date = db.Column(db.Date, nullable=False)              # tanggal terakhir terlihat / ditemukan
    photo_filename = db.Column(db.String(255), nullable=True)    # nama file foto (opsional)
    reporter_name = db.Column(db.String(120), nullable=False)    # nama pelapor
    reporter_contact = db.Column(db.String(120), nullable=False) # kontak pelapor
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relasi satu-ke-banyak: satu barang bisa punya banyak klaim.
    # cascade="all, delete-orphan" -> kalau barang dihapus, klaimnya ikut terhapus.
    claims = db.relationship("Claim", backref="item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Item {self.id} {self.report_type} {self.name}>"


class Claim(db.Model):
    """Tabel pengajuan klaim atas barang yang ditemukan."""
    __tablename__ = "claims"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    claimant_name = db.Column(db.String(120), nullable=False)    # nama lengkap pengklaim
    contact = db.Column(db.String(120), nullable=False)          # kontak pengklaim
    message = db.Column(db.Text, nullable=False)                 # bukti kepemilikan
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending/approved/rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Admin(db.Model):
    """Tabel akun admin. Password disimpan dalam bentuk hash, bukan teks asli."""
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        """Mengubah password biasa menjadi hash sebelum disimpan."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Membandingkan password yang diketik dengan hash di database."""
        return check_password_hash(self.password_hash, password)

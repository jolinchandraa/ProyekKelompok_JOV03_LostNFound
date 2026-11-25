"""
models.py
Definisi tabel database memakai SQLAlchemy (ORM).
Satu class = satu tabel. Satu atribut db.Column = satu kolom.
"""
from datetime import datetime, timedelta
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

# ---- Kategori barang ----
CATEGORY_DOCUMENT = "Dokumen/ID"
CATEGORY_FOOD = "Makanan"
CATEGORIES = ["Elektronik", CATEGORY_DOCUMENT, "Dompet", "Pakaian", CATEGORY_FOOD, "Lainnya"]

# ---- Prioritas ----
# Dokumen/ID, Elektronik, dan Dompet dianggap mendesak (bernilai tinggi / dibutuhkan segera).
PRIORITY_HIGH = "high"
PRIORITY_NORMAL = "normal"
HIGH_PRIORITY_CATEGORIES = {CATEGORY_DOCUMENT, "Elektronik", "Dompet"}

# Laporan dianggap "baru" selama sekian hari sejak dibuat
NEW_ITEM_DAYS = 3

# ---- Pilihan lokasi (dropdown seragam) ----
LOCATION_OTHER = "Lainnya"
LOCATIONS = ["Perpustakaan", "Kantin", "Lantai 1", "Lantai 2", "Lantai 3", "Lantai 4",
             "Lantai 5", "Lantai 6", "Lantai 7", "Parkiran", "Mushola", "Stulo", LOCATION_OTHER]

# ---- Posisi penyimpanan barang (khusus laporan Found) ----
STORAGE_FINDER = "finder"      # masih dipegang penemu
STORAGE_SECURITY = "security"  # sudah dititipkan ke pos satpam
STORAGE_OPTIONS = {STORAGE_FINDER: "Dipegang Penemu",
                   STORAGE_SECURITY: "Dititipkan di Pos Satpam"}


def priority_for_category(category):
    """Prioritas ditentukan otomatis dari kategori: High untuk Dokumen/ID, Elektronik, Dompet."""
    return PRIORITY_HIGH if category in HIGH_PRIORITY_CATEGORIES else PRIORITY_NORMAL


def split_legacy_location(old_text):
    """
    Dipakai saat migrasi data lama yang lokasinya masih teks bebas (mis. "Kantin Fasilkom").
    Mengembalikan (pilihan_dropdown, detail):
      - jika teks mengandung nama lokasi baku (mis. "kantin"), pakai lokasi itu
      - jika tidak, pakai "Lainnya"
      - teks aslinya disimpan sebagai detail agar informasinya tidak hilang
    """
    cleaned = (old_text or "").strip()
    lowered = cleaned.lower()
    chosen = LOCATION_OTHER
    for loc in LOCATIONS:
        if loc != LOCATION_OTHER and loc.lower() in lowered:
            chosen = loc
            break
    detail = None if lowered == chosen.lower() else (cleaned or None)
    return chosen, detail


class Item(db.Model):
    """Tabel laporan barang (Lost maupun Found)."""
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(10), nullable=False)       # 'lost' / 'found'
    name = db.Column(db.String(120), nullable=False)             # nama barang
    description = db.Column(db.Text, nullable=False)             # deskripsi barang
    location = db.Column(db.String(150), nullable=False)         # pilihan dropdown (lihat LOCATIONS)
    location_detail = db.Column(db.String(150), nullable=True)   # detail lokasi opsional (ruang, meja, dll.)
    event_date = db.Column(db.Date, nullable=False)              # tanggal terakhir terlihat / ditemukan
    photo_filename = db.Column(db.String(255), nullable=True)    # nama file foto (opsional)
    category = db.Column(db.String(30), nullable=False, default="Lainnya")        # lihat CATEGORIES
    priority = db.Column(db.String(10), nullable=False, default=PRIORITY_NORMAL)  # 'high' / 'normal'
    # Khusus laporan Found: 'finder' atau 'security'. Untuk laporan Lost nilainya None.
    storage_status = db.Column(db.String(20), nullable=True)
    reporter_name = db.Column(db.String(120), nullable=False)    # nama pelapor
    reporter_contact = db.Column(db.String(120), nullable=False) # kontak pelapor
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relasi satu-ke-banyak: satu barang bisa punya banyak klaim.
    # cascade="all, delete-orphan" -> kalau barang dihapus, klaimnya ikut terhapus.
    claims = db.relationship("Claim", backref="item", cascade="all, delete-orphan")

    # ---- Properti bantu (dipakai di route & template) ----
    @property
    def is_high_priority(self):
        """True jika prioritas High/Urgent."""
        return self.priority == PRIORITY_HIGH

    @property
    def is_new(self):
        """True jika laporan dibuat dalam NEW_ITEM_DAYS hari terakhir."""
        return (self.created_at is not None and
                self.created_at >= datetime.utcnow() - timedelta(days=NEW_ITEM_DAYS))

    @property
    def is_sensitive(self):
        """True jika fotonya perlu disamarkan di halaman publik (kategori Dokumen/ID)."""
        return self.category == CATEGORY_DOCUMENT

    @property
    def location_display(self):
        """Lokasi untuk ditampilkan: 'Kantin (dekat meja 5)' atau 'Kantin' jika tanpa detail."""
        if self.location_detail:
            return f"{self.location} ({self.location_detail})"
        return self.location

    @property
    def storage_label(self):
        """Teks posisi barang untuk laporan Found, mis. 'Dititipkan di Pos Satpam'. None untuk Lost."""
        if self.report_type != TYPE_FOUND:
            return None
        return STORAGE_OPTIONS.get(self.storage_status)

    @property
    def has_approved_claim(self):
        """True jika sudah ada klaim yang disetujui admin untuk barang ini."""
        return any(c.status == "approved" for c in self.claims)

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

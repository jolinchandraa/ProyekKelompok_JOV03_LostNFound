"""
routes/public.py
Route untuk mahasiswa (tanpa login):
  - Read   : daftar + pencarian + filter, detail barang
  - Create : lapor barang hilang / ditemukan
  - Claim  : ajukan klaim untuk barang yang ditemukan
"""
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort, session)
from sqlalchemy import or_
from models import (db, Item, Claim, STATUS_PENDING, STATUS_PUBLISHED,
                    STATUS_CLAIMED, TYPE_LOST, TYPE_FOUND)
from utils import save_photo, allowed_file

public_bp = Blueprint("public", __name__)


def parse_date(text):
    """Mengubah teks 'YYYY-MM-DD' (format input type=date) menjadi objek date. None jika salah."""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- READ (daftar)
@public_bp.route("/")
def index():
    """
    Halaman utama: daftar laporan yang sudah dipublikasikan.
    Parameter query string (semua opsional):
      q        -> kata kunci (nama/deskripsi)
      type     -> 'lost' atau 'found'
      location -> sebagian nama lokasi
      date     -> tanggal kejadian (YYYY-MM-DD)
      status   -> 'published' atau 'claimed'
    Laporan berstatus 'pending' TIDAK ditampilkan ke publik.
    """
    query = Item.query.filter(Item.status.in_([STATUS_PUBLISHED, STATUS_CLAIMED]))

    q = request.args.get("q", "").strip()
    report_type = request.args.get("type", "").strip()
    location = request.args.get("location", "").strip()
    date_str = request.args.get("date", "").strip()
    status = request.args.get("status", "").strip()

    if q:  # cari di nama ATAU deskripsi (ilike = tidak peka huruf besar/kecil)
        like = f"%{q}%"
        query = query.filter(or_(Item.name.ilike(like), Item.description.ilike(like)))
    if report_type in (TYPE_LOST, TYPE_FOUND):
        query = query.filter(Item.report_type == report_type)
    if location:
        query = query.filter(Item.location.ilike(f"%{location}%"))
    if date_str and parse_date(date_str):
        query = query.filter(Item.event_date == parse_date(date_str))
    if status in (STATUS_PUBLISHED, STATUS_CLAIMED):
        query = query.filter(Item.status == status)

    items = query.order_by(Item.event_date.desc(), Item.id.desc()).all()
    return render_template("index.html", items=items)


# ---------------------------------------------------------------- READ (detail)
@public_bp.route("/items/<int:item_id>")
def detail(item_id):
    """Detail satu barang. Barang 'pending' hanya boleh dilihat admin."""
    item = db.get_or_404(Item, item_id)
    if item.status == STATUS_PENDING and "admin_id" not in session:
        abort(404)
    return render_template("item_detail.html", item=item)


# ---------------------------------------------------------------- CREATE
@public_bp.route("/report", methods=["GET", "POST"])
def report():
    """
    Form laporan baru. GET = tampilkan form, POST = simpan data.
    Laporan baru otomatis berstatus 'pending' sampai disetujui admin.
    """
    if request.method == "POST":
        report_type = request.form.get("report_type", "")
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        event_date = parse_date(request.form.get("event_date", ""))
        reporter_name = request.form.get("reporter_name", "").strip()
        reporter_contact = request.form.get("reporter_contact", "").strip()
        photo = request.files.get("photo")

        # Validasi sederhana di sisi server
        errors = []
        if report_type not in (TYPE_LOST, TYPE_FOUND):
            errors.append("Jenis laporan harus Lost atau Found.")
        if not (name and description and location and reporter_name and reporter_contact):
            errors.append("Semua kolom bertanda * wajib diisi.")
        if event_date is None:
            errors.append("Tanggal tidak valid.")
        elif event_date > datetime.now().date():
            errors.append("Tanggal tidak boleh di masa depan.")
        if photo and photo.filename and not allowed_file(photo.filename):
            errors.append("Format foto harus png, jpg, jpeg, gif, atau webp.")

        if errors:
            for e in errors:
                flash(e, "danger")
            # kirim balik isian lama supaya pengguna tidak mengetik ulang
            return render_template("report_form.html", form=request.form), 400

        item = Item(
            report_type=report_type, name=name, description=description,
            location=location, event_date=event_date,
            photo_filename=save_photo(photo),
            reporter_name=reporter_name, reporter_contact=reporter_contact,
            status=STATUS_PENDING,
        )
        db.session.add(item)
        db.session.commit()
        flash("Laporan terkirim! Laporan akan tampil setelah disetujui admin.", "success")
        return redirect(url_for("public.index"))

    return render_template("report_form.html", form={})


# ---------------------------------------------------------------- CLAIM
@public_bp.route("/claim", methods=["GET", "POST"])
def claim():
    """
    Form klaim barang. Field: Item ID, nama lengkap, kontak, pesan bukti.
    Hanya barang 'found' yang berstatus 'published' yang bisa diklaim.
    Klaim masuk dengan status 'pending' untuk ditinjau admin.
    """
    if request.method == "POST":
        item_id = request.form.get("item_id", type=int)
        claimant_name = request.form.get("claimant_name", "").strip()
        contact = request.form.get("contact", "").strip()
        message = request.form.get("message", "").strip()

        item = db.session.get(Item, item_id) if item_id else None

        if not (item_id and claimant_name and contact and message):
            flash("Semua kolom wajib diisi.", "danger")
        elif item is None:
            flash("Item ID tidak ditemukan.", "danger")
        elif item.report_type != TYPE_FOUND:
            flash("Hanya barang yang ditemukan (Found) yang dapat diklaim.", "danger")
        elif item.status != STATUS_PUBLISHED:
            flash("Barang ini belum dipublikasikan atau sudah diklaim.", "danger")
        else:
            db.session.add(Claim(item_id=item.id, claimant_name=claimant_name,
                                 contact=contact, message=message))
            db.session.commit()
            flash("Klaim terkirim. Admin akan meninjau bukti yang kamu berikan.", "success")
            return redirect(url_for("public.detail", item_id=item.id))
        return render_template("claim_form.html", form=request.form), 400

    # GET: Item ID bisa terisi otomatis dari link /claim?item_id=3
    return render_template("claim_form.html", form={"item_id": request.args.get("item_id", "")})

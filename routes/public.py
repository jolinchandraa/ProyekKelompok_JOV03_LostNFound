"""
routes/public.py
Route untuk mahasiswa (tanpa login):
  - Read   : daftar + pencarian + filter + prioritas, detail + auto-matching
  - Create : lapor barang hilang / ditemukan (kategori, lokasi dropdown, posisi barang Found)
  - Claim  : ajukan klaim untuk barang yang ditemukan
  - Photo  : menyajikan foto (dengan privacy blur untuk Dokumen/ID)
"""
import os
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort, session, current_app, send_from_directory)
from sqlalchemy import or_, case
from models import (db, Item, Claim, STATUS_PENDING, STATUS_PUBLISHED, STATUS_CLAIMED,
                    TYPE_LOST, TYPE_FOUND, CATEGORIES, LOCATIONS, STORAGE_OPTIONS,
                    HIGH_PRIORITY_CATEGORIES, PRIORITY_HIGH, NEW_ITEM_DAYS,
                    priority_for_category)
from utils import save_photo, allowed_file, photo_is_blurred, blurred_photo_response
from matching import find_matches

public_bp = Blueprint("public", __name__)


def parse_date(text):
    """Mengubah teks 'YYYY-MM-DD' (format input type=date) menjadi objek date. None jika salah."""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def report_form_context():
    """Data pilihan (dropdown) yang dibutuhkan templat report_form.html."""
    return dict(categories=CATEGORIES, locations=LOCATIONS,
                storage_options=STORAGE_OPTIONS,
                high_categories=sorted(HIGH_PRIORITY_CATEGORIES))


# ---------------------------------------------------------------- READ (daftar)
@public_bp.route("/")
def index():
    """
    Halaman utama: daftar laporan yang sudah dipublikasikan + pencarian & filter.

    Parameter query string (semua opsional, bisa dikombinasikan):
      q        -> kata kunci; tiap kata harus cocok di nama/deskripsi/lokasi/detail lokasi
      type     -> 'lost' atau 'found'
      category -> salah satu dari CATEGORIES
      location -> salah satu dari LOCATIONS (pilihan dropdown)
      date     -> tanggal kejadian (YYYY-MM-DD)
      status   -> 'published' atau 'claimed'

    Urutan tampilan (diprioritaskan):
      1. laporan yang belum diklaim lebih dulu dari yang sudah Claimed
      2. prioritas High/Urgent lebih dulu
      3. laporan baru (<= NEW_ITEM_DAYS hari) lebih dulu
      4. tanggal kejadian terbaru, lalu ID terbaru
    Laporan berstatus 'pending' TIDAK pernah ditampilkan ke publik.
    """
    query = Item.query.filter(Item.status.in_([STATUS_PUBLISHED, STATUS_CLAIMED]))

    q = request.args.get("q", "").strip()
    report_type = request.args.get("type", "").strip()
    category = request.args.get("category", "").strip()
    location = request.args.get("location", "").strip()
    date_str = request.args.get("date", "").strip()
    status = request.args.get("status", "").strip()

    # --- Pencarian kata kunci (tiap kata harus ada di salah satu kolom) ---
    for word in q.split():
        like = f"%{word}%"
        query = query.filter(or_(Item.name.ilike(like),
                                 Item.description.ilike(like),
                                 Item.location.ilike(like),
                                 Item.location_detail.ilike(like)))

    # --- Filter ---
    if report_type in (TYPE_LOST, TYPE_FOUND):
        query = query.filter(Item.report_type == report_type)
    if category in CATEGORIES:
        query = query.filter(Item.category == category)
    if location in LOCATIONS:
        query = query.filter(Item.location == location)
    event_date = parse_date(date_str)
    if event_date:
        query = query.filter(Item.event_date == event_date)
    if status in (STATUS_PUBLISHED, STATUS_CLAIMED):
        query = query.filter(Item.status == status)

    # --- Pengurutan berprioritas ---
    # case((kondisi, nilai), else_=nilai): angka lebih kecil = tampil lebih dulu
    new_cutoff = datetime.utcnow() - timedelta(days=NEW_ITEM_DAYS)
    items = query.order_by(
        case((Item.status == STATUS_CLAIMED, 1), else_=0),
        case((Item.priority == PRIORITY_HIGH, 0), else_=1),
        case((Item.created_at >= new_cutoff, 0), else_=1),
        Item.event_date.desc(),
        Item.id.desc(),
    ).all()

    filters = {"q": q, "type": report_type, "category": category,
               "location": location, "date": date_str, "status": status}
    return render_template("index.html", items=items, filters=filters,
                           locations=LOCATIONS, categories=CATEGORIES,
                           filters_active=any(filters.values()))


# ---------------------------------------------------------------- READ (detail)
@public_bp.route("/items/<int:item_id>")
def detail(item_id):
    """
    Detail satu barang. Barang 'pending' hanya boleh dilihat admin.
    Untuk laporan LOST yang belum selesai, sistem menampilkan rekomendasi
    laporan FOUND yang mirip (smart auto-matching, lihat matching.py).
    """
    item = db.get_or_404(Item, item_id)
    if item.status == STATUS_PENDING and "admin_id" not in session:
        abort(404)

    matches = []
    if item.report_type == TYPE_LOST and item.status != STATUS_CLAIMED:
        matches = find_matches(item)
    return render_template("item_detail.html", item=item, matches=matches)


# ---------------------------------------------------------------- PHOTO
@public_bp.route("/photo/<int:item_id>")
def photo(item_id):
    """
    Menyajikan foto barang. Semua gambar lewat sini (bukan folder static) agar
    hak akses diperiksa di server:
      - foto laporan 'pending' hanya untuk admin
      - foto Dokumen/ID dikirim dalam versi buram kecuali untuk admin / klaim disetujui
    """
    item = db.get_or_404(Item, item_id)
    if not item.photo_filename:
        abort(404)
    if item.status == STATUS_PENDING and "admin_id" not in session:
        abort(404)

    folder = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(folder, item.photo_filename)
    if not os.path.exists(path):
        abort(404)

    if photo_is_blurred(item):
        return blurred_photo_response(path)
    return send_from_directory(folder, item.photo_filename)


# ---------------------------------------------------------------- CREATE
@public_bp.route("/report", methods=["GET", "POST"])
def report():
    """
    Form laporan baru. GET = tampilkan form, POST = simpan data.
    Laporan baru otomatis berstatus 'pending' sampai disetujui admin.
    Prioritas diisi otomatis dari kategori. Posisi penyimpanan hanya berlaku untuk laporan Found.
    """
    if request.method == "POST":
        report_type = request.form.get("report_type", "")
        category = request.form.get("category", "")
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "")
        location_detail = request.form.get("location_detail", "").strip()[:150]
        storage_status = request.form.get("storage_status", "")
        event_date = parse_date(request.form.get("event_date", ""))
        reporter_name = request.form.get("reporter_name", "").strip()
        reporter_contact = request.form.get("reporter_contact", "").strip()
        photo_file = request.files.get("photo")

        errors = []
        if report_type not in (TYPE_LOST, TYPE_FOUND):
            errors.append("Jenis laporan harus Lost atau Found.")
        if category not in CATEGORIES:
            errors.append("Pilih kategori barang.")
        if location not in LOCATIONS:
            errors.append("Pilih lokasi dari daftar.")
        if report_type == TYPE_FOUND and storage_status not in STORAGE_OPTIONS:
            errors.append("Pilih posisi barang (dipegang penemu atau di pos satpam).")
        if not (name and description and reporter_name and reporter_contact):
            errors.append("Semua kolom bertanda * wajib diisi.")
        if event_date is None:
            errors.append("Tanggal tidak valid.")
        elif event_date > datetime.now().date():
            errors.append("Tanggal tidak boleh di masa depan.")
        if photo_file and photo_file.filename and not allowed_file(photo_file.filename):
            errors.append("Format foto harus png, jpg, jpeg, gif, atau webp.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("report_form.html", form=request.form,
                                   **report_form_context()), 400

        item = Item(
            report_type=report_type, name=name, description=description,
            location=location, location_detail=location_detail or None,
            event_date=event_date,
            category=category,
            priority=priority_for_category(category),   # High: Dokumen/ID, Elektronik, Dompet
            # Posisi penyimpanan hanya untuk Found; Lost selalu None
            storage_status=storage_status if report_type == TYPE_FOUND else None,
            photo_filename=save_photo(photo_file),
            reporter_name=reporter_name, reporter_contact=reporter_contact,
            status=STATUS_PENDING,
        )
        db.session.add(item)
        db.session.commit()
        flash("Laporan terkirim! Laporan akan tampil setelah disetujui admin.", "success")
        return redirect(url_for("public.index"))

    return render_template("report_form.html", form={}, **report_form_context())


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

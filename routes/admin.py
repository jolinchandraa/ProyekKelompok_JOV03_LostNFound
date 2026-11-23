"""
routes/admin.py
Semua route admin (prefix URL: /admin):
  - Authentication : login / logout
  - Dashboard      : ringkasan jumlah Pending / Published / Claimed
  - Update         : edit data laporan & ubah status
  - Delete         : hapus laporan
  - Claims         : tinjau (setujui / tolak) klaim
"""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session)
from sqlalchemy import func
from models import (db, Item, Claim, Admin, ALL_STATUSES, STATUS_PENDING,
                    STATUS_PUBLISHED, STATUS_CLAIMED, TYPE_LOST, TYPE_FOUND)
from utils import admin_required, save_photo, delete_photo, allowed_file
from routes.public import parse_date

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------- AUTH
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """Halaman login admin. Jika cocok, simpan id admin di session."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            session.clear()                  # bersihkan session lama
            session["admin_id"] = admin.id   # tanda bahwa admin sudah login
            flash("Login berhasil.", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Username atau password salah.", "danger")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    """Logout: hapus semua data session."""
    session.clear()
    flash("Kamu sudah logout.", "info")
    return redirect(url_for("admin.login"))


# ---------------------------------------------------------------- DASHBOARD
@admin_bp.route("/")
@admin_required
def dashboard():
    """Menghitung jumlah barang per status + jumlah klaim yang menunggu."""
    # GROUP BY status -> hasil: [('pending', 3), ('published', 5), ...]
    rows = db.session.query(Item.status, func.count(Item.id)).group_by(Item.status).all()
    counts = {s: 0 for s in ALL_STATUSES}  # default 0 agar status kosong tetap tampil
    counts.update(dict(rows))

    pending_claims = Claim.query.filter_by(status="pending").count()
    latest_items = Item.query.order_by(Item.created_at.desc()).limit(5).all()
    return render_template("admin/dashboard.html", counts=counts,
                           pending_claims=pending_claims, latest_items=latest_items)


# ---------------------------------------------------------------- DAFTAR BARANG
@admin_bp.route("/items")
@admin_required
def items():
    """Daftar SEMUA barang (termasuk pending). Bisa difilter ?status=pending dll."""
    status = request.args.get("status", "").strip()
    query = Item.query
    if status in ALL_STATUSES:
        query = query.filter_by(status=status)
    items = query.order_by(Item.created_at.desc()).all()
    return render_template("admin/items.html", items=items, active_status=status)


# ---------------------------------------------------------------- UPDATE
@admin_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_item(item_id):
    """Edit seluruh informasi laporan, termasuk status dan foto."""
    item = db.get_or_404(Item, item_id)

    if request.method == "POST":
        event_date = parse_date(request.form.get("event_date", ""))
        report_type = request.form.get("report_type", "")
        status = request.form.get("status", "")
        photo = request.files.get("photo")

        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()

        if (not (name and description and location) or event_date is None
                or report_type not in (TYPE_LOST, TYPE_FOUND) or status not in ALL_STATUSES):
            flash("Data tidak valid. Periksa kembali isian.", "danger")
            return render_template("admin/edit_item.html", item=item,
                                   statuses=ALL_STATUSES), 400
        if photo and photo.filename and not allowed_file(photo.filename):
            flash("Format foto tidak diperbolehkan.", "danger")
            return render_template("admin/edit_item.html", item=item,
                                   statuses=ALL_STATUSES), 400

        item.name = name
        item.description = description
        item.location = location
        item.event_date = event_date
        item.report_type = report_type
        item.status = status
        item.reporter_name = request.form.get("reporter_name", "").strip() or item.reporter_name
        item.reporter_contact = request.form.get("reporter_contact", "").strip() or item.reporter_contact

        # Jika admin mengunggah foto baru: hapus foto lama, simpan yang baru
        if photo and photo.filename:
            delete_photo(item.photo_filename)
            item.photo_filename = save_photo(photo)
        # Jika admin mencentang "hapus foto"
        elif request.form.get("remove_photo"):
            delete_photo(item.photo_filename)
            item.photo_filename = None

        db.session.commit()
        flash("Laporan berhasil diperbarui.", "success")
        return redirect(url_for("admin.items"))

    return render_template("admin/edit_item.html", item=item, statuses=ALL_STATUSES)


@admin_bp.route("/items/<int:item_id>/status", methods=["POST"])
@admin_required
def change_status(item_id):
    """Ubah status cepat dari tombol (mis. Pending -> Published / Claimed)."""
    item = db.get_or_404(Item, item_id)
    new_status = request.form.get("status", "")
    if new_status not in ALL_STATUSES:
        flash("Status tidak valid.", "danger")
    else:
        item.status = new_status
        db.session.commit()
        flash(f"Status '{item.name}' diubah menjadi {new_status}.", "success")
    return redirect(request.referrer or url_for("admin.items"))


# ---------------------------------------------------------------- DELETE
@admin_bp.route("/items/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_item(item_id):
    """Hapus laporan (POST saja, bukan GET, supaya tidak terhapus karena klik link tak sengaja)."""
    item = db.get_or_404(Item, item_id)
    delete_photo(item.photo_filename)  # hapus file fotonya juga
    db.session.delete(item)            # klaim terkait ikut terhapus (cascade)
    db.session.commit()
    flash("Laporan dihapus.", "info")
    return redirect(url_for("admin.items"))


# ---------------------------------------------------------------- KLAIM
@admin_bp.route("/claims")
@admin_required
def claims():
    """Daftar semua permintaan klaim, yang masih pending ditaruh paling atas."""
    claims = Claim.query.order_by(Claim.created_at.desc()).all()
    # Urutkan stabil: yang 'pending' dulu, urutan terbaru tetap terjaga di tiap kelompok
    claims.sort(key=lambda c: c.status != "pending")
    return render_template("admin/claims.html", claims=claims)


@admin_bp.route("/claims/<int:claim_id>/<action>", methods=["POST"])
@admin_required
def review_claim(claim_id, action):
    """
    Tinjau klaim. action = 'approve' atau 'reject'.
    Jika disetujui: klaim jadi 'approved', barang jadi 'claimed',
    dan klaim pending lain atas barang yang sama otomatis ditolak.
    """
    claim = db.get_or_404(Claim, claim_id)

    if action == "approve":
        claim.status = "approved"
        claim.item.status = STATUS_CLAIMED
        for other in claim.item.claims:
            if other.id != claim.id and other.status == "pending":
                other.status = "rejected"
        flash("Klaim disetujui. Barang ditandai Claimed.", "success")
    elif action == "reject":
        claim.status = "rejected"
        flash("Klaim ditolak.", "info")
    else:
        flash("Aksi tidak dikenal.", "danger")
        return redirect(url_for("admin.claims"))

    db.session.commit()
    return redirect(url_for("admin.claims"))

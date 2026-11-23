"""
utils.py
Fungsi bantu yang dipakai di beberapa route: upload foto & proteksi halaman admin.
"""
import os
import uuid
from functools import wraps
from flask import current_app, session, redirect, url_for, flash


def allowed_file(filename):
    """True jika ekstensi file termasuk yang diperbolehkan (png/jpg/dll)."""
    return ("." in filename and
            filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"])


def save_photo(file):
    """
    Menyimpan foto yang diunggah ke static/uploads.
    Mengembalikan nama file baru, atau None jika tidak ada file / format salah.
    Nama file diganti UUID supaya tidak bentrok dan tidak berbahaya.
    """
    if not file or file.filename == "":
        return None
    if not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit(".", 1)[1].lower()
    new_name = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], new_name))
    return new_name


def delete_photo(filename):
    """Menghapus file foto dari disk (dipakai saat barang dihapus / foto diganti)."""
    if not filename:
        return
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(path):
        os.remove(path)


def admin_required(view):
    """
    Decorator untuk melindungi route admin.
    Jika belum login (tidak ada 'admin_id' di session), pengguna dialihkan ke halaman login.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            flash("Silakan login sebagai admin terlebih dahulu.", "warning")
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped

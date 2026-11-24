"""
matching.py
Smart auto-matching: mencari laporan FOUND yang kemungkinan cocok dengan sebuah laporan LOST.

Cara kerja (sistem poin sederhana, mudah dijelaskan):
  +3  kategori sama (+1 saja jika kategorinya "Lainnya", karena terlalu umum)
  +2  untuk tiap kata kunci yang sama di nama/deskripsi (maksimal 4 kata)
  +2  bonus jika ada kata yang sama di NAMA barang
  +3  lokasi persis sama / +2 jika ada kata lokasi yang sama
  +1  barang ditemukan 0-14 hari setelah tanggal kehilangan
Laporan Found dengan total poin >= MIN_SCORE dianggap kandidat, diurutkan dari poin tertinggi.
"""
import re
from models import Item, TYPE_FOUND, STATUS_PUBLISHED

MIN_SCORE = 3

# Kata umum yang tidak berguna untuk mencocokkan barang
STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "ada", "itu", "ini", "untuk", "dengan", "pada",
    "atau", "saya", "aku", "kami", "milik", "punya", "warna", "barang", "hilang",
    "ditemukan", "ketemu", "terakhir", "dekat", "sekitar", "lantai", "ruang", "the", "and",
}


def tokenize(text):
    """Memecah teks menjadi himpunan kata kunci: huruf kecil, minimal 3 huruf, bukan stopword."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}


def _label(score):
    """Mengubah poin menjadi label yang mudah dibaca pengguna."""
    if score >= 10:
        return "Sangat mirip"
    if score >= 6:
        return "Mirip"
    return "Mungkin cocok"


def find_matches(lost_item, limit=5):
    """
    Mengembalikan daftar kandidat (maksimal `limit`) berupa dict:
      {"item": <Item Found>, "score": int, "label": str, "reasons": [str, ...]}
    Hanya laporan Found yang sudah Published (belum diklaim) yang dipertimbangkan.
    """
    candidates = Item.query.filter_by(report_type=TYPE_FOUND, status=STATUS_PUBLISHED).all()

    lost_name = tokenize(lost_item.name)
    lost_all = lost_name | tokenize(lost_item.description)
    lost_loc_words = tokenize(lost_item.location)
    lost_loc_text = " ".join((lost_item.location or "").lower().split())

    results = []
    for found in candidates:
        score, reasons = 0, []

        # 1) Kategori
        if found.category == lost_item.category:
            score += 1 if found.category == "Lainnya" else 3
            reasons.append(f"kategori sama ({found.category})")

        # 2) Kata kunci di nama + deskripsi
        found_name = tokenize(found.name)
        found_all = found_name | tokenize(found.description)
        shared = sorted(lost_all & found_all)
        if shared:
            score += 2 * min(len(shared), 4)
            reasons.append("kata kunci mirip: " + ", ".join(shared[:4]))
        if lost_name & found_name:
            score += 2  # bonus: namanya saling mirip

        # 3) Lokasi
        found_loc_text = " ".join((found.location or "").lower().split())
        if lost_loc_text and lost_loc_text == found_loc_text:
            score += 3
            reasons.append("lokasi sama")
        elif lost_loc_words & tokenize(found.location):
            score += 2
            reasons.append("lokasi mirip")

        # 4) Tanggal: barang ditemukan setelah (atau pas) hari kehilangan
        days = (found.event_date - lost_item.event_date).days
        if 0 <= days <= 14:
            score += 1
            reasons.append("ditemukan tidak lama setelah kehilangan")

        if score >= MIN_SCORE:
            results.append({"item": found, "score": score,
                            "label": _label(score), "reasons": reasons})

    # Poin tertinggi dulu; kalau seri, yang tanggalnya lebih baru dulu
    results.sort(key=lambda r: (-r["score"], -r["item"].event_date.toordinal()))
    return results[:limit]

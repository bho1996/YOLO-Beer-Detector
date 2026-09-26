"""
Pubblica la "Picture of the Day" per la dashboard.

Gira sul NAS (dove ci sono le foto vere in photo_folder/), sceglie UNA foto
approvata dall'AI del giorno indicato (default: ieri), la ridimensiona,
rimuove i metadati EXIF (GPS ecc.) e la salva in potd/AAAA-MM-GG.jpg.
Aggiorna potd/index.json con autore/ora. Il bot poi fa git add + push.

Solo lettura sul DB. Le foto originali non vengono toccate.

Uso:  python publish_potd.py              -> ieri
      python publish_potd.py 2026-09-26   -> giorno specifico
"""
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "1m_beers.db")
PHOTO_DIR = os.path.join(BASE, "photo_folder")
OUT_DIR = os.path.join(BASE, "potd")
INDEX = os.path.join(OUT_DIR, "index.json")
TZ = ZoneInfo("Europe/Rome")
MAX_SIDE = 1080
KEEP_DAYS = 14          # immagini più vecchie vengono rimosse dal repo (i metadati restano)
WA_RE = re.compile(r"^WA_(\d{9,11})\.jpg$")


def candidates(day):
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT nome_file, TRIM(utente), punti FROM log_birre WHERE tipo_file='foto' AND punti > 0"
    ).fetchall()
    conn.close()
    out = []
    for nome_file, utente, punti in rows:
        m = WA_RE.match(str(nome_file).strip())
        if not m:
            continue
        ts = datetime.datetime.fromtimestamp(int(m.group(1)), TZ)
        if ts.date() == day and os.path.exists(os.path.join(PHOTO_DIR, nome_file.strip())):
            out.append((nome_file.strip(), utente, int(punti), ts))
    return out


def pick(day, cands):
    """Scelta deterministica: stessa foto anche se lo script gira più volte."""
    key = lambda c: hashlib.md5(f"{day}|{c[0]}".encode()).hexdigest()
    return min(cands, key=key)


def main():
    day = (datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
           else datetime.datetime.now(TZ).date() - datetime.timedelta(days=1))
    os.makedirs(OUT_DIR, exist_ok=True)
    index = json.load(open(INDEX)) if os.path.exists(INDEX) else {}

    cands = candidates(day)
    if not cands:
        print(f"POTD: nessuna foto disponibile per {day}")
        return
    nome_file, utente, punti, ts = pick(day, cands)

    img = ImageOps.exif_transpose(Image.open(os.path.join(PHOTO_DIR, nome_file))).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out_name = f"{day.isoformat()}.jpg"
    img.save(os.path.join(OUT_DIR, out_name), "JPEG", quality=80, optimize=True)  # senza EXIF

    index[day.isoformat()] = {
        "image": out_name, "source_file": nome_file, "utente": utente,
        "time": ts.strftime("%H:%M"), "beers": punti, "candidates": len(cands),
    }
    # pulizia immagini vecchie (i metadati restano nell'indice)
    limit = day - datetime.timedelta(days=KEEP_DAYS)
    for d, meta in index.items():
        if datetime.date.fromisoformat(d) < limit and meta.get("image"):
            p = os.path.join(OUT_DIR, meta["image"])
            if os.path.exists(p):
                os.remove(p)
            meta["image"] = None
    with open(INDEX, "w") as f:
        json.dump(dict(sorted(index.items())), f, indent=1, ensure_ascii=False)
    print(f"POTD: {day} -> {nome_file} di {utente} ({len(cands)} candidate)")


if __name__ == "__main__":
    main()

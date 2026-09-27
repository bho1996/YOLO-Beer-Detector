"""
Esporta il DB in un JSON compatto per il frontend web (web/).

- Apre il DB in SOLA LETTURA; nessun dato viene modificato.
- Riusa data_quality.py: le stesse correzioni (date, identità) della dashboard.
- Copia anche le "Picture of the Day" pubblicate (potd/) accanto al JSON.

Uso:  python export_data.py [cartella_output]      (default: web/public)
"""
import json
import os
import shutil
import sqlite3
import sys
import time

import pandas as pd

import data_quality as dq
from countries import get_country, flag_of

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "1m_beers.db")
POTD_DIR = os.path.join(BASE, "potd")
EPOCH = pd.Timestamp("1970-01-01")


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "web", "public")
    os.makedirs(out_dir, exist_ok=True)

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    raw = pd.read_sql_query("SELECT * FROM log_birre", conn)
    row = conn.execute("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'").fetchone()
    conn.close()
    with open(os.path.join(BASE, "nicknames.json"), encoding="utf-8") as f:
        nicknames = json.load(f)

    df, report = dq.prepare(raw, nicknames)
    df = df.dropna(subset=["data_ora_dt"])

    # Utenti (indice compatto)
    users = df.groupby("utente", sort=True)["phone_id"].first().reset_index()
    users["prefix"] = users["phone_id"].astype(str).str.extract(r"^(\+\d+)")[0]
    users["nation"] = users["prefix"].apply(get_country)
    user_idx = {u: i for i, u in enumerate(users["utente"])}

    # Righe in formato colonnare. t = minuti dall'epoch in ORA LOCALE (Europe/Rome, naive)
    t = ((df["data_ora_dt"] - EPOCH) // pd.Timedelta(minutes=1)).astype(int)
    rows = {
        "id": df["id"].astype(int).tolist(),
        "t": t.tolist(),
        "u": df["utente"].map(user_idx).astype(int).tolist(),
        "v": (df["tipo_file"] == "video").astype(int).tolist(),
        "b": df["beers"].astype(int).tolist(),
        "s": df["score"].astype(int).tolist(),
        "p": df["punti"].astype(int).tolist(),
        "f": df["nome_file"].astype(str).str.strip().tolist(),
    }

    # Picture of the Day pubblicate dal bot
    potd = {}
    index_path = os.path.join(POTD_DIR, "index.json")
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            for day, meta in json.load(f).items():
                img = meta.get("image")
                if not img or not os.path.exists(os.path.join(POTD_DIR, img)):
                    continue
                u = str(meta.get("utente", "")).strip()
                u = report["aliases"].get(u, u)
                potd[day] = {"image": f"potd/{img}", "user": nicknames.get(u, u),
                             "time": meta.get("time"), "candidates": meta.get("candidates")}
        dst = os.path.join(out_dir, "potd")
        os.makedirs(dst, exist_ok=True)
        for day, meta in potd.items():
            shutil.copy2(os.path.join(POTD_DIR, os.path.basename(meta["image"])), dst)

    official = int(row[0]) if row else 0
    data = {
        "generated_at": int(time.time()),
        "db_updated_at": int(os.path.getmtime(DB_PATH)),
        "official_total": official,
        "users": [{"name": r.utente, "nation": r.nation, "flag": flag_of(r.nation)} for r in users.itertuples()],
        "rows": rows,
        "potd": dict(sorted(potd.items())),
        "report": {
            "rows": report["rows"],
            "ts_fixed": report["ts_fixed"],
            "swap_fixed": report["swap_fixed"],
            "unparsable_dates": report["unparsable_dates"],
            "aliases": report["aliases"],
            "alias_rows": report["alias_rows"],
            "whitespace_fixed": report["whitespace_fixed"],
            "zero_photos": report["zero_photos"],
            "photos_multi_pt": report["photos_multi_pt"],
            "photos_multi_pt_extra": report["photos_multi_pt_extra"],
            "videos_with_1pt": report["videos_with_1pt"],
            "duplicate_files": report["duplicate_files"],
        },
    }
    path = os.path.join(out_dir, "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"data.json: {len(df):,} rows, {len(users):,} users, official={official:,}, "
          f"{os.path.getsize(path) / 1024:.0f} KB, potd={len(potd)}")


if __name__ == "__main__":
    main()

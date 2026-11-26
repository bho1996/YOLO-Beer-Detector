#!/usr/bin/env python3
"""Rimuove dal database (classifica) e da photo_folder le foto duplicate.

Applica gli stessi criteri introdotti in bot.js (commit 87770e72):
  1. Duplicato esatto: stessa dimensione e stesso MD5 (a qualsiasi distanza di tempo).
  2. Quasi-duplicato ravvicinato: dHash 16x16 (256 bit) con distanza di Hamming <= 3
     entro 60 secondi dalla pubblicazione precedente (data da WA_<unix> o data_ora).

NON modifica MAI OFFICIAL_TOTAL in config.

Uso:
  Anteprima (default, sola lettura):
    ./venv/bin/python pulisci_duplicati.py
  Applica (crea backup SQLite, elimina righe duplicate e file su disco):
    ./venv/bin/python pulisci_duplicati.py --apply
  Opzioni:
    --window 60       finestra temporale in secondi per quasi-duplicati (default: 60)
    --tolerance 3     distanza Hamming massima su dHash 256-bit (default: 3)
    --workers 4       processi paralleli per il calcolo dHash (default: 4)
    --db PATH         percorso DB (default: 1m_beers.db nella cartella dello script)
    --photos DIR      cartella foto (default: photo_folder nella cartella dello script)
    --cache PATH      cache SQLite per MD5/dHash (default: /tmp/yolo_dedup_cache.sqlite)
    --json-report F   salva elenco dettagliato dei duplicati in JSON
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "1m_beers.db"
DEFAULT_PHOTOS = BASE_DIR / "photo_folder"
DEFAULT_CACHE = Path("/tmp/yolo_dedup_cache.sqlite")
ROME = ZoneInfo("Europe/Rome")
WA_TS_RE = re.compile(r"^WA_(\d+)")
DATE_FORMATS = (
    "%d/%m/%y, %H:%M",
    "%d/%m/%Y, %H:%M",
    "%d/%m/%y %H:%M",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)


@dataclasses.dataclass
class PhotoRow:
    row_id: int
    data_ora: str
    utente: str
    nome_file: str
    punti: int
    ts: int | None
    path: Path
    exists: bool
    size: int | None
    mtime_ns: int | None = None


@dataclasses.dataclass
class DuplicateMatch:
    removed: PhotoRow
    kept: PhotoRow
    reason: str
    distance: int | None = None
    dt_seconds: int | None = None


def parse_timestamp(nome_file: str, data_ora: str) -> int | None:
    m = WA_TS_RE.match(str(nome_file or ""))
    if m:
        return int(m.group(1))
    raw = str(data_ora or "").strip()
    for fmt in DATE_FORMATS:
        try:
            parsed = dt.datetime.strptime(raw, fmt).replace(tzinfo=ROME)
            return int(parsed.timestamp())
        except ValueError:
            continue
    return None


def compute_md5(path: Path) -> str | None:
    try:
        h = hashlib.md5()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def compute_dhash(path: Path) -> int | None:
    try:
        with Image.open(path) as im:
            gray = im.convert("L").resize((17, 16))
            if hasattr(gray, "get_flattened_data"):
                px = list(gray.get_flattened_data())
            else:
                px = list(gray.getdata())
    except Exception:
        return None
    bits = 0
    for y in range(16):
        row = y * 17
        for x in range(16):
            bits = (bits << 1) | (1 if px[row + x] > px[row + x + 1] else 0)
    return bits


def _dhash_worker(args: tuple[str, str]) -> tuple[str, str | None]:
    fname, path_str = args
    dh = compute_dhash(Path(path_str))
    return fname, (format(dh, "064x") if dh is not None else None)


def _md5_worker(args: tuple[str, str]) -> tuple[str, str | None]:
    fname, path_str = args
    return fname, compute_md5(Path(path_str))


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class HashCache:
    """Cache locale (nome_file, size, mtime_ns) -> md5, dhash per velocizzare riesecuzioni."""

    def __init__(self, path: Path | None):
        self.path = path
        self.conn: sqlite3.Connection | None = None
        if path is not None:
            self.conn = sqlite3.connect(str(path))
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS file_hashes (
                    nome_file TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    md5 TEXT,
                    dhash TEXT
                )"""
            )
            self.conn.commit()

    def load_all(self) -> dict[str, tuple[int, int, str | None, str | None]]:
        if self.conn is None:
            return {}
        out: dict[str, tuple[int, int, str | None, str | None]] = {}
        for fn, sz, mt, md5, dh in self.conn.execute(
            "SELECT nome_file, size, mtime_ns, md5, dhash FROM file_hashes"
        ):
            out[fn] = (sz, mt, md5, dh)
        return out

    def upsert_many(self, items: list[tuple[str, int, int, str | None, str | None]]) -> None:
        if self.conn is None or not items:
            return
        self.conn.executemany(
            """INSERT INTO file_hashes (nome_file, size, mtime_ns, md5, dhash)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(nome_file) DO UPDATE SET
                 size = excluded.size,
                 mtime_ns = excluded.mtime_ns,
                 md5 = COALESCE(excluded.md5, file_hashes.md5),
                 dhash = COALESCE(excluded.dhash, file_hashes.dhash)""",
            items,
        )
        self.conn.commit()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None


def load_photo_rows(conn: sqlite3.Connection, photos_dir: Path) -> list[PhotoRow]:
    # Singola scansione veloce della directory (molto piu' rapida di 38k stat su mergerfs)
    disk_index: dict[str, tuple[int, int]] = {}
    with os.scandir(photos_dir) as it:
        for entry in it:
            try:
                st = entry.stat()
                disk_index[entry.name] = (st.st_size, st.st_mtime_ns)
            except OSError:
                continue

    cur = conn.execute(
        "SELECT id, data_ora, utente, nome_file, punti FROM log_birre WHERE tipo_file = 'foto'"
    )
    rows: list[PhotoRow] = []
    for row_id, data_ora, utente, nome_file, punti in cur.fetchall():
        fname = str(nome_file or "")
        info = disk_index.get(fname)
        rows.append(
            PhotoRow(
                row_id=int(row_id),
                data_ora=str(data_ora or ""),
                utente=str(utente or ""),
                nome_file=fname,
                punti=int(punti or 0),
                ts=parse_timestamp(fname, str(data_ora or "")),
                path=photos_dir / fname,
                exists=info is not None,
                size=info[0] if info is not None else None,
                mtime_ns=info[1] if info is not None else None,
            )
        )
    # Ordine cronologico: conserva la prima pubblicazione; a parita' di timestamp preferisce punti > 0
    rows.sort(key=lambda r: (r.ts if r.ts is not None else 10**18, 0 if r.punti > 0 else 1, r.row_id))
    return rows


def find_duplicates(
    rows: list[PhotoRow],
    window_seconds: int = 60,
    tolerance: int = 3,
    workers: int = 4,
    cache_path: Path | None = None,
    verbose: bool = False,
) -> tuple[list[DuplicateMatch], list[PhotoRow]]:
    """Trova duplicati esatti (MD5/nome_file) e quasi-duplicati (dHash entro window_seconds).

    Ritorna (duplicati, righe_mantenute).
    """
    cache = HashCache(cache_path)
    cached = cache.load_all()
    try:
        # Step 1: MD5 solo per i file con dimensione condivisa (come bot.js)
        size_counts = collections.Counter(r.size for r in rows if r.exists and r.size is not None)
        md5_map: dict[str, str | None] = {}
        md5_todo: list[tuple[str, str]] = []
        meta_by_name: dict[str, tuple[int, int]] = {}
        for r in rows:
            if not r.exists or r.size is None or r.mtime_ns is None or size_counts[r.size] < 2:
                continue
            if r.nome_file in meta_by_name:
                continue
            meta_by_name[r.nome_file] = (r.size, r.mtime_ns)
            c = cached.get(r.nome_file)
            if c and c[0] == r.size and c[1] == r.mtime_ns and c[2] is not None:
                md5_map[r.nome_file] = c[2]
            else:
                md5_todo.append((r.nome_file, str(r.path)))

        if md5_todo:
            if verbose:
                print(f"Calcolo MD5 su {len(md5_todo)} file con stessa dimensione...", flush=True)
            to_save: list[tuple[str, int, int, str | None, str | None]] = []
            if workers > 1 and len(md5_todo) > 20:
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                    for fn, digest in ex.map(_md5_worker, md5_todo):
                        md5_map[fn] = digest
                        sz, mt = meta_by_name[fn]
                        to_save.append((fn, sz, mt, digest, None))
            else:
                for item in md5_todo:
                    fn, digest = _md5_worker(item)
                    md5_map[fn] = digest
                    sz, mt = meta_by_name[fn]
                    to_save.append((fn, sz, mt, digest, None))
            cache.upsert_many(to_save)

        # Step 2: trova le righe uniche per nome_file/MD5 prima di calcolare dHash
        def choose_victim(earlier: PhotoRow, current: PhotoRow) -> tuple[PhotoRow, PhotoRow, bool]:
            if earlier.punti <= 0 and current.punti > 0:
                return earlier, current, True
            return current, earlier, False

        seen_filename: dict[str, PhotoRow] = {}
        seen_md5: dict[tuple[int, str], PhotoRow] = {}
        survivors_by_id: dict[int, PhotoRow] = {}
        matches: list[DuplicateMatch] = []

        for row in rows:
            if row.nome_file and row.nome_file in seen_filename:
                earlier = seen_filename[row.nome_file]
                victim, winner, swapped = choose_victim(earlier, row)
                if swapped:
                    survivors_by_id.pop(earlier.row_id, None)
                    survivors_by_id[winner.row_id] = winner
                    seen_filename[row.nome_file] = winner
                matches.append(
                    DuplicateMatch(
                        removed=victim,
                        kept=winner,
                        reason="same_filename",
                        dt_seconds=(row.ts - earlier.ts) if (row.ts is not None and earlier.ts is not None) else None,
                    )
                )
                continue

            md5 = md5_map.get(row.nome_file)
            if md5 is not None and row.size is not None:
                key = (row.size, md5)
                if key in seen_md5:
                    earlier = seen_md5[key]
                    victim, winner, swapped = choose_victim(earlier, row)
                    if swapped:
                        survivors_by_id.pop(earlier.row_id, None)
                        survivors_by_id[winner.row_id] = winner
                        seen_md5[key] = winner
                        if winner.nome_file:
                            seen_filename[winner.nome_file] = winner
                    matches.append(
                        DuplicateMatch(
                            removed=victim,
                            kept=winner,
                            reason="exact_md5",
                            distance=0,
                            dt_seconds=(row.ts - earlier.ts) if (row.ts is not None and earlier.ts is not None) else None,
                        )
                    )
                    continue

            survivors_by_id[row.row_id] = row
            if row.nome_file:
                seen_filename[row.nome_file] = row
            if md5 is not None and row.size is not None:
                seen_md5[(row.size, md5)] = row

        # Step 3: calcola dHash solo per i sopravvissuti che hanno un vicino entro window_seconds
        survivors = [r for r in rows if r.row_id in survivors_by_id]
        needs_dhash: set[int] = set()
        timed_idx = [i for i, r in enumerate(survivors) if r.exists and r.ts is not None]
        for pos, idx in enumerate(timed_idx):
            if pos + 1 < len(timed_idx):
                nxt = timed_idx[pos + 1]
                if survivors[nxt].ts - survivors[idx].ts < window_seconds:  # type: ignore[operator]
                    needs_dhash.add(survivors[idx].row_id)
                    needs_dhash.add(survivors[nxt].row_id)

        dhash_map: dict[str, int | None] = {}
        dhash_todo: list[tuple[str, str]] = []
        dhash_meta: dict[str, tuple[int, int]] = {}
        for r in survivors:
            if r.row_id not in needs_dhash or r.size is None or r.mtime_ns is None:
                continue
            if r.nome_file in dhash_meta:
                continue
            dhash_meta[r.nome_file] = (r.size, r.mtime_ns)
            c = cached.get(r.nome_file)
            if c and c[0] == r.size and c[1] == r.mtime_ns and c[3] is not None:
                dhash_map[r.nome_file] = int(c[3], 16)
            else:
                dhash_todo.append((r.nome_file, str(r.path)))

        if dhash_todo:
            t0 = time.time()
            if verbose:
                print(
                    f"Calcolo dHash su {len(dhash_todo)} foto ravvicinate "
                    f"(gia' in cache: {len(dhash_meta) - len(dhash_todo)}, workers={workers})...",
                    flush=True,
                )
            batch: list[tuple[str, int, int, str | None, str | None]] = []
            done = 0
            if workers > 1 and len(dhash_todo) > 20:
                with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
                    for fn, hex_dh in ex.map(_dhash_worker, dhash_todo, chunksize=32):
                        dhash_map[fn] = int(hex_dh, 16) if hex_dh is not None else None
                        sz, mt = dhash_meta[fn]
                        batch.append((fn, sz, mt, None, hex_dh))
                        done += 1
                        if len(batch) >= 1000:
                            cache.upsert_many(batch)
                            batch.clear()
                            if verbose:
                                elapsed = time.time() - t0
                                rate = done / elapsed if elapsed > 0 else 0
                                print(f"  dHash: {done}/{len(dhash_todo)} ({rate:.1f} foto/s)", flush=True)
            else:
                for item in dhash_todo:
                    fn, hex_dh = _dhash_worker(item)
                    dhash_map[fn] = int(hex_dh, 16) if hex_dh is not None else None
                    sz, mt = dhash_meta[fn]
                    batch.append((fn, sz, mt, None, hex_dh))
            cache.upsert_many(batch)

        # Step 4: finestra scorrevole cronologica per i quasi-duplicati dHash entro window_seconds
        recent_hashes: collections.deque[list] = collections.deque()
        kept_by_id: dict[int, PhotoRow] = {}

        for row in survivors:
            dh = dhash_map.get(row.nome_file) if row.row_id in needs_dhash else None
            if dh is not None and row.ts is not None:
                while recent_hashes and (row.ts - recent_hashes[0][0].ts) >= window_seconds:
                    recent_hashes.popleft()
                matched_slot = None
                matched_dist = None
                for slot in recent_hashes:
                    earlier_row, earlier_dh = slot
                    if earlier_row.row_id not in kept_by_id:
                        continue
                    dist = hamming_distance(dh, earlier_dh)
                    if dist <= tolerance:
                        matched_slot = slot
                        matched_dist = dist
                        break
                if matched_slot is not None:
                    earlier = matched_slot[0]
                    victim, winner, swapped = choose_victim(earlier, row)
                    if swapped:
                        kept_by_id.pop(earlier.row_id, None)
                        kept_by_id[winner.row_id] = winner
                        matched_slot[0] = winner
                        matched_slot[1] = dh
                    matches.append(
                        DuplicateMatch(
                            removed=victim,
                            kept=winner,
                            reason="near_dhash",
                            distance=matched_dist,
                            dt_seconds=(row.ts - earlier.ts) if earlier.ts is not None else None,
                        )
                    )
                    continue
                recent_hashes.append([row, dh])

            kept_by_id[row.row_id] = row

        kept = sorted(kept_by_id.values(), key=lambda r: r.row_id)
        return matches, kept
    finally:
        cache.close()


def backup_sqlite(db_path: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = db_path.with_name(f"{db_path.name}.backup-dedup-{stamp}")
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return backup_path


def read_official_total(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'").fetchone()
    return str(row[0]) if row else None


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def apply_removals(
    db_path: Path,
    photos_dir: Path,
    matches: list[DuplicateMatch],
) -> dict:
    """Rimuove le righe duplicate dal DB e i file da photo_folder senza toccare OFFICIAL_TOTAL."""
    if not matches:
        return {
            "backup": None,
            "db_rows_deleted": 0,
            "media_hash_deleted": 0,
            "pending_deleted": 0,
            "files_deleted": 0,
            "bytes_freed": 0,
            "official_total": None,
        }

    backup_path = backup_sqlite(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA busy_timeout = 10000")
    total_before = read_official_total(conn)

    ids_to_delete = sorted({m.removed.row_id for m in matches})
    candidate_files = sorted({m.removed.nome_file for m in matches if m.removed.nome_file})

    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany("DELETE FROM log_birre WHERE id = ?", [(i,) for i in ids_to_delete])
        db_rows_deleted = len(ids_to_delete)

        unreferenced_files: list[str] = []
        for fname in candidate_files:
            still_used = conn.execute(
                "SELECT 1 FROM log_birre WHERE nome_file = ? LIMIT 1", (fname,)
            ).fetchone()
            if not still_used:
                unreferenced_files.append(fname)

        media_hash_deleted = 0
        if unreferenced_files and table_exists(conn, "media_hash"):
            cur = conn.executemany(
                "DELETE FROM media_hash WHERE nome_file = ?",
                [(f,) for f in unreferenced_files],
            )
            media_hash_deleted = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0

        pending_deleted = 0
        if unreferenced_files and table_exists(conn, "foto_in_attesa"):
            cur = conn.executemany(
                "DELETE FROM foto_in_attesa WHERE nome_file = ?",
                [(f,) for f in unreferenced_files],
            )
            pending_deleted = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0

        total_after = read_official_total(conn)
        if total_before != total_after:
            conn.execute("ROLLBACK")
            raise RuntimeError(
                f"Sicurezza violata: OFFICIAL_TOTAL cambiato da {total_before} a {total_after}"
            )
        conn.execute("COMMIT")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        conn.close()
        raise
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass

    files_deleted = 0
    bytes_freed = 0
    for fname in unreferenced_files:
        p = photos_dir / fname
        try:
            sz = p.stat().st_size
            p.unlink()
            files_deleted += 1
            bytes_freed += sz
        except FileNotFoundError:
            pass

    return {
        "backup": str(backup_path),
        "db_rows_deleted": db_rows_deleted,
        "media_hash_deleted": media_hash_deleted,
        "pending_deleted": pending_deleted,
        "files_deleted": files_deleted,
        "bytes_freed": bytes_freed,
        "official_total": total_before,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Trova e rimuove foto duplicate dal DB e da photo_folder senza toccare OFFICIAL_TOTAL."
    )
    parser.add_argument("--apply", action="store_true", help="Applica davvero le rimozioni (default: dry-run)")
    parser.add_argument("--window", type=int, default=60, help="Finestra in secondi per quasi-duplicati dHash (default: 60)")
    parser.add_argument("--tolerance", type=int, default=3, help="Distanza Hamming massima dHash 256-bit (default: 3)")
    parser.add_argument("--workers", type=int, default=4, help="Worker paralleli per hashing (default: 4)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Percorso del database SQLite")
    parser.add_argument("--photos", type=Path, default=DEFAULT_PHOTOS, help="Percorso di photo_folder")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="Cache SQLite per hash (usa 'none' per disabilitare)")
    parser.add_argument("--json-report", type=Path, default=None, help="Salva report JSON dei duplicati trovati")
    parser.add_argument("--show", type=int, default=20, help="Numero di esempi da stampare (default: 20)")
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"Errore: DB non trovato: {args.db}", file=sys.stderr)
        return 1
    if not args.photos.exists():
        print(f"Errore: cartella foto non trovata: {args.photos}", file=sys.stderr)
        return 1

    cache_path = None if str(args.cache).lower() == "none" else args.cache

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        official_total = read_official_total(conn)
        rows = load_photo_rows(conn, args.photos)
    finally:
        conn.close()

    matches, _kept = find_duplicates(
        rows,
        window_seconds=args.window,
        tolerance=args.tolerance,
        workers=args.workers,
        cache_path=cache_path,
        verbose=True,
    )

    by_reason = collections.Counter(m.reason for m in matches)
    points_removed = sum(m.removed.punti for m in matches)
    bytes_est = sum(m.removed.size or 0 for m in matches if m.removed.nome_file != m.kept.nome_file)

    print(f"Foto in DB: {len(rows)} (presenti su disco: {sum(1 for r in rows if r.exists)})")
    print(f"Parametri: finestra={args.window}s, tolleranza dHash={args.tolerance}")
    print(f"Duplicati trovati: {len(matches)}")
    for reason, cnt in sorted(by_reason.items()):
        print(f"  - {reason}: {cnt}")
    print(f"Punti classifica da rimuovere: {points_removed} | Spazio disco stimato: {bytes_est / (1024 * 1024):.2f} MB")
    print(f"OFFICIAL_TOTAL attuale: {official_total} (NON verra' modificato)")

    if args.show > 0 and matches:
        print(f"\nPrimi {min(args.show, len(matches))} duplicati:")
        for m in matches[: args.show]:
            dt_s = f"{m.dt_seconds}s" if m.dt_seconds is not None else "?"
            dist_s = f"dist={m.distance}" if m.distance is not None else ""
            print(
                f"  [{m.reason}] RIMUOVI id={m.removed.row_id} {m.removed.nome_file} "
                f"({m.removed.utente}, punti={m.removed.punti}) "
                f"== TIENI id={m.kept.row_id} {m.kept.nome_file} ({m.kept.utente}, punti={m.kept.punti}) "
                f"dt={dt_s} {dist_s}".rstrip()
            )

    if args.json_report:
        report = [
            {
                "reason": m.reason,
                "distance": m.distance,
                "dt_seconds": m.dt_seconds,
                "removed": {
                    "id": m.removed.row_id,
                    "nome_file": m.removed.nome_file,
                    "utente": m.removed.utente,
                    "data_ora": m.removed.data_ora,
                    "punti": m.removed.punti,
                    "size": m.removed.size,
                },
                "kept": {
                    "id": m.kept.row_id,
                    "nome_file": m.kept.nome_file,
                    "utente": m.kept.utente,
                    "data_ora": m.kept.data_ora,
                    "punti": m.kept.punti,
                    "size": m.kept.size,
                },
            }
            for m in matches
        ]
        args.json_report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport JSON salvato in: {args.json_report}")

    if not args.apply:
        print("\nModalita' DRY-RUN: nessuna modifica applicata. Usa --apply per eseguire la pulizia.")
        return 0

    res = apply_removals(args.db, args.photos, matches)
    print("\nPulizia applicata:")
    print(f"  Backup SQLite:         {res['backup']}")
    print(f"  Righe log_birre tolte: {res['db_rows_deleted']}")
    print(f"  Righe media_hash tolte:{res['media_hash_deleted']}")
    print(f"  Righe attesa tolte:    {res['pending_deleted']}")
    print(f"  File eliminati:        {res['files_deleted']} ({res['bytes_freed'] / (1024 * 1024):.2f} MB)")
    print(f"  OFFICIAL_TOTAL:        {res['official_total']} (invariato)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

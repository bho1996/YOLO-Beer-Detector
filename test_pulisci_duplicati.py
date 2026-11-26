import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

import pulisci_duplicati as pd_mod


def make_scene(_seed: int, size=(640, 640)):
    """Pattern strutturato (righe verticali + cerchio), ridimensionabile senza cambiare contenuto."""
    im = Image.new("L", size, 30)
    d = ImageDraw.Draw(im)
    w, h = size
    for x in range(0, w, max(8, w // 8)):
        d.rectangle([x, 0, x + max(4, w // 16), h], fill=240)
    d.ellipse([w // 5, h // 5, 4 * w // 5, 4 * h // 5], fill=200)
    return im


def save_variant(path: Path, seed: int, size=(120, 160), quality=90):
    make_scene(seed).resize(size).save(path, format="JPEG", quality=quality)


class TestPulisciDuplicati(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.photos = self.root / "photo_folder"
        self.photos.mkdir()
        self.db_path = self.root / "1m_beers.db"
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("CREATE TABLE config (chiave TEXT PRIMARY KEY, valore TEXT)")
        conn.execute("INSERT INTO config VALUES ('OFFICIAL_TOTAL', '67840')")
        conn.execute(
            """CREATE TABLE log_birre (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_ora TEXT, utente TEXT, nome_file TEXT, punti INTEGER, tipo_file TEXT
            )"""
        )
        conn.execute("CREATE TABLE media_hash (hash TEXT PRIMARY KEY, nome_file TEXT NOT NULL)")
        conn.execute("CREATE TABLE media_phash (hash TEXT PRIMARY KEY, nome_file TEXT NOT NULL)")
        conn.execute("CREATE TABLE foto_in_attesa (nome_file TEXT PRIMARY KEY, data_ora TEXT, utente TEXT)")
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def insert(self, data_ora, utente, nome_file, punti=1, tipo_file="foto"):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) VALUES (?, ?, ?, ?, ?)",
            (data_ora, utente, nome_file, punti, tipo_file),
        )
        conn.commit()
        conn.close()

    def run_scan(self):
        conn = sqlite3.connect(str(self.db_path))
        rows = pd_mod.load_photo_rows(conn, self.photos)
        conn.close()
        return pd_mod.find_duplicates(
            rows, window_seconds=60, tolerance=8, workers=1,
            cache_path=self.root / "cache.sqlite",
        )

    def test_preview_plus_hd_is_removed_and_different_photo_is_kept(self):
        # Stessa foto: anteprima 576x1024compressa e HD 2160x3840 (distanza pHash 0)
        p1 = self.photos / "WA_1700000000.jpg"
        p2 = self.photos / "WA_1700000003.jpg"
        save_variant(p1, seed=3, size=(120, 160), quality=40)
        save_variant(p2, seed=3, size=(360, 480), quality=95)
        self.insert("26/11/26, 00:00", "+44 *** 1111", p1.name, 1)
        self.insert("26/11/26, 00:00", "+44 *** 1111", p2.name, 1)

        # Foto davvero diversa, 2 secondi dopo -> pHash distanza ~24 -> VALE
        p3 = self.photos / "WA_1700000005.jpg"
        im = Image.new("L", (160, 120), 30)
        d = ImageDraw.Draw(im)
        for y in range(0, 120, 12):
            d.rectangle([0, y, 159, y + 6], fill=240)
        im.save(p3, format="JPEG", quality=40)
        self.insert("26/11/26, 00:00", "+44 *** 2222", p3.name, 1)

        # Duplicato esatto a distanza di ore -> rimosso
        p4 = self.photos / "WA_1700007200.jpg"
        p4.write_bytes(p1.read_bytes())
        self.insert("26/11/26, 02:00", "+44 *** 1111", p4.name, 1)

        matches, _ = self.run_scan()
        removed = {m.removed.nome_file for m in matches}
        self.assertEqual(removed, {p2.name, p4.name})

        res = pd_mod.apply_removals(self.db_path, self.photos, matches)
        self.assertEqual(res["db_rows_deleted"], 2)
        self.assertEqual(res["files_deleted"], 2)
        self.assertFalse(p2.exists())
        self.assertFalse(p4.exists())
        self.assertTrue(p1.exists())
        self.assertTrue(p3.exists())

        conn = sqlite3.connect(str(self.db_path))
        total = conn.execute("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'").fetchone()[0]
        remaining = {r[0] for r in conn.execute("SELECT nome_file FROM log_birre")}
        conn.close()
        self.assertEqual(total, "67840")
        self.assertEqual(remaining, {p1.name, p3.name})

    def test_cache_reuse_gives_same_result(self):
        p1 = self.photos / "WA_1700020000.jpg"
        p2 = self.photos / "WA_1700020005.jpg"
        save_variant(p1, seed=7, size=(120, 160), quality=40)
        save_variant(p2, seed=7, size=(360, 480), quality=95)
        self.insert("26/11/26, 05:00", "+1 *** 4444", p1.name, 0)
        self.insert("26/11/26, 05:00", "+1 *** 4444", p2.name, 1)

        matches1, _ = self.run_scan()
        matches2, _ = self.run_scan()
        self.assertEqual({m.removed.nome_file for m in matches1}, {p1.name})
        self.assertEqual({m.removed.nome_file for m in matches2}, {p1.name})
        self.assertEqual(matches1[0].kept.nome_file, p2.name)
        self.assertEqual(matches1[0].reason, "near_phash")


if __name__ == "__main__":
    unittest.main()

import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import pulisci_duplicati as pd_mod


def make_image(path: Path, seed: int, quality: int = 90, size=(120, 120)):
    """Genera un'immagine con gradiente continuo (senza bande piatte) per testare dHash + JPEG."""
    w, h = size
    im = Image.new("RGB", (w, h))
    px = im.load()
    freq_x = 0.04 + (seed % 5) * 0.03
    freq_y = 0.03 + ((seed * 3) % 5) * 0.025
    phase = seed * 1.1
    for y in range(h):
        for x in range(w):
            r = int(127 + 110 * math.sin(x * freq_x + phase))
            g = int(127 + 110 * math.cos(y * freq_y + phase * 0.7))
            b = int(127 + 100 * math.sin((x + y) * 0.03 + seed))
            px[x, y] = (r, g, b)
    im.save(path, format="JPEG", quality=quality)


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
        conn.execute(
            "CREATE TABLE foto_in_attesa (nome_file TEXT PRIMARY KEY, data_ora TEXT, utente TEXT)"
        )
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

    def test_exact_md5_and_near_dhash_within_60s_without_changing_total(self):
        # 1. Exact duplicate 2 hours apart -> removed
        p1 = self.photos / "WA_1700000000.jpg"
        p2 = self.photos / "WA_1700007200.jpg"
        make_image(p1, seed=1, quality=85)
        p2.write_bytes(p1.read_bytes())
        self.insert("26/11/26, 00:00", "+1 *** 1111", p1.name, 1)
        self.insert("26/11/26, 02:00", "+1 *** 1111", p2.name, 1)

        # 2. Recompressed near-duplicate 10 seconds apart -> removed
        p3 = self.photos / "WA_1700010000.jpg"
        p4 = self.photos / "WA_1700010010.jpg"
        make_image(p3, seed=2, quality=95)
        make_image(p4, seed=2, quality=45)
        self.insert("26/11/26, 02:46", "+44 *** 2222", p3.name, 1)
        self.insert("26/11/26, 02:46", "+44 *** 2222", p4.name, 1)

        # 3. Recompressed near-duplicate 120 seconds apart (> 60s) -> KEPT
        p5 = self.photos / "WA_1700010130.jpg"
        make_image(p5, seed=2, quality=35)
        self.insert("26/11/26, 02:48", "+44 *** 2222", p5.name, 1)

        # 4. Different image 5 seconds apart -> KEPT
        p6 = self.photos / "WA_1700010005.jpg"
        make_image(p6, seed=9, quality=85)
        self.insert("26/11/26, 02:46", "+39 *** 3333", p6.name, 1)

        # 5. Video row -> untouched
        self.insert("26/11/26, 02:47", "+39 *** 3333", "WA_1700010020.mp4", 5, "video")

        conn = sqlite3.connect(str(self.db_path))
        conn.execute("INSERT INTO media_hash VALUES ('abcd', ?)", (p4.name,))
        conn.commit()
        rows = pd_mod.load_photo_rows(conn, self.photos)
        conn.close()

        cache_file = self.root / "cache.sqlite"
        matches, _kept = pd_mod.find_duplicates(rows, window_seconds=60, tolerance=3, workers=1, cache_path=cache_file)
        removed_names = {m.removed.nome_file for m in matches}
        self.assertEqual(removed_names, {p2.name, p4.name})

        # Seconda chiamata dalla cache deve dare lo stesso risultato
        matches2, _ = pd_mod.find_duplicates(rows, window_seconds=60, tolerance=3, workers=1, cache_path=cache_file)
        self.assertEqual({m.removed.nome_file for m in matches2}, removed_names)

        res = pd_mod.apply_removals(self.db_path, self.photos, matches)
        self.assertEqual(res["db_rows_deleted"], 2)
        self.assertEqual(res["files_deleted"], 2)
        self.assertEqual(res["media_hash_deleted"], 1)
        self.assertFalse(p2.exists())
        self.assertFalse(p4.exists())
        self.assertTrue(p1.exists())
        self.assertTrue(p3.exists())
        self.assertTrue(p5.exists())
        self.assertTrue(p6.exists())

        conn = sqlite3.connect(str(self.db_path))
        total = conn.execute("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'").fetchone()[0]
        remaining = {r[0] for r in conn.execute("SELECT nome_file FROM log_birre").fetchall()}
        conn.close()
        self.assertEqual(total, "67840")
        self.assertEqual(remaining, {p1.name, p3.name, p5.name, p6.name, "WA_1700010020.mp4"})

    def test_prefers_keeping_positive_points_over_zero_points(self):
        p1 = self.photos / "WA_1700020000.jpg"
        p2 = self.photos / "WA_1700020005.jpg"
        make_image(p1, seed=4, quality=85)
        p2.write_bytes(p1.read_bytes())
        self.insert("26/11/26, 05:00", "+1 *** 4444", p1.name, 0)
        self.insert("26/11/26, 05:00", "+1 *** 4444", p2.name, 1)

        conn = sqlite3.connect(str(self.db_path))
        rows = pd_mod.load_photo_rows(conn, self.photos)
        conn.close()
        matches, _ = pd_mod.find_duplicates(rows, workers=1)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].removed.nome_file, p1.name)
        self.assertEqual(matches[0].kept.nome_file, p2.name)


if __name__ == "__main__":
    unittest.main()

import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import pandas as pd

import weekly_report as wr


class Tests(unittest.TestCase):
    def test_week_bounds_normalizes_to_monday(self):
        start, end = wr.week_bounds('2026-11-18')
        self.assertEqual(start, pd.Timestamp('2026-11-16'))
        self.assertEqual(end, pd.Timestamp('2026-11-23'))

    def test_only_durable_overtakes_are_reported(self):
        def frame(rows):
            return pd.DataFrame([{
                'utente': u, 'score': s, 'data_ora_dt': pd.Timestamp(t), 'nome_file': f,
            } for u, s, t, f in rows])

        history = frame([
            ('A', 5, '2026-11-15 10:00', 'a1'),
            ('A', 5, '2026-11-15 11:00', 'a2'),
            ('B', 9, '2026-11-15 12:00', 'b1'),
            ('C', 10, '2026-11-15 13:00', 'c1'),
            ('D', 9, '2026-11-15 14:00', 'd1'),
        ])
        weekly = frame([
            ('B', 1, '2026-11-17 10:00', 'b2'),
            ('B', 1, '2026-11-17 11:00', 'b3'),
            ('B', 1, '2026-11-17 12:00', 'b4'),
            ('D', 1, '2026-11-18 10:00', 'd2'),
            ('D', 1, '2026-11-18 11:00', 'd3'),
            ('C', 1, '2026-11-19 10:00', 'c2'),
            ('C', 1, '2026-11-19 11:00', 'c3'),
        ])
        events = wr.find_overtakes(history, weekly)
        p = [(e['by'], e['over']) for e in events]
        self.assertIn(('B', 'A'), p)
        self.assertNotIn(('D', 'C'), p)

    def test_build_returns_english_report(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            conn = sqlite3.connect(path)
            conn.execute('CREATE TABLE log_birre (id INTEGER PRIMARY KEY, data_ora TEXT, utente TEXT, '
                         'nome_file TEXT, punti INTEGER, tipo_file TEXT)')
            conn.execute('CREATE TABLE config (chiave TEXT PRIMARY KEY, valore INTEGER)')
            rows = [
                (1, '16/11/26, 10:00', 'A', 'foto_1.jpg', 1, 'foto'),
                (2, '17/11/26, 10:00', 'B', 'foto_2.mp4', 5, 'video'),
                (3, '18/11/26, 10:00', 'A', 'foto_3.jpg', 1, 'foto'),
            ]
            conn.executemany('INSERT INTO log_birre VALUES (?,?,?,?,?,?)', rows)
            conn.execute("INSERT INTO config VALUES ('OFFICIAL_TOTAL', 100)")
            conn.commit()
            conn.close()
            with mock.patch.object(wr, 'DB_PATH', path):
                report = wr.build('2026-11-18')
            self.assertIn('WEEKLY REPORT', report['message'])
            self.assertIn('Ghost beers', report['message'])
            self.assertEqual(report['beers'], 3)
            self.assertEqual(report['week'], '2026-11-16')
            self.assertTrue(all(isinstance(e['delta'], int) for e in report['leaderboard']))
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()

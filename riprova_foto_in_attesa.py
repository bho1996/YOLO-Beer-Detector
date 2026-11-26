#!/usr/bin/env python3
"""Job notturno: giudica le foto in `foto_in_attesa` (quelle che il bot non ha
potuto analizzare perché l'AI non era disponibile) e le sposta in `log_birre`.

Comportamento identico al bot per una foto live:
  - birra vista  → log_birre punti=1, OFFICIAL_TOTAL +1  (disattivabile con --no-total)
  - niente birra → log_birre punti=0
  - AI ancora non disponibile → la foto resta in attesa, lo script si FERMA
    (non ha senso bruciare chiamate quando la quota è finita).

Nessun Git: il bot committa il DB al prossimo inserimento.
Uso:  riprova_foto_in_attesa.py [--limit N] [--delay SEC] [--no-total] [--dry]
"""
import argparse
import datetime as dt
import pathlib
import re
import sqlite3
import subprocess
import sys
import time

PROJECT = pathlib.Path("/srv/mergerfs/PoolArchivio/YOLO-Beer-Detector")
DATABASE = PROJECT / "1m_beers.db"
PYTHON = PROJECT / "venv/bin/python"
JUDGE = PROJECT / "ai_judge.py"
PHOTOS = PROJECT / "photo_folder"
MAX_TENTATIVI_PRIMA_DI_AVVISARE = 10


def log(msg):
    print(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def verdict(result):
    """0/1 se l'AI ha giudicato, ValueError se NON ha potuto (quota, 404, crash)."""
    output = result.stdout or ""
    if result.returncode != 0 or "[FATAL]" in output:
        riga = next((r for r in output.splitlines() if "fallito" in r or "FATAL" in r), "")
        raise ValueError(f"AI non disponibile: {riga.strip()[:200]}")
    if re.search(r"\[ERRORE\].*non esiste", output):
        raise ValueError("ai_judge non trova il file")
    matches = re.findall(r"^BEERS_FOUND:\s*(-?\d+)\s*$", output, re.MULTILINE)
    if not matches:
        raise ValueError("nessun verdetto nell'output")
    valore = int(matches[-1])
    if valore < 0:
        raise ValueError(f"verdetto non valido: {valore}")
    return 1 if valore >= 1 else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=0, help="max foto da provare (0 = tutte)")
    parser.add_argument("--delay", type=float, default=8, help="pausa tra una foto e l'altra (s)")
    parser.add_argument("--no-total", action="store_true",
                        help="non incrementare OFFICIAL_TOTAL per le birre trovate")
    parser.add_argument("--dry", action="store_true", help="solo elenco, niente AI né scritture")
    args = parser.parse_args()

    conn = sqlite3.connect(f"{DATABASE.as_uri()}?mode={'ro' if args.dry else 'rw'}",
                           uri=True, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        try:
            rows = conn.execute(
                "SELECT nome_file, data_ora, utente, testo, tentativi, COALESCE(aggiungi_totale, 1) FROM foto_in_attesa "
                "ORDER BY creato, nome_file").fetchall()
        except sqlite3.OperationalError as e:
            log(f"Tabella foto_in_attesa assente ({e}): il bot aggiornato non è ancora partito. Niente da fare.")
            return 0
        tot_row = conn.execute("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'").fetchone()
        log(f"Foto in attesa: {len(rows)} | OFFICIAL_TOTAL: {tot_row[0] if tot_row else 'assente'}"
            f"{' | DRY RUN' if args.dry else ''}{' | --no-total' if args.no_total else ''}")
        if not rows:
            return 0
        if args.dry:
            for nome, data_ora, utente, _testo, tent, _agg in rows:
                stato = "presente" if (PHOTOS / nome).is_file() else "FILE MANCANTE"
                print(f"  {data_ora} | {utente} | {nome} | tentativi {tent} | {stato}")
            return 0
        if not PYTHON.is_file() or not JUDGE.is_file():
            raise FileNotFoundError("Manca venv/bin/python oppure ai_judge.py")

        da_fare = rows if args.limit <= 0 else rows[:args.limit]
        birre = zeri = mancanti = 0
        for i, (nome, data_ora, utente, testo, tent, agg_tot) in enumerate(da_fare, 1):
            image = PHOTOS / nome
            if not image.is_file():
                mancanti += 1
                log(f"[{i}/{len(da_fare)}] FILE MANCANTE {nome}: la tolgo dalla coda, non giudicabile.")
                with conn:
                    conn.execute("DELETE FROM foto_in_attesa WHERE nome_file=?", (nome,))
                continue
            if tent >= MAX_TENTATIVI_PRIMA_DI_AVVISARE:
                log(f"[{i}/{len(da_fare)}] ATTENZIONE {nome}: già {tent} tentativi falliti.")

            log(f"[{i}/{len(da_fare)}] Analizzo {nome} | {utente} | {data_ora}")
            result = None
            try:
                # Giudizio solo visivo (totale 0, testo vuoto): a ore di distanza il numero
                # scritto nella didascalia non c'entra più col totale attuale.
                result = subprocess.run([str(PYTHON), str(JUDGE), str(image), "0", ""],
                                        cwd=str(PROJECT), capture_output=True, text=True, timeout=120)
                delta = verdict(result)
            except (subprocess.TimeoutExpired, OSError, ValueError) as e:
                motivo = str(e)[:300]
                with conn:
                    conn.execute("UPDATE foto_in_attesa SET tentativi=tentativi+1, ultimo_errore=? "
                                 "WHERE nome_file=?", (motivo, nome))
                log(f"STOP: {motivo}")
                log(f"Riepilogo parziale: birre {birre}, zeri {zeri}, file mancanti {mancanti}. "
                    f"Restano in attesa {len(rows) - birre - zeri - mancanti} foto.")
                return 2

            # Transazione unica: log_birre + totale + rimozione dalla coda.
            with conn:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO log_birre (data_ora, utente, nome_file, punti, tipo_file) "
                    "VALUES (?, ?, ?, ?, 'foto')", (data_ora, utente, nome, delta))
                inserita = cur.rowcount == 1
                if inserita and delta == 1 and int(agg_tot) != 0 and not args.no_total:
                    conn.execute("UPDATE config SET valore = CAST(valore AS INTEGER) + 1 "
                                 "WHERE chiave='OFFICIAL_TOTAL'")
                conn.execute("DELETE FROM foto_in_attesa WHERE nome_file=?", (nome,))
            if not inserita:
                log(f"  già presente in log_birre, tolta dalla coda: {nome}")
            elif delta == 1:
                birre += 1
                log(f"  ✅ birra → +1 punto a {utente}{', totale +1' if (int(agg_tot) != 0 and not args.no_total) else ' (totale invariato)'}")
            else:
                zeri += 1
                log(f"  ⛔ nessuna birra → 0 punti")
            if i < len(da_fare):
                time.sleep(args.delay)

        tot_row = conn.execute("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'").fetchone()
        rimaste = conn.execute("SELECT COUNT(*) FROM foto_in_attesa").fetchone()[0]
        log(f"FINE: birre {birre}, zeri {zeri}, file mancanti {mancanti}. "
            f"OFFICIAL_TOTAL: {tot_row[0] if tot_row else 'assente'}. Ancora in attesa: {rimaste}.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

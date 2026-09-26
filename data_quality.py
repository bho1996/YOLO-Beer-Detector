"""
Pulizia e verifica dei dati A RUNTIME.
Il database NON viene mai modificato: tutte le correzioni sono applicate
in memoria e documentate nel report "Data Health" della dashboard.
"""
import re
import datetime

import pandas as pd

from countries import build_identity_aliases

TZ = "Europe/Rome"
BEERS_PER_VIDEO = 1      # una "sgolata" conta 1 birra nel totale globale
SCORE_PER_VIDEO = 5      # ...ma vale 5 punti in classifica

_WA_TS_RE = re.compile(r"^WA_(\d{9,11})\.")
_FILE_DATE_RE = re.compile(r"^(?:IMG|VID)-(\d{8})-WA")
_IT_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def _parse_raw(value):
    """Parsa i due formati presenti nel DB. Ritorna (datetime|NaT, is_iso)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NaT, False
    s = str(value).strip()
    try:
        return pd.Timestamp(datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")), True
    except ValueError:
        pass
    s_clean = re.sub(r"\s+", " ", s.replace(",", " ")).strip()
    m = _IT_RE.match(s_clean)
    if m:
        d, mo, y, h, mi, sec = m.groups()
        y = int(y) + (2000 if int(y) < 100 else 0)
        try:
            return pd.Timestamp(datetime.datetime(y, int(mo), int(d), int(h), int(mi), int(sec or 0))), False
        except ValueError:
            pass
    return pd.to_datetime(s_clean, dayfirst=True, errors="coerce"), False


def _swap_day_month(ts):
    if pd.isna(ts) or ts.day > 12 or ts.day == ts.month:
        return None
    try:
        return ts.replace(month=ts.day, day=ts.month)
    except ValueError:
        return None


def fix_dates(df):
    """
    Aggiunge 'data_ora_dt' con date corrette.
    1) File 'WA_<unix>' -> timestamp esatto del messaggio (fonte di verità).
    2) Date ISO con giorno/mese invertiti (bug storico di conversione):
       si sceglie tra originale e invertita quella più vicina alla data nel
       nome file (IMG-YYYYMMDD) o, in mancanza, alle righe vicine per id.
    Ritorna (df, n_corrette_da_timestamp, n_swap_corretti).
    """
    df = df.copy()
    parsed = df["data_ora"].apply(_parse_raw)
    df["data_ora_dt"] = pd.to_datetime(parsed.str[0], errors="coerce")
    is_iso = parsed.str[1].astype(bool)

    # --- 1) Timestamp da nome file WhatsApp ---
    ts = pd.to_numeric(df["nome_file"].astype(str).str.extract(_WA_TS_RE)[0], errors="coerce")
    has_ts = ts.notna()
    ts_dt = (pd.to_datetime(ts[has_ts], unit="s", utc=True)
             .dt.tz_convert(TZ).dt.tz_localize(None).dt.floor("s"))
    diff = (df.loc[has_ts, "data_ora_dt"] - ts_dt).abs()
    ts_fixed = int((diff > pd.Timedelta(minutes=5)).sum())
    df.loc[has_ts, "data_ora_dt"] = ts_dt

    # --- 2) Giorno/mese invertiti senza timestamp ---
    swap_fixed = 0
    df = df.sort_values("id")
    ambiguous = (~has_ts.reindex(df.index)) & is_iso.reindex(df.index) & df["data_ora_dt"].apply(
        lambda t: _swap_day_month(t) is not None)
    reliable = df["data_ora_dt"].where(~ambiguous)
    prev_ref, next_ref = reliable.ffill(), reliable.bfill()
    file_date = pd.to_datetime(df["nome_file"].astype(str).str.extract(_FILE_DATE_RE)[0],
                               format="%Y%m%d", errors="coerce") + pd.Timedelta(hours=12)

    for idx in df.index[ambiguous]:
        orig = df.at[idx, "data_ora_dt"]
        alt = _swap_day_month(orig)
        refs = [file_date[idx]] if pd.notna(file_date[idx]) else [r for r in (prev_ref[idx], next_ref[idx]) if pd.notna(r)]
        if not refs:
            continue
        cost = lambda t: sum(abs((t - r).total_seconds()) for r in refs)
        if cost(alt) < cost(orig):
            df.at[idx, "data_ora_dt"] = alt
            swap_fixed += 1

    return df, ts_fixed, swap_fixed


def prepare(df_raw, nicknames=None):
    """Pipeline completa. Ritorna (df_pulito, report_dict)."""
    report = {"rows": len(df_raw)}
    df = df_raw.copy()

    # Utenti: spazi finali + identità con prefisso troncato
    df["utente_raw"] = df["utente"]
    df["utente"] = df["utente"].astype(str).str.strip()
    stripped = int((df["utente"] != df["utente_raw"].astype(str)).sum())
    aliases = build_identity_aliases(df["utente"].unique())
    merged_rows = int(df["utente"].isin(aliases.keys()).sum())
    df["utente"] = df["utente"].replace(aliases)
    df["phone_id"] = df["utente"]  # identità mascherata canonica (per prefisso/nazione)
    if nicknames:
        df["utente"] = df["utente"].replace(nicknames)
    report.update(whitespace_fixed=stripped, aliases=aliases, alias_rows=merged_rows)

    # Date
    df, ts_fixed, swap_fixed = fix_dates(df)
    report.update(ts_fixed=ts_fixed, swap_fixed=swap_fixed,
                  unparsable_dates=int(df["data_ora_dt"].isna().sum()))

    # Punti: 'beers' = contributo al totale globale, 'score' = punti classifica
    df["punti"] = pd.to_numeric(df["punti"], errors="coerce").fillna(0).astype(int)
    is_video = df["tipo_file"] == "video"
    df["beers"] = df["punti"].where(~is_video, BEERS_PER_VIDEO)
    df["score"] = df["punti"].where(~is_video, SCORE_PER_VIDEO)
    report.update(
        videos_with_1pt=int((is_video & (df["punti"] != SCORE_PER_VIDEO)).sum()),
        negative_rows=int((df["punti"] < 0).sum()),
        zero_photos=int(((~is_video) & (df["punti"] == 0)).sum()),
        big_jumps=int(((~is_video) & (df["punti"] >= 20)).sum()),
        duplicate_files=int(df["nome_file"].astype(str).str.strip().duplicated().sum()),
        future_rows=int((df["data_ora_dt"] > pd.Timestamp.now(tz=TZ).tz_localize(None) + pd.Timedelta(hours=1)).sum()),
    )
    return df.sort_values("data_ora_dt", kind="stable").reset_index(drop=True), report

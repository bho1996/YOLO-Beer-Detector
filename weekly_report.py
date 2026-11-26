import argparse
import json
import os
import sqlite3
import time

import pandas as pd

import data_quality as dq
import stats as S

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "1m_beers.db")
PINT_PRICE = 5.5


def week_bounds(target=None):
    now = pd.Timestamp.now(tz=dq.TZ).tz_localize(None).normalize()
    monday = now - pd.Timedelta(days=now.weekday())
    if target:
        start = pd.Timestamp(target).normalize()
        start -= pd.Timedelta(days=start.weekday())
        return start, start + pd.Timedelta(days=7)
    return monday - pd.Timedelta(days=7), monday


def full_board(df):
    if df.empty:
        return {}
    lb = S.build_leaderboard(df, medals=False)
    return {row["Name"]: {"rank": int(pos), "flag": row["Flag"]} for pos, row in lb.iterrows()}


def find_overtakes(history, weekly, top_users=None, min_gap=2):
    if top_users is not None:
        history = history[history["utente"].isin(top_users)]
        weekly = weekly[weekly["utente"].isin(top_users)]
    scores = {}
    for row in history.itertuples():
        u = getattr(row, "utente")
        scores[u] = scores.get(u, 0) + int(getattr(row, "score"))
    for u in pd.unique(weekly["utente"]):
        scores.setdefault(u, 0)

    def order():
        return sorted(scores, key=lambda u: (-scores[u], str(u)))

    prev = order()
    events = {}
    for row in weekly.itertuples():
        u = getattr(row, "utente")
        before = prev.index(u)
        scores[u] += int(getattr(row, "score"))
        after = order()
        pos = after.index(u)
        for passed in after[:pos]:
            if before < prev.index(passed):
                continue
            events.setdefault((u, passed), {
                "at": getattr(row, "data_ora_dt"),
                "by": u,
                "over": passed,
                "file": str(getattr(row, "nome_file")),
            })
        prev = after
    return [e for e in events.values() if scores[e["by"]] - scores[e["over"]] >= min_gap]


def build(target=None):
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    raw = pd.read_sql_query("SELECT * FROM log_birre", conn)
    cfg = conn.execute("SELECT chiave, valore FROM config").fetchall()
    conn.close()
    official = int(dict(cfg).get("OFFICIAL_TOTAL", 0))
    override = dict(cfg).get("SNIPER_65000")
    overrides = {"65000": str(override)} if override else None
    with open(os.path.join(BASE, "nicknames.json"), encoding="utf-8") as f:
        nicknames = json.load(f)
    df, _ = dq.prepare(raw, nicknames)
    df = df.dropna(subset=["data_ora_dt"]).sort_values("data_ora_dt", kind="stable")

    start, end = week_bounds(target)
    prev_start = start - pd.Timedelta(days=7)
    history = df[df["data_ora_dt"] < start]
    weekly = df[(df["data_ora_dt"] >= start) & (df["data_ora_dt"] < end)]
    prev_weekly = df[(df["data_ora_dt"] >= prev_start) & (df["data_ora_dt"] < start)]

    at_start = full_board(history)
    at_end = full_board(df[df["data_ora_dt"] < end])

    scored = weekly.groupby("utente")["score"].sum().sort_values(ascending=False)
    board = []
    for pos, (user, pts) in enumerate(scored.head(10).items(), 1):
        sub = weekly[weekly["utente"] == user]
        info = at_end.get(user, {})
        board.append({
            "rank": pos,
            "name": user,
            "flag": info.get("flag", "🍺"),
            "score": int(pts),
            "delta": at_start.get(user, {}).get("rank", 0) - info.get("rank", 0),
            "pints": int((sub["tipo_file"] != "video").sum()),
            "downs": int((sub["tipo_file"] == "video").sum()),
        })

    top_users = set(list(at_end)[:50])
    overtakes = sorted(find_overtakes(history, weekly, top_users), key=lambda e: e["at"])
    ghost = max(0, official - int(df["beers"].sum()))
    ms = S.milestones(df[df["data_ora_dt"] < end], ghost, 500, overrides)
    milestones = []
    for r in ms.itertuples():
        when = pd.to_datetime(getattr(r, "Date"), format="%d %b %Y, %H:%M", errors="coerce")
        if pd.notna(when) and start <= when < end:
            milestones.append({"value": getattr(r, "Milestone"), "name": getattr(r, "Sniper"),
                               "at": getattr(r, "Date")})

    beers = int(weekly["beers"].sum())
    prev_beers = int(prev_weekly["beers"].sum())
    fun = S.fun_facts(beers, PINT_PRICE)
    label = f"{start:%d %b} – {end - pd.Timedelta(days=1):%d %b %Y}"
    climbers = sorted([b for b in board if b["delta"] > 0], key=lambda b: -b["delta"])[:3]
    message = "\n".join([
        f"🍻 WEEKLY REPORT · {label}",
        f"Total: {official:,} beers · this week {beers:,} ({beers - prev_beers:+,} vs previous week)",
        "",
        "🏆 TOP DRINKERS OF THE WEEK",
        *[f"{b['rank']}. {b['name']} — {b['score']} pts ({b['pints']} pints, {b['downs']} downs)" for b in board[:5]],
        "",
        "📈 BIGGEST CLIMBS",
        *([f"{b['name']} ↑{b['delta']}" for b in climbers] or ["nobody climbed this week"]),
        "",
        "⚔️ OVERTAKES",
        *([f"{e['by']} passed {e['over']} — {e['at']:%a %d %b, %H:%M}" for e in overtakes[:5]] or ["no position changes this week"]),
        "",
        f"🎯 Milestones: {len(milestones)} · new drinkers: {len(set(weekly['utente']) - set(history['utente']))}",
        f"🍺 {fun['liters']:.0f} L · {fun['bathtubs']:.1f} bathtubs · €{fun['money']:.0f} bar tab",
    ])

    return {
        "generated_at": int(time.time()),
        "week": start.strftime("%Y-%m-%d"),
        "week_end": (end - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        "label": label,
        "total": official,
        "beers": beers,
        "beers_prev": prev_beers,
        "drinkers": int(weekly["utente"].nunique()),
        "videos": int((weekly["tipo_file"] == "video").sum()),
        "zero_photos": int(((weekly["tipo_file"] != "video") & (weekly["punti"] <= 0)).sum()),
        "ghost": ghost,
        "milestones_approximate": True,
        "leaderboard": board,
        "overtakes": [{**e, "at": e["at"].strftime("%a %d %b, %H:%M")} for e in overtakes],
        "milestones": milestones,
        "fun_facts": fun,
        "message": message,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", nargs="?")
    ap.add_argument("--week", help="Monday of the target week (YYYY-MM-DD)")
    args = ap.parse_args()
    report = build(args.week)
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        with open(os.path.join(args.out_dir, "weekly.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, separators=(",", ":"))
        with open(os.path.join(args.out_dir, "weekly.txt"), "w", encoding="utf-8") as f:
            f.write(report["message"] + "\n")
    print(report["message"])


if __name__ == "__main__":
    main()

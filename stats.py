"""Funzioni di calcolo per la dashboard (nessuna dipendenza da Streamlit)."""
import hashlib

import pandas as pd

from countries import get_country, flag_of


def build_leaderboard(df, top_n=None, medals=True):
    """Classifica per 'score' (foto = birre, video = 5 punti)."""
    if df.empty:
        return pd.DataFrame(columns=['Flag', 'Drinker', 'Total Score', 'Regular Pints', 'Downs'])
    is_video = df['tipo_file'] == 'video'
    g = df.groupby('utente')
    lb = pd.DataFrame({
        'Regular Pints': df[~is_video].groupby('utente')['beers'].sum(),
        'Downs': df[is_video].groupby('utente').size(),
        'phone_id': g['phone_id'].first(),
    })
    lb[['Regular Pints', 'Downs']] = lb[['Regular Pints', 'Downs']].fillna(0).astype(int)
    lb['Total Score'] = lb['Regular Pints'] + lb['Downs'] * 5
    lb = lb.reset_index().rename(columns={'utente': 'Drinker'})
    lb['Nation'] = lb['phone_id'].astype(str).str.extract(r'^(\+\d+)')[0].apply(get_country)
    lb['Flag'] = lb['Nation'].apply(flag_of)
    lb = lb.sort_values(['Total Score', 'Drinker'], ascending=[False, True])
    if top_n is not None:
        lb = lb.head(top_n)
    lb.index = range(1, len(lb) + 1)
    lb['Name'] = lb['Drinker']
    if medals:
        for pos, m in ((1, "🥇 "), (2, "🥈 "), (3, "🥉 ")):
            if len(lb) >= pos:
                lb.loc[pos, 'Drinker'] = m + str(lb.loc[pos, 'Drinker'])
    return lb[['Flag', 'Drinker', 'Total Score', 'Regular Pints', 'Downs', 'Nation', 'Name']]


def daily_series(df, col='beers'):
    """Serie giornaliera completa (giorni vuoti = 0)."""
    d = df.dropna(subset=['data_ora_dt'])
    if d.empty:
        return pd.Series(dtype=float)
    s = d.groupby(d['data_ora_dt'].dt.normalize())[col].sum()
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq='D'), fill_value=0)


def calendar_pivot(df):
    daily = daily_series(df)
    if daily.empty:
        return None
    cal = pd.DataFrame({'date': daily.index, 'beers': daily.values})
    cal['weekday'] = cal['date'].dt.dayofweek
    cal['week'] = cal['date'] - pd.to_timedelta(cal['weekday'], unit='D')
    return (cal.pivot_table(index='weekday', columns='week', values='beers', aggfunc='sum', fill_value=0)
            .reindex(range(7), fill_value=0))


def streaks(df, ref_day):
    """Ritorna (max_streaks_df, active_streaks_df)."""
    d = df.dropna(subset=['data_ora_dt'])
    if d.empty:
        return pd.DataFrame(), pd.DataFrame()
    ud = (pd.DataFrame({'utente': d['utente'], 'day': d['data_ora_dt'].dt.normalize()})
          .drop_duplicates().sort_values(['utente', 'day']))
    new_run = ud.groupby('utente')['day'].diff().dt.days.ne(1)
    ud['run'] = new_run.cumsum()
    runs = ud.groupby(['utente', 'run']).agg(length=('day', 'size'), last=('day', 'max')).reset_index()
    best = (runs.groupby('utente')['length'].max().sort_values(ascending=False)
            .head(10).reset_index().rename(columns={'utente': 'Drinker', 'length': 'Max Streak (Days)'}))
    last_runs = runs.sort_values('last').groupby('utente').tail(1)
    active = last_runs[(ref_day - last_runs['last']).dt.days <= 1]
    active = (active.sort_values('length', ascending=False).head(10)
              .assign(**{'Last Beer': lambda x: x['last'].dt.strftime('%d %b')})
              .rename(columns={'utente': 'Drinker', 'length': 'Active Streak'})
              [['Drinker', 'Active Streak', 'Last Beer']])
    return best, active


def death_row(df, members, snapshot, ref_day, months=3):
    """Chi va rimosso dal gruppo: inattivo da `months` mesi (o mai attivo).

    df       : upload già filtrati (fdf), con 'utente', 'data_ora_dt', 'id'.
    members  : DataFrame membri_gruppo (utente, prima_vista, ultima_vista, admin) oppure None.
    snapshot : data (str YYYY-MM-DD) dell'ultima istantanea membri, oppure None.
    Ritorna (candidati, usciti, membership_nota):
      - candidati: ancora nel gruppo (o stato ignoto) e inattivi → da rimuovere
      - usciti: hanno postato in passato ma non risultano più nel gruppo (già via)
      - membership_nota: False se non c'è nessuna istantanea (lista solo dai post)
    """
    cutoff = ref_day - pd.DateOffset(months=months)
    d = df.dropna(subset=['data_ora_dt'])
    activity = d.groupby('utente').agg(last=('data_ora_dt', 'max'), uploads=('id', 'size'))

    known = members is not None and snapshot is not None and not members.empty
    if known:
        m = members.copy()
        m['utente'] = m['utente'].astype(str).str.strip()
        m = m.drop_duplicates('utente').set_index('utente')
        m['prima_vista'] = pd.to_datetime(m['prima_vista'], errors='coerce')
        m['in_group'] = m['ultima_vista'].astype(str) == str(snapshot)
        table = activity.join(m[['prima_vista', 'in_group', 'admin']], how='outer')
    else:
        table = activity.copy()
        table['prima_vista'] = pd.NaT
        table['in_group'] = pd.NA
        table['admin'] = 0

    table['uploads'] = table['uploads'].fillna(0).astype(int)
    table['admin'] = table['admin'].fillna(0).astype(int)
    # Con zero righe (o join senza date) le colonne restano 'object': forzo datetime.
    table['last'] = pd.to_datetime(table['last'], errors='coerce')
    table['prima_vista'] = pd.to_datetime(table['prima_vista'], errors='coerce')

    never = table['last'].isna()
    inactive = (~never & (table['last'] < cutoff))
    # Chi non ha mai postato è candidato solo se è nel gruppo da prima del cutoff
    # (periodo di grazia per i nuovi membri). Se non sappiamo da quando c'è, non lo giudichiamo.
    silent = never & table['prima_vista'].notna() & (table['prima_vista'] < cutoff)

    # in_group: True → nel gruppo, False → uscito, NA/None → non nell'istantanea (o nessuna istantanea)
    table['Status'] = 'Unknown'
    in_group = table['in_group']
    table.loc[in_group.notna() & (in_group.astype('boolean') == True), 'Status'] = 'In group'   # noqa: E712
    table.loc[in_group.notna() & (in_group.astype('boolean') == False), 'Status'] = 'Left'      # noqa: E712
    table['Months silent'] = ((ref_day - table['last']).dt.days / 30.4).round(1)

    candidates = table[(inactive | silent) & (table['Status'] != 'Left')].copy()
    candidates = candidates.sort_values(['last', 'uploads'], ascending=[True, False], na_position='first')
    candidates = candidates.reset_index().rename(columns={'utente': 'Drinker', 'uploads': 'Uploads'})
    candidates['Last upload'] = candidates['last'].dt.strftime('%d %b %Y').fillna('never')
    candidates['Seen in group since'] = candidates['prima_vista'].dt.strftime('%d %b %Y').fillna('?')
    candidates['Admin'] = candidates['admin'].astype(bool)

    gone = table[(table['Status'] == 'Left') & (table['uploads'] > 0)].copy()
    gone = gone.sort_values('last', ascending=False).reset_index().rename(columns={'utente': 'Drinker', 'uploads': 'Uploads'})
    gone['Last upload'] = gone['last'].dt.strftime('%d %b %Y')

    cols = ['Drinker', 'Status', 'Last upload', 'Months silent', 'Uploads', 'Seen in group since', 'Admin']
    return candidates[cols], gone[['Drinker', 'Last upload', 'Uploads']], known


def milestones(df, ghost, step=500):
    d = df.dropna(subset=['data_ora_dt']).sort_values('data_ora_dt')
    if d.empty:
        return pd.DataFrame()
    running = ghost + d['beers'].cumsum()
    out, m = [], (int(ghost) // step + 1) * step
    top = running.max()
    while m <= top:
        pos = (running >= m).to_numpy().argmax()
        row = d.iloc[pos]
        out.append({'Milestone': f"{m:,} Beers", 'Sniper': row['utente'],
                    'Date': row['data_ora_dt'].strftime('%d %b %Y, %H:%M'),
                    'Total Reached': int(running.iloc[pos])})
        m += step
    return pd.DataFrame(out[::-1])


def get_badges(user_df):
    badges = []
    if user_df.empty:
        return badges
    total = user_df['beers'].sum()
    uploads = len(user_df)
    videos = int((user_df['tipo_file'] == 'video').sum())
    hours = user_df['data_ora_dt'].dt.hour
    for thr, b in ((1, "🍺 First Sip"), (50, "🍻 Regular"), (100, "💯 Centurion"), (200, "🏆 Double Century"),
                   (500, "👑 Half-K Legend"), (1000, "💎 The 1000 Club")):
        if total >= thr:
            badges.append(b)
    for thr, b in ((1, "🎬 First Down"), (5, "🎥 Action Hero"), (15, "🤙 Down Machine")):
        if videos >= thr:
            badges.append(b)
    if uploads >= 30:
        badges.append("📸 Paparazzo")
    if uploads >= 100:
        badges.append("📷 Influencer")
    if hours.notna().any():
        if hours.between(0, 5).any():
            badges.append("🌙 Night Owl")
        if hours.between(6, 9).any():
            badges.append("🌅 Breakfast Champ")
        if hours.between(11, 13).any():
            badges.append("🍔 Lunch Break Legend")
    dow = user_df['data_ora_dt'].dt.dayofweek
    if len(user_df) > 5 and (dow >= 5).mean() > 0.6:
        badges.append("🎉 Weekend Warrior")
    days = user_df['data_ora_dt'].dt.normalize().nunique()
    if days >= 30:
        badges.append("📅 Loyal Liver (30+ days)")
    return badges


def picture_of_the_day(df, day, photo_exists, offset=0):
    """
    Sceglie la 'foto del giorno' in modo deterministico (stessa per tutti
    per tutta la giornata). Preferisce foto disponibili come immagine;
    tra queste, pesa di più quelle con più birre.
    """
    d = df[(df['tipo_file'] == 'foto') & (df['beers'] > 0) &
           (df['data_ora_dt'].dt.normalize() == day)].copy()
    if d.empty:
        return None, 0
    d['has_img'] = d['nome_file'].astype(str).apply(photo_exists)
    if d['has_img'].any():
        d = d[d['has_img']]
    # ordine pseudo-casuale ma stabile per il giorno, favorendo le foto "più piene"
    seed = lambda f: int(hashlib.md5(f"{day.date()}|{f}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    d['rank'] = d['nome_file'].astype(str).apply(seed) / d['beers'].clip(lower=1)
    d = d.sort_values('rank')
    return d.iloc[offset % len(d)], len(d)


def fun_facts(total_beers, pint_price):
    liters = total_beers * 0.568
    return {
        'liters': liters,
        'bathtubs': liters / 150,
        'kcal': total_beers * 215,
        'big_macs': total_beers * 215 / 550,
        'money': total_beers * pint_price,
    }

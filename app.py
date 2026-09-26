import os
import math
import sqlite3

import pandas as pd
import streamlit as st

import data_quality as dq
import stats as S
from settings import *  # noqa: F401,F403 (config + helper donazioni)

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

st.set_page_config(page_title="Project 1M Beers", page_icon="🍻", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
GROUP_START = pd.Timestamp(GROUP_START_STR)


# ==========================================
# DATA (sola lettura: il DB non viene mai modificato)
# ==========================================
@st.cache_data(ttl=60, show_spinner="🍺 Pouring fresh data...")
def load_data():
    os.system("git lfs pull >/dev/null 2>&1")
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        raw = pd.read_sql_query("SELECT * FROM log_birre", conn)
        row = conn.execute("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'").fetchone()
        conn.close()
    except Exception as e:
        return pd.DataFrame(), 0, {"error": str(e)}, None
    df, report = dq.prepare(raw, NICKNAMES)
    mtime = pd.Timestamp(os.path.getmtime(DB_PATH), unit="s", tz="UTC").tz_convert(TZ)
    return df, (int(row[0]) if row else 0), report, mtime


df, OFFICIAL_TOTAL_DB, REPORT, DB_MTIME = load_data()
if df.empty:
    st.error(f"No data found! Looks like the keg is empty. {REPORT.get('error', '')}")
    st.stop()

# 'beers' = contributo al totale globale (video = 1), 'score' = punti classifica (video = 5)
db_beers_total = int(df['beers'].sum())
OFFICIAL_TOTAL = max(OFFICIAL_TOTAL_DB, db_beers_total)
ghost_beers = OFFICIAL_TOTAL - db_beers_total   # birre contate prima del bot / senza foto
now_real = pd.Timestamp.now(tz=TZ).tz_localize(None)

# ==========================================
# SIDEBAR: time machine + supporto
# ==========================================
with st.sidebar:
    st.header("🕰️ Time Machine")
    min_date = df['data_ora_dt'].min().date()
    max_date = max(df['data_ora_dt'].max().date(), now_real.date())
    selected_date = st.slider("Rewind to:", min_value=min_date, max_value=max_date,
                              value=max_date, format="DD/MM/YYYY")
    st.divider()
    st.header("🍻 Keep the bot alive")
    st.caption("AI photo checks, the WhatsApp bot and this dashboard run on real servers. "
               "Every pint you buy keeps the counter counting.")
    if MONTHLY_COSTS_EUR and DONATED_THIS_MONTH_EUR is not None:
        goal_eur, got_eur = float(MONTHLY_COSTS_EUR), float(DONATED_THIS_MONTH_EUR)
        st.progress(min(got_eur / goal_eur, 1.0),
                    text=f"Server costs this month: €{got_eur:.0f} / €{goal_eur:.0f}")
    donate_buttons("sidebar")
    if SUPPORTERS:
        st.markdown("**🙏 Hall of Supporters**")
        st.caption(" · ".join(SUPPORTERS))

time_travel = selected_date < now_real.date()
ref_now = (pd.Timestamp(selected_date) + pd.Timedelta(hours=23, minutes=59, seconds=59)) if time_travel else now_real
ref_day = ref_now.normalize()
fdf = df[df['data_ora_dt'] <= ref_now].copy()

# ==========================================
# CORE MATH
# ==========================================
historical_total = int(fdf['beers'].sum()) + ghost_beers
remaining = max(GOAL - historical_total, 0)
daily = S.daily_series(fdf)


def window_sum(start, end):
    return int(fdf.loc[(fdf['data_ora_dt'] >= start) & (fdf['data_ora_dt'] < end), 'beers'].sum())


last7 = window_sum(ref_day - pd.Timedelta(days=6), ref_now + pd.Timedelta(seconds=1))
prev7 = window_sum(ref_day - pd.Timedelta(days=13), ref_day - pd.Timedelta(days=6))
momentum = ((last7 - prev7) / prev7 * 100) if prev7 else None
pace_lifetime = historical_total / max((ref_now - GROUP_START).days, 1)
pace_recent = last7 / 7


def eta(pace, left):
    return ref_now + pd.Timedelta(days=left / pace) if pace > 0 else None


eta_lifetime, eta_recent = eta(pace_lifetime, remaining), eta(pace_recent, remaining)

week_start = ref_day - pd.Timedelta(days=ref_day.weekday())
beers_this_week = window_sum(week_start, ref_now + pd.Timedelta(seconds=1))
prev_week_beers = window_sum(week_start - pd.Timedelta(days=7), week_start)
WEEKLY_GOAL = max(500, int(math.ceil(prev_week_beers * 1.1 / 100.0) * 100)) if prev_week_beers else 1500

today_df = fdf[fdf['data_ora_dt'] >= ref_day]
today_beers = int(today_df['beers'].sum())
yesterday_beers = window_sum(ref_day - pd.Timedelta(days=1), ref_day)
best_day_beers = int(daily.max()) if not daily.empty else 0
best_day_str = daily.idxmax().strftime('%d %b %Y') if not daily.empty else "N/A"
leaderboard = S.build_leaderboard(fdf)

# ==========================================
# HEADER
# ==========================================
h1, h2 = st.columns([4, 1])
with h1:
    st.title("🍻 The 1 Million Beers Project")
    st.markdown("##### One million pints. One legendary group. Zero regrets! 🚀")
with h2:
    st.write("")
    donate_buttons("header", label="🍺 Support the project")
    if DB_MTIME is not None:
        st.caption(f"🔄 Data updated {DB_MTIME.strftime('%d %b, %H:%M')}")

if time_travel:
    st.warning(f"⚠️ Time Travel active: viewing data up to **{selected_date.strftime('%d %b %Y')}**. "
               "Move the sidebar slider to the end to come back to the present.")
else:
    last_beer_time = fdf['data_ora_dt'].max()
    mins_ago = int((ref_now - last_beer_time).total_seconds() / 60)
    if mins_ago < 15:
        st.success(f"🟢 **LIVE:** The group is drinking right now! Last beer **{max(mins_ago, 0)} min ago**.")
    elif mins_ago < 120:
        st.info(f"⏳ **Warm-up:** Last beer {mins_ago} min ago. Keep them coming!")
    else:
        h = mins_ago // 60
        st.error(f"🚨 **DRY ALERT:** No beers for **{h}h {mins_ago % 60}m**! Someone save this group! 🍺")

# ==========================================
# KPI
# ==========================================
k1, k2, k3, k4 = st.columns(4)
k1.metric("🌍 Global Total", f"{historical_total:,}", help="Official counter: bot-tracked beers + beers counted before the bot / without photos.")
k2.metric("🍺 Today", f"{today_beers:,}", delta=f"{today_beers - yesterday_beers:+,} vs yesterday")
k3.metric("📈 Last 7 days", f"{last7:,}", delta=f"{momentum:+.0f}% vs prev. week" if momentum is not None else None)
k4.metric("🏆 Best Day Ever", f"{best_day_beers:,}", delta=best_day_str, delta_color="off")

progress = min(historical_total / GOAL, 1.0)
st.progress(progress, text=f"**{progress * 100:.2f}%** of the way to 1,000,000 — {remaining:,} to go")

# ==========================================
# MISSION CONTROL
# ==========================================
st.subheader("🎯 Mission Control")
next_ms = (historical_total // MILESTONE_STEP + 1) * MILESTONE_STEP
to_next = next_ms - historical_total
m1, m2 = st.columns(2)
with m1:
    st.markdown(f"**🚩 Next Milestone: {next_ms:,}**")
    st.progress(1 - to_next / MILESTONE_STEP)
    eta_ms = f" · ETA ≈ {to_next / (pace_recent / 24):.0f}h at this week's pace" if pace_recent > 0 else ""
    if to_next <= 10:
        st.error(f"🚨 **ONLY {to_next} TO GO!** Who is going to snipe it?")
        if not time_travel and st.session_state.get("balloons_for") != next_ms:
            st.balloons()
            st.session_state["balloons_for"] = next_ms
    else:
        st.caption(f"{to_next} beers left{eta_ms}")
with m2:
    st.markdown(f"**📅 Weekly Mission: {WEEKLY_GOAL:,}**")
    st.progress(min(beers_this_week / WEEKLY_GOAL, 1.0))
    if beers_this_week >= WEEKLY_GOAL:
        st.success(f"🎉 MISSION ACCOMPLISHED! ({beers_this_week:,} beers this week)")
    else:
        days_left = 7 - ref_day.weekday()
        need = (WEEKLY_GOAL - beers_this_week) / days_left
        st.caption(f"{beers_this_week:,} so far · {WEEKLY_GOAL - beers_this_week:,} left · "
                   f"need ~{need:.0f}/day (goal = last week +10%)")

# ==========================================
# PICTURE OF THE DAY + DRINKER OF THE DAY
# ==========================================
st.divider()
p1, p2 = st.columns([3, 2])
potd_day = ref_day
potd, n_candidates = S.picture_of_the_day(fdf, potd_day, lambda f: photo_source(f) is not None,
                                          st.session_state.get("potd_offset", 0))
if potd is None:
    potd_day = ref_day - pd.Timedelta(days=1)
    potd, n_candidates = S.picture_of_the_day(fdf, potd_day, lambda f: photo_source(f) is not None,
                                              st.session_state.get("potd_offset", 0))
with p1:
    label = "today" if potd_day == ref_day else "yesterday"
    st.subheader(f"📸 Picture of the Day ({label})")
    if potd is None:
        st.info("No pictures yet today... the stage is yours! 🍺")
    else:
        src = photo_source(potd['nome_file'])
        who, when, n = potd['utente'], potd['data_ora_dt'].strftime('%H:%M'), int(potd['beers'])
        if src:
            st.image(src, caption=f"📷 {who} · {when} · {n} 🍺", width="stretch")
        else:
            st.markdown(f"""<div class="potd-card"><div class="potd-emoji">{'🍺' * min(n, 5)}</div>
                <h3>{who}</h3><p>raised <b>{n} beer{'s' if n > 1 else ''}</b> at <b>{when}</b></p></div>""",
                        unsafe_allow_html=True)
        if n_candidates > 1 and st.button(f"🎲 Show another one ({n_candidates} photos {label})"):
            st.session_state["potd_offset"] = st.session_state.get("potd_offset", 0) + 1
            st.rerun()
with p2:
    st.subheader("🔥 Today's Top Drinkers")
    today_lb = S.build_leaderboard(today_df, top_n=5)
    if today_lb.empty:
        st.info("No beers today yet... who's going to open the tap? 🍺")
    else:
        top = today_lb.iloc[0]
        st.markdown(f"👑 **Drinker of the Day:** {top['Flag']} {top['Name']} with **{top['Total Score']} pts**")
        st.dataframe(today_lb[['Flag', 'Drinker', 'Total Score']], width="stretch")
    st.markdown(f"""<div class="donate-box">🤖 Today the AI judge already checked <b>{len(today_df):,}</b> uploads.
        If the counter made you smile, fuel the robot with a pint!</div>""", unsafe_allow_html=True)
    st.write("")
    donate_buttons("today", label="🍻 Fuel the AI judge", primary=False)

# ==========================================
# TABS
# ==========================================
st.divider()
tab_lb, tab_stats, tab_nat, tab_player, tab_data = st.tabs(
    ["🏅 Leaderboards", "📊 Stats & Trends", "🌍 Nations Cup", "🕵️ Player Spotlight", "🩺 Data Health & VAR"])

# ---------- LEADERBOARDS ----------
with tab_lb:
    t1, t2, t3, t4 = st.tabs(["👑 All-Time Legends", "🔥 7-Day Heroes", "🚨 Wall of Shame", "🤓 Nerd Stats"])
    with t1:
        st.caption("Score = pints in photos + 5 pts per 'down' video.")
        st.dataframe(leaderboard.head(15)[['Flag', 'Drinker', 'Total Score', 'Regular Pints', 'Downs']], width="stretch")
        st.download_button("⬇️ Download full leaderboard (CSV)",
                           leaderboard.drop(columns=['Drinker']).to_csv(index_label='Rank').encode(),
                           "1m_beers_leaderboard.csv", "text/csv")
    with t2:
        st.dataframe(S.build_leaderboard(fdf[fdf['data_ora_dt'] >= ref_day - pd.Timedelta(days=6)], top_n=10)
                     [['Flag', 'Drinker', 'Total Score']], width="stretch")
    with t3:
        st.caption("Regulars (10+ uploads) who have gone missing. We're worried. 🥺")
        last = fdf.groupby('utente').agg(last=('data_ora_dt', 'max'), uploads=('id', 'size'))
        last = last[last['uploads'] >= 10]
        last['Days MIA'] = (ref_day - last['last'].dt.normalize()).dt.days
        shame = (last[last['Days MIA'] > 2].sort_values('Days MIA', ascending=False).head(10)
                 .reset_index().rename(columns={'utente': 'Drinker', 'uploads': 'Uploads'}))
        if shame.empty:
            st.success("Everyone is drinking! Great job! 🍻")
        else:
            shame['Last Seen'] = shame['last'].dt.strftime('%d %b %Y')
            st.dataframe(shame[['Drinker', 'Days MIA', 'Uploads', 'Last Seen']], hide_index=True, width="stretch")
    with t4:
        users = fdf.groupby('utente').agg(beers=('beers', 'sum'), uploads=('id', 'size'))
        users = users[users['uploads'] >= 10]
        users['Avg Pints / Upload'] = (users['beers'] / users['uploads']).round(2)
        st.dataframe(users.sort_values('Avg Pints / Upload', ascending=False).head(10).reset_index()
                     .rename(columns={'utente': 'Drinker', 'uploads': 'Uploads'})[['Drinker', 'Avg Pints / Upload', 'Uploads']],
                     hide_index=True, width="stretch")

    st.subheader("🎯 Milestone Snipers")
    ms = S.milestones(fdf, ghost_beers, MILESTONE_STEP)
    if ms.empty:
        st.info("No milestone hit yet — the next sniper could be you!")
    else:
        c1, c2 = st.columns([3, 2])
        c1.dataframe(ms, hide_index=True, width="stretch")
        king = ms['Sniper'].value_counts().reset_index()
        king.columns = ['Sniper', 'Milestones']
        c2.markdown("**👑 Sniper Kings**")
        c2.dataframe(king.head(10), hide_index=True, width="stretch")

    st.subheader("🔥 Loyalty Streaks")
    best, active = S.streaks(fdf, ref_day)
    s1, s2 = st.columns(2)
    s1.markdown("**🏆 All-Time Longest Streaks**")
    s1.dataframe(best, hide_index=True, width="stretch")
    s2.markdown("**⚡ Active Streaks (still alive!)**")
    s2.dataframe(active, hide_index=True, width="stretch")

# ---------- STATS & TRENDS ----------
with tab_stats:
    st.subheader("🔮 Road to 1,000,000")
    e1, e2, e3 = st.columns(3)
    e1.metric("Lifetime pace", f"{pace_lifetime:,.0f} / day",
              delta=f"ETA {eta_lifetime.strftime('%b %Y')}" if eta_lifetime is not None else None, delta_color="off")
    e2.metric("This week's pace", f"{pace_recent:,.0f} / day",
              delta=f"ETA {eta_recent.strftime('%b %Y')}" if eta_recent is not None else None, delta_color="off")
    need_per_day = remaining / max((pd.Timestamp('2027-12-31') - ref_now).days, 1)
    e3.metric("Needed for 1M by end of 2027", f"{need_per_day:,.0f} / day")

    st.subheader("🍺 Fun Facts")
    ff = S.fun_facts(historical_total, PINT_PRICE_EUR)
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Liters drunk", f"{ff['liters']:,.0f} L", help="1 pint = 0.568 L")
    f2.metric("Bathtubs filled", f"{ff['bathtubs']:,.0f} 🛁", help="150 L per bathtub")
    f3.metric("Calories", f"{ff['kcal'] / 1e6:,.1f}M kcal", help=f"≈ {ff['big_macs']:,.0f} Big Macs")
    f4.metric("Bar tab", f"€{ff['money']:,.0f}", help=f"At €{PINT_PRICE_EUR:.2f}/pint. A pint for the dev is a rounding error 😉")

    photos = fdf[fdf['tipo_file'] == 'foto']
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("👥 Drinkers", f"{fdf['utente'].nunique():,}")
    new_this_week = int((fdf.groupby('utente')['data_ora_dt'].min() >= week_start).sum())
    g2.metric("🆕 New this week", f"{new_this_week:,}")
    g3.metric("🤖 AI rejected", f"{(photos['beers'] == 0).mean() * 100:.1f}%", help="Photos where the AI judge saw no beer")
    lb_scores = leaderboard['Total Score']
    top10_share = lb_scores.head(max(len(lb_scores) // 10, 1)).sum() / max(lb_scores.sum(), 1) * 100
    g4.metric("📊 Top 10% share", f"{top10_share:.0f}%", help="Share of points scored by the top 10% of drinkers")

    if PLOTLY_AVAILABLE and not daily.empty:
        st.subheader("📈 Daily Beers & 7-Day Average")
        dd = pd.DataFrame({'Beers': daily, '7-day avg': daily.rolling(7, min_periods=1).mean()})
        fig = go.Figure()
        fig.add_bar(x=dd.index, y=dd['Beers'], name='Beers', marker_color=ORANGE, opacity=0.6)
        fig.add_scatter(x=dd.index, y=dd['7-day avg'], name='7-day avg', line=dict(color='#FF4B4B', width=3))
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation='h'), hovermode='x unified')
        st.plotly_chart(fig, width="stretch")

        st.subheader("📊 The Buzz Chart (cumulative)")
        cum = (daily.cumsum() + ghost_beers).rename('Total')
        fig = px.area(cum, color_discrete_sequence=[ORANGE])
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), showlegend=False, yaxis_title='Global Total')
        st.plotly_chart(fig, width="stretch")

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🕐 When does the group drink?")
            hm = fdf.dropna(subset=['data_ora_dt'])
            hm = (hm.groupby([hm['data_ora_dt'].dt.dayofweek, hm['data_ora_dt'].dt.hour])['beers'].sum()
                  .unstack(fill_value=0).reindex(index=range(7), columns=range(24), fill_value=0))
            fig = px.imshow(hm.values, x=[f"{h:02d}" for h in range(24)], y=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                            color_continuous_scale='YlOrBr', aspect='auto', labels=dict(color='Beers'))
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")
            peak = divmod(int(hm.values.argmax()), 24)
            st.caption(f"🍻 Golden hour: **{['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][peak[0]]} at {peak[1]:02d}:00**")
        with c2:
            st.subheader("👥 Community Growth")
            first = fdf.groupby('utente')['data_ora_dt'].min().dt.normalize().value_counts().sort_index()
            growth = first.cumsum().rename('Drinkers')
            fig = px.line(growth, color_discrete_sequence=[ORANGE])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), showlegend=False, yaxis_title='Unique drinkers')
            st.plotly_chart(fig, width="stretch")

        st.subheader("📅 Beer Calendar")
        piv = S.calendar_pivot(fdf)
        if piv is not None:
            fig = px.imshow(piv.values, x=[c.strftime('%d %b') for c in piv.columns],
                            y=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                            color_continuous_scale='YlOrBr', aspect='auto', labels=dict(color='Beers'))
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")

        st.subheader("🗓️ Monthly Totals")
        monthly = fdf.groupby(fdf['data_ora_dt'].dt.to_period('M').astype(str))['beers'].sum()
        st.bar_chart(monthly, color=ORANGE)
    elif not PLOTLY_AVAILABLE:
        st.info("Install plotly for the charts: `pip install plotly`")

    st.subheader("💥 Biggest Single-Day Binges")
    binge = (fdf.groupby(['utente', fdf['data_ora_dt'].dt.date])['score'].sum()
             .sort_values(ascending=False).head(10).reset_index())
    binge.columns = ['Drinker', 'Date', 'Points']
    st.dataframe(binge, hide_index=True, width="stretch")

# ---------- NATIONS ----------
with tab_nat:
    nat = (leaderboard.groupby('Nation')
           .agg(Score=('Total Score', 'sum'), Pints=('Regular Pints', 'sum'), Downs=('Downs', 'sum'), Drinkers=('Name', 'count'))
           .reset_index())
    nat['Beers'] = nat['Pints'] + nat['Downs']
    nat['Pts / Drinker'] = (nat['Score'] / nat['Drinkers']).round(1)
    nat = nat.sort_values('Score', ascending=False)
    nat.index = range(1, len(nat) + 1)
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("🌍 Nations Cup")
        st.dataframe(nat[['Nation', 'Score', 'Beers', 'Drinkers', 'Pts / Drinker']], width="stretch", height=460)
    with c2:
        st.subheader("🎖️ Most dedicated (5+ drinkers)")
        ded = nat[nat['Drinkers'] >= 5].sort_values('Pts / Drinker', ascending=False).head(10)
        st.dataframe(ded[['Nation', 'Pts / Drinker', 'Drinkers']], hide_index=True, width="stretch")
        st.caption("Nation is inferred from the phone prefix. Truncated prefixes from old bot versions are "
                   "grouped into regions (e.g. '🌍 Africa (other)').")

# ---------- PLAYER SPOTLIGHT ----------
with tab_player:
    players = leaderboard['Name'].tolist()
    qp = st.query_params.get("player")
    default_idx = players.index(qp) if qp in players else 0
    scores = dict(zip(leaderboard['Name'], leaderboard['Total Score']))
    sel = st.selectbox("🔍 Choose a drinker (sorted by score, type to search):", players, index=default_idx,
                       format_func=lambda n: f"{n} — {scores.get(n, 0)} pts")
    if sel:
        st.query_params["player"] = sel
        u = fdf[fdf['utente'] == sel].sort_values('data_ora_dt')
        rank = players.index(sel) + 1
        row = leaderboard[leaderboard['Name'] == sel].iloc[0]
        nation_lb = leaderboard[leaderboard['Nation'] == row['Nation']]
        nation_rank = nation_lb['Name'].tolist().index(sel) + 1
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("🏆 Global Rank", f"#{rank} / {len(players):,}")
        a2.metric(f"{row['Flag']} Nation Rank", f"#{nation_rank} / {len(nation_lb):,}")
        a3.metric("⭐ Score", f"{int(row['Total Score']):,}", delta=f"{int(row['Regular Pints'])} pints + {int(row['Downs'])} downs", delta_color="off")
        a4.metric("🌍 Share of group", f"{row['Total Score'] / max(leaderboard['Total Score'].sum(), 1) * 100:.2f}%")

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("🗓️ First beer", u['data_ora_dt'].min().strftime('%d %b %Y'))
        b2.metric("📅 Active days", f"{u['data_ora_dt'].dt.normalize().nunique()}")
        fav_h = int(u['data_ora_dt'].dt.hour.mode().iloc[0])
        b3.metric("⏰ Favourite hour", f"{fav_h:02d}:00")
        pday = u.groupby(u['data_ora_dt'].dt.date)['score'].sum()
        b4.metric("💥 Best day", f"{int(pday.max())} pts", delta=pday.idxmax().strftime('%d %b'), delta_color="off")

        badges = S.get_badges(u)
        if badges:
            st.markdown("**🎖️ Badges:** " + " · ".join(badges))
        if rank > 1:
            gap = int(leaderboard.iloc[rank - 2]['Total Score'] - row['Total Score'])
            st.info(f"🏃 Only **{gap + 1} pts** to overtake **{leaderboard.iloc[rank - 2]['Name']}** for #{rank - 1}!")
        else:
            st.success("👑 Undisputed #1. Bow down.")

        if PLOTLY_AVAILABLE and len(u) > 1:
            fig = px.line(u.assign(Cumulative=u['score'].cumsum()), x='data_ora_dt', y='Cumulative',
                          color_discrete_sequence=[ORANGE], labels={'data_ora_dt': ''})
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")

        st.caption("🔗 Share this page: the URL now contains `?player=...`")
        with st.expander("📜 Upload log"):
            log = u[['data_ora_dt', 'tipo_file', 'beers', 'score']].sort_values('data_ora_dt', ascending=False)
            log.columns = ['Time', 'Type', 'Beers', 'Points']
            st.dataframe(log, hide_index=True, width="stretch")

# ---------- DATA HEALTH & VAR ----------
with tab_data:
    st.subheader("🩺 Data Health")
    st.caption("The database is opened read-only. All fixes below are applied in memory only — no data is ever changed or deleted.")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Rows in DB", f"{REPORT['rows']:,}")
    d2.metric("Dates repaired", f"{REPORT['ts_fixed'] + REPORT['swap_fixed']:,}",
              help="Day/month swapped by an old import. Fixed using the WhatsApp timestamp in the file name or neighbouring uploads.")
    d3.metric("Identities merged", f"{len(REPORT['aliases']):,}", delta=f"{REPORT['alias_rows']:,} uploads", delta_color="off",
              help="Old bot versions stored truncated prefixes (e.g. '+12 *** 1234' instead of '+1 *** 1234').")
    d4.metric("Ghost beers", f"{ghost_beers:,}", help="Official total minus bot-tracked beers (pre-bot history, text-only updates).")
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Official total (DB)", f"{OFFICIAL_TOTAL_DB:,}")
    e2.metric("Bot-tracked beers", f"{db_beers_total:,}")
    e3.metric("Photos with 0 beers", f"{REPORT['zero_photos']:,}")
    e4.metric("Uploads worth 20+", f"{REPORT['big_jumps']:,}", help="Manual corrections / VAR adjustments")
    if OFFICIAL_TOTAL_DB < db_beers_total:
        st.warning(f"The official counter ({OFFICIAL_TOTAL_DB:,}) is lower than the bot-tracked beers ({db_beers_total:,}). "
                   "The dashboard uses the higher value.")
    if REPORT['videos_with_1pt']:
        st.caption(f"ℹ️ {REPORT['videos_with_1pt']} videos are stored with 1 point in the DB: they are counted "
                   "consistently as 1 beer (global total) / 5 points (leaderboard).")
    with st.expander(f"🔗 Merged identities ({len(REPORT['aliases'])})"):
        st.dataframe(pd.DataFrame(sorted(REPORT['aliases'].items()), columns=['Stored as', 'Merged into']),
                     hide_index=True, width="stretch")

    st.subheader("🕵️ VAR Audit Log")
    q = st.text_input("Filter by drinker (optional)")
    log = fdf if not q else fdf[fdf['utente'].str.contains(q, case=False, regex=False)]
    log = log.sort_values('data_ora_dt', ascending=False).head(200)[['data_ora_dt', 'utente', 'tipo_file', 'beers', 'score', 'nome_file']]
    log.columns = ['Time', 'Drinker', 'Type', 'Beers', 'Points', 'File']
    st.dataframe(log, hide_index=True, width="stretch")

# ==========================================
# FOOTER
# ==========================================
st.divider()
fc1, fc2 = st.columns([3, 2])
with fc1:
    st.markdown("### 🍺 Enjoying the counter?")
    st.markdown(f"This project tracked **{historical_total:,} beers** so far with an AI judge, a WhatsApp bot and this dashboard — "
                "all built and hosted for free by one person in their spare time.\n\n"
                "* 🖥️ keeps the server & AI running 24/7\n* 🛠️ funds new features & stats\n* 🍻 and, well, a pint")
with fc2:
    st.write("")
    donate_buttons("footer", label="🍻 Buy the Dev a Pint")
    st.caption("Secure payment via Stripe · any amount helps")
st.caption("Made with ❤️ and 🍺 · Drink responsibly.")

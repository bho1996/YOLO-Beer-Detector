import os
import re
import streamlit as st
import sqlite3
import pandas as pd
import datetime
import math
import numpy as np

# Plotly (opzionale, per la heatmap bella)
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ==========================================
# 1. CONFIGURATIONS & SETUP
# ==========================================
GOAL = 1000000

st.set_page_config(
    page_title="Project 1M Beers",
    page_icon="🍻",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
div[data-testid="metric-container"] {
    background-color: rgba(255, 165, 0, 0.05);
    border: 1px solid rgba(255, 165, 0, 0.2);
    padding: 5% 10% 5% 10%;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# --- INIZIO: Tasto Donazione Sidebar ---
with st.sidebar:
    st.header("👨‍💻 Support the Developer")
    st.write("Server costs, AI tokens, and late-night coding sessions don't pay for themselves! If you enjoy the 1M Beers Project, consider offering a real pint.")
    st.link_button("🍻 Buy me a beer (Stripe)", "https://buy.stripe.com/dRm8wHbyFdS90ss1Fe6EU00", type="primary", width='stretch')
    st.divider()

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
@st.cache_data(ttl=60)
def load_data():
    # FIX: git lfs pull spostato qui, così viene eseguito al massimo una volta al minuto (cache)
    # e non blocca il rendering ad ogni apertura della pagina.
    try:
        os.system("git lfs install >/dev/null 2>&1 && git lfs pull >/dev/null 2>&1")
    except Exception:
        pass
    try:
        conn = sqlite3.connect("1m_beers.db")
        df = pd.read_sql_query("SELECT * FROM log_birre", conn)
        config_df = pd.read_sql_query("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'", conn)
        official_total = config_df['valore'].iloc[0] if not config_df.empty else 17500
        conn.close()
        return df, official_total
    except Exception as e:
        return pd.DataFrame(), 17500


def get_country(prefix):
    if pd.isna(prefix) or not prefix:
        return '🏴‍☠️ Unknown'
    prefix = str(prefix)

    # +7 Russia/Kazakistan
    if prefix.startswith('+7'): return '🇷🇺 Russia/KZ'
    # +1 USA/Canada/Caraibi
    if prefix.startswith('+1'): return '🇺🇸/🇨🇦 Americas'

    # Prefissi a 3+ cifre (controllare PRIMA dei 2 cifre)
    if prefix.startswith('+212'): return '🇲🇦 Morocco'
    if prefix.startswith('+213'): return '🇩🇿 Algeria'
    if prefix.startswith('+216'): return '🇹🇳 Tunisia'
    if prefix.startswith('+218'): return '🇱🇾 Libya'
    if prefix.startswith('+220'): return '🇬🇲 Gambia'
    if prefix.startswith('+221'): return '🇸🇳 Senegal'
    if prefix.startswith('+222'): return '🇲🇷 Mauritania'
    if prefix.startswith('+223'): return '🇲🇱 Mali'
    if prefix.startswith('+224'): return '🇬🇳 Guinea'
    if prefix.startswith('+225'): return '🇨🇮 Ivory Coast'
    if prefix.startswith('+226'): return '🇧🇫 Burkina Faso'
    if prefix.startswith('+227'): return '🇳🇪 Niger'
    if prefix.startswith('+228'): return '🇹🇬 Togo'
    if prefix.startswith('+229'): return '🇧🇯 Benin'
    if prefix.startswith('+230'): return '🇲🇺 Mauritius'
    if prefix.startswith('+231'): return '🇱🇷 Liberia'
    if prefix.startswith('+232'): return '🇸🇱 Sierra Leone'
    if prefix.startswith('+233'): return '🇬🇭 Ghana'
    if prefix.startswith('+234'): return '🇳🇬 Nigeria'
    if prefix.startswith('+235'): return '🇹🇩 Chad'
    if prefix.startswith('+237'): return '🇨🇲 Cameroon'
    if prefix.startswith('+238'): return '🇨🇻 Cape Verde'
    if prefix.startswith('+240'): return '🇬🇶 Eq. Guinea'
    if prefix.startswith('+241'): return '🇬🇦 Gabon'
    if prefix.startswith('+242'): return '🇨🇬 Congo'
    if prefix.startswith('+243'): return '🇨🇩 DR Congo'
    if prefix.startswith('+244'): return '🇦🇴 Angola'
    if prefix.startswith('+249'): return '🇸🇩 Sudan'
    if prefix.startswith('+250'): return '🇷🇼 Rwanda'
    if prefix.startswith('+251'): return '🇪🇹 Ethiopia'
    if prefix.startswith('+252'): return '🇸🇴 Somalia'
    if prefix.startswith('+253'): return '🇩🇯 Djibouti'
    if prefix.startswith('+254'): return '🇰🇪 Kenya'
    if prefix.startswith('+255'): return '🇹🇿 Tanzania'
    if prefix.startswith('+256'): return '🇺🇬 Uganda'
    if prefix.startswith('+257'): return '🇧🇮 Burundi'
    if prefix.startswith('+258'): return '🇲🇿 Mozambique'
    if prefix.startswith('+260'): return '🇿🇲 Zambia'
    if prefix.startswith('+261'): return '🇲🇬 Madagascar'
    if prefix.startswith('+263'): return '🇿🇼 Zimbabwe'
    if prefix.startswith('+264'): return '🇳🇦 Namibia'
    if prefix.startswith('+265'): return '🇲🇼 Malawi'
    if prefix.startswith('+266'): return '🇱🇸 Lesotho'
    if prefix.startswith('+267'): return '🇧🇼 Botswana'
    if prefix.startswith('+268'): return '🇸🇿 Eswatini'
    if prefix.startswith('+350'): return '🇬🇮 Gibraltar'
    if prefix.startswith('+351'): return '🇵🇹 Portugal'
    if prefix.startswith('+352'): return '🇱🇺 Luxembourg'
    if prefix.startswith('+353'): return '🇮🇪 Ireland'
    if prefix.startswith('+354'): return '🇮🇸 Iceland'
    if prefix.startswith('+355'): return '🇦🇱 Albania'
    if prefix.startswith('+356'): return '🇲🇹 Malta'
    if prefix.startswith('+357'): return '🇨🇾 Cyprus'
    if prefix.startswith('+358'): return '🇫🇮 Finland'
    if prefix.startswith('+359'): return '🇧🇬 Bulgaria'
    if prefix.startswith('+370'): return '🇱🇹 Lithuania'
    if prefix.startswith('+371'): return '🇱🇻 Latvia'
    if prefix.startswith('+372'): return '🇪🇪 Estonia'
    if prefix.startswith('+373'): return '🇲🇩 Moldova'
    if prefix.startswith('+374'): return '🇦🇲 Armenia'
    if prefix.startswith('+375'): return '🇧🇾 Belarus'
    if prefix.startswith('+380'): return '🇺🇦 Ukraine'
    if prefix.startswith('+381'): return '🇷🇸 Serbia'
    if prefix.startswith('+382'): return '🇲🇪 Montenegro'
    if prefix.startswith('+383'): return '🇽🇰 Kosovo'
    if prefix.startswith('+385'): return '🇭🇷 Croatia'
    if prefix.startswith('+386'): return '🇸🇮 Slovenia'
    if prefix.startswith('+387'): return '🇧🇦 Bosnia'
    if prefix.startswith('+389'): return '🇲🇰 N. Macedonia'
    if prefix.startswith('+420'): return '🇨🇿 Czech Rep.'
    if prefix.startswith('+421'): return '🇸🇰 Slovakia'
    if prefix.startswith('+501'): return '🇧🇿 Belize'
    if prefix.startswith('+502'): return '🇬🇹 Guatemala'
    if prefix.startswith('+503'): return '🇸🇻 El Salvador'
    if prefix.startswith('+504'): return '🇭🇳 Honduras'
    if prefix.startswith('+505'): return '🇳🇮 Nicaragua'
    if prefix.startswith('+506'): return '🇨🇷 Costa Rica'
    if prefix.startswith('+507'): return '🇵🇦 Panama'
    if prefix.startswith('+509'): return '🇭🇹 Haiti'
    if prefix.startswith('+591'): return '🇧🇴 Bolivia'
    if prefix.startswith('+592'): return '🇬🇾 Guyana'
    if prefix.startswith('+593'): return '🇪🇨 Ecuador'
    if prefix.startswith('+595'): return '🇵🇾 Paraguay'
    if prefix.startswith('+597'): return '🇸🇷 Suriname'
    if prefix.startswith('+598'): return '🇺🇾 Uruguay'
    if prefix.startswith('+670'): return '🇹🇱 Timor-Leste'
    if prefix.startswith('+673'): return '🇧🇳 Brunei'
    if prefix.startswith('+675'): return '🇵🇬 Papua N.G.'
    if prefix.startswith('+676'): return '🇹🇴 Tonga'
    if prefix.startswith('+679'): return '🇫🇯 Fiji'
    if prefix.startswith('+852'): return '🇭🇰 Hong Kong'
    if prefix.startswith('+853'): return '🇲🇴 Macau'
    if prefix.startswith('+855'): return '🇰🇭 Cambodia'
    if prefix.startswith('+856'): return '🇱🇦 Laos'
    if prefix.startswith('+880'): return '🇧🇩 Bangladesh'
    if prefix.startswith('+886'): return '🇹🇼 Taiwan'
    if prefix.startswith('+960'): return '🇲🇻 Maldives'
    if prefix.startswith('+961'): return '🇱🇧 Lebanon'
    if prefix.startswith('+962'): return '🇯🇴 Jordan'
    if prefix.startswith('+963'): return '🇸🇾 Syria'
    if prefix.startswith('+964'): return '🇮🇶 Iraq'
    if prefix.startswith('+965'): return '🇰🇼 Kuwait'
    if prefix.startswith('+966'): return '🇸🇦 Saudi Arabia'
    if prefix.startswith('+967'): return '🇾🇪 Yemen'
    if prefix.startswith('+968'): return '🇴🇲 Oman'
    if prefix.startswith('+970'): return '🇵🇸 Palestine'
    if prefix.startswith('+971'): return '🇦🇪 UAE'
    if prefix.startswith('+972'): return '🇮🇱 Israel'
    if prefix.startswith('+973'): return '🇧🇭 Bahrain'
    if prefix.startswith('+974'): return '🇶🇦 Qatar'
    if prefix.startswith('+975'): return '🇧🇹 Bhutan'
    if prefix.startswith('+976'): return '🇲🇳 Mongolia'
    if prefix.startswith('+977'): return '🇳🇵 Nepal'
    if prefix.startswith('+992'): return '🇹🇯 Tajikistan'
    if prefix.startswith('+993'): return '🇹🇲 Turkmenistan'
    if prefix.startswith('+994'): return '🇦🇿 Azerbaijan'
    if prefix.startswith('+995'): return '🇬🇪 Georgia'
    if prefix.startswith('+996'): return '🇰🇬 Kyrgyzstan'
    if prefix.startswith('+998'): return '🇺🇿 Uzbekistan'

    # Prefissi a 2 cifre
    if prefix.startswith('+20'): return '🇪🇬 Egypt'
    if prefix.startswith('+27'): return '🇿🇦 South Africa'
    if prefix.startswith('+30'): return '🇬🇷 Greece'
    if prefix.startswith('+31'): return '🇳🇱 Netherlands'
    if prefix.startswith('+32'): return '🇧🇪 Belgium'
    if prefix.startswith('+33'): return '🇫🇷 France'
    if prefix.startswith('+34'): return '🇪🇸 Spain'
    if prefix.startswith('+36'): return '🇭🇺 Hungary'
    if prefix.startswith('+39'): return '🇮🇹 Italy'
    if prefix.startswith('+40'): return '🇷🇴 Romania'
    if prefix.startswith('+41'): return '🇨🇭 Switzerland'
    if prefix.startswith('+43'): return '🇦🇹 Austria'
    if prefix.startswith('+44'): return '🇬🇧 UK'
    if prefix.startswith('+45'): return '🇩🇰 Denmark'
    if prefix.startswith('+46'): return '🇸🇪 Sweden'
    if prefix.startswith('+47'): return '🇳🇴 Norway'
    if prefix.startswith('+48'): return '🇵🇱 Poland'
    if prefix.startswith('+49'): return '🇩🇪 Germany'
    if prefix.startswith('+51'): return '🇵🇪 Peru'
    if prefix.startswith('+52'): return '🇲🇽 Mexico'
    if prefix.startswith('+53'): return '🇨🇺 Cuba'
    if prefix.startswith('+54'): return '🇦🇷 Argentina'
    if prefix.startswith('+55'): return '🇧🇷 Brazil'
    if prefix.startswith('+56'): return '🇨🇱 Chile'
    if prefix.startswith('+57'): return '🇨🇴 Colombia'
    if prefix.startswith('+58'): return '🇻🇪 Venezuela'
    if prefix.startswith('+60'): return '🇲🇾 Malaysia'
    if prefix.startswith('+61'): return '🇦🇺 Australia'
    if prefix.startswith('+62'): return '🇮🇩 Indonesia'
    if prefix.startswith('+63'): return '🇵🇭 Philippines'
    if prefix.startswith('+64'): return '🇳🇿 New Zealand'
    if prefix.startswith('+65'): return '🇸🇬 Singapore'
    if prefix.startswith('+66'): return '🇹🇭 Thailand'
    if prefix.startswith('+81'): return '🇯🇵 Japan'
    if prefix.startswith('+82'): return '🇰🇷 South Korea'
    if prefix.startswith('+84'): return '🇻🇳 Vietnam'
    if prefix.startswith('+86'): return '🇨🇳 China'
    if prefix.startswith('+90'): return '🇹🇷 Turkey'
    if prefix.startswith('+91'): return '🇮🇳 India'
    if prefix.startswith('+92'): return '🇵🇰 Pakistan'
    if prefix.startswith('+93'): return '🇦🇫 Afghanistan'
    if prefix.startswith('+94'): return '🇱🇰 Sri Lanka'
    if prefix.startswith('+95'): return '🇲🇲 Myanmar'
    if prefix.startswith('+98'): return '🇮🇷 Iran'

    return '🏴‍☠️ Other'


def build_leaderboard(df_to_use, top_n=None):
    if df_to_use.empty:
        return pd.DataFrame()
    pints = df_to_use[df_to_use['tipo_file'] == 'foto'].groupby('utente')['punti_clean'].sum().rename('Regular Pints')
    num_downs = df_to_use[df_to_use['tipo_file'] == 'video'].groupby('utente').size().rename('Downs')
    lb = pd.concat([pints, num_downs], axis=1).fillna(0)
    lb['Total Score'] = lb['Regular Pints'] + (lb['Downs'] * 5)
    lb = lb.reset_index().rename(columns={'utente': 'Drinker'})
    lb['Prefix'] = lb['Drinker'].replace(REVERSE_NICKNAMES).astype(str).str.extract(r'^(\+\d+)')
    lb['Nation'] = lb['Prefix'].apply(get_country)
    lb['Flag'] = lb['Nation'].apply(lambda x: str(x).split(' ')[0] if x else '🏴‍☠️')
    lb = lb.sort_values(by='Total Score', ascending=False)
    if top_n is not None:
        lb = lb.head(top_n)
    lb['Total Score'] = lb['Total Score'].astype(int)
    lb['Regular Pints'] = lb['Regular Pints'].astype(int)
    lb['Downs'] = lb['Downs'].astype(int)
    lb.index = range(1, len(lb) + 1)
    if len(lb) > 0: lb.loc[1, 'Drinker'] = "🥇 " + str(lb.loc[1, 'Drinker'])
    if len(lb) > 1: lb.loc[2, 'Drinker'] = "🥈 " + str(lb.loc[2, 'Drinker'])
    if len(lb) > 2: lb.loc[3, 'Drinker'] = "🥉 " + str(lb.loc[3, 'Drinker'])
    return lb[['Flag', 'Drinker', 'Total Score', 'Regular Pints', 'Downs']]


def build_calendar_pivot(df_input):
    """Costruisce la matrice giorno/settimana per la heatmap stile GitHub."""
    plot_df = df_input.dropna(subset=['data_ora_dt']).copy()
    if plot_df.empty:
        return None
    plot_df['Date_only'] = pd.to_datetime(plot_df['data_ora_dt'].dt.date)
    daily = plot_df.groupby('Date_only')['punti_clean'].sum()
    if daily.empty:
        return None
    full_idx = pd.date_range(daily.index.min(), daily.index.max(), freq='D')
    daily_full = daily.reindex(full_idx, fill_value=0)
    cal_df = pd.DataFrame({'date': daily_full.index, 'beers': daily_full.values})
    cal_df['weekday'] = cal_df['date'].dt.dayofweek
    # Il "week" è il lunedì di quella settimana
    cal_df['week'] = cal_df['date'] - pd.to_timedelta(cal_df['weekday'], unit='D')
    pivot = cal_df.pivot_table(index='weekday', columns='week', values='beers', aggfunc='sum', fill_value=0)
    pivot = pivot.reindex(range(7), fill_value=0)
    return pivot


def get_badges(user_df):
    """Achievement/trophy system for a user."""
    badges = []
    if user_df.empty:
        return badges

    total = user_df['punti_clean'].sum()
    uploads = len(user_df)
    videos = len(user_df[user_df['tipo_file'] == 'video'])
    hours = pd.to_datetime(user_df['data_ora_dt'], errors='coerce').dt.hour

    if total >= 1:    badges.append("🍺 First Sip")
    if total >= 50:   badges.append("🍻 Regular")
    if total >= 100:  badges.append("💯 Centurion")
    if total >= 200:  badges.append("🏆 Double Century")
    if total >= 500:  badges.append("👑 Half-K Legend")
    if total >= 1000: badges.append("💎 The 1000 Club")
    if videos >= 1:   badges.append("🎬 First Down")
    if videos >= 5:   badges.append("🎥 Action Hero")
    if videos >= 15:  badges.append("🤙 Down Machine")
    if uploads >= 30: badges.append("📸 Paparazzo")
    if uploads >= 100: badges.append("📷 Influencer")

    # Special hours
    if hours.notna().any():
        if ((hours >= 0) & (hours < 6)).any(): badges.append("🌙 Night Owl")
        if ((hours >= 6) & (hours < 10)).any(): badges.append("🌅 Breakfast Champ")
        if ((hours >= 11) & (hours < 14)).any(): badges.append("🍔 Lunch Break Legend")

    # Weekend warrior: >60% of beers on weekends
    dow = pd.to_datetime(user_df['data_ora_dt'], errors='coerce').dt.dayofweek
    if dow.notna().any() and len(user_df) > 5:
        if (dow >= 5).mean() > 0.6:
            badges.append("🎉 Weekend Warrior")

    return badges


# ==========================================
# 3. DATA LOADING & BASE PROCESSING
# ==========================================
df, CURRENT_OFFICIAL_TOTAL = load_data()

if df.empty:
    st.error("No data found! Looks like the keg is empty. Run `build_db.py` first.")
    st.stop()

# --- GESTIONE NICKNAME ---
NICKNAMES = {
    "+39 *** 2936": "Frank 👑",
    "+49 *** 8462": "Ernesto Freyberg",
    "+49 *** 3870": "Anton Freyberg",
    "+41 *** 5011": "Constantin Huet",
    "+33 *** 2961": "Adhemar"
}
REVERSE_NICKNAMES = {v: k for k, v in NICKNAMES.items()}
df['utente'] = df['utente'].replace(NICKNAMES)

# ==========================================
# PARSING DATE ROBUSTO
# ==========================================
def parse_flexible(date_val):
    if pd.isna(date_val):
        return pd.NaT
    s = str(date_val).strip()
    if isinstance(date_val, (pd.Timestamp, datetime.datetime)):
        return pd.to_datetime(date_val)
    try:
        return pd.to_datetime(s, format='%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        pass
    s_clean = s.replace(',', ' ').strip()
    s_clean = re.sub(r'\s+', ' ', s_clean)
    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})\s+(\d{1,2}):(\d{2})$', s_clean)
    if match:
        day, month, year, hour, minute = match.groups()
        day, month, hour, minute = int(day), int(month), int(hour), int(minute)
        year = int(year)
        if year < 100:
            year += 2000
        try:
            dt = datetime.datetime(year, month, day, hour, minute)
            return pd.to_datetime(dt)
        except ValueError:
            pass
    return pd.to_datetime(s_clean, dayfirst=True, errors='coerce')

df['data_ora_dt'] = df['data_ora'].apply(parse_flexible)

# ==========================================
# PULIZIA PUNTI A RUNTIME (senza toccare il DB)
# ==========================================
def clean_points(row):
    if row['tipo_file'] == 'video':
        return 5  # FIX: era 1, ma il bot salva 5
    else:
        return row['punti']  # Per le foto: usa il valore reale dal DB (0 o 1)

df['punti_clean'] = df.apply(clean_points, axis=1)

# Calcolo Ghost Beers
totale_foto_db = df[df['tipo_file'] == 'foto']['punti_clean'].sum()
totale_video_db = len(df[df['tipo_file'] == 'video'])
current_db_total = totale_foto_db + totale_video_db
ghost_beers = CURRENT_OFFICIAL_TOTAL - current_db_total

calculated_total = df['punti_clean'].sum()
CURRENT_OFFICIAL_TOTAL = max(CURRENT_OFFICIAL_TOTAL, calculated_total)
ghost_beers = CURRENT_OFFICIAL_TOTAL - current_db_total

# ==========================================
# 4. UI: PRENOTAZIONE SPAZI VISIVI (Top Layout)
# ==========================================
st.title("🍻 The 1 Million Beers Project")
st.markdown("##### One million pints. One legendary group. Zero regrets! 🚀")
st.write("")

fomo_container = st.container()          # NUOVO: Time Since Last Beer
st.write("")
top_metrics_container = st.container(border=True)
st.write("")
mission_container = st.container(border=True)
st.write("")
mvp_container = st.container(border=True)

# ==========================================
# 5. ⏳ TIME MACHINE
# ==========================================
st.divider()
st.subheader("🕰️ The Time Machine")
st.write("Rewind time to see past stats!")
min_date = df['data_ora_dt'].min().date() if not df['data_ora_dt'].isna().all() else pd.Timestamp.now(tz='Europe/Rome').date()
max_date = df['data_ora_dt'].max().date() if not df['data_ora_dt'].isna().all() else pd.Timestamp.now(tz='Europe/Rome').date()
selected_date = st.slider(
    "Select Date:",
    min_value=min_date,
    max_value=max_date,
    value=max_date,
    format="DD/MM/YYYY",
    label_visibility="collapsed"
)
if selected_date < max_date:
    st.warning(f"⚠️ Time Travel Active: Viewing data up to {selected_date.strftime('%b %d, %Y')}.")
selected_datetime = pd.to_datetime(selected_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
filtered_df = df[df['data_ora_dt'] <= selected_datetime].copy()

# ==========================================
# 6. CORE MATH & STATS
# ==========================================
punti_foto = filtered_df[filtered_df['tipo_file'] == 'foto']['punti_clean'].sum()
punti_video = len(filtered_df[filtered_df['tipo_file'] == 'video'])
db_counted_beers = punti_foto + punti_video
historical_total = db_counted_beers + ghost_beers
total_videos = len(filtered_df[filtered_df['tipo_file'] == 'video'])

eta_text = "ETA: Keep drinking to calculate..."
beers_per_day = 0
beers_this_week = 0
WEEKLY_GOAL = 1500

if not filtered_df.empty and filtered_df['data_ora_dt'].notna().any():
    vero_inizio_gruppo = pd.to_datetime("2025-06-11")
    last_date = filtered_df['data_ora_dt'].max()
    giorni_totali_veri = (last_date - vero_inizio_gruppo).days
    if giorni_totali_veri > 0 and historical_total > 0:
        beers_per_day = historical_total / giorni_totali_veri
        if beers_per_day > 0:
            remaining_beers = GOAL - historical_total
            remaining_days = remaining_beers / beers_per_day
            eta_date = last_date + pd.Timedelta(days=remaining_days)
            eta_text = f"🎯 **ETA Date:** {eta_date.strftime('%B %Y')}"

    oggi_locale = pd.Timestamp.now(tz='Europe/Rome').normalize().tz_localize(None)
    inizio_questa_settimana = oggi_locale - pd.Timedelta(days=oggi_locale.weekday())
    inizio_settimana_scorsa = inizio_questa_settimana - pd.Timedelta(days=7)
    weekly_df = filtered_df[filtered_df['data_ora_dt'] >= inizio_questa_settimana]
    beers_this_week = weekly_df['punti_clean'].sum()
    prev_week_df = filtered_df[(filtered_df['data_ora_dt'] >= inizio_settimana_scorsa) & (filtered_df['data_ora_dt'] < inizio_questa_settimana)]
    prev_week_beers = prev_week_df['punti_clean'].sum()
    if prev_week_beers > 0:
        WEEKLY_GOAL = max(500, int(math.ceil((prev_week_beers * 1.1) / 100.0) * 100))

# ==========================================
# 7. RIEMPIMENTO DEI CONTENITORI (Top UI)
# ==========================================

# --- NUOVO: TIME SINCE LAST BEER (FOMO Engine) ---
with fomo_container:
    valid_times = filtered_df['data_ora_dt'].dropna()
    if not valid_times.empty:
        ultima_birra = valid_times.max()
        now_naive = pd.Timestamp.now(tz='Europe/Rome').replace(tzinfo=None)
        delta = now_naive - ultima_birra
        total_sec = max(0, delta.total_seconds())
        giorni_digiuno = int(total_sec // 86400)
        ore_digiuno = int((total_sec % 86400) // 3600)
        minuti_digiuno = int((total_sec % 3600) // 60)

        try:
            ultimo_beone = filtered_df.loc[valid_times.idxmax(), 'utente']
        except Exception:
            ultimo_beone = "someone"

        if giorni_digiuno > 0:
            tempo_str = f"{giorni_digiuno}d {ore_digiuno}h {minuti_digiuno}m"
        else:
            tempo_str = f"{ore_digiuno}h {minuti_digiuno}m"

        if giorni_digiuno >= 1:
            st.error(f"🚨 **DRY ALERT!** It's been **{tempo_str}** since the last beer (by {ultimo_beone}). SOMEONE DO SOMETHING, NOW!")
        elif ore_digiuno >= 6:
            st.warning(f"🍺 It's been **{tempo_str}** since {ultimo_beone}'s last beer. The situation is getting critical...")
        else:
            st.success(f"✅ Last beer **{tempo_str}** ago, by {ultimo_beone}. The group is well hydrated.")

# --- Top metrics (come prima) ---
with top_metrics_container:
    oggi_date = pd.Timestamp.now(tz='Europe/Rome').date()
    oggi_pints = int(filtered_df[filtered_df['data_ora_dt'].dt.date == oggi_date]['punti_clean'].sum()) if not filtered_df.empty else 0

    if not filtered_df.empty and filtered_df['data_ora_dt'].notna().any():
        filtered_df['Date_only'] = filtered_df['data_ora_dt'].dt.date
        daily_totals = filtered_df.groupby('Date_only')['punti_clean'].sum()
        if not daily_totals.empty:
            best_day = daily_totals.idxmax()
            best_day_beers = int(daily_totals.max())
            best_day_str = best_day.strftime('%d %b %Y')
        else:
            best_day_str = "N/A"
            best_day_beers = 0
    else:
        best_day_str = "N/A"
        best_day_beers = 0

    unique_drinkers = filtered_df['utente'].nunique() if not filtered_df.empty else 0

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric(label="🏆 Global", value=f"{int(historical_total):,}", help="Includes ghost beers from WhatsApp history.")
    col2.metric(label="🍺 Today", value=oggi_pints, help="How many pints the group logged today.")
    col3.metric(label="🔥 Best Day", value=best_day_beers, delta=best_day_str, delta_color="off", help="The absolute most pints drank in a single 24h period.")
    col4.metric(label="👥 Legends", value=unique_drinkers, help="The number of unique heroes who contributed to the goal.")
    col5.metric(label="📈 Pace / Day", value=f"{beers_per_day:.1f}", help="Average daily speed since the project started.")
    col6.metric(label="🎬 Videos", value=total_videos, help="A video (down) is worth 5 points in the leaderboard!")

# ==========================================
# MISSION CONTROL — one clean panel for all progress
# ==========================================
with mission_container:
    st.markdown("#### 🎛️ Mission Control")
    mc1, mc2, mc3 = st.columns(3)

    with mc1:
        progress_global = min(historical_total / GOAL, 1.0)
        st.markdown("**🚀 The Journey**")
        st.markdown(f"### {int(historical_total):,} / {GOAL:,}")
        st.progress(progress_global, text=f"{progress_global * 100:.3f}%")
        st.caption(eta_text)

    with mc2:
        next_milestone = math.ceil(historical_total / 500) * 500
        if next_milestone <= historical_total:
            next_milestone += 500
        remaining = next_milestone - historical_total
        progress_to_next = max(0.0, min(1.0, 1 - (remaining / 500)))
        st.markdown(f"**🎯 Next Milestone: {next_milestone:,}**")
        st.markdown(f"### 🔥 {int(remaining)} to go")
        st.progress(progress_to_next)
        if remaining <= 3:
            st.error(f"🚨 ONLY {int(remaining)} BEERS LEFT! WHO'S GOING TO MAKE HISTORY?")
            st.balloons()
        elif remaining <= 10:
            st.warning(f"Only {int(remaining)} beers left — PUSH HARD!")
        else:
            st.caption(f"{int(remaining)} beers to the next milestone.")

    with mc3:
        progress_weekly = min(beers_this_week / WEEKLY_GOAL, 1.0)
        st.markdown("**🗓️ Weekly Mission**")
        st.markdown(f"### {int(beers_this_week)} / {WEEKLY_GOAL}")
        st.progress(progress_weekly)
        if beers_this_week >= WEEKLY_GOAL:
            st.caption("✅ Weekly target smashed! Awesome job team.")
        else:
            st.caption(f"Need {int(WEEKLY_GOAL - beers_this_week)} more pints to beat last week's pace!")

with mvp_container:
    oggi = pd.Timestamp.now(tz='Europe/Rome').date()
    df_oggi = df[df['data_ora_dt'].dt.date == oggi]
    st.markdown("#### 🏆 Today's Top Drinkers", help="A 'cheer' is an upload event (a photo or a video). 1 upload = 1 cheer, regardless of how many beers were in the picture!")

    if not df_oggi.empty:
        daily_counts = df_oggi.groupby('utente').size().reset_index(name='Uploads')
        daily_counts = daily_counts.sort_values(by='Uploads', ascending=False).head(5).reset_index(drop=True)
        cols = st.columns(len(daily_counts))
        medals = ["🥇 1st", "🥈 2nd", "🥉 3rd", "4th", "5th"]
        for i, row in daily_counts.iterrows():
            with cols[i]:
                st.metric(label=medals[i], value=str(row['utente']), delta=f"{row['Uploads']} cheers", delta_color="off")
    else:
        st.info("😴 Nobody has had a drink yet today. Who will be the first to break the ice?")

    st.divider()
    st.markdown("#### 👑 All-Time Binge Records (Top 5)", help="The top 5 maximum number of pints logged by a single person in a 24-hour period.")
    if not filtered_df.empty and filtered_df['data_ora_dt'].notna().any():
        record_df = filtered_df.copy()
        record_df['Date_only'] = record_df['data_ora_dt'].dt.date
        daily_user_totals = record_df.groupby(['Date_only', 'utente'])['punti_clean'].sum().reset_index()
        if not daily_user_totals.empty:
            top_5_records = daily_user_totals.sort_values(by='punti_clean', ascending=False).head(5).reset_index(drop=True)
            cols_record = st.columns(len(top_5_records))
            medals_record = ["🥇 1st", "🥈 2nd", "🥉 3rd", "4th", "5th"]
            for i, row in top_5_records.iterrows():
                with cols_record[i]:
                    data_str = row['Date_only'].strftime('%d %b %Y')
                    st.metric(label=f"{medals_record[i]} {row['utente']}", value=f"{int(row['punti_clean'])} pts", delta=f"Set on {data_str}", delta_color="off")
        else:
            st.info("No records yet.")
    else:
        st.info("No records yet.")

st.divider()

# ==========================================
# 8. UI: MAIN DASHBOARD TABS
# ==========================================
col_left, col_right = st.columns([1, 1.5])

with col_left:
    st.subheader("🏅 Hall of Fame")
    tab1, tab2, tab3, tab4 = st.tabs(["🌟 Legends", "🔥 7-Day Heroes", "🏜️ Wall of Shame", "🛠️ Nerd Stats"])

    with tab1:
        leaderboard = build_leaderboard(filtered_df, top_n=None)
        if not leaderboard.empty:
            st.dataframe(leaderboard, width='stretch', hide_index=True)
        else:
            st.info("No data yet.")

    with tab2:
        weekly_df_filtered = filtered_df[filtered_df['data_ora_dt'] >= (filtered_df['data_ora_dt'].max() - pd.Timedelta(days=7))]
        if not weekly_df_filtered.empty:
            w_leaderboard = build_leaderboard(weekly_df_filtered, top_n=10)
            st.dataframe(w_leaderboard, width='stretch', hide_index=True)
        else:
            st.info("No beers logged in the 7 days prior.")

    with tab3:
        st.write("Friends don't let friends stay sober. Who hasn't had a drink in the longest time?")
        if not filtered_df.empty:
            last_seen = filtered_df.groupby('utente')['data_ora_dt'].max().reset_index()
            last_seen['Days MIA'] = (pd.Timestamp.now(tz='Europe/Rome').tz_localize(None) - last_seen['data_ora_dt']).dt.days
            shame_df = last_seen[last_seen['Days MIA'] > 2].sort_values(by='Days MIA', ascending=False).head(10)
            shame_df['Last Pint'] = shame_df['data_ora_dt'].dt.strftime('%d %b %Y')
            shame_df = shame_df[['utente', 'Days MIA', 'Last Pint']].rename(columns={'utente': 'Deserter'})
            if not shame_df.empty:
                st.dataframe(shame_df, width='stretch', hide_index=True)
            else:
                st.success("Everyone has been drinking recently! It's a miracle!")

    with tab4:
        st.write("Want to know why the Official Count is higher than the Database?")
        st.write(f"The DB counted **{int(current_db_total)}** points from photos and videos.")
        st.write(f"The remaining **{int(ghost_beers)}** beers were either lost in the WhatsApp export limit, or logged without a photo!")

with col_right:
    st.subheader("📈 The Buzz Level Over Time")
    with st.container(border=True):
        if not filtered_df.empty and filtered_df['data_ora_dt'].notna().any():
            plot_df = filtered_df.copy()
            plot_df.drop(columns=['Date', 'punti_grafico'], inplace=True, errors='ignore')
            plot_df['Date'] = plot_df['data_ora_dt'].dt.normalize()
            plot_df['punti_grafico'] = plot_df['punti_clean']
            daily_beers = plot_df.groupby('Date')['punti_grafico'].sum().reset_index()
            daily_beers['Cumulative'] = daily_beers['punti_grafico'].cumsum() + ghost_beers
            daily_beers = daily_beers.sort_values('Date')
            chart_data = daily_beers.set_index('Date')[['Cumulative']]
            if len(chart_data) == 0:
                st.info("No timeline data available.")
            elif len(chart_data) == 1:
                st.bar_chart(chart_data, color="#FFA500")
            else:
                st.area_chart(chart_data, color="#FFA500")
        else:
            st.info("Not enough timeline data.")

    st.write("")
    st.subheader("🌍 The Nations Cup")
    with st.container(border=True):
        if not filtered_df.empty:
            df_nations = filtered_df.copy()
            df_nations['prefix'] = df_nations['utente'].replace(REVERSE_NICKNAMES).astype(str).str.extract(r'^(\+\d+)')
            df_nations['Country'] = df_nations['prefix'].apply(get_country)
            nation_stats = df_nations.groupby('Country').agg(
                Total_Pints=('punti_clean', 'sum'),   # FIX: era 'punti', ora 'punti_clean'
                Unique_Drinkers=('utente', 'nunique')
            ).reset_index()
            nation_stats['Per_Capita'] = (nation_stats['Total_Pints'] / nation_stats['Unique_Drinkers']).round(1)

            # --- NUOVO: Limita alle top N nazioni per il grafico ---
            TOP_NATIONS = 15
            nation_stats_sorted = nation_stats.sort_values('Total_Pints', ascending=False)
            nation_stats_top = nation_stats_sorted.head(TOP_NATIONS)
            # --- FINE NUOVO ---

            view_mode = st.radio("Select Leaderboard:", 
                ["🏆 Absolute Total", "⚖️ Per Capita (Pints per person)"], 
                horizontal=True, label_visibility="collapsed")

            if view_mode == "🏆 Absolute Total":
                # USA nation_stats_top INVECE DI nation_stats
                chart_data = nation_stats_top.set_index('Country')[['Total_Pints']]
                st.bar_chart(chart_data, color="#4682B4")
            else:
                # USA nation_stats_top INVECE DI nation_stats
                chart_data = nation_stats_top.sort_values('Per_Capita', ascending=False).set_index('Country')[['Per_Capita']]
                st.bar_chart(chart_data, color="#FF8C00")

            with st.expander(f"📊 View all {len(nation_stats)} nations (full table)"):
                # Tabella completa resta disponibile per chi vuole
                st.dataframe(nation_stats_sorted, use_container_width=True, hide_index=True)
        else:
            st.info("No data available.")

# ==========================================
# 8b. NUOVO: 🗓️ THE DRINKING CALENDAR (Heatmap stile GitHub)
# ==========================================
st.write("")
st.subheader("🗓️ The Drinking Calendar")
st.caption("Each column is a week, each row is a day. The more orange it is, the more we drank. Hover for details!")

calendar_pivot = build_calendar_pivot(filtered_df)
if calendar_pivot is not None:
    if PLOTLY_AVAILABLE:
        day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        week_labels = [w.strftime('%d %b') for w in calendar_pivot.columns]
        fig = px.imshow(
            calendar_pivot.values,
            labels=dict(x="Week", y="Day", color="Beers"),
            x=week_labels,
            y=day_labels,
            color_continuous_scale=['#2a2a2a', '#7a4a00', '#cc7a00', '#ffa500', '#ffd700'],
            aspect='auto'
        )
        fig.update_layout(
            height=230,
            margin=dict(l=10, r=10, t=10, b=10),
            coloraxis_colorbar=dict(title='🍺', thickness=12),
            xaxis=dict(tickangle=45)
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("Install `plotly` for the fancy heatmap. Showing a table instead.")
        calendar_pivot.index = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        st.dataframe(calendar_pivot, width='stretch')
else:
    st.info("Not enough data to build the calendar yet.")

# ==========================================
# 9. UI: ADVANCED ANALYTICS
# ==========================================
st.divider()
st.subheader("📊 Advanced Analytics & Milestones")
tab_time, tab_streaks, tab_milestones, tab_eta = st.tabs(["🕒 Drinking Habits", "🔥 Iron Livers", "🎯 Milestones", "🚀 ETA Tracker"])

with tab_time:
    if not filtered_df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("When do we drink? (Hour of the Day)")
            filtered_df['Hour'] = filtered_df['data_ora_dt'].dt.hour
            hourly_stats = filtered_df.groupby('Hour')['punti_clean'].sum().rename("Points")
            hourly_stats = hourly_stats.reindex(range(24), fill_value=0)
            st.bar_chart(hourly_stats, color="#FFD700")
        with c2:
            st.markdown("**Best Day of the Week?**")
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            nomi_giorni = filtered_df['data_ora_dt'].dt.day_name()
            filtered_df['DayOfWeek'] = pd.Categorical(nomi_giorni, categories=days_order, ordered=True)
            day_stats = filtered_df.groupby('DayOfWeek', observed=False)['punti_clean'].sum().reset_index()
            day_stats = day_stats.rename(columns={'punti_clean': 'Points'})
            st.bar_chart(day_stats, x='DayOfWeek', y='Points', color="#FF8C00")

with tab_streaks:
    st.write("Consecutive days logging at least one beer. Who has the most resilient liver?")
    if not filtered_df.empty:
        streak_df = filtered_df.dropna(subset=['data_ora_dt']).copy()
        streak_df['Date_only'] = pd.to_datetime(streak_df['data_ora_dt'].dt.date)
        user_dates = streak_df[['utente', 'Date_only']].drop_duplicates().sort_values(['utente', 'Date_only'])

        if not user_dates.empty:
            user_dates['Date_diff'] = user_dates.groupby('utente')['Date_only'].diff().dt.days
            user_dates['Streak_ID'] = (user_dates['Date_diff'] != 1).cumsum()
            streak_counts = user_dates.groupby(['utente', 'Streak_ID']).size().reset_index(name='Consecutive Days')
            top_streaks = streak_counts.groupby('utente')['Consecutive Days'].max().reset_index()
            top_streaks = top_streaks.sort_values(by='Consecutive Days', ascending=False).head(10)
            top_streaks.columns = ['Drinker', 'Max Streak (Days)']
            st.markdown("**🏆 All-Time Max Streaks**")
            st.dataframe(top_streaks, width='stretch', hide_index=True)

            # --- ACTIVE STREAKS ---
            st.markdown("---")
            st.markdown("**🔥 Active Streaks — Who is drinking RIGHT NOW?**")

            oggi_streak = pd.Timestamp.now(tz='Europe/Rome').tz_localize(None).normalize()
            active_streaks = []
            for user, grp in streak_df.groupby('utente'):
                dates = sorted(grp['Date_only'].unique())
                if not dates:
                    continue
                streak = 1
                for i in range(len(dates) - 1, 0, -1):
                    if (dates[i] - dates[i - 1]).days == 1:
                        streak += 1
                    else:
                        break
                last_beer = pd.Timestamp(dates[-1]).normalize()
                if (oggi_streak - last_beer).days <= 1:
                    active_streaks.append({
                        'Drinker': user,
                        'Active Streak': streak,
                        'Last Beer': last_beer.strftime('%d %b')
                    })

            if active_streaks:
                as_df = pd.DataFrame(active_streaks).sort_values('Active Streak', ascending=False).head(8)
                st.dataframe(as_df, width='stretch', hide_index=True)
            else:
                st.info("No active streaks. It's a desert out there. 🏜️")

        # [CORRETTO] Questo else ora è allineato perfettamente con l'if iniziale
        else:
            st.info("No streak data available yet.")

with tab_milestones:
    st.write("The legends who posted the exact message that crossed every 500-beer milestone.")
    if not filtered_df.empty:
        ms_df = filtered_df.dropna(subset=['data_ora_dt']).sort_values('data_ora_dt').copy()
        ms_df['running_total'] = ghost_beers + ms_df['punti_clean'].cumsum()
        milestones_hit = []
        min_beers = ghost_beers
        max_beers = ms_df['running_total'].max()
        if max_beers >= 500:
            next_milestone = math.ceil(min_beers / 500) * 500
            if next_milestone == min_beers:
                next_milestone += 500
            while next_milestone <= max_beers:
                hit_rows = ms_df[ms_df['running_total'] >= next_milestone]
                if not hit_rows.empty:
                    hit_row = hit_rows.iloc[0]
                    milestones_hit.append({
                        'Milestone': f"{next_milestone:,} Beers",
                        'Sniper': hit_row['utente'],
                        'Date': hit_row['data_ora_dt'].strftime('%d %b %Y, %H:%M'),
                        'Total Reached': int(hit_row['running_total'])
                    })
                next_milestone += 500
        if milestones_hit:
            ms_display = pd.DataFrame(milestones_hit)
            st.dataframe(ms_display, width='stretch', hide_index=True)
        else:
            st.info("No new 500-beer milestones hit in the recorded history yet!")

with tab_eta:
    st.markdown("Time to 1 Million 🚀")
    st.write("If the line goes down, we are drinking faster! If it goes up, we are slowing down.")
    if not filtered_df.empty and filtered_df['data_ora_dt'].notna().any():
        vero_inizio = pd.to_datetime("2025-06-11").date()
        daily_pts = filtered_df.groupby(filtered_df['data_ora_dt'].dt.date)['punti_clean'].sum()
        daily_cumul = daily_pts.cumsum() + ghost_beers
        eta_data = []
        for d, cumul in daily_cumul.items():
            days_passed = (d - vero_inizio).days
            if days_passed > 10 and cumul > 0:
                pace = cumul / days_passed
                days_left = (GOAL - cumul) / pace
                years_left = round(days_left / 365.25, 2)
                eta_data.append({'Date': d, 'Years Left': years_left})
        if eta_data:
            eta_df = pd.DataFrame(eta_data).set_index('Date')
            if beers_per_day > 0:
                c_days = (GOAL - historical_total) / beers_per_day
                c_years = int(c_days // 365.25)
                c_months = int((c_days % 365.25) // 30.44)
                st.info(f"⏳ **Current Estimate:** At our current pace, it will take us **{c_years} years and {c_months} months** to reach the 1 Million mark.")
            st.line_chart(eta_df, color="#00FA9A")
        else:
            st.info("Not enough historical data to calculate ETA trends yet.")
    else:
        st.info("No data available.")

# ==========================================
# 10. UI: PLAYER SPOTLIGHT & RIVALRY
# ==========================================
st.divider()
st.subheader("🕵️ Player Spotlight & Rivalry")
st.write("Search for a user to see their stats and who they need to beat!")
all_users = sorted(filtered_df['utente'].unique()) if not filtered_df.empty else []
selected_user = st.selectbox("Select a legend:", all_users, label_visibility="collapsed")

if selected_user:
    with st.container(border=True):
        user_df = filtered_df[filtered_df['utente'] == selected_user]
        user_total = user_df['punti_clean'].sum()
        user_uploads = len(user_df)
        user_videos = len(user_df[user_df['tipo_file'] == 'video'])
        avg_beers = user_total / user_uploads if user_uploads > 0 else 0

        lb_completa = build_leaderboard(filtered_df, top_n=1000)
        lb_completa['Drinker_Clean'] = lb_completa['Drinker'].astype(str).str.replace(r'[🥇🥈🥉]\s', '', regex=True)
        try:
            user_rank = lb_completa[lb_completa['Drinker_Clean'] == selected_user].index[0]
            user_score = lb_completa.loc[user_rank, 'Total Score']
            if user_rank == 1:
                rivalry_text = "👑 **You are the undisputed KING.** Everyone is hunting you down."
            else:
                target_score = lb_completa.loc[user_rank - 1, 'Total Score']
                target_name = lb_completa.loc[user_rank - 1, 'Drinker_Clean']
                diff = target_score - user_score
                rivalry_text = f"🎯 **Target acquired:** You only need **{int(diff) + 1} points** to overtake {target_name}!"
        except Exception:
            rivalry_text = "📊 Drink more to get on the leaderboard radar!"

        st.info(rivalry_text)

        # --- NUOVO: ACHIEVEMENTS / BADGES ---
        user_badges = get_badges(user_df)
        if user_badges:
            st.markdown("**🏅 Achievements Unlocked:**")
            st.markdown(" &nbsp;•&nbsp; ".join(user_badges))
            st.write("")

        ucol1, ucol2, ucol3, ucol4 = st.columns(4)
        ucol1.metric("🍻 Logged Beers", int(user_total))
        ucol2.metric("📸 Photos Uploaded", user_uploads)
        ucol3.metric("🍺 Avg per Upload", f"{avg_beers:.1f}")
        ucol4.metric("🎬 Downs", user_videos)

        with st.expander("🔎 View detailed log (Debugger)"):
            debug_table = user_df.sort_values(by='data_ora_dt', ascending=False)[['data_ora', 'punti', 'tipo_file', 'nome_file']].copy()
            debug_table['punti_mostrati'] = debug_table.apply(lambda row: 5 if row['tipo_file'] == 'video' else row['punti'], axis=1)
            debug_table = debug_table[['data_ora', 'punti_mostrati', 'tipo_file', 'nome_file']]
            debug_table.columns = ['Date & Time', 'Personal Points', 'File Type', 'File Name']
            st.dataframe(debug_table, width='stretch', hide_index=True)

# ==========================================
# 11. UI: GLOBAL AUDIT LOG (VAR)
# ==========================================
st.divider()
st.subheader("📺 VAR: Global Audit Log")
with st.expander("Open the full log (Last 100 beers)"):
    st.write("Use this table to find discrepancies between the WhatsApp group count and the Database.")
    audit_df = df.sort_values(by='data_ora_dt', ascending=False).head(100).copy()
    audit_df = audit_df[['data_ora', 'utente', 'punti', 'tipo_file', 'nome_file']]
    audit_df.columns = ['Date & Time', 'Drinker', 'Points Awarded', 'Type', 'File Name']
    st.dataframe(audit_df, width='stretch', hide_index=True)

# ==========================================
# 12. FOOTER & DONATIONS
# ==========================================
st.divider()
col_foot1, col_foot2, col_foot3 = st.columns([1, 2, 1])
with col_foot2:
    st.markdown("<h4 style='text-align: center;'>Enjoying the dashboard? 🍻</h4>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>This project runs on caffeine, beer, and cloud servers. If you want to support the development and keep the bot alive, drop a tip!</p>", unsafe_allow_html=True)
    st.link_button("💸 Buy the Dev a Pint", "https://buy.stripe.com/dRm8wHbyFdS90ss1Fe6EU00", type="primary", width='stretch')
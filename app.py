import streamlit as st
import sqlite3
import pandas as pd
import datetime
import math

# ==========================================
# 1. CONFIGURATIONS & SETUP
# ==========================================
GOAL = 1000000
WEEKLY_GOAL = 250 

st.set_page_config(
    page_title="Project 1M Beers",
    page_icon="🍻",
    layout="wide",
    initial_sidebar_state="expanded" # Aperta di default per far vedere la Time Machine
)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
@st.cache_data(ttl=60) 
def load_data():
    try:
        conn = sqlite3.connect("1m_beers.db")
        df = pd.read_sql_query("SELECT * FROM log_birre", conn)
        
        # Load the Official Total extracted from the chat
        config_df = pd.read_sql_query("SELECT valore FROM config WHERE chiave='OFFICIAL_TOTAL'", conn)
        official_total = config_df['valore'].iloc[0] if not config_df.empty else 17500
        
        conn.close()
        return df, official_total
    except Exception as e:
        return pd.DataFrame(), 17500

def build_leaderboard(df_to_use, top_n=15):
    if df_to_use.empty:
        return pd.DataFrame()
    
    pints = df_to_use[df_to_use['tipo_file'] == 'foto'].groupby('utente')['punti'].sum().rename('Regular Pints')
    num_downs = df_to_use[df_to_use['tipo_file'] == 'video'].groupby('utente').size().rename('Downs')
    
    lb = pd.concat([pints, num_downs], axis=1).fillna(0)
    lb['Total Score'] = lb['Regular Pints'] + (lb['Downs'] * 5)
    
    lb = lb.reset_index().rename(columns={'utente': 'Drinker'})
    lb = lb.sort_values(by='Total Score', ascending=False).head(top_n)
    
    lb['Total Score'] = lb['Total Score'].astype(int)
    lb['Regular Pints'] = lb['Regular Pints'].astype(int)
    lb['Downs'] = lb['Downs'].astype(int)
    
    lb.index = range(1, len(lb) + 1)
    if len(lb) > 0: lb.loc[1, 'Drinker'] = "🥇 " + str(lb.loc[1, 'Drinker'])
    if len(lb) > 1: lb.loc[2, 'Drinker'] = "🥈 " + str(lb.loc[2, 'Drinker'])
    if len(lb) > 2: lb.loc[3, 'Drinker'] = "🥉 " + str(lb.loc[3, 'Drinker'])
    return lb[['Drinker', 'Total Score', 'Regular Pints', 'Downs']]

# ==========================================
# 3. DATA LOADING & BASE PROCESSING
# ==========================================
df, CURRENT_OFFICIAL_TOTAL = load_data()

if df.empty:
    st.error("No data found! Looks like the keg is empty. Run `build_db.py` first.")
    st.stop()

# Date cleaning
df['data_ora_dt'] = pd.to_datetime(df['data_ora'], format='mixed', dayfirst=True, errors='coerce')

# Global logic (Ghost Beers)
totale_foto_db = df[df['tipo_file'] == 'foto']['punti'].sum()
totale_video_db = len(df[df['tipo_file'] == 'video'])
current_db_total = totale_foto_db + totale_video_db
ghost_beers = CURRENT_OFFICIAL_TOTAL - current_db_total

# ==========================================
# 4. SIDEBAR (TIME MACHINE & FILTERS)
# ==========================================
with st.sidebar:
    st.subheader("🕰️ The Time Machine")
    min_date = df['data_ora_dt'].min().date() if not df['data_ora_dt'].isna().all() else datetime.date.today()
    max_date = df['data_ora_dt'].max().date() if not df['data_ora_dt'].isna().all() else datetime.date.today()

    selected_date = st.slider(
        "Drag back in time to see past stats:",
        min_value=min_date,
        max_value=max_date,
        value=max_date,
        format="DD/MM/YYYY"
    )

selected_datetime = pd.to_datetime(selected_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
filtered_df = df[df['data_ora_dt'] <= selected_datetime].copy()

# ==========================================
# 5. CORE MATH & STATS (Based on filtered_df)
# ==========================================
punti_foto = filtered_df[filtered_df['tipo_file'] == 'foto']['punti'].sum()
punti_video = len(filtered_df[filtered_df['tipo_file'] == 'video'])

db_counted_beers = punti_foto + punti_video
historical_total = db_counted_beers + ghost_beers 

total_videos = len(filtered_df[filtered_df['tipo_file'] == 'video'])
record_upload = filtered_df['punti'].max() if not filtered_df.empty else 0

eta_text = "ETA: Keep drinking to calculate..."
beers_per_day = 0
beers_this_week = 0

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
            eta_text = f"🎯 **Milestone ETA:** {eta_date.strftime('%B %Y')}"
            
    seven_days_ago = last_date - pd.Timedelta(days=7)
    weekly_df = filtered_df[filtered_df['data_ora_dt'] >= seven_days_ago]
    beers_this_week = weekly_df['punti'].sum()

# ==========================================
# 6. UI: HEADER & DAILY MVP
# ==========================================
st.title("🍻 The 1 Million Beers Project")
st.markdown("### *One million pints. One legendary group. Zero regrets!* 🚀")

# Daily MVP (Always uses today's un-filtered data)
oggi = pd.Timestamp.now().date()
df_oggi = df[df['data_ora_dt'].dt.date == oggi]

if not df_oggi.empty:
    daily_counts = df_oggi.groupby('utente').size().reset_index(name='Uploads')
    daily_counts = daily_counts.sort_values(by='Uploads', ascending=False).head(3).reset_index(drop=True)
    
    st.markdown("#### 🏆 Today's Top Drinkers")
    cols = st.columns(len(daily_counts))
    medals = ["🥇 1st", "🥈 2nd", "🥉 3rd"]
    
    for i, row in daily_counts.iterrows():
        with cols[i]:
            st.metric(label=medals[i], value=str(row['utente']), delta=f"{row['Uploads']} cheers", delta_color="off")
else:
    st.info("😴 Nobody has had a drink yet today. Who will be the first to break the ice?")

st.write("") 

# ==========================================
# 7. UI: TOP METRICS & PROGRESS BARS
# ==========================================
col1, col2, col3, col4 = st.columns(4)
col1.metric(label="🏆 Estimated Global Count", value=f"{int(historical_total):,}")
col2.metric(label="🔥 Group Pace (Beers/Day)", value=f"{beers_per_day:.1f}")
col3.metric(label="🎬 Downs (Videos)", value=total_videos)
col4.metric(label="👑 Biggest Single Upload", value=int(record_upload) if pd.notna(record_upload) else 0)

st.write("") 

prog_col1, prog_col2 = st.columns(2)
with prog_col1:
    progress_global = min(historical_total / GOAL, 1.0) 
    st.markdown(f"#### 🚀 The Journey: **{int(historical_total):,}** / {GOAL:,} ({progress_global * 100:.3f}%)")
    st.progress(progress_global)
    st.caption(eta_text)

with prog_col2:
    progress_weekly = min(beers_this_week / WEEKLY_GOAL, 1.0)
    st.markdown(f"#### 🗓️ Weekly Mission: **{int(beers_this_week)}** / {WEEKLY_GOAL}")
    st.progress(progress_weekly)
    if beers_this_week >= WEEKLY_GOAL:
        st.caption("✅ **Weekly target smashed!** Awesome job team.")
    else:
        st.caption(f"Need **{int(WEEKLY_GOAL - beers_this_week)}** more pints to hit the target!")

st.divider()

# ==========================================
# 8. UI: MAIN DASHBOARD TABS
# ==========================================
col_left, col_right = st.columns([1, 1.5])

with col_left:
    st.subheader("🏅 Hall of Fame")
    tab1, tab2, tab3, tab4 = st.tabs(["🌟 Legends", "🔥 7-Day Heroes", "🏜️ Wall of Shame", "🛠️ Nerd Stats"])
    
    with tab1:
        leaderboard = build_leaderboard(filtered_df, top_n=15)
        if not leaderboard.empty:
            st.dataframe(leaderboard, width='stretch')
        else:
            st.info("No data yet.")
        
    with tab2:
        weekly_df_filtered = filtered_df[filtered_df['data_ora_dt'] >= (filtered_df['data_ora_dt'].max() - pd.Timedelta(days=7))]
        if not weekly_df_filtered.empty:
            w_leaderboard = build_leaderboard(weekly_df_filtered, top_n=10)
            st.dataframe(w_leaderboard, width='stretch')
        else:
            st.info("No beers logged in the 7 days prior.")
    
    with tab3:
        st.write("Friends don't let friends stay sober. Who hasn't had a drink in the longest time?")
        if not filtered_df.empty:
            last_seen = filtered_df.groupby('utente')['data_ora_dt'].max().reset_index()
            last_seen['Days MIA'] = (pd.Timestamp.now() - last_seen['data_ora_dt']).dt.days
            
            shame_df = last_seen[last_seen['Days MIA'] > 2].sort_values(by='Days MIA', ascending=False).head(10)
            shame_df['Last Pint'] = shame_df['data_ora_dt'].dt.strftime('%d %b %Y')
            
            shame_df = shame_df[['utente', 'Days MIA', 'Last Pint']].rename(columns={'utente': 'Deserter'})
            shame_df.index = range(1, len(shame_df) + 1)
            
            if not shame_df.empty:
                st.dataframe(shame_df, width='stretch')
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
            filtered_df['Date'] = filtered_df['data_ora_dt'].dt.normalize()
            daily_beers = filtered_df.groupby('Date')['punti'].sum().reset_index()
            daily_beers['Cumulative'] = daily_beers['punti'].cumsum() + ghost_beers
            chart_data = daily_beers.set_index('Date')[['Cumulative']]
            
            if len(chart_data) == 0:
                st.info("No timeline data available for the selected period.")
            elif len(chart_data) == 1:
                st.bar_chart(chart_data)
            else:
                st.area_chart(chart_data)
        else:
            st.write("Not enough timeline data to show the chart.")

# ==========================================
# 9. UI: ADVANCED ANALYTICS
# ==========================================
st.divider()
st.subheader("📊 Advanced Analytics & Milestones")
tab_time, tab_streaks, tab_milestones = st.tabs(["🕒 Drinking Habits", "🔥 Iron Livers (Streaks)", "🎯 Milestone Snipers"])

with tab_time:
    if not filtered_df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**When do we drink? (Hour of the Day)**")
            filtered_df['Hour'] = filtered_df['data_ora_dt'].dt.hour
            hourly_stats = filtered_df.groupby('Hour')['punti'].sum()
            hourly_stats = hourly_stats.reindex(range(24), fill_value=0)
            st.bar_chart(hourly_stats)
            
        with c2:
            st.markdown("**Best Day of the Week?**")
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            nomi_giorni = filtered_df['data_ora_dt'].dt.day_name()
            filtered_df['DayOfWeek'] = pd.Categorical(nomi_giorni, categories=days_order, ordered=True)
            
            day_stats = filtered_df.groupby('DayOfWeek', observed=False)['punti'].sum().reset_index()
            st.bar_chart(day_stats, x='DayOfWeek', y='punti')

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
            top_streaks.index = range(1, len(top_streaks) + 1)
            st.dataframe(top_streaks, width='stretch')
        else:
            st.info("No streak data available yet.")

with tab_milestones:
    st.write("The legends who posted the exact message that crossed every 500-beer milestone.")
    if not filtered_df.empty:
        ms_df = filtered_df.dropna(subset=['data_ora_dt']).sort_values('data_ora_dt').copy()
        ms_df['running_total'] = ghost_beers + ms_df['punti'].cumsum()
        
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
            ms_display.index = range(1, len(ms_display) + 1)
            st.dataframe(ms_display, width='stretch')
        else:
            st.info("No new 500-beer milestones hit in the recorded history yet!")

# ==========================================
# 10. UI: PLAYER SPOTLIGHT & RIVALRY
# ==========================================
st.divider()
st.subheader("🕵️ Player Spotlight & Rivalry")
st.write("Search for a user to see their stats and who they need to beat!")

all_users = sorted(filtered_df['utente'].unique()) if not filtered_df.empty else []
selected_user = st.selectbox("Select a legend:", all_users)

if selected_user:
    with st.container(border=True):
        user_df = filtered_df[filtered_df['utente'] == selected_user]
        user_total = user_df['punti'].sum()
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
        except:
            rivalry_text = "📊 Drink more to get on the leaderboard radar!"

        st.info(rivalry_text)
        
        ucol1, ucol2, ucol3, ucol4 = st.columns(4)
        ucol1.metric("🍻 Logged Beers", int(user_total))
        ucol2.metric("📸 Photos Uploaded", user_uploads)
        ucol3.metric("🍺 Avg per Upload", f"{avg_beers:.1f}")
        ucol4.metric("🎬 Downs", user_videos)
        
        with st.expander("🔎 View detailed log (Debugger)"):
            debug_table = user_df.sort_values(by='data_ora_dt', ascending=False)[['data_ora', 'punti', 'tipo_file', 'nome_file']]
            debug_table.columns = ['Date & Time', 'Points Awarded', 'File Type', 'File Name']
            st.dataframe(debug_table, width='stretch')
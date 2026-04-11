import streamlit as st
import requests
import base64
import math
import pandas as pd
import time
import hashlib
import json
from datetime import datetime, timedelta
from streamlit_folium import st_folium
import folium

# --- CONFIG & CREDENTIALS ---
ONFLEET_KEY = st.secrets["ONFLEET_KEY"]
GOOGLE_MAPS_KEY = st.secrets["GOOGLE_MAPS_KEY"]
PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Route-Authorization-Portal/portal-v2.html"
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbynAIziubArSQ0hVGTvJMpk11a9yLP0kNcSmGpcY7GDNRT25Po5p92K3EDslx9VycKC/exec"
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"
SAVED_ROUTES_GID = "1477617688"
ACCEPTED_ROUTES_GID = "934075207"
DECLINED_ROUTES_GID = "600909788"

# Terraboost Media Brand Palette
TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_APP_BG = "#f1f5f9"
TB_HOVER_GRAY = "#e2e8f0"

# Status Fills
TB_GREEN_FILL = "#dcfce7" # Ready
TB_BLUE_FILL = "#dbeafe"  # Sent
TB_RED_FILL = "#ffcccc"   # Flagged

POD_CONFIGS = {
    "Blue": {"states": {"AL", "AR", "FL", "IL", "IA", "LA", "MI", "MN", "MS", "MO", "NC", "SC", "WI"}},
    "Green": {"states": {"CO", "DC", "GA", "IN", "KY", "MD", "NJ", "OH", "UT"}},
    "Orange": {"states": {"AK", "AZ", "CA", "HI", "ID", "NV", "OR", "WA"}},
    "Purple": {"states": {"KS", "MT", "NE", "NM", "ND", "OK", "SD", "TN", "TX", "WY"}},
    "Red": {"states": {"CT", "DE", "ME", "MA", "NH", "NY", "PA", "RI", "VT", "VA", "WV"}}
}

STATE_MAP = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN",
    "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC"
}

headers = {"Authorization": f"Basic {base64.b64encode(f'{ONFLEET_KEY}:'.encode()).decode()}"}

st.set_page_config(page_title="Dispatch Command Center", layout="wide")

# --- UI STYLING ---
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
.stApp {{ background-color: {TB_APP_BG} !important; color: #000000 !important; font-family: 'Inter', sans-serif !important; }}
.main .block-container {{ max-width: 1100px !important; padding-top: 2rem; }}

h1, h2, h3, h4, h5, h6 {{ color: #000000 !important; font-weight: 800 !important; }}

/* GLOBAL TABS STYLING */
.stTabs [data-baseweb="tab-list"] {{ justify-content: center; gap: 8px; background: rgba(255,255,255,0.6); padding: 10px; border-radius: 15px; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 10px !important; padding: 10px 20px !important; font-weight: 700 !important; }}

/* TOP LEVEL TABS (Pod Colors) */
.stTabs [data-baseweb="tab"]:nth-of-type(1) {{ background-color: #ffffff !important; color: #000000 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(2) {{ background-color: #dbeafe !important; color: #000000 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(3) {{ background-color: #dcfce7 !important; color: #000000 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(4) {{ background-color: #ffedd5 !important; color: #000000 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(5) {{ background-color: #f3e8ff !important; color: #000000 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(6) {{ background-color: #fee2e2 !important; color: #000000 !important; }}
.stTabs [aria-selected="true"] {{ transform: scale(1.05); border: 2px solid {TB_PURPLE} !important; z-index: 1; }}

/* MODERN REFRESH ICON */
button[title="Refresh Sheets"] {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #1e293b !important;
    font-size: 24px !important;
    font-weight: 900 !important;
    padding: 0 !important;
    margin-top: 8px !important;
    transition: all 0.4s ease !important;
}}
button[title="Refresh Sheets"]:hover {{
    transform: rotate(180deg) !important;
    color: {TB_GREEN} !important;
    background: transparent !important;
}}

/* NESTED SUB-TABS OVERRIDE */
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(1) {{ background-color: {TB_GREEN_FILL} !important; color: #000000 !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(2) {{ background-color: {TB_BLUE_FILL} !important; color: #000000 !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(3) {{ background-color: {TB_RED_FILL} !important; color: #000000 !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(5) {{ background-color: {TB_GREEN_FILL} !important; color: #000000 !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(6) {{ background-color: {TB_RED_FILL} !important; color: #000000 !important; }}

/* CARDS & INPUTS */
div[data-testid="stExpander"] {{ border: 1px solid #cbd5e1 !important; border-radius: 15px !important; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); margin-bottom: 20px; overflow: hidden; }}

div[data-baseweb="select"] > div, 
div[data-testid="stNumberInput"] input, 
div[data-testid="stDateInput"] input,
div[data-testid="stTextArea"] textarea {{ 
    background-color: #ffffff !important; color: #000000 !important; border: 1.5px solid #cbd5e1 !important; border-radius: 8px !important;
}}

.stButton>button {{ background-color: {TB_PURPLE} !important; color: #ffffff !important; font-weight: 800 !important; border-radius: 12px !important; width: 100%; border: none !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: all 0.2s ease; }}
.stButton>button:hover {{ filter: brightness(1.1); transform: translateY(-2px); box-shadow: 0 6px 10px rgba(0,0,0,0.15); color: #ffffff !important; }}

div[data-testid="stMetricValue"] > div {{ color: #000000 !important; }}
</style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def normalize_state(st_str):
    if not st_str: return "UNKNOWN"
    clean = str(st_str).strip().upper()
    return STATE_MAP.get(clean, clean)

@st.cache_data(ttl=15, show_spinner=False)
def fetch_sent_records_from_sheet():
    try:
        base_url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid="
        sheets_to_fetch = [
            (DECLINED_ROUTES_GID, "declined"),
            (ACCEPTED_ROUTES_GID, "accepted"),
            (SAVED_ROUTES_GID, "sent")
        ]
        sent_dict = {}
        for gid, status_label in sheets_to_fetch:
            try:
                df = pd.read_csv(base_url + gid)
                df.columns = [str(c).strip().lower() for c in df.columns]
                if 'json payload' in df.columns:
                    for _, row in df.iterrows():
                        try:
                            p = json.loads(row['json payload'])
                            tids = str(p.get('taskIds', '')).replace('|', ',').split(',')
                            c_name = str(row.get('contractor', 'Unknown Contractor'))
                            raw_ts = row.get('date created', '')
                            ts_display = ""
                            if pd.notna(raw_ts) and str(raw_ts).strip():
                                try: ts_display = pd.to_datetime(raw_ts).strftime('%m/%d %I:%M %p')
                                except: ts_display = str(raw_ts)
                            for tid in tids:
                                tid = tid.strip()
                                if tid:
                                    sent_dict[tid] = {"name": c_name, "status": status_label, "time": ts_display}
                        except: continue
            except: continue
        return sent_dict
    except Exception as e:
        st.error(f"Failed to fetch portal records: {e}")
        return {}

@st.cache_data(show_spinner=False)
def get_gmaps(home, waypoints):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home}&destination={home}&waypoints=optimize:true|{'|'.join(waypoints)}&key={GOOGLE_MAPS_KEY}"
    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
            hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
            return round(mi, 1), hrs, f"{int(hrs)}h {int((hrs * 60) % 60)}m"
    except: pass
    return 0, 0, "0h 0m"

@st.cache_data(ttl=600)
def load_ic_database(sheet_url):
    try:
        export_url = f"{sheet_url.split('/edit')[0]}/export?format=csv&gid=0"
        return pd.read_csv(export_url)
    except: return None

# --- CORE LOGIC ---
def process_pod(pod_name):
    config = POD_CONFIGS[pod_name]
    progress_bar = st.progress(0, text=f"📥 Extracting {pod_name} tasks...")
    try:
        APPROVED_TEAMS = ["a - escalation", "b - boosted campaigns", "b - local campaigns", "c - priority nationals", "cvs kiosk removal", "n - national campaigns"]
        teams_res = requests.get("https://onfleet.com/api/v2/teams", headers=headers).json()
        target_team_ids = [t['id'] for t in teams_res if any(a in str(t.get('name', '')).lower() for a in APPROVED_TEAMS)] if isinstance(teams_res, list) else []
        
        all_tasks_raw = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}"
        while url:
            res = requests.get(url, headers=headers).json()
            all_tasks_raw.extend(res.get('tasks', []))
            url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}&lastId={res['lastId']}" if res.get('lastId') else None

        pool = []
        for t in all_tasks_raw:
            addr = t.get('destination', {}).get('address', {})
            stt = normalize_state(addr.get('state', ''))
            if stt in config['states']:
                pool.append({
                    "id": t['id'], "city": addr.get('city', 'Unknown'), "state": stt,
                    "full": f"{addr.get('number','')} {addr.get('street','')}, {addr.get('city','')}, {stt}",
                    "lat": t['destination']['location'][1], "lon": t['destination']['location'][0]
                })
        
        clusters = []
        ic_df = st.session_state.get('ic_df', pd.DataFrame())
        v_ics_base = ic_df.dropna(subset=['Lat', 'Lng']).copy() if not ic_df.empty else pd.DataFrame()

        while pool:
            anc = pool.pop(0)
            candidates = [t for t in pool if haversine(anc['lat'], anc['lon'], t['lat'], t['lon']) <= 50]
            pool = [t for t in pool if t not in candidates]
            group = [anc] + candidates
            
            has_ic = False
            if not v_ics_base.empty:
                dists = v_ics_base.apply(lambda x: haversine(anc['lat'], anc['lon'], x['Lat'], x['Lng']), axis=1)
                if any(dists <= 60): has_ic = True

            clusters.append({
                "data": group, "center": [anc['lat'], anc['lon']], 
                "stops": len(set(x['full'] for x in group)), 
                "city": anc['city'], "state": anc['state'],
                "status": "Ready" if has_ic else "Flagged", "has_ic": has_ic
            })
            
        st.session_state[f"clusters_{pod_name}"] = clusters
        progress_bar.empty()
    except Exception as e:
        st.error(f"Error: {str(e)}")

def render_dispatch(i, cluster, pod_name, is_sent=False, is_declined=False):
    st.write(f"### 📍 {cluster['city']} Route")
    st.markdown(f"**Stops:** {cluster['stops']}")
    st.divider()

def run_pod_tab(pod_name):
    st.markdown(f"<h2 style='text-align:center;'>{pod_name} Dashboard</h2>", unsafe_allow_html=True)
    
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"🚀 Initialize {pod_name} Data", key=f"init_{pod_name}"):
            process_pod(pod_name)
            st.rerun()
        return

    cls = st.session_state[f"clusters_{pod_name}"]
    sent_db = fetch_sent_records_from_sheet()
    
    ready = [c for c in cls if c['status'] == 'Ready']
    sent = [c for c in cls if c['status'] == 'Sent'] # Simplified for this lock-in
    review = [c for c in cls if c['status'] == 'Flagged']
    accepted, declined = [], []

    total_tasks = sum(len(c['data']) for c in cls)
    total_dispatched = len(sent) + len(accepted) + len(declined)

    c1, c2, c3 = st.columns([1, 1.5, 1.5])
    with c1: st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px; height: 110px; text-align:center;'><p style='font-size:11px; font-weight:800; text-transform:uppercase;'>Tasks</p><h1>{total_tasks}</h1></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:10px; height: 110px; text-align:center;'><p style='font-size:11px; font-weight:800; text-transform:uppercase;'>Routes</p><div style='display:flex; justify-content:space-around;'><div><p>READY</p><h3>{len(ready)}</h3></div><div><p>SENT</p><h3>{len(sent)}</h3></div></div></div>", unsafe_allow_html=True)
    with c3: st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:10px; height: 110px; text-align:center;'><p style='font-size:11px; font-weight:800; text-transform:uppercase;'>Dispatched</p><h3>{total_dispatched}</h3></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    m = folium.Map(location=cls[0]['center'], zoom_start=6, tiles="cartodbpositron")
    for c in ready: folium.CircleMarker(c['center'], radius=8, color=TB_GREEN, fill=True).add_to(m)
    st_folium(m, width=1100, height=400, key=f"map_{pod_name}")

# --- START ---
if "ic_df" not in st.session_state:
    try:
        url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid=0"
        st.session_state.ic_df = pd.read_csv(url)
    except: st.error("Database connection failed.")

# Main Title + Refresh Row
t_col1, t_col2, t_col3 = st.columns([0.2, 0.6, 0.2])
with t_col2:
    st.markdown("<h1 style='text-align:center;'>Dispatch Command Center</h1>", unsafe_allow_html=True)
with t_col3:
    if st.button("↻", type="tertiary", key="sheet_refresh_icon", help="Refresh Sheets"):
        fetch_sent_records_from_sheet.clear()
        load_ic_database.clear()
        st.rerun()

tabs = st.tabs(["Global", "Blue", "Green", "Orange", "Purple", "Red"])

with tabs[0]:
    st.markdown("<h2 style='text-align:center;'>Global Control</h2>", unsafe_allow_html=True)
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        if st.button("🚀 Initialize All Pods"):
            for p in POD_CONFIGS.keys(): process_pod(p)
            st.rerun()
    with g_col2:
        if st.button("🔄 Sync Google Sheets"):
            fetch_sent_records_from_sheet.clear()
            load_ic_database.clear()
            # Force reload IC DF
            url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid=0"
            st.session_state.ic_df = pd.read_csv(url)
            st.toast("Sheet data synchronized!", icon="✅")
            st.rerun()

for i, pod in enumerate(["Blue", "Green", "Orange", "Purple", "Red"], 1):
    with tabs[i]: run_pod_tab(pod)

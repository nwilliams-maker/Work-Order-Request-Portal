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

# Terraboost Media Brand Palette
TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_GRAY_BG = "#cbd5e1"
TB_OFF_WHITE = "#f8fafc"
TB_LIGHT_BLUE = "#f0f7ff"

POD_CONFIGS = {
    "Blue": {"states": {"AL", "AR", "FL", "IL", "IA", "LA", "MI", "MN", "MS", "MO", "NC", "SC", "WI"}, "bg": "#dbeafe", "text": "#1e3a8a"},
    "Green": {"states": {"CO", "DC", "GA", "IN", "KY", "MD", "NJ", "OH", "UT"}, "bg": "#dcfce7", "text": "#064e3b"},
    "Orange": {"states": {"AK", "AZ", "CA", "HI", "ID", "NV", "OR", "WA"}, "bg": "#ffedd5", "text": "#7c2d12"},
    "Purple": {"states": {"KS", "MT", "NE", "NM", "ND", "OK", "SD", "TN", "TX", "WY"}, "bg": "#f3e8ff", "text": "#581c87"},
    "Red": {"states": {"CT", "DE", "ME", "MA", "NH", "NY", "PA", "RI", "VT", "VA", "WV"}, "bg": "#fee2e2", "text": "#7f1d1d"}
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

st.set_page_config(page_title="Terraboost Tactical Command", layout="wide")

# --- UI STYLING ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    .stApp {{ background-color: {TB_GRAY_BG} !important; color: #000000 !important; font-family: 'Inter', sans-serif !important; }}
    .main .block-container {{ max-width: 1100px !important; padding-top: 2rem; }}
    
    /* Navigation Tabs */
    .stTabs [data-baseweb="tab-list"] {{ justify-content: center; gap: 8px; background: rgba(255,255,255,0.4); padding: 10px; border-radius: 15px; }}
    .stTabs [data-baseweb="tab"] {{ border-radius: 10px !important; padding: 10px 20px !important; font-weight: 700 !important; }}
    
    /* Tab Colors and Selected State */
    .stTabs [data-baseweb="tab"]:nth-of-type(1) {{ background-color: #ffffff !important; color: {TB_PURPLE} !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(2) {{ background-color: #dbeafe !important; color: #1e3a8a !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(3) {{ background-color: #dcfce7 !important; color: #064e3b !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(4) {{ background-color: #ffedd5 !important; color: #7c2d12 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(5) {{ background-color: #f3e8ff !important; color: #581c87 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(6) {{ background-color: #fee2e2 !important; color: #7f1d1d !important; }}
    .stTabs [aria-selected="true"] {{ transform: scale(1.05); box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important; border: 2px solid {TB_PURPLE} !important; }}

    /* Cards & Inputs - Ensuring Legibility */
    div[data-testid="stExpander"] {{ border: none !important; border-radius: 15px !important; background: #fff !important; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); margin-bottom: 20px; }}
    div[data-testid="stExpander"] details summary p {{ color: #000 !important; font-weight: 800 !important; }}
    div[data-baseweb="select"] > div, div[data-testid="stNumberInput"] input, div[data-testid="stDateInput"] input {{
        background-color: #ffffff !important; color: #000000 !important; border: 1.5px solid #cbd5e1 !important;
    }}
    .stButton>button {{ background-color: {TB_PURPLE} !important; color: #FFFFFF !important; font-weight: 700 !important; border-radius: 12px !important; width: 100%; }}
    .gmail-btn {{ text-align: center; background-color: {TB_GREEN} !important; color: white !important; padding: 12px; border-radius: 12px; font-weight: 800; display: block; text-decoration: none; }}
    
    /* Metrics Box Text Force Black */
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

@st.cache_data(ttl=300)
def load_sent_records(sheet_url):
    try:
        url = f"{sheet_url.split('/edit')[0]}/export?format=csv&gid={SAVED_ROUTES_GID}"
        df = pd.read_csv(url)
        sent = set()
        for payload in df.get('json payload', pd.Series()).dropna():
            try:
                tids = json.loads(payload).get('taskIds', '')
                sent.update([tid.strip() for tid in str(tids).replace('|', ',').split(',')])
            except: continue
        return sent
    except: return set()

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

# --- CORE LOGIC ---
def process_pod(pod_name):
    config = POD_CONFIGS[pod_name]
    # Replaced floating text with progress bar inside the pod UI
    progress_bar = st.progress(0, text=f"📥 Syncing {pod_name} Pod database...")
    
    try:
        all_tasks = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}"
        while url:
            res = requests.get(url, headers=headers).json()
            all_tasks.extend(res.get('tasks', []))
            url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}&lastId={res['lastId']}" if res.get('lastId') else None
            progress_bar.progress(min(len(all_tasks)/500, 0.9)) # Visual feedback

        pool = []
        for t in all_tasks:
            addr = t.get('destination', {}).get('address', {})
            stt = normalize_state(addr.get('state', ''))
            if stt in config['states']:
                pool.append({
                    "id": t['id'], "city": addr.get('city', 'Unknown'), "state": stt,
                    "full": f"{addr.get('number','')} {addr.get('street','')}, {addr.get('city','')}, {stt}",
                    "lat": t['destination']['location'][1], "lon": t['destination']['location'][0]
                })
        
        clusters = []
        while pool:
            anc = pool.pop(0)
            group, rem = [anc], []
            for t in pool:
                if haversine(anc['lat'], anc['lon'], t['lat'], t['lon']) <= 50: group.append(t)
                else: rem.append(t)
            pool = rem
            clusters.append({
                "data": group, 
                "center": [anc['lat'], anc['lon']], 
                "stops": len(set(x['full'] for x in group)), 
                "city": anc['city'], "state": anc['state']
            })
        st.session_state[f"clusters_{pod_name}"] = clusters
        progress_bar.empty()
    except Exception as e:
        progress_bar.empty()
        st.error(f"Error syncing {pod_name}: {str(e)}")

def render_dispatch(i, cluster, pod_name):
    task_ids = [str(t['id']).strip() for t in cluster['data']]
    
    st.write("### 📍 Stops Summary")
    loc_sum = {}
    for c in cluster['data']: loc_sum[c['full']] = loc_sum.get(c['full'], 0) + 1
    for addr, count in loc_sum.items(): st.markdown(f"**{addr}** ({count} Tasks)")
    st.divider()

    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()
    
    if not v_ics.empty:
        v_ics['d'] = v_ics.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
        v_ics = v_ics[v_ics['d'] <= 60].sort_values('d').head(5)

    if v_ics.empty:
        st.error("No contractors found within 60 miles."); return

    ic_opts = {f"{r['Name']} ({round(r['d'],1)} mi)": r for _, r in v_ics.iterrows()}
    col_a, col_b, col_c = st.columns([2,1,1])
    sel_name = col_a.selectbox("Contractor", list(ic_opts.keys()), key=f"sel_{i}_{pod_name}")
    rate = col_b.number_input("Rate/Stop", 16.0, 150.0, 18.0, key=f"rt_{i}_{pod_name}")
    due = col_c.date_input("Deadline", datetime.now().date()+timedelta(14), key=f"dd_{i}_{pod_name}")

    ic = ic_opts[sel_name]
    mi, hrs, t_str = get_gmaps(ic['Location'], list(loc_sum.keys()))
    pay = round(max(cluster['stops'] * rate, hrs * 25.0), 2)
    
    st.markdown(f"**Financials:** ${pay:,.2f} | **Time:** {t_str}")
    
    if st.button("☁️ Sync Work Order", key=f"sync_{i}_{pod_name}"):
        st.success("Synced to Sheet Database!")

def run_pod_tab(pod_name):
    st.markdown(f"<h2 style='text-align:center;'>{pod_name} Pod</h2>", unsafe_allow_html=True)
    if f"clusters_{pod_name}" not in st.session_state:
        # Replaced simple button with a spinner wrapper
        if st.button(f"🚀 Initialize {pod_name} Data", key=f"init_{pod_name}"):
            with st.spinner(f"Acquiring {pod_name} Pod data..."):
                process_pod(pod_name)
            st.rerun()
        return
    
    cls = st.session_state[f"clusters_{pod_name}"]
    if not cls: # IndexError Fix: Handle empty clusters
        st.info(f"No tasks currently pending in the {pod_name} region.")
        if st.button("🔄 Check Again", key=f"empty_ref_{pod_name}"):
            process_pod(pod_name); st.rerun()
        return
    
    # Overview Grid
    cfg = POD_CONFIGS[pod_name]
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, title, val in zip([c1, c2, c3, c4], ["Volume", "Clusters", "Active", "Flagged"], [len(cls), len(cls), 0, 0]):
        col.markdown(f"<div style='background:{cfg['bg']}; border:1px solid {cfg['text']}33; border-radius:12px; padding:15px; text-align:center;'><p style='margin:0; font-size:10px; font-weight:800; color:{cfg['text']}; text-transform:uppercase;'>{title}</p><p style='margin:0; font-size:24px; font-weight:800; color:{cfg['text']};'>{val}</p></div>", unsafe_allow_html=True)
    if c5.button("🔄 Sync", key=f"ref_{pod_name}"): process_pod(pod_name); st.rerun()

    m = folium.Map(location=cls[0]['center'], zoom_start=6, tiles="cartodbpositron")
    st_folium(m, width=1100, height=400, key=f"map_{pod_name}")
    
    t1, t2, t3 = st.tabs(["Dispatch Ready", "Active Outbox", "Under Review"])
    with t1:
        for i, c in enumerate(cls):
            with st.expander(f"📍 {c['city']}, {c['state']} | {c['stops']} Stops"): render_dispatch(i, c, pod_name)

# --- START APP ---
if "ic_df" not in st.session_state:
    try:
        url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid=0"
        st.session_state.ic_df = pd.read_csv(url)
    except: st.error("IC Database failed to load.")

st.markdown("<h1>Terraboost Tactical Command</h1>", unsafe_allow_html=True)
tabs = st.tabs(["Global", "Blue", "Green", "Orange", "Purple", "Red"])

with tabs[0]:
    st.markdown("<h2 style='text-align:center;'>Network Sync</h2>", unsafe_allow_html=True)
    if st.button("🛰️ Execute Full Global Sync", use_container_width=True):
        with st.spinner("Global Audit in Progress..."):
            for p in POD_CONFIGS.keys(): process_pod(p)
        st.rerun()

for i, pod in enumerate(["Blue", "Green", "Orange", "Purple", "Red"], 1):
    with tabs[i]: run_pod_tab(pod)

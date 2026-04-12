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

/* TARGET THE GMAIL (PRIMARY) BUTTON SPECIFICALLY */
button[kind="primary"] {{
    background-color: #76bc21 !important; /* TB_GREEN */
    color: white !important;
    height: 3.5rem !important;
    font-size: 1.2rem !important;
    font-weight: 800 !important;
    border: none !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    transition: all 0.2s ease !important;
}}

button[kind="primary"]:hover {{
    filter: brightness(1.1) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 10px rgba(0,0,0,0.15) !important;
}}

/* NESTED SUB-TABS OVERRIDE (Clean Uniform Layout) */
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"] {{
    background-color: #f8fafc !important; 
    color: #475569 !important; 
    border: 1px solid #cbd5e1 !important;
}}
div[data-testid="stTabs"] div[data-testid="stTabs"] [aria-selected="true"] {{
    background-color: #ffffff !important;
    color: #000000 !important;
    border: 2px solid #633094 !important;
}}

/* CARDS & INPUTS */
div[data-testid="stExpander"],
div[data-testid="stExpander"] > details,
div[data-testid="stExpander"] > details > summary,
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
    background-color: #ffffff !important; 
    color: #000000 !important;
}}
div[data-testid="stExpander"] {{ border: 1px solid #cbd5e1 !important; border-radius: 15px !important; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); margin-bottom: 20px; overflow: hidden; }}
div[data-testid="stExpander"] details summary p {{ color: #000000 !important; font-weight: 800 !important; }}

div[data-baseweb="select"] > div, 
    div[data-testid="stNumberInput"] input, 
    div[data-testid="stDateInput"] input,
    div[data-testid="stTextArea"] textarea {{ 
    background-color: #ffffff !important; color: #000000 !important; border: 1.5px solid #cbd5e1 !important; border-radius: 8px !important;
}}

label, div[data-testid="stWidgetLabel"] p {{ color: #000000 !important; font-weight: 600 !important; }}

.stButton>button {{ background-color: {TB_PURPLE} !important; color: #ffffff !important; font-weight: 800 !important; border-radius: 12px !important; width: 100%; border: none !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: all 0.2s ease; }}
.stButton>button:hover {{ filter: brightness(1.1); transform: translateY(-2px); box-shadow: 0 6px 10px rgba(0,0,0,0.15); color: #ffffff !important; }}

div[data-testid="stMetricValue"] > div {{ color: #000000 !important; }}

/* MAP CONTAINER CLEANUP */
    iframe[title="streamlit_folium.st_folium"] {{
        border-radius: 15px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        background-color: transparent !important;
    }}
    
    /* Prevents the 'black box' flicker on refresh */
    .stFolium {{
        background: transparent !important;
    }}
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
                                try:
                                    ts_display = pd.to_datetime(raw_ts).strftime('%m/%d %I:%M %p')
                                except:
                                    ts_display = str(raw_ts)
                            
                            for tid in tids:
                                tid = tid.strip()
                                if tid:
                                    sent_dict[tid] = {
                                        "name": c_name, 
                                        "status": status_label,
                                        "time": ts_display
                                    }
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
    progress_bar = st.progress(0, text=f"📥 Extracting {pod_name} tasks & evaluating dense routes...")
    try:
        APPROVED_TEAMS = [
            "a - escalation", "b - boosted campaigns", "b - local campaigns", 
            "c - priority nationals", "cvs kiosk removal", "n - national campaigns"
        ]

        teams_res = requests.get("https://onfleet.com/api/v2/teams", headers=headers).json()
        target_team_ids = []
        esc_team_ids = []
        
        if isinstance(teams_res, list):
            for team in teams_res:
                t_name = str(team.get('name', '')).lower().strip()
                if any(appr in t_name for appr in APPROVED_TEAMS):
                    target_team_ids.append(team['id'])
                if 'escalation' in t_name:
                    esc_team_ids.append(team['id'])

        all_tasks_raw = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}"
        while url:
            res = requests.get(url, headers=headers).json()
            all_tasks_raw.extend(res.get('tasks', []))
            url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}&lastId={res['lastId']}" if res.get('lastId') else None
            progress_bar.progress(min(len(all_tasks_raw)/500, 0.4))

        unique_tasks_dict = {t['id']: t for t in all_tasks_raw}
        all_tasks = list(unique_tasks_dict.values())

        pool = []
        for t in all_tasks:
            container = t.get('container', {})
            c_type = str(container.get('type', '')).upper()
            
            if c_type == 'TEAM' and container.get('team') not in target_team_ids:
                continue

            addr = t.get('destination', {}).get('address', {})
            stt = normalize_state(addr.get('state', ''))
            is_esc = (c_type == 'TEAM' and container.get('team') in esc_team_ids)
            
            if not is_esc:
                for m in (t.get('metadata') or []):
                    if 'escalation' in str(m.get('name', '')).lower() and str(m.get('value', '')).strip() in ['1', '1.0', 'true', 'yes']:
                        is_esc = True
                        break
            
            tt_val = str(t.get('taskType', '')).strip()
            if not tt_val:
                for m in (t.get('metadata') or []):
                    m_name = str(m.get('name', '')).lower().strip()
                    if m_name in ['tasktype', 'task type']:
                        tt_val = str(m.get('value', '')).strip()
                        break
            
            if not tt_val and 'customFields' in t:
                for cf in (t.get('customFields') or []):
                    cf_name = str(cf.get('name', '')).lower().strip()
                    if cf_name in ['tasktype', 'task type']:
                        tt_val = str(cf.get('value', '')).strip()
                        break
                        
            if not tt_val:
                tt_val = str(t.get('taskDetails', '')).strip()
            
            if stt in config['states']:
                pool.append({
                    "id": t['id'], "city": addr.get('city', 'Unknown'), "state": stt,
                    "full": f"{addr.get('number','')} {addr.get('street','')}, {addr.get('city','')}, {stt}",
                    "lat": t['destination']['location'][1], "lon": t['destination']['location'][0],
                    "escalated": is_esc, "task_type": tt_val
                })
        
        clusters = []
        total_pool = len(pool)
        
        ic_df = st.session_state.get('ic_df', pd.DataFrame())
        v_ics_base = pd.DataFrame()
        if not ic_df.empty:
            v_ics_base = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()

        while pool:
            prog_val = 0.4 + (0.6 * (1 - (len(pool) / total_pool if total_pool > 0 else 1)))
            progress_bar.progress(min(prog_val, 0.99), text=f"🗺️ Auto-routing {pod_name}... ({len(pool)} tasks remaining)")
            
            anc = pool.pop(0)
            candidates = []
            rem = []
            
            for t in pool:
                d = haversine(anc['lat'], anc['lon'], t['lat'], t['lon'])
                if d <= 50: candidates.append((d, t))
                else: rem.append(t)
            
            candidates.sort(key=lambda x: x[0])
            group = [anc] + [c[1] for c in candidates]
            
            has_ic = False
            closest_ic_loc = f"{anc['lat']},{anc['lon']}" 
            
            if not v_ics_base.empty:
                dists = v_ics_base.apply(lambda x: haversine(anc['lat'], anc['lon'], x['Lat'], x['Lng']), axis=1)
                valid_ics = v_ics_base[dists <= 60].copy()
                if not valid_ics.empty:
                    has_ic = True
                    valid_ics['d'] = dists[dists <= 60]
                    best_ic = valid_ics.sort_values('d').iloc[0]
                    closest_ic_loc = best_ic['Location']

            def check_viability(grp):
                seen = set(); unique_locs = []
                for x in grp:
                    if x['full'] not in seen:
                        seen.add(x['full']); unique_locs.append(x['full'])
                if not unique_locs: return 0, 0
                waypts = unique_locs[:25] 
                
                _, hrs, _ = get_gmaps(closest_ic_loc, waypts)
                pay = round(max(len(unique_locs) * 18.0, hrs * 25.0), 2)
                avg = round(pay / len(unique_locs), 2) if len(unique_locs) > 0 else 0
                return avg, len(unique_locs)
            
            gate_avg, u_count = check_viability(group)
            status = "Ready"
            
            if gate_avg > 23.00 and len(group) > 1:
                removed_stops = []
                passed = False
                for _ in range(min(3, len(group) - 1)):
                    removed_stops.append(group.pop()) 
                    new_avg, _ = check_viability(group)
                    if new_avg <= 23.00:
                        passed = True
                        break
                
                if passed:
                    rem.extend(removed_stops)
                    status = "Ready"
                else:
                    group.extend(removed_stops[::-1])
                    status = "Flagged"
            elif gate_avg > 23.00:
                status = "Flagged"
            
            if not has_ic:
                status = "Flagged"
            
            pool = rem
            clusters.append({
                "data": group, "center": [anc['lat'], anc['lon']], 
                "stops": len(set(x['full'] for x in group)), 
                "city": anc['city'], "state": anc['state'],
                "status": status, "has_ic": has_ic,
                "esc_count": sum(1 for x in group if x.get('escalated'))
            })
            
        st.session_state[f"clusters_{pod_name}"] = clusters
        progress_bar.empty()
    except Exception as e:
        progress_bar.empty()
        st.error(f"Error initializing {pod_name}: {str(e)}")

def render_dispatch(i, cluster, pod_name, is_sent=False, is_declined=False):
    task_ids = [str(t['id']).strip() for t in cluster['data']]
    cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
    sync_key = f"sync_{cluster_hash}"
    real_id = st.session_state.get(sync_key)
    link_id = real_id if real_id else "LINK_PENDING"

    # --- 1. STATE KEYS & INITIALIZATION ---
    pay_key = f"pay_val_{cluster_hash}"
    rate_key = f"rate_val_{cluster_hash}"
    sel_key = f"sel_{cluster_hash}"
    last_sel_key = f"last_sel_{cluster_hash}" # Tracks the "previous" selection

    st.write("### 📍 Route Stops")

    # (Task categorization logic remains the same)
    stop_metrics = {}
    for c in cluster['data']:
        addr = c['full']
        if addr not in stop_metrics:
            stop_metrics[addr] = {'t_count': 0, 'n_ad': 0, 'c_ad': 0, 'd_ad': 0, 'inst': 0, 'remov': 0, 'digi': 0, 'oth': 0}

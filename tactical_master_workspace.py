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

/* NESTED SUB-TABS OVERRIDE */
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(1) {{ background-color: {TB_GREEN_FILL} !important; color: #000000 !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(2) {{ background-color: {TB_BLUE_FILL} !important; color: #000000 !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(3) {{ background-color: {TB_RED_FILL} !important; color: #000000 !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(5) {{ background-color: {TB_GREEN_FILL} !important; color: #000000 !important; }}
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(6) {{ background-color: {TB_RED_FILL} !important; color: #000000 !important; }}

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

    st.write("### 📍 Route Stops")

    # --- 1. STOP METRICS & PILLS ---
    stop_metrics = {}
    for c in cluster['data']:
        addr = c['full']
        if addr not in stop_metrics:
            stop_metrics[addr] = {'t_count': 0, 'n_ad': 0, 'c_ad': 0, 'd_ad': 0, 'inst': 0, 'remov': 0, 'digi': 0, 'oth': 0}
        stop_metrics[addr]['t_count'] += 1
        tt = str(c.get('task_type', '')).strip().lower()
        if not tt or any(x in tt for x in ["new ad", "digital ad with bottom", "digital ad with magnet", "art change", "location in venue incorrect", "top"]):
            stop_metrics[addr]['n_ad'] += 1
        elif any(x in tt for x in ["continuity", "move kiosk", "photo retake", "swap magnets", "reorder", "fix", "digital photo", "photo"]):
            stop_metrics[addr]['c_ad'] += 1
        elif any(x in tt for x in ["default", "store default", "default ad", "ad takedown", "pull down"]):
            stop_metrics[addr]['d_ad'] += 1
        elif any(x in tt for x in ["kiosk install", "install"]): stop_metrics[addr]['inst'] += 1
        elif any(x in tt for x in ["kiosk removal", "cvs kiosk removal"]): stop_metrics[addr]['remov'] += 1
        elif any(x in tt for x in ["digital service", "digital ins/remove", "service kiosk"]): stop_metrics[addr]['digi'] += 1
        else: stop_metrics[addr]['oth'] += 1

    loc_pills = {} 
    for addr, metrics in stop_metrics.items():
        pill_parts = []
        if metrics['n_ad'] > 0: pill_parts.append(f"🆕 {metrics['n_ad']} New Ad")
        if metrics['c_ad'] > 0: pill_parts.append(f"🔄 {metrics['c_ad']} Continuity")
        if metrics['d_ad'] > 0: pill_parts.append(f"⚪ {metrics['d_ad']} Default")
        if metrics['inst'] > 0: pill_parts.append(f"🛠️ {metrics['inst']} Kiosk Install")
        if metrics['remov'] > 0: pill_parts.append(f"🛑 {metrics['remov']} Kiosk Removal")
        if metrics['digi'] > 0: pill_parts.append(f"📱 {metrics['digi']} Digital Service")
        if metrics['oth'] > 0: pill_parts.append(f"📦 {metrics['oth']} Other")
        pill_str = " | ".join(pill_parts)
        loc_pills[addr] = f"({metrics['t_count']} Tasks) {pill_str}"
        st.markdown(f"**{addr}** &nbsp;<span style='color: #633094; background-color: #f3e8ff; padding: 2px 6px; border-radius: 10px; font-weight: 800; font-size: 11px;'>{metrics['t_count']} Tasks</span>&nbsp; <span style='font-size: 13px; color: #475569;'>— {pill_str}</span>", unsafe_allow_html=True)
        
    st.divider()

    # --- 2. CONTRACTOR SELECTION ---
    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()
    if not v_ics.empty:
        v_ics['d'] = v_ics.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
        v_ics = v_ics[v_ics['d'] <= 100].sort_values('d').head(5)

    if v_ics.empty:
        st.error("⚠️ No contractors found within 100 miles."); return

    ic_opts = {f"{r['Name']} ({round(r['d'],1)} mi)": r for _, r in v_ics.iterrows()}
    pay_key, rate_key, sel_key, last_sel_key = f"pay_{cluster_hash}", f"rate_{cluster_hash}", f"sel_{cluster_hash}", f"lsel_{cluster_hash}"

    # --- 3. DYNAMIC SYNC & LOCK LOGIC ---
    def sync_on_total(): st.session_state[rate_key] = round(st.session_state[pay_key] / cluster['stops'], 2)
    def sync_on_rate(): st.session_state[pay_key] = round(st.session_state[rate_key] * cluster['stops'], 2)
    
    def update_ic_change():
        sel_label = st.session_state[sel_key]
        if sel_label != st.session_state.get(last_sel_key):
            ic_new = ic_opts[sel_label]
            _, h, _ = get_gmaps(ic_new['Location'], list(stop_metrics.keys())[:25])
            new_pay = float(round(max(cluster['stops'] * 18.0, h * 25.0), 2))
            st.session_state[pay_key] = new_pay
            st.session_state[rate_key] = round(new_pay / cluster['stops'], 2)
            st.session_state[last_sel_key] = sel_label

    if pay_key not in st.session_state:
        ic_init = list(ic_opts.values())[0]
        _, h, _ = get_gmaps(ic_init['Location'], list(stop_metrics.keys())[:25])
        st.session_state[pay_key] = float(round(max(cluster['stops'] * 18.0, h * 25.0), 2))
        st.session_state[rate_key] = round(st.session_state[pay_key] / cluster['stops'], 2)

    col_a, col_b, col_c, col_d = st.columns([1.5, 1, 1, 1])
    with col_a: sel_label = st.selectbox("Contractor", list(ic_opts.keys()), key=sel_key, on_change=update_ic_change)
    
    ic = ic_opts[sel_label]
    mi, hrs, t_str = get_gmaps(ic['Location'], list(stop_metrics.keys())[:25])
    
    curr_rate = st.session_state[rate_key]
    needs_unlock = (curr_rate >= 25.0) or (ic['d'] > 60) or (cluster['status'] == 'Flagged')
    is_unlocked = st.checkbox("🔓 Authorize Premium Rate / Distance", key=f"lock_{cluster_hash}") if needs_unlock else True

    if needs_unlock and not is_unlocked:
        st.warning(f"🔒 Locked: {('High Rate ' if curr_rate >= 25 else '')}{('Distance ' if ic['d'] > 60 else '')}{('Flagged' if cluster['status'] == 'Flagged' else '')}")

    with col_b: pay = st.number_input("Total Comp ($)", step=5.0, key=pay_key, on_change=sync_on_total, disabled=not is_unlocked)
    with col_c: eff_stop = st.number_input("Rate/Stop ($)", step=1.0, key=rate_key, on_change=sync_on_rate, disabled=not is_unlocked)
    with col_d: due = st.date_input("Deadline", datetime.now().date()+timedelta(14), key=f"dd_{cluster_hash}", disabled=not is_unlocked)

    # --- 4. DISPLAY & GMAIL ---
    m1, m2 = st.columns(2)
    with m1: st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px; margin-bottom:10px;'><p style='font-size:11px; font-weight:800; text-transform:uppercase;'>Financials</p><p style='margin:0; font-size:24px; font-weight:800; color:{TB_GREEN if eff_stop <= 23 else '#ef4444'};'>Total: ${pay:,.2f}</p><p style='margin:0; font-size:13px;'>Breakdown: ${eff_stop}/stop</p></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px; margin-bottom:10px;'><p style='font-size:11px; font-weight:800; text-transform:uppercase;'>Logistics</p><p style='margin:0; font-size:24px; font-weight:800;'>{t_str}</p><p style='margin:0; font-size:13px;'>Round Trip: {mi} mi</p></div>", unsafe_allow_html=True)

    sig_preview = (f"Work Order: {ic['Name']} - {datetime.now().strftime('%m%d%Y')}\nContractor: {ic['Name']}\nDue Date: {due.strftime('%A, %b %d, %Y')}\n\n"
           f"Metrics:\n- Stops: {cluster['stops']}\n- Mileage: {mi} mi\n- Time: {t_str}\n- Compensation: ${pay:.2f}\n\n"
           f"Authorize here:\n{PORTAL_BASE_URL}?route={link_id}&v2=true")
    st.text_area("Email Content Preview", sig_preview, height=150, key=f"tx_{cluster_hash}_preview", disabled=not is_unlocked)

    if st.button("🚀 GENERATE LINK & OPEN GMAIL", type="primary", key=f"gbtn_{cluster_hash}", disabled=not is_unlocked):
        final_route_id = real_id
        with st.spinner("Generating..."):
            if not final_route_id or is_declined:
                payload = {"icn": ic['Name'], "ice": ic['Email'], "wo": f"{ic['Name']} - {datetime.now().strftime('%m%d%Y')}", "due": str(due), "comp": pay, "lCnt": cluster['stops'], "mi": mi, "time": t_str, "phone": str(ic['Phone']), "locs": " | ".join([ic['Location']] + list(stop_metrics.keys()) + [ic['Location']]), "taskIds": ",".join(task_ids), "tCnt": len(task_ids), "jobOnly": " | ".join([f"{a} {p}" for a, p in loc_pills.items()])}
                res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}).json()
                if res.get("success"): final_route_id = res.get("routeId")
                else: st.error("Failed."); st.stop()
        gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={ic['Email']}&su=Route Request: {ic['Name']}&body={requests.utils.quote(sig_preview.replace('LINK_PENDING', final_route_id))}"
        st.components.v1.html(f"<script>window.open('{gmail_url}', '_blank');</script>", height=0)
        st.session_state[f"route_state_{cluster_hash}"] = "email_sent"
        st.rerun()
            
def run_pod_tab(pod_name):
    # Grab data from state
    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    st.markdown(f"<h2 style='text-align:center;'>{pod_name} Dashboard</h2>", unsafe_allow_html=True)
    
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"🚀 Initialize {pod_name} Data", key=f"init_{pod_name}"):
            process_pod(pod_name)
            st.rerun()
        return

    cls = st.session_state[f"clusters_{pod_name}"]
    if not cls:
        st.info(f"No tasks pending in the {pod_name} region.")
        return

    # --- 1. SORTING LOGIC ---
    sent_db = fetch_sent_records_from_sheet()
    ready, review, sent, accepted, declined = [], [], [], [], []

    for c in cls:
        task_ids = [str(t['id']).strip() for t in c['data']]
        cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
        
        sheet_match = sent_db.get(next((tid for tid in task_ids if tid in sent_db), None))
        route_state = st.session_state.get(f"route_state_{cluster_hash}")
        
        # Determine status for categorization
        if sheet_match:
            raw_status = sheet_match.get('status')
            if raw_status == 'accepted': accepted.append(c)
            elif raw_status == 'declined': declined.append(c)
            else: sent.append(c)
        elif route_state == "email_sent":
            sent.append(c)
        else:
            if c.get('status') == 'Ready': ready.append(c)
            else: review.append(c)

    # --- 2. METRICS BAR ---
    c1, c2, c3 = st.columns([1, 1.5, 1.5])
    with c1:
        st.markdown(f"""<div style='background:#f8fafc; border:1px solid #cbd5e1; border-radius:12px; padding:15px; height:110px; text-align:center;'><p style='font-size:11px; font-weight:800; text-transform:uppercase; margin:0;'>Tasks</p><h1 style='margin:0;'>{sum(len(c['data']) for c in cls)}</h1></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:10px; height:110px; text-align:center;'><p style='font-size:11px; font-weight:800; text-transform:uppercase; margin:0;'>Routes</p>
            <div style='display:flex; justify-content:space-around;'>
                <div><p style='font-size:10px; margin:0;'>READY</p><h3 style='margin:0;'>{len(ready)}</h3></div>
                <div><p style='font-size:10px; margin:0;'>SENT</p><h3 style='margin:0;'>{len(sent)}</h3></div>
                <div><p style='font-size:10px; margin:0;'>FLAG</p><h3 style='margin:0;'>{len(review)}</h3></div>
            </div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:10px; height:110px; text-align:center;'><p style='font-size:11px; font-weight:800; text-transform:uppercase; margin:0;'>Portal Status</p>
            <div style='display:flex; justify-content:space-around;'>
                <div><p style='font-size:10px; margin:0;'>ACCEPTED</p><h3 style='margin:0;'>{len(accepted)}</h3></div>
                <div><p style='font-size:10px; margin:0;'>DECLINED</p><h3 style='margin:0;'>{len(declined)}</h3></div>
            </div></div>""", unsafe_allow_html=True)

    # --- 3. MAP & ICON KEY ---
    m = folium.Map(location=cls[0]['center'], zoom_start=6, tiles="cartodbpositron")
    for c in ready: folium.CircleMarker(c['center'], radius=8, color=TB_GREEN, fill=True).add_to(m)
    st_folium(m, height=400, use_container_width=True, key=f"map_{pod_name}")

    # --- ICON KEY (LEGEND) WITH HOVER DEFINITIONS ---
    st.markdown("""
        <div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; background: #ffffff; padding: 12px; border-radius: 12px; border: 1px solid #cbd5e1; margin-top: -15px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="font-size: 11px; font-weight: 800; color: #64748b; text-transform: uppercase; align-self: center; margin-right: 5px;">Route Key:</div>
            
            <div style="font-size: 13px; cursor: help; display: flex; align-items: center; gap: 5px;" 
                 title="Standard: Route is within distance limits (<60mi) and standard rate (<$25/stop).">📍 <span>Ready</span></div>
            
            <div style="font-size: 13px; cursor: help; display: flex; align-items: center; gap: 5px;" 
                 title="Locked: Requires manual dispatcher authorization before the email button unlocks.">🔒 <span>Action Required</span></div>
            
            <div style="font-size: 13px; cursor: help; display: flex; align-items: center; gap: 5px;" 
                 title="Cost Alert: The calculated price per stop is $25.00 or higher.">💰 <span>High Rate</span></div>
            
            <div style="font-size: 13px; cursor: help; display: flex; align-items: center; gap: 5px;" 
                 title="Travel Alert: The closest contractor is located more than 60 miles from the route center.">📡 <span>Long Distance</span></div>
            
            <div style="font-size: 13px; cursor: help; display: flex; align-items: center; gap: 5px;" 
                 title="System Flag: This route was flagged for review (e.g., low density or scattered stops).">🔴 <span>Flagged</span></div>
            
            <div style="font-size: 13px; cursor: help; display: flex; align-items: center; gap: 5px;" 
                 title="Priority: This route contains tasks marked with high priority stars.">⭐ <span>Escalated</span></div>
            
            <div style="font-size: 13px; cursor: help; display: flex; align-items: center; gap: 5px;" 
                 title="Dispatched: The route request has been generated and sent to the contractor.">✉️ <span>Sent</span></div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # --- 4. THE SUB-TABS ---
    t1, t2, t3, gap, t4, t5 = st.tabs(["Ready", "Sent", "Flagged", " ", "Accepted", "Declined"])
    
    with t1:
        if not ready: st.info("No tasks ready for dispatch.")
        for i, c in enumerate(ready):
            # Calculate dynamic badges for Ready tab
            badges = ""
            if not ic_df.empty:
                v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()
                if not v_ics.empty:
                    v_ics['d'] = v_ics.apply(lambda x: haversine(c['center'][0], c['center'][1], x['Lat'], x['Lng']), axis=1)
                    best = v_ics.sort_values('d').iloc[0]
                    _, h, _ = get_gmaps(best['Location'], [t['full'] for t in c['data'][:25]])
                    est_rate = max(c['stops'] * 18.0, h * 25.0) / c['stops'] if c['stops'] > 0 else 0
                    if est_rate >= 25: badges += "💰"
                    if best['d'] > 60: badges += "📡"
                    if badges: badges = "🔒 " + badges
            
            with st.expander(f"{badges} 📍 {c['city']}, {c['state']} | {c['stops']} Stops"):
                render_dispatch(i, c, pod_name)

    with t2:
        if not sent: st.info("No pending routes sent.")
        for i, c in enumerate(sent):
            with st.expander(f"✉️ {c['city']}, {c['state']} | {c['stops']} Stops"):
                render_dispatch(i+500, c, pod_name, is_sent=True)
            
    with t3:
        if not review: st.info("No flagged tasks requiring review.")
        for i, c in enumerate(review):
            with st.expander(f"🔒 🔴 {c['city']}, {c['state']} | {c['stops']} Stops"):
                render_dispatch(i+1000, c, pod_name)

    with t4:
        if not accepted: st.info("No routes accepted yet.")
        for i, c in enumerate(accepted):
            with st.expander(f"✅ {c['city']}, {c['state']} | {c['stops']} Stops"):
                render_dispatch(i+2000, c, pod_name, is_sent=True)

    with t5:
        if not declined: st.info("No declined routes.")
        for i, c in enumerate(declined):
            with st.expander(f"❌ {c['city']}, {c['state']} | {c['stops']} Stops"):
                render_dispatch(i+3000, c, pod_name, is_declined=True)

# --- START ---
if "ic_df" not in st.session_state:
    try:
        url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid=0"
        st.session_state.ic_df = pd.read_csv(url)
    except: st.error("Database connection failed.")

st.markdown("<h1>Dispatch Command Center</h1>", unsafe_allow_html=True)
tabs = st.tabs(["Global", "Blue", "Green", "Orange", "Purple", "Red"])

with tabs[0]:
    st.markdown("<h2 style='text-align:center;'>Global Control</h2>", unsafe_allow_html=True)
    c_btn = st.columns([1,2,1])[1]
    if c_btn.button("🚀 Initialize All Pods", use_container_width=True):
        st.session_state.sent_db = fetch_sent_records_from_sheet()
        for p in POD_CONFIGS.keys(): process_pod(p)
        st.rerun()

for i, pod in enumerate(["Blue", "Green", "Orange", "Purple", "Red"], 1):
    with tabs[i]: run_pod_tab(pod)

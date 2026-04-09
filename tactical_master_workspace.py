import streamlit as st
import requests
import base64
import math
import pandas as pd
import time
import hashlib
from datetime import datetime, timedelta
from streamlit_folium import st_folium
import folium

# --- CONFIG & CREDENTIALS ---
ONFLEET_KEY = st.secrets["ONFLEET_KEY"]
GOOGLE_MAPS_KEY = st.secrets["GOOGLE_MAPS_KEY"]
PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Route-Authorization-Portal/portal-v2.html"
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbynAIziubArSQ0hVGTvJMpk11a9yLP0kNcSmGpcY7GDNRT25Po5p92K3EDslx9VycKC/exec"

IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"

MAX_DEADHEAD_MILES = 60
HOURLY_FLOOR_RATE = 25.00
MAX_RATE_PER_STOP = 22.00

TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_LIGHT_BLUE = "#e6f0fa"

POD_CONFIGS = {
    "Blue Pod": {"states": {"AL", "AR", "FL", "IL", "IA", "LA", "MI", "MN", "MS", "MO", "NC", "SC", "WI"}, "color": "blue"},
    "Green Pod": {"states": {"CO", "DC", "GA", "IN", "KY", "MD", "NJ", "OH", "UT"}, "color": "green"},
    "Orange Pod": {"states": {"AK", "AZ", "CA", "HI", "ID", "NV", "OR", "WA"}, "color": "orange"},
    "Purple Pod": {"states": {"KS", "MT", "NE", "NM", "ND", "OK", "SD", "TN", "TX", "WY"}, "color": "purple"},
    "Red Pod": {"states": {"CT", "DE", "ME", "MA", "NH", "NY", "PA", "RI", "VT", "VA", "WV"}, "color": "red"}
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

GEO_PRICING = {
    "CA": 20.00, "WA": 19.50, "OR": 18.00, "HI": 20.00, "AK": 18.50,
    "NV": 16.00, "AZ": 17.50, "ID": 16.00, "NY": 20.00, "NJ": 19.00,
    "CT": 18.00, "MA": 18.00, "IL": 18.00, "FL": 17.50, "TX": 17.00
}

headers = {"Authorization": f"Basic {base64.b64encode(f'{ONFLEET_KEY}:'.encode()).decode()}"}

st.set_page_config(page_title="Terraboost Tactical Workspace", layout="wide")

# --- UI STYLING ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
    .stApp {{ background-color: #f4f5f7 !important; color: #323338 !important; font-family: 'Roboto', sans-serif !important; }}
    
    .main-header {{ 
        font-family: 'Roboto', sans-serif !important; 
        color: {TB_PURPLE}; 
        font-weight: 700; 
        font-size: 32px; 
        margin-bottom: 20px;
    }}

    .metric-container {{ display: flex; gap: 20px; margin-bottom: 20px; }}
    .metric-card {{
        background: white;
        padding: 15px 20px;
        border-radius: 8px;
        border-left: 5px solid {TB_PURPLE};
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        min-width: 180px;
    }}
    .metric-card.ready {{ border-left-color: {TB_GREEN}; }}
    .metric-card.review {{ border-left-color: #f44336; }}
    
    .metric-label {{ font-size: 12px; text-transform: uppercase; color: #676879; font-weight: 700; }}
    .metric-value {{ font-size: 24px; color: #323338; font-weight: 700; }}

    .stTabs [data-baseweb="tab"] {{ font-family: 'Roboto', sans-serif !important; font-weight: 500; }}
    .stButton>button {{ font-family: 'Roboto', sans-serif !important; font-weight: 700; }}
    </style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
def normalize_state(st_str):
    if not st_str: return "UNKNOWN"
    clean = str(st_str).strip().upper()
    return STATE_MAP.get(clean, clean)

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

@st.cache_data(show_spinner=False, ttl=86400)
def fetch_gmaps_directions(home, waypoints_tuple):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home}&destination={home}&waypoints=optimize:true|{'|'.join(waypoints_tuple)}&key={GOOGLE_MAPS_KEY}"
    mi, hrs, t_str = 0, 0, "0h 0m"
    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
            hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
            t_str = f"{int(hrs)}h {int((hrs * 60) % 60)}m"
    except: pass
    return mi, hrs, t_str

def get_metrics(home, cluster_nodes, stop_rate):
    unique_addrs = list(set([c['full_addr'] for c in cluster_nodes]))
    mi, hrs, t_str = fetch_gmaps_directions(home, tuple(unique_addrs[:10]))
    stop_count = len(unique_addrs)
    pre_pay = max(stop_count * stop_rate, hrs * HOURLY_FLOOR_RATE)
    max_cap = stop_count * MAX_RATE_PER_STOP
    pay = min(pre_pay, max_cap)
    p_type = f"Capped at ${MAX_RATE_PER_STOP}/Stop" if pre_pay > max_cap else "Standard Rate"
    h_rate = (pay / hrs) if hrs > 0 else 0
    return round(mi, 1), t_str, round(pay, 2), round(h_rate, 2), p_type

def sync_to_sheet(ic, cluster_data, mi, time_str, pay, work_order, location_summary, due_date):
    locs_str = " | ".join([f"{addr} ({count} Tasks)" for addr, count in location_summary.items()])
    payload = {
        "icn": str(ic.get('Name', '')), "ice": str(ic.get('Email', '')), "wo": work_order,
        "due": due_date.strftime('%Y-%m-%d'), "comp": f"{pay:.2f}", "mi": str(mi),
        "time": str(time_str), "locs": locs_str, "lCnt": len(location_summary),
        "tCnt": len(cluster_data), "phone": str(ic.get('Phone', '')),
        "taskIds": ",".join([c['id'] for c in cluster_data])
    }
    try:
        res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload})
        if res.status_code == 200:
            data = res.json()
            if data.get("success"): return data.get("routeId")
    except: pass
    return False

@st.cache_data(ttl=600)
def load_ic_database(sheet_url):
    try: return pd.read_csv(f"{sheet_url.split('/edit')[0]}/export?format=csv&gid=0")
    except: return None

# --- AGGRESSIVE ROUTING LOGIC ---
def process_pod_data(pod_name):
    config = POD_CONFIGS[pod_name]
    with st.status(f"📡 Synchronizing {pod_name} Intelligence...", expanded=True) as status:
        all_tasks = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time() * 1000) - (80 * 24 * 3600 * 1000)}"
        while True:
            res = requests.get(url, headers=headers)
            if res.status_code != 200: break
            data = res.json(); batch = data.get('tasks', [])
            all_tasks.extend(batch)
            if data.get('lastId') and len(batch) > 0:
                url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time() * 1000) - (80 * 24 * 3600 * 1000)}&lastId={data['lastId']}"
            else: break
        
        pool = []
        for t in all_tasks:
            a = t.get('destination', {}).get('address', {})
            stt = normalize_state(a.get('state', ''))
            if stt in config['states']:
                pool.append({"id": t['id'], "city": a.get('city', 'Unknown'), "state": stt,
                    "full_addr": f"{a.get('number', '')} {a.get('street', '')}, {a.get('city', '')}, {stt}",
                    "lat": t.get('destination', {}).get('location', [0, 0])[1],
                    "lon": t.get('destination', {}).get('location', [0, 0])[0]})

        # --- TWO-PASS CLUSTERING ---
        final_routes = []
        
        # Pass 1: Build Strong Anchors (routes that likely meet criteria)
        while pool:
            anchor = pool.pop(0)
            group, unique_locs, rem = [anchor], {anchor['full_addr']}, []
            for t in pool:
                if haversine(anchor['lat'], anchor['lon'], t['lat'], t['lon']) <= 30.0:
                    group.append(t); unique_locs.add(t['full_addr'])
                else: rem.append(t)
            
            pool = rem
            final_routes.append({
                "data": group, 
                "center": [anchor['lat'], anchor['lon']], 
                "unique_count": len(unique_locs)
            })

        # Pass 2: Straggler Integration
        # Look for small routes and try to merge them into larger ones within range
        merged_indices = set()
        for i in range(len(final_routes)):
            if i in merged_indices: continue
            if final_routes[i]['unique_count'] < 4: # Identify "Straggler" candidates
                for j in range(len(final_routes)):
                    if i == j or j in merged_indices: continue
                    # If this straggler is within 30 miles of another route's center
                    dist = haversine(final_routes[i]['center'][0], final_routes[i]['center'][1], 
                                     final_routes[j]['center'][0], final_routes[j]['center'][1])
                    if dist <= 30.0:
                        final_routes[j]['data'].extend(final_routes[i]['data'])
                        # Recalculate unique count for the receiving route
                        all_addrs = set([d['full_addr'] for d in final_routes[j]['data']])
                        final_routes[j]['unique_count'] = len(all_addrs)
                        merged_indices.add(i)
                        break

        # Final Cleanup
        cleaned_routes = [final_routes[k] for k in range(len(final_routes)) if k not in merged_indices]
        
        # Define 'acceptable' for categorization in UI
        for r in cleaned_routes:
            r['acceptable'] = r['unique_count'] >= 4

        st.session_state[f"clusters_{pod_name}"] = cleaned_routes
        status.update(label="✅ Aggressive Route Intelligence Loaded", state="complete", expanded=False)

# --- UI RENDER FUNCTIONS ---
def render_dispatch_logic(i, cluster, pod_name):
    cluster_hash = hashlib.md5("".join(sorted([t['id'] for t in cluster['data']])).encode()).hexdigest()
    sync_key = f"sync_{cluster_hash}"
    real_gas_id = st.session_state.get(sync_key, None)
    link_id = real_gas_id if real_gas_id else "LINK_GENERATED_UPON_SYNC"

    loc_sum = {}
    for d in cluster['data']:
        addr = d['full_addr']
        loc_sum[addr] = loc_sum.get(addr, 0) + 1
    for addr, count in loc_sum.items(): st.write(f"• **{addr}** ({count} Tasks)")
    
    ic_df = st.session_state.ic_df
    v_ics = ic_df.dropna(subset=['Lat', 'Lng']).copy() if ic_df is not None else pd.DataFrame()
    
    c_lat, c_lon = cluster['center']
    if not v_ics.empty:
        v_ics['d'] = v_ics.apply(lambda x: haversine(c_lat, c_lon, x['Lat'], x['Lng']), axis=1)
        valid_ics = v_ics[v_ics['d'] <= MAX_DEADHEAD_MILES].sort_values('d').head(5)
    else: valid_ics = pd.DataFrame()

    if valid_ics.empty:
        st.error("⚠️ No nearby contractors found.")
        return

    ic_opts = {f"{row['Name']} ({round(row['d'], 1)} mi)": row for _, row in valid_ics.iterrows()}
    c_ic, c_rate, c_due = st.columns([2, 1, 1])
    sel_label = c_ic.selectbox("Contractor", list(ic_opts.keys()), key=f"s_{i}_{pod_name}")
    rate = c_rate.number_input("Rate", 16.0, 22.0, 18.0, 0.5, key=f"r_{i}_{pod_name}")
    due = c_due.date_input("Due", datetime.now().date() + timedelta(days=14), key=f"d_{i}_{pod_name}")
    
    sel_ic = ic_opts[sel_label]
    mi, t_str, pay, hr_rate, p_type = get_metrics(sel_ic['Location'], cluster['data'], rate)
    
    st.markdown(f"""
        <div style="background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; margin: 10px 0;">
            <b>Comp: <span style="color:{TB_GREEN}">${pay:.2f}</span></b> | <b>Drive: {mi} mi</b> | <b>Time: {t_str}</b>
        </div>
    """, unsafe_allow_html=True)

    wo_title = f"{sel_ic['Name']} - {datetime.now().strftime('%m%d%Y')}-{i}"
    sig = f"Work Order: {wo_title}\nDue: {due.strftime('%Y-%m-%d')}\nMetrics: {mi} mi, {t_str}\nPay: ${pay:.2f}\n\nAuthorize: {PORTAL_BASE_URL}?route={link_id}&v2=true"
    st.text_area("Email Preview", sig, height=150, key=f"txt_{i}_{pod_name}_{link_id}")

    col1, col2 = st.columns(2)
    with col1:
        if not real_gas_id:
            if st.button("☁️ Sync Data", key=f"btn_s_{i}_{pod_name}"):
                rid = sync_to_sheet(sel_ic, cluster['data'], mi, t_str, pay, wo_title, loc_sum, due)
                if rid: st.session_state[sync_key] = rid; st.rerun()
        else: st.button("✅ Synced", disabled=True, key=f"btn_d_{i}_{pod_name}")
    
    with col2:
        if real_gas_id:
            mail = f"https://mail.google.com/mail/?view=cm&fs=1&to={sel_ic['Email']}&su=Route Request&body={requests.utils.quote(sig)}"
            st.markdown(f'<a href="{mail}" target="_blank" style="text-decoration:none;"><div style="background:{TB_GREEN};color:white;padding:10px;text-align:center;border-radius:4px;font-weight:bold;">📧 Send Gmail</div></a>', unsafe_allow_html=True)
        else: st.markdown('<div style="background:#e2e8f0;color:#94a3b8;padding:10px;text-align:center;border-radius:4px;font-weight:bold;">📧 Sync First</div>', unsafe_allow_html=True)

# --- TAB RENDER ---
def run_pod_tab(pod_name):
    st.markdown(f'<div class="main-header">{pod_name} Command Center</div>', unsafe_allow_html=True)
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"📥 Initialize {pod_name}", key=f"init_{pod_name}"): process_pod_data(pod_name); st.rerun()
        return

    clusters = st.session_state[f"clusters_{pod_name}"]
    ic_df = st.session_state.ic_df
    v_ics = ic_df.dropna(subset=['Lat', 'Lng']) if ic_df is not None else pd.DataFrame()
    
    acc, unacc = [], []
    for c in clusters:
        has_ic = False
        if not v_ics.empty:
            dists = v_ics.apply(lambda x: haversine(c['center'][0], c['center'][1], x['Lat'], x['Lng']), axis=1)
            has_ic = (dists <= MAX_DEADHEAD_MILES).any()
        
        # DISTINCTION LOGIC: Ready vs Review
        if c['acceptable'] and has_ic:
            acc.append(c)
        else:
            unacc.append(c)

    st.markdown(f"""
        <div class="metric-container">
            <div class="metric-card"><div class="metric-label">Total Routes</div><div class="metric-value">{len(clusters)}</div></div>
            <div class="metric-card ready"><div class="metric-label">Ready</div><div class="metric-value">{len(acc)}</div></div>
            <div class="metric-card review"><div class="metric-label">Review</div><div class="metric-value">{len(unacc)}</div></div>
        </div>
    """, unsafe_allow_html=True)

    m = folium.Map(location=clusters[0]['center'], zoom_start=6, tiles="cartodbpositron")
    for c in acc: folium.CircleMarker(c['center'], radius=10, color=TB_GREEN, fill=True, opacity=0.7).add_to(m)
    for c in unacc: folium.CircleMarker(c['center'], radius=10, color="#f44336", fill=True, opacity=0.7).add_to(m)
    st_folium(m, use_container_width=True, height=450, key=f"map_{pod_name}")

    t1, t2 = st.tabs(["🟢 Ready to Dispatch", "🔴 Review Required"])
    with t1:
        for i, c in enumerate(acc):
            with st.expander(f"📍 {c['data'][0]['city']} | {c['unique_count']} Stops"): render_dispatch_logic(i, c, pod_name)
    with t2:
        for i, c in enumerate(unacc):
            with st.expander(f"🔴 Review Required | {c['data'][0]['city']} | {c['unique_count']} Stops"): render_dispatch_logic(i+1000, c, pod_name)

# --- MAIN ---
if "ic_df" not in st.session_state: st.session_state.ic_df = load_ic_database(IC_SHEET_URL)
tab_b, tab_gr, tab_o, tab_p, tab_r = st.tabs(["🔵 Blue", "🟢 Green", "🟠 Orange", "🟣 Purple", "🔴 Red"])
with tab_b: run_pod_tab("Blue Pod")
with tab_gr: run_pod_tab("Green Pod")
with tab_o: run_pod_tab("Orange Pod")
with tab_p: run_pod_tab("Purple Pod")
with tab_r: run_pod_tab("Red Pod")

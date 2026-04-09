import streamlit as st
import requests
import base64
import math
import pandas as pd
import time
import hashlib
from datetime import datetime, timedelta

# --- CONFIG & CREDENTIALS ---
ONFLEET_KEY = st.secrets["ONFLEET_KEY"]
GOOGLE_MAPS_KEY = st.secrets["GOOGLE_MAPS_KEY"]
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbynAIziubArSQ0hVGTvJMpk11a9yLP0kNcSmGpcY7GDNRT25Po5p92K3EDslx9VycKC/exec"
PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Route-Authorization-Portal/portal-v2.html"
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"

HOURLY_FLOOR_RATE = 25.00
TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_LIGHT_BLUE = "#e6f0fa"

headers = {"Authorization": f"Basic {base64.b64encode(f'{ONFLEET_KEY}:'.encode()).decode()}"}

@st.cache_data(ttl=600)
def load_ics():
    return pd.read_csv(f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid=0")

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_metrics(home_addr, cluster_data, rate):
    unique_addrs = list(set([t['full_addr'] for t in cluster_data]))
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home_addr}&destination={home_addr}&waypoints=optimize:true|{'|'.join(unique_addrs[:10])}&key={GOOGLE_MAPS_KEY}"
    res = requests.get(url).json()
    mi, hrs, t_str = 0, 0, "0h 0m"
    if res['status'] == 'OK':
        mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
        hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
        t_str = f"{int(hrs)}h {int((hrs * 60) % 60)}m"
    pay = max(len(unique_addrs) * rate, hrs * HOURLY_FLOOR_RATE)
    return round(mi, 1), t_str, round(pay, 2)

# --- UI RENDERING ---
def render_card(i, cluster, pod_name):
    ic_df = st.session_state.ic_df.dropna(subset=['Lat', 'Lng'])
    ic_df['d'] = ic_df.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
    valid_ics = ic_df[ic_df['d'] <= 60].sort_values('d').head(5)
    
    if valid_ics.empty: st.error("No ICs nearby"); return

    ic_opts = {f"{r['Name']} ({round(r['d'], 1)} mi)": r for _, r in valid_ics.iterrows()}
    sel_label = st.selectbox("Contractor", list(ic_opts.keys()), key=f"s_{i}")
    sel_ic = ic_opts[sel_label]
    
    rate = st.number_input("Rate", 16.0, 100.0, 18.0, key=f"r_{i}")
    mi, t_str, pay = get_metrics(sel_ic['Location'], cluster['data'], rate)
    
    wo_id = f"{sel_ic['Name'][:3].upper()}-{int(time.time())}"
    
    # DYNAMIC PAYLOAD
    sig = (f"Work Order: {wo_id}\nPay: ${pay}\nStops: {cluster['unique_count']}\n"
           f"Authorize: {PORTAL_BASE_URL}?route=PENDING&v2=true")
    
    st.text_area("Email Payload", sig, height=150)
    
    if st.button("Sync & Generate Link", key=f"b_{i}"):
        payload = {
            "icn": sel_ic['Name'], "wo": wo_id, "comp": pay, 
            "lCnt": cluster['unique_count'], "tCnt": len(cluster['data']),
            "mi": mi, "time": t_str, "ic_home": sel_ic['Location'],
            "locs": " | ".join([t['full_addr'] for t in cluster['data']])
        }
        res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}).json()
        st.success(f"Link: {PORTAL_BASE_URL}?route={res['routeId']}&v2=true")

st.session_state.ic_df = load_ics()
# ... (Tab Logic and Onfleet Fetching same as previously established)

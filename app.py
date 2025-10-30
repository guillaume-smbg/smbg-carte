
import os, io, re, unicodedata, math
from typing import Optional
import pandas as pd
import streamlit as st
import folium
import requests
from streamlit_folium import st_folium

# ---------- Page / style ----------

st.set_page_config(page_title="SMBG Carte — Leaflet (Mapnik)", layout="wide")

LOGO_BLUE = "#05263d"
COPPER = "#c47e47"

CSS = f"""
<style>
  [data-testid="collapsedControl"] {{ display: none !important; }}

  [data-testid="stSidebar"] {{
    width: 275px; min-width: 275px; max-width: 275px;
    background: {LOGO_BLUE}; color: {COPPER};
  }}
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3,
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] label {{
    color: {COPPER} !important;
  }}

  [data-testid="stSidebar"] .group-title {{
    margin: 8px 0 4px 0;
    font-weight: 700;
    color: {COPPER};
  }}

  [data-testid="stSidebar"] .stButton > button,
  [data-testid="stSidebar"] .stButton > button * {{
    background: {COPPER} !important;
    color: #ffffff !important;
    font-weight: 700;
    border-radius: 10px;
    border: none;
  }}

  [data-testid="stAppViewContainer"] {{
    padding-top: 0;
    padding-bottom: 0;
  }}
  .block-container {{
    padding-top: 8px !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
  }}

  .drawer {{
    position: fixed;
    top:0;
    right:0;
    width:275px;
    height:100vh;
    background:#fff;
    transform: translateX(0);
    transition: transform .24s ease;
    z-index: 9999;
    border-left: 1px solid #e9eaee;
    box-shadow: -14px 0 28px rgba(0,0,0,.12);
    overflow-y:auto;
  }}

  .drawer-banner {{
    background:{LOGO_BLUE};
    color:#fff;
    padding:12px 16px;
    font-weight:800;
    font-size:18px;
    position:sticky;
    top:0;
  }}

  .drawer-body {{
    padding:14px 16px 24px;
  }}

  .lots-title {{
    margin-top: 12px;
    font-weight: 800;
    color: {LOGO_BLUE};
  }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"

def normalize_excel_url(url: str) -> str:
    if not url:
        return url
    return re.sub(r"https://github\.com/(.+)/blob/([^ ]+)", r"https://github.com/\1/raw/\2", url.strip())

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    excel_url = normalize_excel_url(excel_url)
    if excel_url:
        r = requests.get(excel_url, timeout=25)
        r.raise_for_status()
        return pd.read_excel(io.BytesIO(r.content))
    if not os.path.exists(DEFAULT_LOCAL_PATH):
        st.stop()
    return pd.read_excel(DEFAULT_LOCAL_PATH)

def normalize_bool(val):
    if isinstance(val, str): return val.strip().lower() in ["oui", "yes", "true", "1", "vrai"]
    if isinstance(val, (int, float)): return int(val) == 1
    return bool(val)

def norm_txt(x: str) -> str:
    if x is None: return ""
    s = str(x).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s)

def find_col(df, *candidates):
    norm_map = {c: norm_txt(c) for c in df.columns}
    for cand in candidates:
        cn = norm_txt(cand)
        for c, n in norm_map.items():
            if n == cn: return c
        for c, n in norm_map.items():
            if all(part in n for part in cn.split()): return c
    return ""

def to_number(value):
    if value is None: return None
    s = str(value).strip().replace("€","").replace("m²","").replace("m2","").replace(" ","").replace(",",".")
    try: return float(re.findall(r"-?\d+(?:\.\d+)?", s)[0])
    except: return None

def clean_numeric_series(s): return s.map(to_number)
def clean_latlon_series(s): return s.astype(str).str.strip().str.replace(",",".",regex=False).map(to_number)

def build_lots_table(df):
    cols = list(df.columns)
    if len(cols) > 33: view = df.iloc[:,6:34].copy()
    else: view = df.copy()
    return view

def drawer_for_reference(df, gm_col, ref):
    st.markdown('<div class="drawer">', unsafe_allow_html=True)
    st.markdown(f'<div class="drawer-banner">Référence : {ref}</div>', unsafe_allow_html=True)
    st.markdown('<div class="drawer-body">', unsafe_allow_html=True)
    gm_link = None
    if gm_col in df.columns:
        for v in df[gm_col].astype(str):
            if v.strip() and v not in ["-","/"]: gm_link=v.strip(); break
    if gm_link:
        st.markdown(f'<a href="{gm_link}" target="_blank"><button class="stButton">Cliquer ici</button></a>', unsafe_allow_html=True)
    st.dataframe(build_lots_table(df), use_container_width=True, height=500)
    st.markdown("</div></div>", unsafe_allow_html=True)

def main():
    df = load_excel()
    col_lat, col_lon, col_ref = find_col(df,"Latitude"), find_col(df,"Longitude"), find_col(df,"Référence annonce","Reference")
    col_gmaps = find_col(df,"Lien Google Maps","Google Maps")
    df["_lat"], df["_lon"] = clean_latlon_series(df[col_lat]), clean_latlon_series(df[col_lon])
    df = df[df["_lat"].notna() & df["_lon"].notna()]
    refs = df.groupby(col_ref,as_index=False).agg({"_lat":"mean","_lon":"mean"})
    refs["ref_label"]=refs[col_ref].astype(str).str.replace(".0","",regex=False)

    m = folium.Map(location=[46.6,1.88],zoom_start=6,tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                   attr="© OpenStreetMap contributors")
    css_marker=f"background:{LOGO_BLUE};color:#fff;border:2px solid #fff;width:28px;height:28px;line-height:28px;border-radius:50%;text-align:center;font-size:11px;font-weight:600;"
    for _,r in refs.iterrows():
        folium.Marker(location=[r["_lat"],r["_lon"]],
                      icon=folium.DivIcon(html=f'<div style="{css_marker}">{r["ref_label"]}</div>'),
                      tooltip=r["ref_label"],popup=r["ref_label"]).add_to(m)
    out=st_folium(m,height=950,width=None,returned_objects=[])
    ref_clicked=None
    if isinstance(out,dict) and "last_object_clicked" in out and out["last_object_clicked"]:
        ref_clicked=out["last_object_clicked"].get("popup")
    if ref_clicked:
        lots=df[df[col_ref].astype(str).str.replace(".0","")==ref_clicked]
        drawer_for_reference(lots,col_gmaps,ref_clicked)

if __name__=="__main__":
    main()

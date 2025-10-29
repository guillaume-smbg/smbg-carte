
import os
import io
import re
from typing import Optional, List
import pandas as pd
import streamlit as st
import requests
import folium
from streamlit.components.v1 import html as st_html

# ================== PAGE LAYOUT & THEME ==================
st.set_page_config(page_title="SMBG Carte — Leaflet (Mapnik)", layout="wide")
LOGO_BLUE = "#05263d"

STYLES = '''
<style>
  html, body {height:100%;}
  [data-testid="stAppViewContainer"]{padding:0; margin:0; height:100vh;}
  [data-testid="stMain"]{padding:0; margin:0; height:100vh;}
  .block-container{padding:0 !important; margin:0 !important;}
  header, footer {visibility:hidden; height:0;}
  .smbg-badge{background:#eeefe9; border:1px solid #d9d7cf; color:#333; padding:2px 8px; border-radius:10px; font-size:12px;}
  .smbg-button{background:__BLUE__; color:#fff; border:none; padding:8px 12px; border-radius:8px; cursor:pointer; font-weight:600;}
  .smbg-drawer{height:calc(100vh - 24px); overflow:auto; padding:16px 20px 24px 20px; border-left:1px solid #e7e7e7; box-shadow:-8px 0 16px rgba(0,0,0,0.04);}
  .smbg-photo{width:100%; height:auto; border-radius:12px; display:block; margin-bottom:12px; box-shadow:0 4px 12px rgba(0,0,0,0.08);}
  .smbg-item{display:flex; gap:8px; align-items:flex-start; margin-bottom:6px;}
  .smbg-key{min-width:160px; color:#4b5563; font-weight:600;}
  .smbg-val{color:#111827;}
</style>
'''.replace("__BLUE__", LOGO_BLUE)

st.markdown(STYLES, unsafe_allow_html=True)

# ================== HELPERS: Excel Loading ==================
DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"

def normalize_excel_url(url: str) -> str:
    if not url: return url
    url = url.strip()
    url = re.sub(r"https://github\.com/(.+)/blob/([^ ]+)", r"https://github.com/\1/raw/\2", url)
    return url

def is_github_folder(url: str) -> bool:
    return bool(re.match(r"^https://github\.com/[^/]+/[^/]+/tree/[^/]+/.+", url))

def folder_to_api(url: str) -> str:
    m = re.match(r"^https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.*)$", url)
    if not m: return ""
    owner, repo, branch, path = m.groups()
    return f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"

def fetch_first_excel_from_folder(url: str) -> bytes:
    api_url = folder_to_api(url)
    r = requests.get(api_url, timeout=20); r.raise_for_status()
    entries = r.json()
    excel_items = [e for e in entries if e.get("type")=="file" and e.get("name","").lower().endswith((".xlsx",".xls"))]
    if not excel_items:
        raise FileNotFoundError("Aucun .xlsx trouvé dans ce dossier GitHub.")
    excel_items.sort(key=lambda e: (not e["name"].lower().endswith(".xlsx"), e["name"].lower()))
    raw = requests.get(excel_items[0]["download_url"], timeout=30); raw.raise_for_status()
    return raw.content

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    excel_url = normalize_excel_url(excel_url)
    if excel_url:
        if is_github_folder(excel_url):
            content = fetch_first_excel_from_folder(excel_url)
            return pd.read_excel(io.BytesIO(content))
        else:
            resp = requests.get(excel_url, timeout=20); resp.raise_for_status()
            return pd.read_excel(io.BytesIO(resp.content))
    if not os.path.exists(DEFAULT_LOCAL_PATH):
        st.stop()
    return pd.read_excel(DEFAULT_LOCAL_PATH)

# ================== COLUMN DETECTION ==================
def find_col(df, *candidates):
    cols = {str(c).strip(): c for c in df.columns}
    lower = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand in cols: return cols[cand]
        if cand.lower() in lower: return lower[cand.lower()]
    for c in df.columns:
        name = str(c).lower()
        for cand in candidates:
            if cand.lower() in name: return c
    return None

def build_mapping(df):
    m = {}
    m["ref"]        = find_col(df, "Référence annonce", "Référence", "Reference")
    m["gmap"]       = find_col(df, "Lien Google Maps", "Google Maps", "Maps")
    m["photos"]     = find_col(df, "Photos annonce", "photos_urls", "photos")
    m["photo_main"] = find_col(df, "photo_principale", "Photo principale")
    m["lat"]        = find_col(df, "Latitude", "Lat")
    m["lon"]        = find_col(df, "Longitude", "Lon", "Lng", "Long")
    m["actif"]      = find_col(df, "Actif", "Active")
    m["date_pub"]   = find_col(df, "Date publication", "Date de publication")
    return m

def normalize_bool(val):
    if isinstance(val, str): return val.strip().lower() in ["oui","yes","true","1","vrai"]
    if isinstance(val, (int, float)):
        try: return int(val)==1
        except Exception: return False
    if isinstance(val, bool): return val
    return False

# ================== DATA PREP ==================
def prepare_df(df: pd.DataFrame, m: dict) -> pd.DataFrame:
    actif_col = m["actif"]
    df["_actif"] = True if actif_col is None else df[actif_col].apply(normalize_bool)
    latc, lonc = m["lat"], m["lon"]
    if latc is None or lonc is None:
        st.error("Colonnes Latitude/Longitude introuvables.")
        st.stop()
    df["_lat"] = pd.to_numeric(df[latc], errors="coerce")
    df["_lon"] = pd.to_numeric(df[lonc], errors="coerce")
    df = df[df["_actif"] & df["_lat"].notna() & df["_lon"].notna()].copy()
    if m["date_pub"] is not None and m["date_pub"] in df.columns:
        def _is_new(x):
            try:
                d = pd.to_datetime(x)
                return (pd.Timestamp.now() - d) <= pd.Timedelta(days=30)
            except Exception:
                return False
        df["_is_new"] = df[m["date_pub"]].apply(_is_new)
    else:
        df["_is_new"] = False
    return df

# ================== MAP ==================
def build_map(df_valid: pd.DataFrame, ref_col: Optional[str]):
    FR_LAT, FR_LON, FR_ZOOM = 46.603354, 1.888334, 6
    m = folium.Map(location=[FR_LAT, FR_LON], zoom_start=FR_ZOOM, tiles="OpenStreetMap")
    css = f"background:{LOGO_BLUE}; color:#fff; border:2px solid #fff; width:28px; height:28px; line-height:28px; border-radius:50%; text-align:center; font-size:11px; font-weight:600;"
    for _, r in df_valid.iterrows():
        lat, lon = float(r["_lat"]), float(r["_lon"])
        ref_text = str(r[ref_col]) if ref_col else ""
        icon = folium.DivIcon(html=f'<div style="{css}">{ref_text}</div>')
        folium.Marker(location=[lat, lon], icon=icon).add_to(m)
    return m

# ================== RIGHT PANEL ==================
def sanitize_value(val):
    if val is None: return ""
    s = str(val).strip()
    if s in ["/", "-", ""]:
        return ""
    return s

def pictures(listing: pd.Series, photos_col, photo_main_col) -> List[str]:
    urls = []
    if photos_col and photos_col in listing and isinstance(listing[photos_col], str):
        for u in str(listing[photos_col]).split("|"):
            u = u.strip()
            if u:
                urls.append(u)
    main = None
    if photo_main_col and photo_main_col in listing:
        mv = str(listing[photo_main_col]).strip()
        main = mv if mv else None
    if main and main in urls:
        urls.remove(main)
        urls.insert(0, main)
    return urls

def render_right_panel(df_valid: pd.DataFrame, m: dict):
    ref_col = m.get("ref")
    refs = df_valid[ref_col].astype(str).tolist() if ref_col else [f"#{i+1}" for i in range(len(df_valid))]
    if not refs:
        st.info("Aucune annonce à afficher.")
        return
    sel = st.selectbox("Référence annonce", refs)
    row = df_valid[df_valid[ref_col].astype(str) == sel].iloc[0] if ref_col else df_valid.iloc[refs.index(sel)]
    st.markdown(f"### Détails annonce **{sel}**")
    if row.get("_is_new", False):
        st.markdown('<span class="smbg-badge">Nouveau</span>', unsafe_allow_html=True)
    gmap_col = m.get("gmap")
    if gmap_col and isinstance(row.get(gmap_col), str) and row[gmap_col].strip():
        st.markdown(f'<a href="{row[gmap_col].strip()}" target="_blank"><button class="smbg-button">Ouvrir dans Google Maps</button></a>', unsafe_allow_html=True)
    skip = {m.get("lat"), m.get("lon"), m.get("actif"), m.get("photos"), m.get("photo_main"), m.get("gmap"), "_lat", "_lon", "_actif", "_is_new"}
    for c in [c for c in df_valid.columns if c not in skip]:
        val = sanitize_value(row.get(c))
        if val:
            st.markdown(f'<div class="smbg-item"><div class="smbg-key">{c}</div><div class="smbg-val">{val}</div></div>', unsafe_allow_html=True)
    ph_urls = pictures(row, m.get("photos"), m.get("photo_main"))
    if ph_urls:
        st.markdown("#### Photos")
        for u in ph_urls:
            st.markdown(f'<img class="smbg-photo" loading="lazy" src="{u}" />', unsafe_allow_html=True)

# ================== MAIN ==================
def main():
    df = load_excel()
    if df.empty:
        st.warning("Excel vide ou introuvable.")
        st.stop()
    m = build_mapping(df)
    df_valid = prepare_df(df, m)
    if df_valid.empty:
        st.warning("Aucune ligne active avec coordonnées valides.")
        st.stop()
    ref_col = m.get("ref") if m.get("ref") in df_valid.columns else None
    col_map, col_right = st.columns([7, 5], gap="small")
    with col_map:
        mapp = build_map(df_valid, ref_col)
        st_html(mapp.get_root().render(), height=900, scrolling=False)
    with col_right:
        st.markdown('<div class="smbg-drawer">', unsafe_allow_html=True)
        render_right_panel(df_valid, m)
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()


import os
import io
import re
import time
import urllib.parse as up
import pandas as pd
import streamlit as st
import requests
import folium
from streamlit.components.v1 import html as st_html

# ================== PAGE LAYOUT ==================
st.set_page_config(page_title="SMBG Carte (Leaflet Mapnik - Fast)", layout="wide")
DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"
LOGO_BLUE = "#05263d"

st.sidebar.markdown("### Filtres (à venir)")

st.markdown(
    """
    <style>
      html, body {height:100%; overflow:hidden;}
      [data-testid="stAppViewContainer"]{padding:0; margin:0; height:100vh; overflow:hidden;}
      [data-testid="stMain"]{padding:0; margin:0; height:100vh; overflow:hidden;}
      .block-container{padding:0 !important; margin:0 !important;}
      [data-testid="stSidebar"]{min-width:275px; max-width:275px;}
      header, footer {visibility:hidden; height:0;}
    </style>
    """,
    unsafe_allow_html=True
)

# ================== HELPERS: Excel Loading ==================
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
    m["adresse"]     = find_col(df, "Adresse", "Adresse complète", "G")
    m["lat"]         = find_col(df, "Latitude", "Lat", "AI")
    m["lon"]         = find_col(df, "Longitude", "Lon", "Lng", "Long", "AJ")
    m["actif"]       = find_col(df, "Actif", "Active", "AO")
    m["ref"]         = find_col(df, "Référence annonce", "Référence", "AM")
    m["gmap"]        = find_col(df, "Lien Google Maps", "Google Maps", "Maps", "H")
    return m

def normalize_bool(val):
    if isinstance(val, str): return val.strip().lower() in ["oui","yes","true","1","vrai"]
    if isinstance(val, (int, float)):
        try: return int(val)==1
        except Exception: return False
    if isinstance(val, bool): return val
    return False

def coerce_num(series): return pd.to_numeric(series, errors="coerce")

# ================== GEOCODING (fast & persistent-cache) ==================
def clean_address(a: str) -> str:
    a = re.sub(r'\s+', ' ', str(a)).strip()
    a = re.sub(r'\s*-\s*', ' ', a)
    if a and 'france' not in a.lower():
        a = f"{a}, France"
    return a

@st.cache_data(show_spinner=False)
def resolve_redirect(url: str) -> str:
    try:
        r = requests.get(url, timeout=15, allow_redirects=True, headers={"User-Agent":"Mozilla/5.0"})
        return r.url
    except Exception:
        return url

def extract_lat_lon_from_gmap(url: str):
    if not isinstance(url, str) or url.strip() == "": return None, None
    url = url.strip()
    if re.search(r"(goo\.gl|maps\.app\.goo\.gl)", url): url = resolve_redirect(url)
    parsed = up.urlparse(url); qs = up.parse_qs(parsed.query)
    m = re.search(r"@([0-9.\-]+),([0-9.\-]+)", url)
    if m:
        try: return float(m.group(1)), float(m.group(2))
        except: pass
    m = re.search(r"!3d([0-9.\-]+)!4d([0-9.\-]+)", url)
    if m:
        try: return float(m.group(1)), float(m.group(2))
        except: pass
    if "ll" in qs:
        try:
            lat, lon = qs["ll"][0].split(","); return float(lat), float(lon)
        except: pass
    if "q" in qs:
        qv = qs["q"][0].replace("loc:", "").strip()
        m = re.match(r"\s*([0-9.\-]+)\s*,\s*([0-9.\-]+)\s*$", qv)
        if m:
            try: return float(m.group(1)), float(m.group(2))
            except: pass
    if "center" in qs:
        try:
            lat, lon = qs["center"][0].split(","); return float(lat), float(lon)
        except: pass
    m = re.search(r"/place/([0-9.\-]+),([0-9.\-]+)", parsed.path)
    if m:
        try: return float(m.group(1)), float(m.group(2))
        except: pass
    return None, None

def extract_query_from_gmap(url: str):
    try:
        if not isinstance(url, str) or not url.strip(): return None
        url = resolve_redirect(url.strip())
        parsed = up.urlparse(url)
        q = up.parse_qs(parsed.query).get('q', [''])[0].strip()
        return q or None
    except Exception:
        return None

# Persisted success cache across sessions (st.cache_data)
@st.cache_data(show_spinner=False)
def geocode_success_cached(address: str, gmap_url: str):
    """Return (lat, lon) for a given address/link if successful. If not found, raise to avoid caching failure."""
    # 1) direct coords in Google URL
    lat, lon = extract_lat_lon_from_gmap(gmap_url)
    if lat is not None and lon is not None:
        return lat, lon

    # 2) geocode q= from Google URL
    q = extract_query_from_gmap(gmap_url)
    if q:
        cla = clean_address(q)
        lat, lon = geocode_one(cla)
        if lat is not None and lon is not None:
            return lat, lon

    # 3) geocode cleaned address (retry)
    cla = clean_address(address)
    for _ in range(2):
        lat, lon = geocode_one(cla)
        if lat is not None and lon is not None:
            return lat, lon
        time.sleep(1.3)  # backoff only when we call Nominatim
    # Fail: raise so Streamlit does NOT cache the failure
    raise RuntimeError("geocode_failed")

# Session cache to avoid duplicate calls within the same page view
if "geo_cache" not in st.session_state:
    st.session_state["geo_cache"] = {}

def geocode_best_effort(address: str, gmap_url: str):
    key = (address or "").strip() + "|" + (gmap_url or "").strip()
    if key in st.session_state["geo_cache"]:
        return st.session_state["geo_cache"][key]
    try:
        lat, lon = geocode_success_cached(address, gmap_url)
        st.session_state["geo_cache"][key] = (lat, lon)
        return lat, lon
    except Exception:
        return None, None

def geocode_one(addr: str, email: str = ""):
    if not addr: return None, None
    base = "https://nominatim.openstreetmap.org/search"
    params = {"q": addr, "format": "json", "limit": 1, "countrycodes": "fr"}
    ua = f"SMBG-CARTE/1.0 ({email})" if email else "SMBG-CARTE/1.0 (contact@smbg-conseil.fr)"
    headers = {"User-Agent": ua, "Accept-Language": "fr"}
    try:
        r = requests.get(base, params=params, headers=headers, timeout=20); r.raise_for_status()
        data = r.json()
        if data: return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None, None
    return None, None

def ensure_latlon(df, mapcols):
    latc, lonc = mapcols["lat"], mapcols["lon"]
    gmapc, addrc = mapcols["gmap"], mapcols["adresse"]
    if latc is None: latc = "Latitude"; df[latc] = None; mapcols["lat"] = latc
    if lonc is None: lonc = "Longitude"; df[lonc] = None; mapcols["lon"] = lonc
    lat_num = pd.to_numeric(df[latc], errors="coerce"); lon_num = pd.to_numeric(df[lonc], errors="coerce")
    need = lat_num.isna() | lon_num.isna()
    to_fill = df[need].copy()
    if not to_fill.empty:
        email = st.secrets.get("NOMINATIM_EMAIL", os.environ.get("NOMINATIM_EMAIL", ""))
        for idx, row in to_fill.iterrows():
            lat, lon = geocode_best_effort(
                address=str(row.get(addrc, "")),
                gmap_url=str(row.get(gmapc, "")) if gmapc else ""
            )
            df.loc[idx, mapcols["lat"]] = lat
            df.loc[idx, mapcols["lon"]] = lon
    return df

# ================== MAP (Leaflet via Folium, iframe) ==================
def build_map(df_valid: pd.DataFrame, ref_col: str | None):
    FR_LAT, FR_LON, FR_ZOOM = 46.603354, 1.888334, 6

    m = folium.Map(
        location=[FR_LAT, FR_LON],
        zoom_start=FR_ZOOM,
        tiles=None,
        control_scale=False,
        zoom_control=True
    )

    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
        name="OpenStreetMap.Mapnik",
        max_zoom=19,
        min_zoom=0,
        opacity=1.0
    ).add_to(m)

    group = folium.FeatureGroup(name="Annonces").add_to(m)

    CSS = f"background:{LOGO_BLUE}; color:#fff; border:2px solid #fff; width:28px; height:28px; line-height:28px; border-radius:50%; text-align:center; font-size:11px; font-weight:600;"
    for _, r in df_valid.iterrows():
        lat, lon = float(r["_lat"]), float(r["_lon"])
        ref_text = str(r[ref_col]) if ref_col else ""
        html = f'<div style="{CSS}">{ref_text}</div>'
        icon = folium.DivIcon(html=html)
        folium.Marker(location=[lat, lon], icon=icon).add_to(group)

    return m

def main():
    df = load_excel()
    mapcols = build_mapping(df)

    actif_col = mapcols["actif"]
    df["_actif"] = True if actif_col is None else df[actif_col].apply(normalize_bool)

    df = ensure_latlon(df, mapcols)

    df = df[df["_actif"]].copy()
    df["_lat"] = pd.to_numeric(df[mapcols["lat"]], errors="coerce")
    df["_lon"] = pd.to_numeric(df[mapcols["lon"]], errors="coerce")
    df_valid = df.dropna(subset=["_lat", "_lon"]).copy()
    if df_valid.empty:
        st.warning("Aucune ligne active avec coordonnées valides.")
        st.stop()

    ref_col = mapcols.get("ref") if mapcols.get("ref") in df_valid.columns else None

    m = build_map(df_valid, ref_col)

    html_str = m.get_root().render()
    st_html(html_str, height=1080, scrolling=False)

if __name__ == "__main__":
    main()

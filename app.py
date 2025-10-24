import os
import io
import re
import time
import urllib.parse as up
import pandas as pd
import streamlit as st
import pydeck as pdk
import requests

# --------------------- PAGE LAYOUT (fullscreen map + fixed left panel) ---------------------
st.set_page_config(page_title="SMBG Carte", layout="wide")
LEFT_PANEL_WIDTH = 275

CUSTOM_CSS = f"""
<style>
/* remove default padding and chrome */
.block-container {{ padding: 0 !important; }}
header, footer {{ visibility: hidden; height: 0 !important; }}
/* fixed left panel (placeholder for future filters) */
#left-fixed {{
  position: fixed; left: 0; top: 0; bottom: 0;
  width: {LEFT_PANEL_WIDTH}px;
  background: white; border-right: 1px solid #eee; z-index: 1000; overflow: auto;
}}
/* map takes all remaining space */
#map-wrap {{
  position: fixed; left: {LEFT_PANEL_WIDTH}px; right: 0; top: 0; bottom: 0;
  z-index: 1; padding: 0; margin: 0;
}}
/* ensure deck.gl fills the viewport */
div[data-testid="stDeckGlChart"] {{ height: 100vh !important; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown('<div id="left-fixed"></div>', unsafe_allow_html=True)
st.markdown('<div id="map-wrap">', unsafe_allow_html=True)

LOGO_BLUE_RGB = [5, 38, 61]
DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"

# --------------------- Helpers: GitHub URL normalization ---------------------
def normalize_excel_url(url: str) -> str:
    if not url: return url
    url = url.strip()
    # Convert /blob/ to /raw/
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
    r = requests.get(api_url, timeout=20)
    r.raise_for_status()
    entries = r.json()
    excel_items = [e for e in entries if e.get("type")=="file" and e.get("name","").lower().endswith((".xlsx",".xls"))]
    if not excel_items:
        raise FileNotFoundError("Aucun .xlsx trouvé dans ce dossier GitHub.")
    excel_items.sort(key=lambda e: (not e["name"].lower().endswith(".xlsx"), e["name"].lower()))
    raw = requests.get(excel_items[0]["download_url"], timeout=30)
    raw.raise_for_status()
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
            resp = requests.get(excel_url, timeout=20)
            resp.raise_for_status()
            return pd.read_excel(io.BytesIO(resp.content))
    if not os.path.exists(DEFAULT_LOCAL_PATH):
        st.error("Fichier Excel introuvable. Définissez EXCEL_URL (raw ou dossier GitHub)."); st.stop()
    return pd.read_excel(DEFAULT_LOCAL_PATH)

# --------------------- Column detection (by headers) ---------------------
def find_col(df, *candidates):
    cols = {str(c).strip(): c for c in df.columns}
    lower = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand in cols: return cols[cand]
        if cand.lower() in lower: return lower[cand.lower()]
    for c in df.columns:
        name = str(c).lower()
        for cand in candidates:
            if cand.lower() in name:
                return c
    return None

def build_mapping(df):
    m = {}
    m["adresse"]     = find_col(df, "Adresse", "Adresse complète")
    m["lat"]         = find_col(df, "Latitude", "Lat", "AI")
    m["lon"]         = find_col(df, "Longitude", "Lon", "Lng", "Long", "AJ")
    m["actif"]       = find_col(df, "Actif", "Active", "AO")
    m["ref"]         = find_col(df, "Référence annonce", "Référence", "AM")
    m["gmap"]        = find_col(df, "Lien Google Maps", "Google Maps", "Maps", "H")
    return m

# --------------------- Geocoding: from Google Maps link first, then OSM ---------------------
def normalize_bool(val):
    if isinstance(val, str):
        v = val.strip().lower()
        return v in ["oui", "yes", "true", "1", "vrai"]
    if isinstance(val, (int, float)):
        try: return int(val) == 1
        except Exception: return False
    if isinstance(val, bool): return val
    return False

def coerce_num(series):
    return pd.to_numeric(series, errors="coerce")

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
    if re.search(r"(goo\.gl|maps\.app\.goo\.gl)", url):
        url = resolve_redirect(url)
    parsed = up.urlparse(url)
    qs = up.parse_qs(parsed.query)

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
        qv = qs["q"][0].replace("loc:", "")
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

@st.cache_data(show_spinner=False)
def geocode_one(addr: str, email: str = ""):
    if not addr: return None, None
    base = "https://nominatim.openstreetmap.org/search"
    params = {"q": addr, "format": "json", "limit": 1}
    ua = f"SMBG-CARTE/1.0 ({email})" if email else "SMBG-CARTE/1.0 (contact@smbg-conseil.fr)"
    headers = {"User-Agent": ua, "Accept-Language": "fr"}
    try:
        r = requests.get(base, params=params, headers=headers, timeout=20)
        r.raise_for_status()
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

    lat_num = coerce_num(df[latc]); lon_num = coerce_num(df[lonc])
    need = lat_num.isna() | lon_num.isna()
    to_fill = df[need].copy()

    if not to_fill.empty:
        email = st.secrets.get("NOMINATIM_EMAIL", os.environ.get("NOMINATIM_EMAIL", ""))
        with st.spinner(f"Remplissage des coordonnées (Google Maps ▶ OSM) : {len(to_fill)} lignes…"):
            for idx, row in to_fill.iterrows():
                lat, lon = None, None
                if gmapc is not None:
                    lat, lon = extract_lat_lon_from_gmap(str(row.get(gmapc, "")))
                if (lat is None or lon is None) and addrc is not None:
                    lat, lon = geocode_one(str(row.get(addrc, "")), email=email)
                    time.sleep(1.05)  # OSM rate limit
                df.loc[idx, mapcols["lat"]] = lat
                df.loc[idx, mapcols["lon"]] = lon
    return df

# --------------------- MAP ---------------------
def main():
    # No titles/captions; just map + left panel placeholder
    df = load_excel()
    mapcols = build_mapping(df)

    # Actif
    actif_col = mapcols["actif"]
    if actif_col is None:
        df["_actif"] = True
    else:
        df["_actif"] = df[actif_col].apply(normalize_bool)

    # Coordinates
    df = ensure_latlon(df, mapcols)

    # Keep only active with valid coords
    df = df[df["_actif"]].copy()
    df["_lat"] = coerce_num(df[mapcols["lat"]])
    df["_lon"] = coerce_num(df[mapcols["lon"]])
    df_valid = df.dropna(subset=["_lat", "_lon"]).copy()
    if df_valid.empty:
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Text for labels (reference)
    ref_col = mapcols.get("ref")
    if ref_col is None:
        df_valid["_ref_text"] = ""
    else:
        df_valid["_ref_text"] = df_valid[ref_col].fillna("").astype(str)

    # Center on mean
    mean_lat, mean_lon = float(df_valid["_lat"].mean()), float(df_valid["_lon"].mean())

    # Basemap (overridable via secret MAP_TILE_URL)
    tile_url = st.secrets.get("MAP_TILE_URL", os.environ.get("MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"))
    basemap = pdk.Layer("TileLayer", data=tile_url, min_zoom=0, max_zoom=19, tile_size=256)

    # Pins (blue)
    pins = pdk.Layer(
        "ScatterplotLayer",
        data=df_valid,
        get_position=["_lon", "_lat"],
        get_radius=40,
        radius_min_pixels=8,
        radius_max_pixels=30,
        get_fill_color=[5, 38, 61, 220],
        stroked=True,
        get_line_color=[255, 255, 255, 180],
        line_width_min_pixels=1,
        pickable=False,  # no hover popup
    )

    # Text labels (reference in the middle of pin)
    labels = pdk.Layer(
        "TextLayer",
        data=df_valid,
        get_position=["_lon", "_lat"],
        get_text="_ref_text",
        get_size=12,                 # small
        get_color=[255, 255, 255, 230],
        get_angle=0,
        get_alignment_baseline="'center'",  # vertical centering
        get_text_anchor="'middle'",         # horizontal centering
        pickable=False,
    )

    view_state = pdk.ViewState(longitude=mean_lon, latitude=mean_lat, zoom=5)
    deck = pdk.Deck(
        layers=[basemap, pins, labels],
        initial_view_state=view_state,
        tooltip=None,               # no tooltip at all
        map_style=None
    )

    st.pydeck_chart(deck, use_container_width=True)

    # Close map wrapper
    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
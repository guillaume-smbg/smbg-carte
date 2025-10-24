import os
import io
import re
import time
import urllib.parse as up
import pandas as pd
import streamlit as st
import pydeck as pdk
import requests

st.set_page_config(page_title="SMBG Carte — Étape 1", layout="wide")

LOGO_BLUE_RGB = [5, 38, 61]
DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"

# ---------- Helpers: Excel URL ----------
def normalize_excel_url(url: str) -> str:
    if not url:
        return url
    url = url.strip()
    url = re.sub(r"https://github\.com/(.+)/blob/([^ ]+)", r"https://github.com/\1/raw/\2", url)
    return url

def is_github_folder(url: str) -> bool:
    return bool(re.match(r"^https://github\.com/[^/]+/[^/]+/tree/[^/]+/.+", url))

def folder_to_api(url: str) -> str:
    m = re.match(r"^https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.*)$", url)
    if not m:
        return ""
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
        st.error("Fichier Excel introuvable. Définissez EXCEL_URL (raw ou dossier GitHub).")
        st.stop()
    return pd.read_excel(DEFAULT_LOCAL_PATH)

# ---------- Column detection ----------
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
    m["adresse"]      = find_col(df, "Adresse", "Adresse complète")
    m["lat"]          = find_col(df, "Latitude", "Lat")
    m["lon"]          = find_col(df, "Longitude", "Lon", "Lng", "Long")
    m["actif"]        = find_col(df, "Actif", "Active")
    m["ref"]          = find_col(df, "Référence annonce", "Référence")
    m["typologie"]    = find_col(df, "Typologie")
    m["emplacement"]  = find_col(df, "Emplacement")
    m["gmap"]         = find_col(df, "Lien Google Maps", "Google Maps", "Maps", "H")
    return m

# ---------- Utils ----------
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

# Resolve short links (goo.gl/maps, maps.app.goo.gl) -> final URL with coordinates
@st.cache_data(show_spinner=False)
def resolve_redirect(url: str) -> str:
    try:
        r = requests.get(url, timeout=15, allow_redirects=True, headers={"User-Agent":"Mozilla/5.0"})
        return r.url
    except Exception:
        return url

def extract_lat_lon_from_gmap(url: str):
    if not isinstance(url, str) or url.strip() == "":
        return None, None
    url = url.strip()

    # Follow redirects for short links
    if re.search(r"(goo\.gl|maps\.app\.goo\.gl)", url):
        url = resolve_redirect(url)

    # Parse query params
    parsed = up.urlparse(url)
    qs = up.parse_qs(parsed.query)

    # Common patterns
    # 1) @48.8566,2.3522,17z
    m = re.search(r"@([0-9.\-]+),([0-9.\-]+)", url)
    if m:
        try: return float(m.group(1)), float(m.group(2))
        except: pass

    # 2) !3d48.8566!4d2.3522
    m = re.search(r"!3d([0-9.\-]+)!4d([0-9.\-]+)", url)
    if m:
        try: return float(m.group(1)), float(m.group(2))
        except: pass

    # 3) ll=lat,lon
    if "ll" in qs:
        try:
            lat, lon = qs["ll"][0].split(",")
            return float(lat), float(lon)
        except: pass

    # 4) q=lat,lon  or q=loc:lat,lon
    if "q" in qs:
        qv = qs["q"][0]
        qv = qv.replace("loc:", "")
        m = re.match(r"\s*([0-9.\-]+)\s*,\s*([0-9.\-]+)\s*$", qv)
        if m:
            try: return float(m.group(1)), float(m.group(2))
            except: pass

    # 5) center=lat,lon
    if "center" in qs:
        try:
            lat, lon = qs["center"][0].split(",")
            return float(lat), float(lon)
        except: pass

    # 6) /place/lat,lon
    m = re.search(r"/place/([0-9.\-]+),([0-9.\-]+)", parsed.path)
    if m:
        try: return float(m.group(1)), float(m.group(2))
        except: pass

    return None, None

@st.cache_data(show_spinner=False)
def geocode_one(addr: str, email: str = ""):
    if not addr:
        return None, None
    base = "https://nominatim.openstreetmap.org/search"
    params = {"q": addr, "format": "json", "limit": 1}
    ua = f"SMBG-CARTE/1.0 ({email})" if email else "SMBG-CARTE/1.0 (contact@smbg-conseil.fr)"
    headers = {"User-Agent": ua, "Accept-Language": "fr"}
    try:
        r = requests.get(base, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None, None
    return None, None

def ensure_latlon(df, mapcols):
    latc, lonc = mapcols["lat"], mapcols["lon"]
    gmapc, addrc = mapcols["gmap"], mapcols["adresse"]

    if latc is None:
        latc = "Latitude"; df[latc] = None; mapcols["lat"] = latc
    if lonc is None:
        lonc = "Longitude"; df[lonc] = None; mapcols["lon"] = lonc

    lat_num = coerce_num(df[latc])
    lon_num = coerce_num(df[lonc])
    need = lat_num.isna() | lon_num.isna()
    to_fill = df[need].copy()

    unresolved = []

    if not to_fill.empty:
        with st.spinner(f"Remplissage des coordonnées (Google Maps ▶ OSM) : {len(to_fill)} lignes…"):
            email = st.secrets.get("NOMINATIM_EMAIL", os.environ.get("NOMINATIM_EMAIL", ""))
            for idx, row in to_fill.iterrows():
                lat, lon = None, None

                # 1) Essayer depuis le lien Google Maps
                if gmapc is not None:
                    lat, lon = extract_lat_lon_from_gmap(str(row.get(gmapc, "")))

                # 2) Sinon, géocoder depuis l'adresse
                if (lat is None or lon is None) and addrc is not None:
                    lat, lon = geocode_one(str(row.get(addrc, "")), email=email)
                    # sleep uniquement si on a appelé OSM
                    time.sleep(1.05)

                if lat is None or lon is None:
                    unresolved.append(idx)

                df.loc[idx, mapcols["lat"]] = lat
                df.loc[idx, mapcols["lon"]] = lon

    return df, unresolved

# ---------- App ----------
def main():
    st.sidebar.markdown("### Filtres (à venir)")
    st.markdown("<style>[data-testid='stSidebar']{min-width:275px;max-width:275px;width:275px}</style>", unsafe_allow_html=True)

    st.title("SMBG Carte — Étape 1 : Carte + pins bleus")
    st.caption("Source : Excel • Actif = oui • Pins = bleu du logo (#05263d)")

    df = load_excel()
    mapcols = build_mapping(df)

    # Actif
    actif_col = mapcols["actif"]
    if actif_col is None:
        df["_actif"] = True
    else:
        df["_actif"] = df[actif_col].apply(normalize_bool)

    # Coordinates
    df, unresolved = ensure_latlon(df, mapcols)

    df = df[df["_actif"]].copy()
    df["_lat"] = coerce_num(df[mapcols["lat"]])
    df["_lon"] = coerce_num(df[mapcols["lon"]])
    df_valid = df.dropna(subset=["_lat", "_lon"]).copy()

    if df_valid.empty:
        st.warning("Aucune ligne active avec coordonnées valides à afficher.")
        with st.expander("Debug (colonnes détectées)", expanded=False):
            st.write(mapcols); st.dataframe(df.head(10))
        return

    df_valid["_tooltip"] = df_valid.apply(lambda r: " | ".join([
        f"Ref: {str(r.get(mapcols['ref'], ''))}".strip(),
        str(r.get(mapcols['adresse'], "")),
        str(r.get(mapcols['typologie'], "")),
        str(r.get(mapcols['emplacement'], "")),
    ]).strip(" | "), axis=1)

    mean_lat, mean_lon = df_valid["_lat"].mean(), df_valid["_lon"].mean()

    basemap = pdk.Layer("TileLayer", data="https://tile.openstreetmap.org/{z}/{x}/{y}.png", min_zoom=0, max_zoom=19, tile_size=256)
    layer = pdk.Layer(
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
        pickable=True,
    )
    view_state = pdk.ViewState(longitude=float(mean_lon), latitude=float(mean_lat), zoom=5)
    tooltip = {"html": "<b>{_tooltip}</b>", "style": {"backgroundColor":"white","color":"black"}}
    deck = pdk.Deck(layers=[basemap, layer], initial_view_state=view_state, tooltip=tooltip, map_style=None)
    st.pydeck_chart(deck, height=900, use_container_width=True)

    with st.expander("Debug + Liens Google Maps non résolus", expanded=False):
        st.write(mapcols)
        st.write(f"Points affichés : {len(df_valid)}")
        if unresolved:
            st.warning(f"Liens non résolus : {len(unresolved)} ligne(s).")
            cols_to_show = [c for c in [mapcols.get('ref'), mapcols.get('adresse'), mapcols.get('gmap')] if c]
            st.dataframe(df.loc[unresolved, cols_to_show])
        else:
            st.success("Tous les liens Google Maps ont été résolus.")

if __name__ == "__main__":
    main()
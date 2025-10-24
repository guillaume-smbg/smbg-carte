import os
import io
import re
import time
import pandas as pd
import streamlit as st
import pydeck as pdk
import requests

st.set_page_config(page_title="SMBG Carte — Étape 1", layout="wide")

LOGO_BLUE_RGB = [5, 38, 61]
DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"

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
            resp.raise_for_status();
            return pd.read_excel(io.BytesIO(resp.content))

    if not os.path.exists(DEFAULT_LOCAL_PATH):
        st.error("Fichier Excel introuvable. Définissez EXCEL_URL (raw ou dossier GitHub).")
        st.stop()
    return pd.read_excel(DEFAULT_LOCAL_PATH)

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
    m["adresse"]   = find_col(df, "Adresse", "Adresse complète", "Adresse complète (rue + CP + ville)")
    m["lat"]       = find_col(df, "Latitude", "Lat")
    m["lon"]       = find_col(df, "Longitude", "Lon", "Lng", "Long")
    m["actif"]     = find_col(df, "Actif", "Active")
    m["ref"]       = find_col(df, "Référence annonce", "Référence")
    m["typologie"] = find_col(df, "Typologie")
    m["emplacement"]=find_col(df, "Emplacement")
    m["gmap"]      = find_col(df, "Lien Google Maps", "Google Maps", "Maps")
    m["photos"]    = find_col(df, "Photos annonce", "Photos")
    return m

def normalize_bool(val):
    if isinstance(val, str):
        v = val.strip().lower()
        return v in ["oui", "yes", "true", "1", "vrai"]
    if isinstance(val, (int, float)):
        try: return int(val)==1
        except: return False
    if isinstance(val, bool): return val
    return False

def coerce_num(series):
    return pd.to_numeric(series, errors="coerce")

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
    latc, lonc, addrc = mapcols["lat"], mapcols["lon"], mapcols["adresse"]
    if latc is None:
        latc = "Latitude"; df[latc] = None; mapcols["lat"] = latc
    if lonc is None:
        lonc = "Longitude"; df[lonc] = None; mapcols["lon"] = lonc

    lat_num = coerce_num(df[latc])
    lon_num = coerce_num(df[lonc])
    need = lat_num.isna() | lon_num.isna()
    to_geo = df[need].copy()
    if not to_geo.empty:
        email = st.secrets.get("NOMINATIM_EMAIL", os.environ.get("NOMINATIM_EMAIL", ""))
        with st.spinner(f"Géocodage des adresses manquantes ({len(to_geo)})…"):
            for idx, row in to_geo.iterrows():
                addr = "" if addrc is None else str(df.loc[idx, addrc])
                lat, lon = geocode_one(addr, email)
                df.loc[idx, mapcols["lat"]] = lat
                df.loc[idx, mapcols["lon"]] = lon
                time.sleep(1.05)
    return df

def make_tooltip(row, mapcols):
    items = []
    for (key,label) in [("ref","Ref"), ("adresse","Adresse"), ("typologie","Typologie"), ("emplacement","Emplacement")]:
        col = mapcols.get(key)
        if col:
            val = str(row.get(col, "")).strip()
            if val and val.lower()!="nan":
                items.append(f"{label}: {val}")
    return " | ".join(items)

def main():
    st.sidebar.markdown("### Filtres (à venir)")
    st.markdown("<style>[data-testid='stSidebar']{min-width:275px;max-width:275px;width:275px}</style>", unsafe_allow_html=True)

    st.title("SMBG Carte — Étape 1 : Carte + pins bleus")
    st.caption("Source : Excel • Actif = oui • Pins = bleu du logo (#05263d)")

    df = load_excel()
    mapcols = build_mapping(df)

    actif_col = mapcols["actif"]
    if actif_col is None:
        df["_actif"] = True
    else:
        df["_actif"] = df[actif_col].apply(normalize_bool)
    df = df[df["_actif"]].copy()

    df = ensure_latlon(df, mapcols)
    df["_lat"] = coerce_num(df[mapcols["lat"]])
    df["_lon"] = coerce_num(df[mapcols["lon"]])
    df = df.dropna(subset=["_lat", "_lon"])

    if df.empty:
        st.warning("Aucune ligne active avec coordonnées valides à afficher.")
        with st.expander("Debug (colonnes détectées)", expanded=False):
            st.write(mapcols); st.dataframe(df.head(10))
        return

    df["_tooltip"] = df.apply(lambda r: make_tooltip(r, mapcols), axis=1)

    mean_lat, mean_lon = df["_lat"].mean(), df["_lon"].mean()

    basemap = pdk.Layer("TileLayer", data="https://tile.openstreetmap.org/{z}/{x}/{y}.png", min_zoom=0, max_zoom=19, tile_size=256)
    layer = pdk.Layer("ScatterplotLayer", data=df, get_position=["_lon","_lat"], get_radius=40, get_fill_color=[5,38,61], pickable=True)
    view_state = pdk.ViewState(longitude=float(mean_lon), latitude=float(mean_lat), zoom=5)
    tooltip = {"html": "<b>{_tooltip}</b>", "style": {"backgroundColor":"white","color":"black"}}
    deck = pdk.Deck(layers=[basemap, layer], initial_view_state=view_state, tooltip=tooltip, map_style=None)
    st.pydeck_chart(deck, height=900, use_container_width=True)

    with st.expander("Debug (colonnes détectées)", expanded=False):
        st.write(mapcols)
        st.write(f"Points affichés : {len(df)}")
        show_cols = [c for c in [mapcols.get('lat'), mapcols.get('lon'), mapcols.get('actif'), mapcols.get('adresse')] if c]
        st.dataframe(df[show_cols].head(20))

if __name__ == "__main__":
    main()
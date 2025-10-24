
import os
import io
import re
import time
import json
import pandas as pd
import streamlit as st
import pydeck as pdk
import requests

st.set_page_config(page_title="SMBG Carte — Étape 1", layout="wide")

LOGO_BLUE_HEX = "#05263d"
LOGO_BLUE_RGB = [5, 38, 61]

DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"

def _is_github_folder_url(url: str) -> bool:
    return bool(re.match(r"^https://github\.com/[^/]+/[^/]+/tree/[^/]+/.+", url))

def _github_folder_to_api(url: str) -> str:
    m = re.match(r"^https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.*)$", url)
    if not m:
        return ""
    owner, repo, branch, path = m.groups()
    return f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"

def _fetch_first_excel_from_github_folder(folder_url: str) -> bytes:
    api_url = _github_folder_to_api(folder_url)
    if not api_url:
        raise ValueError("URL de dossier GitHub invalide.")
    r = requests.get(api_url, timeout=20)
    r.raise_for_status()
    entries = r.json()
    if not isinstance(entries, list):
        raise ValueError("Réponse GitHub inattendue.")
    excel_items = [
        e for e in entries
        if e.get("type") == "file" and (e.get("name","").lower().endswith(".xlsx") or e.get("name","").lower().endswith(".xls"))
    ]
    if not excel_items:
        raise FileNotFoundError("Aucun fichier Excel trouvé dans ce dossier GitHub.")
    excel_items.sort(key=lambda e: (not e["name"].lower().endswith(".xlsx"), e["name"].lower()))
    download_url = excel_items[0].get("download_url")
    if not download_url:
        raise ValueError("download_url manquant pour le fichier Excel.")
    fr = requests.get(download_url, timeout=30)
    fr.raise_for_status()
    return fr.content

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    if excel_url:
        try:
            if _is_github_folder_url(excel_url):
                content = _fetch_first_excel_from_github_folder(excel_url)
                return pd.read_excel(io.BytesIO(content))
            else:
                resp = requests.get(excel_url, timeout=20)
                resp.raise_for_status()
                return pd.read_excel(io.BytesIO(resp.content))
        except Exception as e:
            st.error(f"Impossible de charger l'Excel depuis EXCEL_URL : {e}")
            st.stop()

    path = DEFAULT_LOCAL_PATH
    if not os.path.exists(path):
        st.error(
            "Fichier Excel introuvable.\n\n"
            "Options :\n"
            "• Ajoutez le fichier localement : data/Liste_des_lots.xlsx\n"
            "• OU définissez EXCEL_URL (Secrets/env) vers un fichier raw ou un dossier GitHub contenant un .xlsx."
        )
        st.stop()

    return pd.read_excel(path)

def normalize_bool(val):
    if isinstance(val, str):
        return val.strip().lower() in ["oui", "yes", "true", "1"]
    if isinstance(val, (int, float)):
        return val == 1
    if isinstance(val, bool):
        return val
    return False

def coerce_float(series):
    return pd.to_numeric(series, errors="coerce")

@st.cache_data(show_spinner=False)
def geocode_one(addr: str, email_for_nominatim: str = ""):
    if not addr or str(addr).strip() == "":
        return None, None
    base = "https://nominatim.openstreetmap.org/search"
    params = {"q": addr, "format": "json", "limit": 1}
    headers = {}
    if email_for_nominatim:
        headers["User-Agent"] = f"SMBG-CARTE/1.0 ({email_for_nominatim})"
        headers["Accept-Language"] = "fr"
    try:
        r = requests.get(base, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None, None
    return None, None

def ensure_latlon(df: pd.DataFrame):
    if "AI" not in df.columns:
        df["AI"] = None  # Latitude
    if "AJ" not in df.columns:
        df["AJ"] = None  # Longitude

    addr_series = None
    if "G" in df.columns:
        addr_series = df["G"].fillna("").astype(str)
    else:
        addr_series = pd.Series([""] * len(df))

    nominatim_email = st.secrets.get("NOMINATIM_EMAIL", os.environ.get("NOMINATIM_EMAIL", ""))

    need_geo = df["AI"].isna() | df["AJ"].isna() | (df["AI"] == "") | (df["AJ"] == "")
    to_geo = df[need_geo].copy()

    if len(to_geo) > 0:
        with st.spinner(f"Géocodage des adresses manquantes ({len(to_geo)})…"):
            new_lats, new_lons = [], []
            for idx, row in to_geo.iterrows():
                addr = addr_series.loc[idx]
                lat, lon = geocode_one(addr, email_for_nominatim=nominatim_email)
                new_lats.append(lat)
                new_lons.append(lon)
                time.sleep(1.05)  # respect rate limit
            df.loc[to_geo.index, "AI"] = new_lats
            df.loc[to_geo.index, "AJ"] = new_lons

    return df

def make_tooltip(row):
    ref = str(row.get("AM", ""))
    adresse = str(row.get("G", ""))
    typologie = str(row.get("J", ""))
    emplacement = str(row.get("I", ""))
    parts = []
    if ref and ref != "nan":
        parts.append(f"Ref: {ref}")
    if adresse and adresse != "nan":
        parts.append(adresse)
    if typologie and typologie != "nan":
        parts.append(typologie)
    if emplacement and emplacement != "nan":
        parts.append(emplacement)
    return " | ".join(parts)

CSS = '''
<style>
    /* Remove outer paddings to use full screen */
    .block-container { padding: 0 !important; }
    header { visibility: hidden; height: 0; }
    /* Fixed left placeholder for future filters */
    #left-fixed {
        position: fixed;
        left: 0; top: 0; bottom: 0;
        width: 275px;
        background: white;
        border-right: 1px solid #eee;
        z-index: 1000;
    }
    /* Fullscreen map area on the right */
    #map-wrap {
        position: fixed;
        left: 275px; right: 0; top: 0; bottom: 0;
        z-index: 1;
        padding: 0;
        margin: 0;
    }
    /* Force deck.gl widget to fill viewport height */
    div[data-testid="stDeckGlChart"] {
        height: 100vh !important;
    }
</style>
'''  # placeholder

def main():
    
    st.title("SMBG Carte — Étape 1 : Carte + pins bleus")
    st.caption("Source : Excel • Actif = oui • Pins = bleu du logo (#05263d)")

    # Sidebar placeholder (future filters). We force width to ~275px.
    st.sidebar.markdown("### Filtres (à venir)")
    st.markdown(
        "<style>[data-testid='stSidebar']{min-width:275px;max-width:275px;width:275px}</style>",
        unsafe_allow_html=True
    )


    df = load_excel()

    if "AO" not in df.columns:
        df["AO"] = "oui"

    df = ensure_latlon(df)

    df["_actif"] = df["AO"].apply(normalize_bool)
    df = df[df["_actif"] == True].copy()

    df["_lat"] = coerce_float(df["AI"])
    df["_lon"] = coerce_float(df["AJ"])
    df = df.dropna(subset=["_lat", "_lon"])

    if df.empty:
        st.warning("Aucune ligne active avec coordonnées valides à afficher.")
                return

    for needed in ["G", "I", "J", "AM"]:
        if needed not in df.columns:
            df[needed] = ""

    df["_tooltip"] = df.apply(make_tooltip, axis=1)

    mean_lat = df["_lat"].mean()
    mean_lon = df["_lon"].mean()

    st.write(f"**Points affichés :** {len(df)}")
    with st.expander("Debug (colonnes détectées)", expanded=False):
        show_cols = [c for c in ["AI", "AJ", "AO", "G", "I", "J", "AM"] if c in df.columns]
        st.dataframe(df[show_cols].head(20))

    basemap = pdk.Layer(
        "TileLayer",
        data="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        min_zoom=0,
        max_zoom=19,
        tile_size=256,
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["_lon", "_lat"],
        get_radius=20,
        get_fill_color=[5, 38, 61],
        pickable=True,
        radius_min_pixels=4,
        radius_max_pixels=24,
    )

    view_state = pdk.ViewState(
        longitude=float(mean_lon),
        latitude=float(mean_lat),
        zoom=5,
        min_zoom=2,
        max_zoom=18,
    )

    tooltip = {"html": "<b>{_tooltip}</b>", "style": {"backgroundColor": "white", "color": "black"}}

    r = pdk.Deck(layers=[basemap, layer], initial_view_state=view_state, tooltip=tooltip, map_style=None)
    st.pydeck_chart(r, height=900, use_container_width=True)

    
if __name__ == "__main__":
    main()

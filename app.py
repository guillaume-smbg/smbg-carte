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

# --------------------- Utilitaires GitHub ---------------------

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
    r = requests.get(api_url, timeout=20)
    r.raise_for_status()
    entries = r.json()
    excel_items = [
        e for e in entries
        if e.get("type") == "file" and e.get("name", "").lower().endswith((".xlsx", ".xls"))
    ]
    if not excel_items:
        raise FileNotFoundError("Aucun fichier Excel trouvé dans ce dossier GitHub.")
    download_url = excel_items[0]["download_url"]
    fr = requests.get(download_url, timeout=30)
    fr.raise_for_status()
    return fr.content

# --------------------- Chargement Excel ---------------------

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    if excel_url:
        if _is_github_folder_url(excel_url):
            content = _fetch_first_excel_from_github_folder(excel_url)
            return pd.read_excel(io.BytesIO(content))
        else:
            resp = requests.get(excel_url, timeout=20)
            resp.raise_for_status()
            return pd.read_excel(io.BytesIO(resp.content))

    if not os.path.exists(DEFAULT_LOCAL_PATH):
        st.error("Fichier Excel introuvable.")
        st.stop()
    return pd.read_excel(DEFAULT_LOCAL_PATH)

# --------------------- Géocodage ---------------------

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
def geocode_one(addr: str, email: str = ""):
    if not addr:
        return None, None
    base = "https://nominatim.openstreetmap.org/search"
    params = {"q": addr, "format": "json", "limit": 1}
    headers = {"User-Agent": f"SMBG-CARTE/1.0 ({email})", "Accept-Language": "fr"}
    try:
        r = requests.get(base, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None, None
    return None, None

def ensure_latlon(df: pd.DataFrame):
    if "AI" not in df.columns:
        df["AI"] = None
    if "AJ" not in df.columns:
        df["AJ"] = None

    addr = df["G"].fillna("").astype(str) if "G" in df.columns else pd.Series([""] * len(df))
    email = st.secrets.get("NOMINATIM_EMAIL", os.environ.get("NOMINATIM_EMAIL", ""))

    need_geo = df["AI"].isna() | df["AJ"].isna()
    to_geo = df[need_geo]
    if not to_geo.empty:
        with st.spinner(f"Géocodage des adresses manquantes ({len(to_geo)})…"):
            for idx, row in to_geo.iterrows():
                lat, lon = geocode_one(addr.loc[idx], email)
                df.loc[idx, "AI"] = lat
                df.loc[idx, "AJ"] = lon
                time.sleep(1.05)
    return df

# --------------------- Tooltip ---------------------

def make_tooltip(row):
    items = []
    for c, label in [("AM", "Ref"), ("G", "Adresse"), ("J", "Typologie"), ("I", "Emplacement")]:
        val = str(row.get(c, "")).strip()
        if val and val.lower() != "nan":
            items.append(f"{label}: {val}")
    return " | ".join(items)

# --------------------- Application principale ---------------------

def main():
    st.sidebar.markdown("### Filtres (à venir)")
    st.markdown(
        "<style>[data-testid='stSidebar']{min-width:275px;max-width:275px;width:275px}</style>",
        unsafe_allow_html=True
    )

    st.title("SMBG Carte — Étape 1 : Carte + pins bleus")
    st.caption("Source : Excel • Actif = oui • Pins = bleu du logo (#05263d)")

    df = load_excel()
    if "AO" not in df.columns:
        df["AO"] = "oui"

    df = ensure_latlon(df)
    df["_actif"] = df["AO"].apply(normalize_bool)
    df = df[df["_actif"]].copy()

    df["_lat"] = coerce_float(df["AI"])
    df["_lon"] = coerce_float(df["AJ"])
    df = df.dropna(subset=["_lat", "_lon"])

    if df.empty:
        st.warning("Aucune ligne active avec coordonnées valides à afficher.")
        return

    for c in ["G", "I", "J", "AM"]:
        if c not in df.columns:
            df[c] = ""
    df["_tooltip"] = df.apply(make_tooltip, axis=1)

    mean_lat, mean_lon = df["_lat"].mean(), df["_lon"].mean()

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
        get_fill_color=LOGO_BLUE_RGB,
        pickable=True,
    )

    view_state = pdk.ViewState(longitude=mean_lon, latitude=mean_lat, zoom=5)
    tooltip = {"html": "<b>{_tooltip}</b>", "style": {"backgroundColor": "white", "color": "black"}}

    deck = pdk.Deck(layers=[basemap, layer], initial_view_state=view_state, tooltip=tooltip)
    st.pydeck_chart(deck, height=900, use_container_width=True)


if __name__ == "__main__":
    main()

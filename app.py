import os
import io
import re
import math
import unicodedata
from typing import Optional, Dict, Tuple, List

import pandas as pd
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
st.set_page_config(
    page_title="SMBG Carte",
    layout="wide",
)

LOGO_BLUE = "#05263d"
COPPER = "#b87333"
LEFT_PANEL_WIDTH_PX = 275
RIGHT_PANEL_WIDTH_PX = 275
DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"

# -------------------------------------------------
# CSS GLOBAL
# -------------------------------------------------
st.markdown(f"""
<style>
[data-testid="column"]:nth-of-type(1) {{
    background-color: {LOGO_BLUE};
    color: white !important;
    border-radius: 12px;
    padding: 15px;
}}
[data-testid="column"]:nth-of-type(1) * {{
    color: white !important;
    font-family: 'Futura', sans-serif !important;
}}
[data-testid="column"]:nth-of-type(3) {{
    border-radius: 12px;
    border: 1px solid rgba(0,0,0,0.1);
    background-color: white;
    padding: 0px;
}}
.smbg-header {{
    background-color: {LOGO_BLUE};
    color: white !important;
    font-weight: 600;
    font-size: 14px;
    border-radius: 8px;
    padding: 8px 12px;
    margin-bottom: 10px;
}}
.copper-btn {{
    background-color: {COPPER};
    color: white !important;
    border-radius: 8px;
    border: none;
    padding: 8px 10px;
    margin-top: 8px;
    font-weight: 500;
    cursor: pointer;
}}
.copper-btn:hover {{ filter: brightness(1.1); }}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# UTILITAIRES
# -------------------------------------------------
def normalize_excel_url(url: str) -> str:
    if not url:
        return url
    return re.sub(
        r"https://github\.com/(.+)/blob/([^ ]+)",
        r"https://github.com/\1/raw/\2",
        url.strip()
    )

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    excel_url = normalize_excel_url(excel_url)
    if excel_url:
        r = requests.get(excel_url, timeout=25)
        r.raise_for_status()
        return pd.read_excel(io.BytesIO(r.content))
    if os.path.exists(DEFAULT_LOCAL_PATH):
        return pd.read_excel(DEFAULT_LOCAL_PATH)
    st.error("Impossible de charger le fichier Excel.")
    st.stop()

def normalize_bool(val):
    if isinstance(val, str):
        return val.strip().lower() in ["oui", "yes", "true", "1", "vrai"]
    if isinstance(val, (int, float)):
        return int(val) == 1
    if isinstance(val, bool):
        return val
    return False

def to_number(value) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    s = s.replace("€", "").replace("m²", "").replace(" ", "").replace(",", ".")
    m = re.findall(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    return float(m[0])

def clean_latlon_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False)
        .map(to_number)
    )

def find_col(df: pd.DataFrame, *candidates) -> str:
    def _norm(x: str) -> str:
        return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", str(x).lower()))
    for cand in candidates:
        for c in df.columns:
            if _norm(cand) in _norm(c):
                return c
    return ""

# -------------------------------------------------
# PANNEAU DROIT
# -------------------------------------------------
def render_right_panel(ref, df, col_ref, col_addr_full, col_city, col_gmaps):
    if not ref:
        st.markdown("<div class='smbg-header'>Aucune sélection</div>", unsafe_allow_html=True)
        return
    row = df[df[col_ref].astype(str) == str(ref)].iloc[0]
    st.markdown(f"<div class='smbg-header'>Réf. {ref}</div>", unsafe_allow_html=True)
    if col_gmaps:
        link = row.get(col_gmaps, "")
        if link and link not in ["-", "/"]:
            st.markdown(f"<a href='{link}' target='_blank'><button class='copper-btn'>Cliquer ici</button></a>", unsafe_allow_html=True)
    st.write(row.get(col_addr_full, ""))
    st.write(row.get(col_city, ""))
    st.write("")
    st.dataframe(row.to_frame().iloc[6:25])  # aperçu simplifié G→AD

# -------------------------------------------------
# MAIN
# -------------------------------------------------
def main():
    df = load_excel()
    col_lat = find_col(df, "Latitude")
    col_lon = find_col(df, "Longitude")
    col_actif = find_col(df, "Actif")
    col_ref = find_col(df, "Référence annonce")
    col_addr = find_col(df, "Adresse complète", "Adresse")
    col_city = find_col(df, "Ville")
    col_gmaps = find_col(df, "Google Maps", "Lien Google Maps")
    if not col_ref:
        st.error("Référence annonce manquante.")
        return

    df["_actif"] = df[col_actif].apply(normalize_bool) if col_actif else True
    df["_lat"] = clean_latlon_series(df[col_lat]) if col_lat else None
    df["_lon"] = clean_latlon_series(df[col_lon]) if col_lon else None
    df_map = df[df["_actif"] & df["_lat"].notna() & df["_lon"].notna()]

    col_left, col_map, col_right = st.columns([1,4,1])

    with col_left:
        st.markdown("<div class='smbg-header'>Filtres</div>", unsafe_allow_html=True)
        st.checkbox("Centre-ville")
        st.checkbox("Périphérie")
        st.button("Réinitialiser les filtres", key='reset', help='Réinitialiser tous les filtres')
        st.button("Je suis intéressé", key='interet', help='Contact SMBG Conseil')

    with col_map:
        if df_map.empty:
            st.warning("Aucune donnée valide pour la carte.")
        else:
            m = folium.Map(location=[46.6, 1.88], zoom_start=6)
            for _, r in df_map.iterrows():
                ref_text = str(r[col_ref])
                folium.Marker(
                    location=[r["_lat"], r["_lon"]],
                    icon=folium.DivIcon(html=f"<div style='background:{LOGO_BLUE};color:white;border-radius:50%;width:28px;height:28px;text-align:center;line-height:28px;font-size:11px;font-weight:bold'>{ref_text}</div>")
                ).add_to(m)
            st_folium(m, height=800, width=None)

    with col_right:
        render_right_panel(df_map[col_ref].iloc[0] if not df_map.empty else None, df, col_ref, col_addr, col_city, col_gmaps)

if __name__ == "__main__":
    main()

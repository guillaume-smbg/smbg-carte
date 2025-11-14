
import math
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ----------------------
# Config de la page
# ----------------------
st.set_page_config(
    page_title="SMBG Carte - Step 1",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----------------------
# Constantes et chemins
# ----------------------
ASSETS_DIR = Path("assets")
DATA_PATH = Path("data") / "Liste des lots.xlsx"

BLUE_SMBG = "#05263d"
COPPER_SMBG = "#C67B42"


# ----------------------
# CSS global : carte plein écran + panneau droit rétractable
# ----------------------
css = f"""
html, body {{
    margin: 0;
    padding: 0;
    height: 100%;
    overflow: hidden;  /* pas de scroll global */
}}

[data-testid="stAppViewContainer"] {{
    margin: 0;
    padding: 0 !important;
    height: 100vh;
}}

[data-testid="stAppViewContainer"] > .main {{
    margin: 0;
    padding: 0 !important;
    height: 100vh;
}}

main.block-container, .block-container {{
    padding: 0 !important;
    margin: 0 !important;
}}

/* on supprime le header Streamlit */
[data-testid="stHeader"], [data-testid="stToolbar"] {{
    display: none;
}}

/* conteneur de la carte : fixé, plein écran */
#map-container {{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 100vh;
    margin: 0;
    padding: 0;
    overflow: hidden;
    z-index: 1;
}}

/* forcer l'iframe folium à prendre toute la hauteur */
iframe[title="st_folium.smbg_map"] {{
    height: 100vh !important;
    width: 100% !important;
    border: none;
}}

/* panneau droit rétractable (vide pour l'instant) */
#detail-drawer {{
    position: fixed;
    top: 0;
    right: 0;
    width: 275px;
    height: 100vh;
    background-color: {BLUE_SMBG};
    color: white;
    box-shadow: -2px 0 8px rgba(0, 0, 0, 0.3);
    padding: 1.5rem 1rem 1.5rem 1.25rem;
    z-index: 9999;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}}

#detail-drawer .title {{
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0;
    padding: 0;
}}

#detail-drawer .subtitle {{
    font-size: 0.9rem;
    color: {COPPER_SMBG};
}}

#detail-drawer .close-hint {{
    font-size: 0.75rem;
    opacity: 0.7;
}}
"""

st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ----------------------
# Data
# ----------------------
@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    # On garde uniquement les lignes actives si la colonne existe
    if "Actif" in df.columns:
        df = df[df["Actif"].astype(str).str.lower() == "oui"]
    return df.reset_index(drop=True)


def format_reference(value) -> str:
    """Formate la référence selon les règles : 0003 -> 3, 0005.1 -> 5.1"""
    if pd.isna(value):
        return ""
    s = str(value).strip().replace(" ", "")
    if s == "":
        return ""
    # Cas nombre simple ou float avec .0
    if s.replace(".", "", 1).isdigit():
        if "." in s:
            int_part, dec_part = s.split(".", 1)
            try:
                int_val = int(int_part)
            except ValueError:
                int_val = 0
            int_str = str(int_val)
            if set(dec_part) == {"0"}:
                return int_str
            dec_part = dec_part.rstrip("0")
            if dec_part == "":
                return int_str
            return f"{int_str}.{dec_part}"
        else:
            try:
                int_val = int(s)
            except ValueError:
                return s
            return str(int_val)
    # Cas custom style "0005.1"
    if "." in s:
        int_part, dec_part = s.split(".", 1)
        try:
            int_val = int(int_part)
        except ValueError:
            int_val = 0
        int_str = str(int_val)
        return f"{int_str}.{dec_part}" if dec_part else int_str
    try:
        return str(int(s))
    except Exception:
        return s


df = load_data(DATA_PATH)

if df.empty:
    st.error("Aucune donnée active trouvée dans le fichier Excel.")
    st.stop()

if "Latitude" not in df.columns or "Longitude" not in df.columns:
    st.error("Le fichier Excel doit contenir des colonnes 'Latitude' et 'Longitude'.")
    st.stop()


# ----------------------
# Session state (panneau droit)
# ----------------------
if "selected_ref" not in st.session_state:
    st.session_state.selected_ref = None

if "drawer_open" not in st.session_state:
    st.session_state.drawer_open = False


# ----------------------
# Carte (plein écran)
# ----------------------
# centre sur la moyenne des points (France si vide)
if not df[["Latitude", "Longitude"]].dropna().empty:
    center_lat = df["Latitude"].mean()
    center_lon = df["Longitude"].mean()
else:
    center_lat, center_lon = 46.6, 2.4

m = folium.Map(
    location=[center_lat, center_lon],
    tiles="OpenStreetMap",
    zoom_start=6,
    control_scale=False,
    zoom_control=True,
)

# Ajout des pins : 1 lot = 1 pin, pas de popup
for _, row in df.iterrows():
    lat = row.get("Latitude")
    lon = row.get("Longitude")
    if pd.isna(lat) or pd.isna(lon):
        continue

    ref_raw = row.get("Référence annonce")
    ref_display = format_reference(ref_raw)

    icon_html = f'''
<div style="
    background-color: {BLUE_SMBG};
    border-radius: 50%;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #000000;
    color: #ffffff;
    font-size: 13px;
    font-weight: bold;
    cursor: pointer;
">
    {ref_display}
</div>
'''
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(
            html=icon_html,
            icon_size=(32, 32),
            icon_anchor=(16, 16),
            class_name="smbg-divicon",
        ),
    ).add_to(m)

# Rendu de la carte (plein écran)
st.markdown('<div id="map-container">', unsafe_allow_html=True)
map_data = st_folium(
    m,
    width=None,
    height=600,  # surchargé par le CSS à 100vh
    key="smbg_map",
)
st.markdown("</div>", unsafe_allow_html=True)


# ----------------------
# Gestion des clics (pins / carte)
# ----------------------
def find_ref_from_click(lat_click, lon_click):
    """Retrouve le lot en fonction du couple latitude/longitude cliqué."""
    tol = 1e-6
    candidates = df[
        (df["Latitude"].sub(lat_click).abs() < tol)
        & (df["Longitude"].sub(lon_click).abs() < tol)
    ]
    if candidates.empty:
        return None
    return candidates.iloc[0].get("Référence annonce")


if map_data is not None:
    obj_clicked = map_data.get("last_object_clicked")
    map_clicked = map_data.get("last_clicked")

    # Priorité au clic sur un pin
    if obj_clicked is not None:
        lat_click = obj_clicked.get("lat")
        lon_click = obj_clicked.get("lng")
        if lat_click is not None and lon_click is not None:
            ref = find_ref_from_click(lat_click, lon_click)
            if ref is not None:
                st.session_state.selected_ref = ref
                st.session_state.drawer_open = True
    elif map_clicked is not None:
        # Clic sur la carte (hors pin) -> fermeture du panneau
        st.session_state.selected_ref = None
        st.session_state.drawer_open = False


# ----------------------
# Panneau droit (rétractable, vide pour l'instant)
# ----------------------
if st.session_state.drawer_open and st.session_state.selected_ref is not None:
    ref_display = format_reference(st.session_state.selected_ref)
    drawer_html = f"""
<div id="detail-drawer">
    <p class="subtitle">Détails de l'annonce</p>
    <p class="title">{ref_display}</p>
    <p class="close-hint">Cliquer sur la carte pour refermer ce panneau.</p>
    <!-- Contenu détaillé à ajouter aux étapes suivantes -->
</div>
"""
    st.markdown(drawer_html, unsafe_allow_html=True)

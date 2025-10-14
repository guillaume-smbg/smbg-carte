import os, re, math
from typing import Optional, Tuple, List, Dict

import pandas as pd
import numpy as np
import streamlit as st
from PIL import Image
from streamlit_folium import st_folium
import folium

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="SMBG Carte — Sélection d’annonces", layout="wide")

# =========================
# ASSETS & COULEURS
# =========================
COPPER = "#B87333"

LOGO_CANDIDATES = [
    "logo bleu crop.png", "Logo bleu crop.png",
    "assets/logo bleu crop.png", "assets/Logo bleu crop.png",
    "images/logo bleu crop.png", "static/logo bleu crop.png",
]

def first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def hex_from_rgb(rgb) -> str:
    r, g, b = [int(x) for x in rgb]
    return "#{:02X}{:02X}{:02X}".format(r, g, b)

def get_blue_from_logo(path: str) -> str:
    try:
        with Image.open(path).convert("RGBA") as im:
            im = im.resize((80, 80))
            data = np.array(im)
            mask = data[:, :, 3] > 10
            if not mask.any():
                return "#0A2942"
            rgb = data[:, :, :3][mask]
            med = np.median(rgb, axis=0)
            return hex_from_rgb(med)
    except Exception:
        return "#0A2942"

LOGO_PATH = first_existing(LOGO_CANDIDATES)
BLUE_SMBG = get_blue_from_logo(LOGO_PATH) if LOGO_PATH else "#0A2942"

# =========================
# CSS — PLEIN ÉCRAN + SIDEBAR TOUJOURS VISIBLE + PAS DE SCROLL
# =========================
st.markdown(f"""
<style>
  html, body, .stApp {{ height: 100%; margin: 0; overflow: hidden; }}

  /* Conteneur principal : aucune marge/padding, largeur complète, 100vh */
  [data-testid="stAppViewContainer"] {{
    padding: 0 !important;
  }}
  .block-container {{
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
    height: 100vh !important;
    box-sizing: border-box;
  }}
  /* Supprime le padding haut/bas que Streamlit ajoute parfois */
  section.main > div {{ padding: 0 !important; }}

  /* Sidebar (volet gauche) toujours visible et fixe à 275px */
  [data-testid="stSidebar"] {{
    background: {BLUE_SMBG};
    width: 275px !important;
    min-width: 275px !important;
    padding: 6px 10px 8px 10px !important;
  }}

  /* Masque tous les contrôles de rétraction/chevrons */
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapseButton"],
  button[kind="header"] {{ display: none !important; }}

  /* Logo centré et compact */
  .smbg-logo-wrap {{ display:flex; justify-content:center; align-items:flex-start; margin:0 0 8px 0; }}
  [data-testid="stSidebar"] img {{
    width: 38% !important; max-width: 110px !important; height:auto !important; margin:2px auto 0 auto !important;
  }}

  /* Titres/labels en cuivré */
  .smbg-title, .smbg-counter {{ color: {COPPER} !important; }}
  [data-testid="stSidebar"] label p, [data-testid="stSidebar"] .stMarkdown p {{
    color: {COPPER} !important; margin:0 0 4px 0 !important; font-size: 13px !important;
  }}

  /* La carte (iframe folium) doit prendre 100vh et toute la largeur restante */
  iframe[title^="st_folium"], iframe[title="st_folium"] {{
    height: 100vh !important;
    width: 100% !important;
    border: 0;
    display: block;
  }}
</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS
# =========================
def truthy_yes(x) -> bool:
    return str(x).strip().lower() in {"oui","yes","true","1","y"}

def empty(v) -> bool:
    if pd.isna(v): return True
    s = str(v).strip()
    return s=="" or s in {"/","-","—"}

def geo_float(x)->Optional[float]:
    """Convertit latitude/longitude en float, supporte virgules/espaces."""
    if pd.isna(x): return None
    s = str(x).strip()
    if s in ("", "/", "-", "—"): return None
    s = s.replace(",", ".")
    try: return float(s)
    except: return None

# =========================
# CHARGEMENT EXCEL
# =========================
@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    # 1) fichiers locaux usuels
    for p in ["annonces.xlsx", "data/annonces.xlsx", "Liste des lots Version 2.xlsx"]:
        if os.path.exists(p):
            return pd.read_excel(p)
    # 2) variable d’env (Streamlit Cloud)
    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL","")).strip()
    if url:
        return pd.read_excel(url)
    st.error("Aucun Excel trouvé. Place ‘annonces.xlsx’ (ou ‘Liste des lots Version 2.xlsx’) ou définis EXCEL_URL.")
    return pd.DataFrame()

df = load_excel()
if df.empty:
    st.stop()

# =========================
# MAPPING COLONNES (Version 2)
# =========================
COL_REGION="Région"
COL_DEPT="Département"
COL_EMPLACEMENT="Emplacement"
COL_TYPO="Typologie"
COL_REF="Référence annonce"
COL_LAT="Latitude"
COL_LON="Longitude"
COL_ACTIF="Actif"

# Garde uniquement Actif = oui si dispo
if COL_ACTIF in df.columns:
    df = df[df[COL_ACTIF].apply(truthy_yes)].copy()

# =========================
# SIDEBAR (on garde juste le logo + un rappel de comptage)
# =========================
with st.sidebar:
    st.markdown("<div class='smbg-logo-wrap'>", unsafe_allow_html=True)
    if LOGO_PATH:
        st.image(LOGO_PATH)
    else:
        st.markdown("<p style='text-align:center;color:white;font-weight:600;'>SMBG CONSEIL</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='smbg-title'><b>Rappel</b></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='smbg-counter'>{len(df)} lignes chargées</div>", unsafe_allow_html=True)

# =========================
# CARTE PLEIN ÉCRAN (aucun volet droit pour l’instant)
# =========================

# Prépare les données géo
df_geo = df.copy()
if {COL_LAT, COL_LON}.issubset(df_geo.columns):
    df_geo["_lat"] = df_geo[COL_LAT].apply(geo_float)
    df_geo["_lon"] = df_geo[COL_LON].apply(geo_float)
    df_geo = df_geo.dropna(subset=["_lat","_lon"])
else:
    df_geo = df_geo.iloc[0:0]

# Centre carte : moyenne des points si dispo, sinon France
if not df_geo.empty:
    center = [df_geo["_lat"].mean(), df_geo["_lon"].mean()]
else:
    center = [46.6, 2.5]

# Création carte
m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")

# Ajoute les pins
bounds = []
for _, row in df_geo.iterrows():
    ref_txt = str(row.get(COL_REF, "")).strip()
    lat = float(row["_lat"]); lon = float(row["_lon"])
    folium.Marker([lat, lon],
                  tooltip=ref_txt if ref_txt else None,
                  popup=ref_txt if ref_txt else None).add_to(m)
    bounds.append([lat, lon])

# Ajuste la vue si on a des points
if bounds:
    folium.FitBounds(bounds).add_to(m)

# Affiche la carte — la hauteur/largeur réelles sont forcées par le CSS (100vh / 100%)
st_folium(m, key="smbg_map_full", use_container_width=True, height=800)

# Petit indicateur (debug) du nombre de pins rendus
st.caption(f"Pins rendus : {len(bounds)} / {len(df)} (via {COL_LAT}/{COL_LON})")

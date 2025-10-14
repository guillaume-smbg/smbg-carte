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
# ASSETS & COLORS
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
# CSS — FULLSCREEN, NO SCROLL, SIDEBAR FIXE, SANS BOUTON DE RÉTRACTION
# =========================
st.markdown(f"""
<style>
  html, body, .stApp {{ height: 100%; margin: 0; overflow: hidden; }}

  [data-testid="stAppViewContainer"] {{ padding: 0 !important; }}
  .block-container {{
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
    height: 100vh !important;
    box-sizing: border-box;
  }}
  section.main > div {{ padding: 0 !important; }}

  /* Sidebar */
  [data-testid="stSidebar"] {{
    background: {BLUE_SMBG};
    width: 275px !important;
    min-width: 275px !important;
    padding: 6px 10px 8px 10px !important;
  }}
  /* Masque TOUT contrôle de rétraction */
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapseButton"],
  button[kind="header"] {{ display: none !important; }}

  /* Logo compact et centré */
  .smbg-logo-wrap {{ display:flex; justify-content:center; align-items:flex-start; margin:0 0 8px 0; }}
  [data-testid="stSidebar"] img {{
    width: 38% !important; max-width: 110px !important; height:auto !important; margin:2px auto 0 auto !important;
  }}

  /* Titres/labels cuivrés */
  .smbg-title, .smbg-counter {{ color: {COPPER} !important; }}
  [data-testid="stSidebar"] label p, [data-testid="stSidebar"] .stMarkdown p {{
    color: {COPPER} !important; margin:0 0 4px 0 !important; font-size: 13px !important;
  }}
  .smbg-indent {{ margin-left: 16px; }}
  .two-col {{ display:grid; grid-template-columns:repeat(2,1fr); gap:2px 8px; }}
  .nested-scroll {{ max-height: 180px; overflow-y:auto; padding-right:4px; }}

  /* Carte plein écran (iframe folium) */
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

def find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Trouve une colonne de df en testant lowercase/strip des noms."""
    norm = {str(c).strip().lower(): c for c in df.columns}
    for wanted in candidates:
        key = wanted.strip().lower()
        if key in norm:
            return norm[key]
    # essaie sans accents simples
    def deaccent(s: str) -> str:
        repl = (("é","e"),("è","e"),("ê","e"),("à","a"),("ù","u"),("ô","o"),("ï","i"),("î","i"))
        t = s.lower().strip()
        for a,b in repl: t = t.replace(a,b)
        return t
    norm2 = {deaccent(k): v for k, v in norm.items()}
    for wanted in candidates:
        key = deaccent(wanted)
        if key in norm2:
            return norm2[key]
    return None

# =========================
# CHARGEMENT EXCEL
# =========================
@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    for p in ["annonces.xlsx", "data/annonces.xlsx", "Liste des lots Version 2.xlsx"]:
        if os.path.exists(p):
            return pd.read_excel(p)
    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL","")).strip()
    if url:
        return pd.read_excel(url)
    st.error("Aucun Excel trouvé. Place ‘annonces.xlsx’ (ou ‘Liste des lots Version 2.xlsx’) ou définis EXCEL_URL.")
    return pd.DataFrame()

df = load_excel()
if df.empty:
    st.stop()

# =========================
# COLONNES (robustes)
# =========================
COL_REGION = find_column(df, ["Région","Region"])
COL_DEPT   = find_column(df, ["Département","Departement"])
COL_EMPL   = find_column(df, ["Emplacement"])
COL_TYPO   = find_column(df, ["Typologie"])
COL_REF    = find_column(df, ["Référence annonce","Reference annonce","Référence","Reference"])
COL_LAT    = find_column(df, ["Latitude","lat","Lat"])
COL_LON    = find_column(df, ["Longitude","lon","Lng","Long"])

COL_ACTIF  = find_column(df, ["Actif","Active"])

if COL_ACTIF:
    df = df[df[COL_ACTIF].apply(truthy_yes)].copy()

# =========================
# SIDEBAR — filtres de base (restaurés)
# =========================
with st.sidebar:
    st.markdown("<div class='smbg-logo-wrap'>", unsafe_allow_html=True)
    if LOGO_PATH: st.image(LOGO_PATH)
    else: st.markdown("<p style='text-align:center;color:white;font-weight:600;'>SMBG CONSEIL</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = df.copy()

    # Région -> Départements imbriqués
    if COL_REGION and COL_DEPT:
        st.markdown("<div class='smbg-title'><b>Région</b></div>", unsafe_allow_html=True)
        reg2deps: Dict[str, List[str]] = {}
        for r, d in df[[COL_REGION, COL_DEPT]].dropna().drop_duplicates().itertuples(index=False):
            reg2deps.setdefault(str(r), set()).add(str(d))
        reg2deps = {k: sorted(list(v)) for k, v in reg2deps.items()}
        selected_regions = []
        selected_deps = []
        st.markdown("<div class='nested-scroll'>", unsafe_allow_html=True)
        for ridx, reg in enumerate(sorted(reg2deps.keys())):
            if st.checkbox(reg, key=f"reg_{ridx}"):
                selected_regions.append(reg)
                st.markdown("<div class='smbg-indent two-col'>", unsafe_allow_html=True)
                for i, dep in enumerate(reg2deps[reg]):
                    if st.checkbox(dep, key=f"dep_{ridx}_{i}"):
                        selected_deps.append(dep)
                st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        if selected_regions:
            filtered = filtered[filtered[COL_REGION].astype(str).isin(selected_regions)]
            if selected_deps:
                filtered = filtered[filtered[COL_DEPT].astype(str).isin(selected_deps)]

    # Emplacement
    if COL_EMPL and COL_EMPL in df.columns:
        st.markdown("<div class='smbg-title'><b>Emplacement</b></div>", unsafe_allow_html=True)
        vals = sorted([str(x) for x in df[COL_EMPL].dropna().unique()])
        st.markdown("<div class='smbg-indent two-col'>", unsafe_allow_html=True)
        picked=[]
        for i,v in enumerate(vals):
            if st.checkbox(v, key=f"emp_{i}"): picked.append(v)
        st.markdown("</div>", unsafe_allow_html=True)
        if picked:
            filtered = filtered[filtered[COL_EMPL].astype(str).isin(picked)]

    # Typologie
    if COL_TYPO and COL_TYPO in df.columns:
        st.markdown("<div class='smbg-title'><b>Typologie</b></div>", unsafe_allow_html=True)
        vals = sorted([str(x) for x in df[COL_TYPO].dropna().unique()])
        st.markdown("<div class='smbg-indent two-col'>", unsafe_allow_html=True)
        picked=[]
        for i,v in enumerate(vals):
            if st.checkbox(v, key=f"typ_{i}"): picked.append(v)
        st.markdown("</div>", unsafe_allow_html=True)
        if picked:
            filtered = filtered[filtered[COL_TYPO].astype(str).isin(picked)]

# =========================
# CARTE PLEIN ÉCRAN (aucun volet droit pour l’instant)
# =========================

# Données géo depuis lat/lon (détection robuste)
df_geo = filtered.copy()
if COL_LAT and COL_LON and (COL_LAT in df_geo.columns) and (COL_LON in df_geo.columns):
    df_geo["_lat"] = df_geo[COL_LAT].apply(geo_float)
    df_geo["_lon"] = df_geo[COL_LON].apply(geo_float)
    df_geo = df_geo.dropna(subset=["_lat","_lon"])
else:
    df_geo = df_geo.iloc[0:0]

# Centre : moyenne ou France
center = [df_geo["_lat"].mean(), df_geo["_lon"].mean()] if not df_geo.empty else [46.6, 2.5]
m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")

# Pins
bounds=[]
for _, row in df_geo.iterrows():
    ref_txt = str(row.get(COL_REF, "")).strip() if COL_REF else ""
    lat = float(row["_lat"]); lon = float(row["_lon"])
    folium.Marker([lat, lon], tooltip=ref_txt or None, popup=ref_txt or None).add_to(m)
    bounds.append([lat, lon])
if bounds:
    folium.FitBounds(bounds).add_to(m)

# Affichage (CSS force réellement 100vh / 100%)
st_folium(m, key="smbg_map_full", use_container_width=True, height=800)

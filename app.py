import os, re, time
from typing import Optional, Tuple, List, Dict

import pandas as pd
import numpy as np
import streamlit as st
from PIL import Image
from streamlit_folium import st_folium
import folium
import requests

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="SMBG Carte — Sélection d’annonces", layout="wide")

# =========================
# COULEURS / LOGO
# =========================
COPPER = "#B87333"
LOGO_CANDIDATES = [
    "logo bleu crop.png", "Logo bleu crop.png",
    "assets/logo bleu crop.png", "assets/Logo bleu crop.png",
    "images/logo bleu crop.png", "static/logo bleu crop.png",
]
def first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if os.path.exists(p): return p
    return None

def hex_from_rgb(rgb) -> str:
    r,g,b = [int(x) for x in rgb]; return "#{:02X}{:02X}{:02X}".format(r,g,b)

def get_blue_from_logo(path: str) -> str:
    try:
        with Image.open(path).convert("RGBA") as im:
            im = im.resize((80, 80))
            data = np.array(im); mask = data[:,:,3] > 10
            if not mask.any(): return "#0A2942"
            rgb = data[:,:,:3][mask]
            return hex_from_rgb(np.median(rgb, axis=0))
    except Exception:
        return "#0A2942"

LOGO_PATH = first_existing(LOGO_CANDIDATES)
BLUE_SMBG = get_blue_from_logo(LOGO_PATH) if LOGO_PATH else "#0A2942"

# =========================
# CSS — carte VRAI plein écran + sidebar fixe + pas de scroll
# =========================
st.markdown(f"""
<style>
  html, body, .stApp {{ height: 100%; margin: 0; overflow: hidden; }}
  /* Enlève header/menu/footer Streamlit */
  [data-testid="stHeader"] {{ display:none !important; }}
  #MainMenu, footer {{ visibility: hidden !important; }}

  [data-testid="stAppViewContainer"] {{ padding: 0 !important; }}
  .block-container {{
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
    height: 100vh !important;        /* plein écran réel */
    box-sizing: border-box;
  }}
  section.main > div {{ padding: 0 !important; }}

  /* Sidebar fixe, jamais rétractable */
  [data-testid="stSidebar"] {{
    background: {BLUE_SMBG};
    width: 275px !important; min-width: 275px !important;
    padding: 6px 10px 8px 10px !important;
  }}
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapseButton"],
  button[kind="header"] {{ display:none !important; }}

  /* Logo compact */
  .smbg-logo-wrap {{ display:flex; justify-content:center; margin:0 0 8px 0; }}
  [data-testid="stSidebar"] img {{
    width: 38% !important; max-width: 110px !important; height:auto !important; margin:2px auto 0 auto !important;
  }}

  /* Titres/labels en cuivré */
  .smbg-title, .smbg-counter {{ color:{COPPER} !important; }}
  [data-testid="stSidebar"] label p, [data-testid="stSidebar"] .stMarkdown p {{
    color:{COPPER} !important; margin:0 0 4px 0 !important; font-size:13px !important;
  }}
  .smbg-indent {{ margin-left:16px; }}
  .two-col {{ display:grid; grid-template-columns:repeat(2,1fr); gap:2px 8px; }}
  .nested-scroll {{ max-height: 180px; overflow-y:auto; padding-right:4px; }}

  /* L'iframe folium prend 100% largeur dispo & 100vh de hauteur */
  iframe[title^="st_folium"], iframe[title="st_folium"] {{
    height: 100vh !important;
    width: 100% !important;
    border: 0 !important;
    display: block !important;
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
    return s == "" or s in {"/", "-", "—"}

def geo_float(x) -> Optional[float]:
    if pd.isna(x): return None
    s = str(x).strip()
    if s in ("", "/", "-", "—"): return None
    s = s.replace(",", ".")
    try: return float(s)
    except: return None

def find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Trouve une colonne en tolérant casse/espaces/accents."""
    norm = {str(c).strip().lower(): c for c in df.columns}
    for wanted in candidates:
        k = wanted.strip().lower()
        if k in norm: return norm[k]
    def deaccent(s: str) -> str:
        repl = (("é","e"),("è","e"),("ê","e"),("à","a"),("ù","u"),("ô","o"),("ï","i"),("î","i"),("ç","c"))
        t = s.lower().strip()
        for a,b in repl: t = t.replace(a,b)
        return t
    norm2 = {deaccent(k): v for k,v in norm.items()}
    for wanted in candidates:
        k = deaccent(wanted)
        if k in norm2: return norm2[k]
    return None

# =========================
# CHARGEMENT EXCEL
# =========================
@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    for p in ["annonces.xlsx", "data/annonces.xlsx", "Liste des lots Version 2.xlsx"]:
        if os.path.exists(p): return pd.read_excel(p)
    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL","")).strip()
    if url: return pd.read_excel(url)
    st.error("Aucun Excel trouvé. Place ‘annonces.xlsx’ ou définis EXCEL_URL.")
    return pd.DataFrame()

df = load_excel()
if df.empty: st.stop()

# Colonnes (robustes)
COL_REGION = find_column(df, ["Région","Region"])
COL_DEPT   = find_column(df, ["Département","Departement"])
COL_EMPL   = find_column(df, ["Emplacement"])
COL_TYPO   = find_column(df, ["Typologie"])
COL_REF    = find_column(df, ["Référence annonce","Reference annonce","Référence","Reference"])
COL_LAT    = find_column(df, ["Latitude","lat","Lat"])
COL_LON    = find_column(df, ["Longitude","lon","Lng","Long"])
COL_ADDR   = find_column(df, ["Adresse"])
COL_RUE    = find_column(df, ["Rue"])
COL_CP     = find_column(df, ["Code Postal","CP","CodePostal"])
COL_VILLE  = find_column(df, ["Ville"])
COL_ACTIF  = find_column(df, ["Actif","Active"])

if COL_ACTIF:
    df = df[df[COL_ACTIF].apply(truthy_yes)].copy()

# =========================
# GÉOCODAGE — Nominatim + cache
# =========================
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = os.environ.get("GEOCODER_UA", "SMBG-Streamlit/1.0")  # mets ton UA si tu veux

@st.cache_data(show_spinner=False)
def geocode_cached(addr: str) -> Optional[Tuple[float,float]]:
    """Retourne (lat, lon) en cache pour une adresse précise, sinon None."""
    try:
        params = {"q": addr, "format": "json", "addressdetails": 0, "limit": 1, "countrycodes": "fr"}
        r = requests.get(NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
        if r.status_code == 200:
            js = r.json()
            if js:
                lat = float(js[0]["lat"]); lon = float(js[0]["lon"])
                return (lat, lon)
    except Exception:
        pass
    return None

def build_address(row) -> Optional[str]:
    if COL_ADDR and not empty(row.get(COL_ADDR, None)):
        return str(row[COL_ADDR]).strip()
    parts = []
    for c in [COL_RUE, COL_CP, COL_VILLE]:
        if c and not empty(row.get(c, None)):
            parts.append(str(row[c]).strip())
    return " ".join(parts) if parts else None

def add_latlon_from_geocoding(df_in: pd.DataFrame) -> pd.DataFrame:
    """Complète _lat/_lon :
       - 1) parse depuis colonnes lat/lon si dispo
       - 2) sinon géocode les adresses manquantes (avec limite de débit)
    """
    df2 = df_in.copy()

    # 1) parse lat/lon si colonnes présentes
    if COL_LAT and COL_LON and (COL_LAT in df2.columns) and (COL_LON in df2.columns):
        df2["_lat"] = df2[COL_LAT].apply(geo_float)
        df2["_lon"] = df2[COL_LON].apply(geo_float)

    # 2) géocode adresses manquantes
    need_geo = df2[df2.get("_lat").isna() | df2.get("_lon").isna()] if "_lat" in df2 and "_lon" in df2 else df2
    max_to_geocode = int(os.environ.get("GEOCODE_MAX", "50"))  # limite par exécution
    done = 0
    if not need_geo.empty:
        for idx, row in need_geo.iterrows():
            if done >= max_to_geocode: break
            addr = build_address(row)
            if not addr: continue
            res = geocode_cached(addr)
            if res:
                df2.loc[idx, "_lat"] = res[0]
                df2.loc[idx, "_lon"] = res[1]
                done += 1
                time.sleep(float(os.environ.get("GEOCODE_DELAY", "1.0")))  # politesse Nominatim
    return df2

# =========================
# SIDEBAR — (simple, on gardera les gros filtres plus tard)
# =========================
with st.sidebar:
    st.markdown("<div class='smbg-logo-wrap'>", unsafe_allow_html=True)
    if LOGO_PATH: st.image(LOGO_PATH)
    else: st.markdown("<p style='text-align:center;color:white;font-weight:600;'>SMBG CONSEIL</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Mini filtres (Région->Département)
    filtered = df.copy()
    if COL_REGION and COL_DEPT:
        st.markdown("<div class='smbg-title'><b>Région</b></div>", unsafe_allow_html=True)
        reg2deps: Dict[str, List[str]] = {}
        for r,d in df[[COL_REGION, COL_DEPT]].dropna().drop_duplicates().itertuples(index=False):
            reg2deps.setdefault(str(r), set()).add(str(d))
        reg2deps = {k: sorted(list(v)) for k,v in reg2deps.items()}

        st.markdown("<div class='nested-scroll'>", unsafe_allow_html=True)
        chosen_regs, chosen_deps = [], []
        for i, reg in enumerate(sorted(reg2deps.keys())):
            if st.checkbox(reg, key=f"reg_{i}"):
                chosen_regs.append(reg)
                st.markdown("<div class='smbg-indent two-col'>", unsafe_allow_html=True)
                for j, dep in enumerate(reg2deps[reg]):
                    if st.checkbox(dep, key=f"dep_{i}_{j}"): chosen_deps.append(dep)
                st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if chosen_regs:
            filtered = filtered[filtered[COL_REGION].astype(str).isin(chosen_regs)]
            if chosen_deps:
                filtered = filtered[filtered[COL_DEPT].astype(str).isin(chosen_deps)]

# =========================
# CARTE — occupation totale de l’espace libre
# =========================
df_geo = add_latlon_from_geocoding(filtered)
df_geo = df_geo.dropna(subset=["_lat","_lon"])

center = [df_geo["_lat"].mean(), df_geo["_lon"].mean()] if not df_geo.empty else [46.6, 2.5]
m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")

bounds=[]
for _, row in df_geo.iterrows():
    ref = str(row.get(COL_REF, "")).strip() if COL_REF else ""
    lat, lon = float(row["_lat"]), float(row["_lon"])
    folium.Marker([lat, lon], tooltip=ref or None, popup=ref or None).add_to(m)
    bounds.append([lat, lon])
if bounds: folium.FitBounds(bounds).add_to(m)

# Affichage — la hauteur/largeur réelles sont forcées par le CSS à 100vh/100%
st_folium(m, key="map_full", use_container_width=True, height=800)

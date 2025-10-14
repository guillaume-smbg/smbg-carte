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
COPPER = "#B87333"  # orangé cuivré validé

LOGO_PATH_CANDIDATES = [
    "logo bleu crop.png", "Logo bleu crop.png",
    "assets/logo bleu crop.png", "assets/Logo bleu crop.png",
    "images/logo bleu crop.png", "static/logo bleu crop.png",
]

def get_first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def hex_from_rgb(rgb) -> str:
    r, g, b = [int(x) for x in rgb]
    return "#{:02X}{:02X}{:02X}".format(r, g, b)

def get_dominant_color(path: str) -> str:
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

LOGO_PATH = get_first_existing(LOGO_PATH_CANDIDATES)
BLUE_SMBG = get_dominant_color(LOGO_PATH) if LOGO_PATH else "#0A2942"

# =========================
# CSS (volets 275px, carte 100vh, drawer rétractile)
# =========================
st.markdown(f"""
<style>
  /* Sidebar (volet gauche) */
  [data-testid="stSidebar"] {{
    background: {BLUE_SMBG};
    width: 275px !important;
    min-width: 275px !important;
    padding: 6px 10px 8px 10px !important;
  }}
  [data-testid="collapsedControl"] {{ display:none !important; }}

  .smbg-logo-wrap {{ display:flex; justify-content:center; margin:0 0 8px 0; }}
  [data-testid="stSidebar"] img {{
    width: 38% !important; max-width: 110px !important; height:auto !important; margin: 2px auto 0 auto !important;
  }}

  .smbg-title, .smbg-actions-title, .smbg-counter {{ color: {COPPER} !important; }}
  [data-testid="stSidebar"] label p, [data-testid="stSidebar"] .stMarkdown p {{
    color: {COPPER} !important; margin:0 0 4px 0 !important; font-size:13px !important;
  }}
  .smbg-indent {{ margin-left: 16px; }}

  /* Carte plein écran */
  iframe[title="st_folium"] {{
    height: calc(100vh - 40px) !important;
    min-height: 600px;
  }}

  /* Volet droit FIXE 275px, rétractile */
  .smbg-right-drawer {{
    position: fixed; top: 0; right: 0; width: 275px; height: 100vh;
    padding: 14px; background: #fff; box-shadow: -6px 0 16px rgba(0,0,0,0.12);
    overflow-y: auto; z-index: 9999;
  }}
  .smbg-right-hidden {{ display: none; }}

  .ref-banner {{
    background:{BLUE_SMBG}; color:#fff; padding:8px 12px; border-radius:10px; display:inline-block; font-weight:600;
  }}
  .field {{ margin-bottom: 6px; }}
  .field b {{ color:#333; }}
</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS
# =========================
def truthy_yes(x) -> bool:
    return str(x).strip().lower() in {"oui","yes","true","1","y"}

def is_empty_cell(v) -> bool:
    if pd.isna(v): return True
    s = str(v).strip()
    return s == "" or s in {"/", "-", "—"}

def to_float_clean(x) -> Optional[float]:
    if pd.isna(x): return None
    s = str(x).strip().lower()
    if s in {"", "/", "-", "—"}: return None
    if "selon surface" in s: return None
    s = re.sub(r"[^\d,.\-]", "", s)
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return None

def parse_surface_range(text: str) -> Tuple[Optional[float], Optional[float]]:
    if pd.isna(text): return (None, None)
    s = str(text).lower()
    nums = re.findall(r"[\d]+(?:[.,]\d+)?", s)
    if not nums:
        v = to_float_clean(s)
        return (v, v) if v is not None else (None, None)
    vals = []
    for n in nums:
        n = n.replace(",", ".")
        try:
            vals.append(float(n))
        except: pass
    if not vals: return (None, None)
    if len(vals) == 1: return (vals[0], vals[0])
    return (min(vals), max(vals))

def row_surface_interval(row, col_gla: Optional[str], col_rep_gla: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    mins, maxs = [], []
    if col_gla and col_gla in row.index:
        v = to_float_clean(row[col_gla])
        if v is not None: mins.append(v); maxs.append(v)
    if col_rep_gla and col_rep_gla in row.index and not is_empty_cell(row[col_rep_gla]):
        rmin, rmax = parse_surface_range(row[col_rep_gla])
        if rmin is not None: mins.append(rmin)
        if rmax is not None: maxs.append(rmax)
    if mins and maxs: return (min(mins), max(maxs))
    return (None, None)

def normalize_extraction(value: str) -> str:
    if is_empty_cell(value): return "NR"
    s = str(value).strip().lower()
    if any(k in s for k in ["oui", "faisable", "possible", "ok"]): return "OUI"
    if "non" in s: return "NON"
    return "NR"

def dab_is_yes(value) -> Optional[bool]:
    if is_empty_cell(value): return None
    s = str(value).strip().lower()
    if s in {"néant", "neant", "0", "0€", "0 €"}: return False
    f = to_float_clean(s)
    if f is not None and f > 0: return True
    return True

def to_float_geo(x: any) -> Optional[float]:
    """Latitude/Longitude -> float ; gère les virgules."""
    if pd.isna(x): return None
    s = str(x).strip()
    if s in ("", "/", "-", "—"): return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return None

# =========================
# LOAD DATA
# =========================
@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    for p in ["annonces.xlsx", "data/annonces.xlsx"]:
        if os.path.exists(p):
            return pd.read_excel(p)
    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    if url:
        return pd.read_excel(url)
    st.error("Aucun Excel trouvé. Place ‘annonces.xlsx’ ou définis EXCEL_URL.")
    return pd.DataFrame()

df = load_excel()
if df.empty:
    st.stop()

# =========================
# COLUMN MAP (V2+)
# =========================
COL_REGION        = "Région"
COL_DEPT          = "Département"
COL_EMPLACEMENT   = "Emplacement"
COL_TYPOLOGIE     = "Typologie"

COL_DAB           = "Cession / Droit au bail"
COL_NB_LOTS       = "Nombre de lots"          # M
COL_GLA           = "Surface GLA"              # N
COL_REP_GLA       = "Répartition surface GLA"  # O
COL_UTILE         = "Surface Utile"            # P
COL_REP_UTILE     = "Répartition surface utile"# Q
COL_LOYER_ANNUEL  = "Loyer annuel"             # R

COL_EXTRACTION    = "Extraction"
COL_GOOGLE        = "Lien Google Maps"
COL_REF           = "Référence annonce"
COL_LAT           = "Latitude"
COL_LON           = "Longitude"
COL_ACTIF         = "Actif"

# Actif = oui
if COL_ACTIF in df.columns:
    df = df[df[COL_ACTIF].apply(truthy_yes)].copy()

# =========================
# STATE (sélection + volet droit)
# =========================
st.session_state.setdefault("last_selected_ref", None)
st.session_state.setdefault("drawer_open", False)

# =========================
# SIDEBAR (volet gauche) — on garde la version actuelle
# =========================
with st.sidebar:
    st.markdown("<div class='smbg-logo-wrap'>", unsafe_allow_html=True)
    if LOGO_PATH:
        st.image(LOGO_PATH)
    else:
        st.markdown("<p style='text-align:center;color:white;font-weight:600;'>SMBG CONSEIL</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = df.copy()

    # (On peut garder quelques filtres simples pour tester)
    if COL_REGION in df.columns:
        st.markdown("<div class='smbg-title'><b>Région</b></div>", unsafe_allow_html=True)
        regs = sorted([str(x) for x in df[COL_REGION].dropna().unique()])
        sel_regs = []
        for i, r in enumerate(regs):
            if st.checkbox(r, key=f"reg_{i}"):
                sel_regs.append(r)
        if sel_regs:
            filtered = filtered[filtered[COL_REGION].astype(str).isin(sel_regs)]

    if COL_EMPLACEMENT in df.columns:
        st.markdown("<div class='smbg-title'><b>Emplacement</b></div>", unsafe_allow_html=True)
        vals = sorted([str(x) for x in df[COL_EMPLACEMENT].dropna().unique()])
        sel_vals = []
        col1, col2 = st.columns(2)
        for i, v in enumerate(vals):
            with (col1 if i % 2 == 0 else col2):
                if st.checkbox(v, key=f"emp_{i}"):
                    sel_vals.append(v)
        if sel_vals:
            filtered = filtered[filtered[COL_EMPLACEMENT].astype(str).isin(sel_vals)]

# =========================
# CARTE 100vh + VOLET DROIT RÉTRACTILE
# =========================

# Données géo
df_geo = filtered.copy()
if COL_LAT in df_geo.columns and COL_LON in df_geo.columns:
    df_geo["_lat"] = df_geo[COL_LAT].apply(to_float_geo)
    df_geo["_lon"] = df_geo[COL_LON].apply(to_float_geo)
    df_geo = df_geo.dropna(subset=["_lat","_lon"])
else:
    df_geo = df_geo.iloc[0:0]

# Centre
center = [df_geo["_lat"].mean(), df_geo["_lon"].mean()] if not df_geo.empty else [46.6, 2.5]

# Carte
m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")

bounds = []
for _, row in df_geo.iterrows():
    ref_txt = str(row.get(COL_REF, ""))
    lat = float(row["_lat"]); lon = float(row["_lon"])
    folium.Marker([lat, lon], tooltip=ref_txt, popup=ref_txt).add_to(m)
    bounds.append([lat, lon])
if bounds:
    folium.FitBounds(bounds).add_to(m)

# Affichage + évènements
map_event = st_folium(m, key="smbg_map")

# ---- LOGIQUE RÉTRACTILE DU VOLET DROIT ----
# 1) Clic sur un pin -> map_event['last_object_clicked_popup'] (texte du popup)
clicked_popup = None
if isinstance(map_event, dict):
    clicked_popup = map_event.get("last_object_clicked_popup", None)

# 2) Clic ailleurs sur la carte -> map_event['last_clicked'] = {'lat':..., 'lng':...}
clicked_map = None
if isinstance(map_event, dict):
    clicked_map = map_event.get("last_clicked", None)

# Cas 1 : pin cliqué -> ouvrir le tiroir + mémoriser la référence
if clicked_popup:
    st.session_state["last_selected_ref"] = str(clicked_popup)
    st.session_state["drawer_open"] = True

# Cas 2 : clic fond de carte -> fermer le tiroir
elif clicked_map is not None:
    st.session_state["drawer_open"] = False

# Choisir la ligne à afficher si le tiroir est ouvert
detail_row = None
if st.session_state["drawer_open"]:
    if st.session_state["last_selected_ref"] and COL_REF in filtered.columns:
        mask = filtered[COL_REF].astype(str) == str(st.session_state["last_selected_ref"])
        if mask.any():
            detail_row = filtered[mask].iloc[0]
        else:
            # si la ref sélectionnée n'existe plus (filtres), on ferme
            st.session_state["drawer_open"] = False

# ---- Rendu du tiroir ----
drawer_cls = "smbg-right-drawer" if st.session_state["drawer_open"] and (detail_row is not None) else "smbg-right-drawer smbg-right-hidden"
st.markdown(f"<div class='{drawer_cls}'>", unsafe_allow_html=True)

if st.session_state["drawer_open"] and (detail_row is not None):
    # Référence
    ref_val = str(detail_row.get(COL_REF, ""))
    if ref_val:
        st.markdown(f"<span class='ref-banner'>Référence annonce : {ref_val}</span>", unsafe_allow_html=True)
        st.write("")

    # Google Maps
    gm = detail_row.get(COL_GOOGLE, "")
    if gm and not is_empty_cell(gm):
        st.link_button("Ouvrir Google Maps", str(gm).strip(), type="primary")

    st.write("")

    # Adresse
    parts = []
    for col in ["Rue", "Code Postal", "Ville"]:
        if col in filtered.columns and not is_empty_cell(detail_row.get(col, None)):
            parts.append(str(detail_row[col]))
    if parts:
        st.markdown(f"<div class='field'><b>Adresse</b> : {' — '.join(parts)}</div>", unsafe_allow_html=True)

    # Emplacement / Typologie / Type
    for col in [COL_EMPLACEMENT, COL_TYPOLOGIE, "Type"]:
        if col in filtered.columns and not is_empty_cell(detail_row.get(col, None)):
            st.markdown(f"<div class='field'><b>{col}</b> : {detail_row[col]}</div>", unsafe_allow_html=True)

    # Surfaces + répartitions (infos)
    gla_val = detail_row.get(COL_GLA, None)
    if not is_empty_cell(gla_val):
        st.markdown(f"<div class='field'><b>Surface GLA</b> : {gla_val}</div>", unsafe_allow_html=True)
    rep_gla = detail_row.get(COL_REP_GLA, None)
    if not is_empty_cell(rep_gla):
        st.markdown(f"<div class='field'><b>Répartition Surface GLA</b> : {rep_gla}</div>", unsafe_allow_html=True)

    utile_val = detail_row.get(COL_UTILE, None)
    if not is_empty_cell(utile_val):
        st.markdown(f"<div class='field'><b>Surface Utile</b> : {utile_val}</div>", unsafe_allow_html=True)
    rep_utile = detail_row.get(COL_REP_UTILE, None)
    if not is_empty_cell(rep_utile):
        st.markdown(f"<div class='field'><b>Répartition Surface Utile</b> : {rep_utile}</div>", unsafe_allow_html=True)

    # Cession / DAB
    if COL_DAB in filtered.columns and not is_empty_cell(detail_row.get(COL_DAB, None)):
        st.markdown(f"<div class='field'><b>Cession / Droit au bail</b> : {detail_row[COL_DAB]}</div>", unsafe_allow_html=True)

    # Loyer
    if COL_LOYER_ANNUEL in filtered.columns:
        ly = detail_row.get(COL_LOYER_ANNUEL, None)
        if not is_empty_cell(ly):
            s = str(ly)
            st.markdown(f"<div class='field'><b>Loyer annuel</b> : {'Selon surface' if 'selon surface' in s.lower() else s}</div>", unsafe_allow_html=True)

    # Extraction
    if COL_EXTRACTION in filtered.columns and not is_empty_cell(detail_row.get(COL_EXTRACTION, None)):
        st.markdown(f"<div class='field'><b>Extraction</b> : {detail_row[COL_EXTRACTION]}</div>", unsafe_allow_html=True)

    # Région / Département
    for col in [COL_DEPT, COL_REGION]:
        if col in filtered.columns and not is_empty_cell(detail_row.get(col, None)):
            st.markdown(f"<div class='field'><b>{col}</b> : {detail_row[col]}</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

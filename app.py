import os, re, math, time
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

# -------------------------
# DEBUG SWITCH (aucun affichage en prod)
# -------------------------
SHOW_DEBUG = False  # passe à True pour diagnostiquer en local

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
    r,g,b = [int(x) for x in rgb]
    return "#{:02X}{:02X}{:02X}".format(r,g,b)
def get_blue_from_logo(path: str) -> str:
    try:
        with Image.open(path).convert("RGBA") as im:
            im = im.resize((80, 80))
            data = np.array(im)
            mask = data[:,:,3] > 10
            if not mask.any(): return "#0A2942"
            rgb = data[:,:,:3][mask]
            med = np.median(rgb, axis=0)
            return hex_from_rgb(med)
    except Exception:
        return "#0A2942"
LOGO_PATH = first_existing(LOGO_CANDIDATES)
BLUE_SMBG = get_blue_from_logo(LOGO_PATH) if LOGO_PATH else "#0A2942"

# =========================
# CSS — plein écran, sidebar figée, logo fixe, tiroir droit
# =========================
st.markdown(f"""
<style>
  html, body, .stApp {{ height: 100%; margin: 0; overflow: hidden; }}
  [data-testid="stHeader"] {{ display: none !important; }}
  #MainMenu, footer {{ display: none !important; }}
  [data-testid="stAppViewContainer"] {{ padding: 0 !important; }}
  section.main {{ height: 100vh !important; }}
  section.main > div {{ padding: 0 !important; height: 100vh !important; }}
  .block-container {{
    padding: 0 !important; margin: 0 !important;
    max-width: 100% !important; height: 100vh !important; box-sizing: border-box;
  }}
  [data-testid="stSidebar"] {{
    background: {BLUE_SMBG};
    width: 275px !important; min-width: 275px !important;
    padding: 6px 10px 8px 10px !important;
  }}
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapseButton"],
  button[kind="header"] {{ display: none !important; }}
  .smbg-logo-wrap {{ display:flex; justify-content:center; margin: 0 0 8px 0; }}
  [data-testid="stSidebar"] [data-testid="stImage"] button {{ display:none !important; }}
  [data-testid="stSidebar"] img {{
    width: 38% !important; max-width: 110px !important; height:auto !important; margin:2px auto 0 auto !important;
  }}
  .smbg-title, .smbg-counter {{ color:{COPPER} !important; }}
  [data-testid="stSidebar"] label p, [data-testid="stSidebar"] .stMarkdown p {{
    color:{COPPER} !important; margin: 0 0 4px 0 !important; font-size: 13px !important;
  }}
  .smbg-indent {{ margin-left: 16px; }}
  .two-col {{ display:grid; grid-template-columns:repeat(2, 1fr); gap: 2px 8px; }}
  .nested-scroll {{ max-height: 180px; overflow-y:auto; padding-right:4px; }}
  iframe[title^="st_folium"], iframe[title="st_folium"] {{
    height: 100vh !important;
    width: 100% !important;
    border: 0 !important;
    display: block !important;
  }}
  .drawer {{
    position: fixed; top: 0; right: 0; width: 275px; height: 100vh;
    background: #fff; box-shadow: -6px 0 16px rgba(0,0,0,.14);
    padding: 14px; overflow-y: auto; z-index: 9999;
  }}
  .drawer.hidden {{ display: none; }}
  .ref-banner {{
    background:{BLUE_SMBG}; color:#fff;
    padding:8px 12px; border-radius:10px; display:inline-block; font-weight:600;
  }}
  .field {{ margin-bottom: 6px; }}
  .field b {{ color: #333; }}
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
def to_float(x) -> Optional[float]:
    if pd.isna(x): return None
    s = str(x).strip().lower()
    if s in {"","/","-","—"}: return None
    if "selon surface" in s: return None
    s = re.sub(r"[^\d,.\-]", "", s)
    if s.count(",")==1 and s.count(".")==0: s = s.replace(",", ".")
    try: return float(s)
    except: return None
def parse_range(text: str) -> Tuple[Optional[float], Optional[float]]:
    if pd.isna(text): return (None,None)
    s = str(text).lower()
    nums = re.findall(r"[\d]+(?:[.,]\d+)?", s)
    if not nums:
        v = to_float(s)
        return (v,v) if v is not None else (None,None)
    vals=[]
    for n in nums:
        try: vals.append(float(n.replace(",", ".")))
        except: pass
    if not vals: return (None,None)
    if len(vals)==1: return (vals[0], vals[0])
    return (min(vals), max(vals))
def gla_interval(row, col_gla, col_rep):
    mins, maxs = [], []
    if col_gla in row and not empty(row[col_gla]):
        v = to_float(row[col_gla])
        if v is not None: mins.append(v); maxs.append(v)
    if col_rep in row and not empty(row[col_rep]):
        a,b = parse_range(row[col_rep])
        if a is not None: mins.append(a)
        if b is not None: maxs.append(b)
    if mins and maxs: return (min(mins), max(maxs))
    return (None,None)
def norm_extraction(v:str) -> str:
    if empty(v): return "NR"
    s=str(v).strip().lower()
    if any(k in s for k in ["oui","faisable","possible","ok"]): return "OUI"
    if "non" in s: return "NON"
    return "NR"
def dab_yes(v) -> Optional[bool]:
    if empty(v): return None
    s=str(v).strip().lower()
    if s in {"néant","neant","0","0€","0 €"}: return False
    f=to_float(s)
    if f is not None and f>0: return True
    return True
def geo_float(x)->Optional[float]:
    if pd.isna(x): return None
    s = str(x).strip()
    if s in ("","","/","-","—"): return None
    s = s.replace(",", ".")
    try: return float(s)
    except: return None
def deaccent(s: str) -> str:
    for a,b in (("é","e"),("è","e"),("ê","e"),("à","a"),("ù","u"),("ô","o"),("ï","i"),("î","i"),("ç","c")):
        s = s.replace(a,b)
    return s
def find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    norm = {deaccent(str(c)).strip().lower(): c for c in df.columns}
    for wanted in candidates:
        k = deaccent(wanted).strip().lower()
        if k in norm: return norm[k]
    return None

# =========================
# CHARGEMENT EXCEL
# =========================
@st.cache_data(show_spinner=False)
def load_excel()->pd.DataFrame:
    for p in ["Liste des lots Version 2.xlsx","annonces.xlsx","data/annonces.xlsx"]:
        if os.path.exists(p): return pd.read_excel(p)
    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL","")).strip()
    if url: return pd.read_excel(url)
    st.error("Aucun Excel trouvé. Place ‘Liste des lots Version 2.xlsx’ ou définis EXCEL_URL.")
    return pd.DataFrame()
df = load_excel()
if df.empty: st.stop()

# =========================
# COLONNES (Version 2 + fallback)
# =========================
COL_REGION = find_column(df, ["Région","Region"]) or "Région"
COL_DEPT   = find_column(df, ["Département","Departement"]) or "Département"
COL_EMPL   = find_column(df, ["Emplacement"]) or "Emplacement"
COL_TYPO   = find_column(df, ["Typologie"]) or "Typologie"
COL_DAB    = find_column(df, ["Cession / Droit au bail","Cession","Droit au bail"]) or "Cession / Droit au bail"
COL_GLA    = find_column(df, ["Surface GLA"]) or "Surface GLA"
COL_REP_GLA= find_column(df, ["Répartition surface GLA","Repartition surface GLA"]) or "Répartition surface GLA"
COL_UTILE  = find_column(df, ["Surface Utile"]) or "Surface Utile"
COL_REP_UT = find_column(df, ["Répartition surface utile","Repartition surface utile"]) or "Répartition surface utile"
COL_LOYER  = find_column(df, ["Loyer annuel","Loyer annuel HT","Loyer HT annuel"]) or "Loyer annuel"
COL_EXT    = find_column(df, ["Extraction"]) or "Extraction"
COL_GMAP   = find_column(df, ["Lien Google Maps","Lien Google","Google Maps"]) or "Lien Google Maps"
COL_REF    = find_column(df, ["Référence annonce","Reference annonce","Référence","Reference"]) or "Référence annonce"
COL_LAT    = find_column(df, ["Latitude","lat","Lat"]) or "Latitude"
COL_LON    = find_column(df, ["Longitude","lon","Lng","Long"]) or "Longitude"
COL_ACTIF  = find_column(df, ["Actif","Active"]) or "Actif"

# garder Actif = Oui (comportement précédent)
if COL_ACTIF in df.columns:
    df = df[df[COL_ACTIF].apply(truthy_yes)].copy()

# =========================
# GÉOCODAGE — 3 fournisseurs en cascade + cache
# =========================
UA = os.environ.get("GEOCODER_UA", "SMBG-Streamlit/1.0 (contact: contact@smbg.fr)")
DELAY = float(os.environ.get("GEOCODE_DELAY", "1.0"))
MAX_GEOCODE = int(os.environ.get("GEOCODE_MAX", "50"))

@st.cache_data(show_spinner=False)
def geocode_nominatim(addr: str) -> Optional[Tuple[float,float]]:
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": addr, "format":"json", "limit":1, "countrycodes":"fr"},
            headers={"User-Agent": UA}, timeout=10
        )
        if r.status_code == 200:
            js = r.json()
            if js:
                return float(js[0]["lat"]), float(js[0]["lon"])
    except Exception:
        pass
    return None

@st.cache_data(show_spinner=False)
def geocode_photon(addr: str) -> Optional[Tuple[float,float]]:
    try:
        r = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": addr, "limit": 1, "lang":"fr"},
            headers={"User-Agent": UA}, timeout=10
        )
        if r.status_code == 200:
            js = r.json()
            feats = js.get("features", [])
            if feats:
                coords = feats[0]["geometry"]["coordinates"]  # [lon, lat]
                return float(coords[1]), float(coords[0])
    except Exception:
        pass
    return None

@st.cache_data(show_spinner=False)
def geocode_mapsco(addr: str) -> Optional[Tuple[float,float]]:
    try:
        r = requests.get(
            "https://geocode.maps.co/search",
            params={"q": addr, "countrycodes":"fr", "limit": 1},
            headers={"User-Agent": UA}, timeout=10
        )
        if r.status_code == 200:
            js = r.json()
            if isinstance(js, list) and js:
                return float(js[0]["lat"]), float(js[0]["lon"])
    except Exception:
        pass
    return None

def geocode_any(addr: str) -> Optional[Tuple[float,float]]:
    for fn in (geocode_nominatim, geocode_photon, geocode_mapsco):
        res = fn(addr)
        if res: return res
    return None

def build_address(row) -> Optional[str]:
    # priorité à "Adresse" si existante, sinon Rue + CP + Ville
    adr = None
    if "Adresse" in df.columns and not empty(row.get("Adresse", None)):
        adr = str(row["Adresse"]).strip()
    else:
        parts=[]
        if "Rue" in df.columns and not empty(row.get("Rue", None)):
            parts.append(str(row["Rue"]).strip())
        if "Code Postal" in df.columns and not empty(row.get("Code Postal", None)):
            cp = str(row["Code Postal"]).strip()
            if cp.endswith(".0"): cp = cp[:-2]
            parts.append(cp)
        if "Ville" in df.columns and not empty(row.get("Ville", None)):
            parts.append(str(row["Ville"]).strip())
        if parts:
            adr = " ".join(parts)
    if adr:
        # nettoie doublons et espaces
        adr = re.sub(r"\s+", " ", adr)
        return adr.strip()
    return None

def enrich_latlon(df_in: pd.DataFrame) -> pd.DataFrame:
    """1) lit lat/lon; 2) essaie géocodage en cascade; 3) ne droppe qu'après try."""
    out = df_in.copy()

    # 1) Colonnes lat/lon → _lat/_lon
    if (COL_LAT in out.columns) and (COL_LON in out.columns):
        out["_lat"] = out[COL_LAT].apply(geo_float)
        out["_lon"] = out[COL_LON].apply(geo_float)

    # 2) Géocode ceux qui restent vides
    need = out[(out.get("_lat").isna()) | (out.get("_lon").isna())] if ("_lat" in out and "_lon" in out) else out
    done = 0
    if not need.empty:
        for idx, row in need.iterrows():
            if done >= MAX_GEOCODE: break
            addr = build_address(row)
            if not addr: continue
            res = geocode_any(addr)
            if res:
                out.loc[idx, "_lat"], out.loc[idx, "_lon"] = res
                done += 1
                time.sleep(DELAY)  # politesse

    return out

# =========================
# STATE tiroir droit
# =========================
st.session_state.setdefault("drawer_open", False)
st.session_state.setdefault("last_ref", None)

# =========================
# VOLET GAUCHE — (inchangé / figé)
# =========================
with st.sidebar:
    st.markdown("<div class='smbg-logo-wrap'>", unsafe_allow_html=True)
    if LOGO_PATH: st.image(LOGO_PATH)
    else: st.markdown("<p style='text-align:center;color:white;font-weight:600;'>SMBG CONSEIL</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = df.copy()

    # Région -> Départements imbriqués
    if (COL_REGION in df.columns) and (COL_DEPT in df.columns):
        st.markdown("<div class='smbg-title'><b>Région</b></div>", unsafe_allow_html=True)
        reg2deps: Dict[str, List[str]] = {}
        for r,d in df[[COL_REGION, COL_DEPT]].dropna().drop_duplicates().itertuples(index=False):
            reg2deps.setdefault(str(r), set()).add(str(d))
        reg2deps = {k: sorted(list(v)) for k,v in reg2deps.items()}

        sel_regs, sel_deps = [], []
        st.markdown("<div class='nested-scroll'>", unsafe_allow_html=True)
        for i,reg in enumerate(sorted(reg2deps.keys())):
            if st.checkbox(reg, key=f"reg_{i}"):
                sel_regs.append(reg)
                st.markdown("<div class='smbg-indent two-col'>", unsafe_allow_html=True)
                for j,dep in enumerate(reg2deps[reg]):
                    if st.checkbox(dep, key=f"dep_{i}_{j}"):
                        sel_deps.append(dep)
                st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if sel_regs:
            filtered = filtered[filtered[COL_REGION].astype(str).isin(sel_regs)]
            if sel_deps:
                filtered = filtered[filtered[COL_DEPT].astype(str).isin(sel_deps)]

    # Emplacement
    if COL_EMPL in df.columns:
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
    if COL_TYPO in df.columns:
        st.markdown("<div class='smbg-title'><b>Typologie</b></div>", unsafe_allow_html=True)
        vals = sorted([str(x) for x in df[COL_TYPO].dropna().unique()])
        st.markdown("<div class='smbg-indent two-col'>", unsafe_allow_html=True)
        picked=[]
        for i,v in enumerate(vals):
            if st.checkbox(v, key=f"typ_{i}"): picked.append(v)
        st.markdown("</div>", unsafe_allow_html=True)
        if picked:
            filtered = filtered[filtered[COL_TYPO].astype(str).isin(picked)]

    # Cession / DAB — visible si au moins une valeur
    show_dab = (COL_DAB in df.columns) and (~df[COL_DAB].apply(empty)).any()
    if show_dab:
        st.markdown("<div class='smbg-title'><b>Cession / Droit au bail</b></div>", unsafe_allow_html=True)
        choice = st.radio(" ", ["Oui","Non","Les deux"], horizontal=True, label_visibility="collapsed")
        if choice!="Les deux":
            flags = df[COL_DAB].apply(lambda v: True if dab_yes(v) is True else False)
            mask = flags if choice=="Oui" else ~flags
            filtered = filtered[mask.reindex(filtered.index).fillna(True)]

    # Surface GLA
    st.markdown("<div class='smbg-title'><b>Surface GLA (m²)</b></div>", unsafe_allow_html=True)
    mins,maxs=[],[]
    for _,row in df.iterrows():
        a,b = gla_interval(row, COL_GLA, COL_REP_GLA)
        if a is not None: mins.append(a)
        if b is not None: maxs.append(b)
    if mins and maxs and min(mins)<max(maxs):
        a,b = int(math.floor(min(mins))), int(math.ceil(max(maxs)))
        sl = st.slider(" ", a,b,(a,b), label_visibility="collapsed")
        keep=[]
        for idx,row in filtered.iterrows():
            x,y = gla_interval(row, COL_GLA, COL_REP_GLA)
            if x is None and y is None: keep.append(idx)
            else:
                if (y>=sl[0]) and (x<=sl[1]): keep.append(idx)
        filtered = filtered.loc[keep]

    # Loyer annuel
    if COL_LOYER in df.columns:
        st.markdown("<div class='smbg-title'><b>Loyer annuel (€)</b></div>", unsafe_allow_html=True)
        vals = [to_float(x) for x in df[COL_LOYER].tolist()]
        nums = [v for v in vals if v is not None]
        if nums and min(nums)<max(nums):
            a,b = int(math.floor(min(nums))), int(math.ceil(max(nums)))
            sl = st.slider("  ", a,b,(a,b), label_visibility="collapsed")
            num = filtered[COL_LOYER].apply(to_float)
            keep = num.isna() | ((num>=sl[0]) & (num<=sl[1]))
            filtered = filtered[keep]

    # Extraction
    if COL_EXT in df.columns:
        st.markdown("<div class='smbg-title'><b>Extraction</b></div>", unsafe_allow_html=True)
        c = st.radio("  ", ["Oui","Non","Les deux"], horizontal=True, label_visibility="collapsed")
        if c!="Les deux":
            nrm = df[COL_EXT].apply(norm_extraction)
            mask = nrm.eq("OUI") if c=="Oui" else nrm.eq("NON")
            filtered = filtered[mask.reindex(filtered.index).fillna(c=="Oui")]

# =========================
# CARTE — plein écran
# =========================
def debug(msg):
    if SHOW_DEBUG:
        st.sidebar.write(f"🔧 {msg}")

df_geo = enrich_latlon(filtered)
debug(f"Après enrich_latlon: {len(df_geo)} lignes")

# on ne DROP que maintenant
df_geo = df_geo.dropna(subset=["_lat","_lon"])
debug(f"Après dropna lat/lon: {len(df_geo)} lignes")

# Centre
center = [df_geo["_lat"].mean(), df_geo["_lon"].mean()] if not df_geo.empty else [46.6, 2.5]
m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")

# Marqueurs: icône Folium (très fiable)
bounds=[]
for _, row in df_geo.iterrows():
    lat, lon = float(row["_lat"]), float(row["_lon"])
    ref = str(row.get(COL_REF, "")).strip() if COL_REF in df_geo.columns else ""
    folium.Marker(
        [lat, lon],
        icon=folium.Icon(color="orange"),
        tooltip=ref or None,
        popup=folium.Popup(ref, max_width=260) if ref else None
    ).add_to(m)
    bounds.append([lat, lon])

# FitBounds de force si au moins 1 point
if bounds:
    m.fit_bounds(bounds)

map_event = st_folium(m, key="smbg_map_full", use_container_width=True, height=800)

# =========================
# TIROIR DROIT
# =========================
st.session_state.setdefault("drawer_open", False)
st.session_state.setdefault("last_ref", None)

clicked_popup = None
if isinstance(map_event, dict):
    if map_event.get("last_object_clicked_popup"):
        clicked_popup = map_event["last_object_clicked_popup"]
    elif map_event.get("last_object_clicked") and isinstance(map_event["last_object_clicked"], dict):
        clicked_popup = map_event["last_object_clicked"].get("popup")

clicked_map = map_event.get("last_clicked") if isinstance(map_event, dict) else None

if clicked_popup:
    st.session_state["last_ref"] = str(clicked_popup)
    st.session_state["drawer_open"] = True
elif clicked_map is not None:
    st.session_state["drawer_open"] = False

detail = None
if st.session_state["drawer_open"] and st.session_state.get("last_ref") and (COL_REF in filtered.columns):
    mask = filtered[COL_REF].astype(str) == st.session_state["last_ref"]
    if mask.any():
        detail = filtered[mask].iloc[0]
    else:
        st.session_state["drawer_open"] = False

drawer_class = "drawer" if (st.session_state["drawer_open"] and detail is not None) else "drawer hidden"
st.markdown(f"<div class='{drawer_class}'>", unsafe_allow_html=True)

if st.session_state["drawer_open"] and (detail is not None):
    ref_val = str(detail.get(COL_REF, "")).strip()
    if ref_val:
        st.markdown(f"<span class='ref-banner'>Référence annonce : {ref_val}</span>", unsafe_allow_html=True)
        st.write("")
    if COL_GMAP in filtered.columns:
        g = detail.get(COL_GMAP, "")
        if g and not empty(g):
            st.link_button("Ouvrir Google Maps", str(g).strip(), type="primary")
    st.write("")
    parts=[]
    for c in ["Rue","Code Postal","Ville"]:
        if c in filtered.columns and not empty(detail.get(c,None)):
            parts.append(str(detail[c]).strip())
    if parts:
        st.markdown(f"<div class='field'><b>Adresse</b> : {' — '.join(parts)}</div>", unsafe_allow_html=True)
    for c in [COL_EMPL, COL_TYPO, "Type"]:
        if c in filtered.columns and not empty(detail.get(c,None)):
            st.markdown(f"<div class='field'><b>{c}</b> : {detail[c]}</div>", unsafe_allow_html=True)
    if "Surface GLA" in filtered.columns and not empty(detail.get("Surface GLA", None)):
        st.markdown(f"<div class='field'><b>Surface GLA</b> : {detail['Surface GLA']}</div>", unsafe_allow_html=True)
    if "Répartition surface GLA" in filtered.columns and not empty(detail.get("Répartition surface GLA", None)):
        st.markdown(f"<div class='field'><b>Répartition Surface GLA</b> : {detail['Répartition surface GLA']}</div>", unsafe_allow_html=True)
    if "Surface Utile" in filtered.columns and not empty(detail.get("Surface Utile", None)):
        st.markdown(f"<div class='field'><b>Surface Utile</b> : {detail['Surface Utile']}</div>", unsafe_allow_html=True)
    if "Répartition surface utile" in filtered.columns and not empty(detail.get("Répartition surface utile", None)):
        st.markdown(f"<div class='field'><b>Répartition Surface Utile</b> : {detail['Répartition surface utile']}</div>", unsafe_allow_html=True)
    if COL_DAB in filtered.columns and not empty(detail.get(COL_DAB, None)):
        st.markdown(f"<div class='field'><b>Cession / Droit au bail</b> : {detail[COL_DAB]}</div>", unsafe_allow_html=True)
    if COL_LOYER in filtered.columns and not empty(detail.get(COL_LOYER, None)):
        s = str(detail[COL_LOYER])
        st.markdown(f"<div class='field'><b>Loyer annuel</b> : {{'Selon surface' if 'selon surface' in s.lower() else s}}</div>", unsafe_allow_html=True)
    if COL_EXT in filtered.columns and not empty(detail.get(COL_EXT, None)):
        st.markdown(f"<div class='field'><b>Extraction</b> : {detail[COL_EXT]}</div>", unsafe_allow_html=True)
    for c in [COL_DEPT, COL_REGION]:
        if c in filtered.columns and not empty(detail.get(c, None)):
            st.markdown(f"<div class='field'><b>{c}</b> : {detail[c]}</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

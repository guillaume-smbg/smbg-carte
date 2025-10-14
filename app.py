import os, re, math
from typing import Optional, Tuple, List, Dict

import pandas as pd
import numpy as np
import streamlit as st
from PIL import Image
from streamlit_folium import st_folium
import folium

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="SMBG Carte — Sélection d’annonces", layout="wide")

COPPER = "#B87333"

LOGO_PATHS = [
    "logo bleu crop.png", "Logo bleu crop.png",
    "assets/logo bleu crop.png", "assets/Logo bleu crop.png",
    "images/logo bleu crop.png", "static/logo bleu crop.png",
]
def first_existing(paths): 
    for p in paths:
        if os.path.exists(p): return p
    return None

def hex_from_rgb(rgb) -> str:
    r,g,b = [int(x) for x in rgb]
    return "#{:02X}{:02X}{:02X}".format(r,g,b)

def logo_blue(path: str) -> str:
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

LOGO = first_existing(LOGO_PATHS)
BLUE = logo_blue(LOGO) if LOGO else "#0A2942"

# =========================
# CSS (plein écran, pas de scroll, sidebar fixe, bouton retract masqué, tiroir droit)
# =========================
st.markdown(f"""
<style>
  html, body, .stApp {{ height: 100%; margin: 0; overflow: hidden; }}
  .block-container {{
    max-width: 1700px;
    padding: 4px 300px 4px 4px; /* réserve 300px à droite pour le tiroir */
    height: 100vh;             /* occupe toute la hauteur */
    box-sizing: border-box;
  }}

  /* Sidebar fixée et toujours visible */
  [data-testid="stSidebar"] {{
    background: {BLUE};
    width: 275px !important; min-width: 275px !important;
    padding: 6px 10px 8px 10px !important;
  }}
  /* Masque tous les contrôles de rétraction/chevrons */
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapseButton"],
  button[kind="header"] {{ display:none !important; }}

  /* Logo compact et centré */
  .smbg-logo {{ display:flex; justify-content:center; margin:0 0 8px 0; }}
  [data-testid="stSidebar"] img {{
    width: 38% !important; max-width: 110px !important; height:auto !important; margin: 2px auto 0 auto !important;
  }}

  /* Titres et labels cuivre */
  .smbg-title, .smbg-counter {{ color:{COPPER} !important; }}
  [data-testid="stSidebar"] label p, [data-testid="stSidebar"] .stMarkdown p {{
    color:{COPPER} !important; margin:0 0 4px 0 !important; font-size:13px !important;
  }}
  .smbg-indent {{ margin-left:16px; }}
  .two-col {{ display:grid; grid-template-columns:repeat(2,1fr); gap:2px 8px; }}
  .nested-scroll {{ max-height:180px; overflow-y:auto; padding-right:4px; }}

  /* Carte: on force la hauteur réelle de l'iframe folium (selon versions) */
  iframe[title^="st_folium"], iframe[title="st_folium"] {{
    height: calc(100vh - 8px) !important;  /* sans scroll */
    width: 100% !important;
    border: 0;
  }}

  /* Tiroir droit */
  .drawer {{
    position: fixed; top:0; right:0; width:275px; height:100vh;
    padding:14px; background:#fff; box-shadow:-6px 0 16px rgba(0,0,0,.12);
    overflow-y:auto; z-index: 9999;
  }}
  .drawer.hidden {{ display:none; }}

  .ref-banner {{
    background:{BLUE}; color:#fff; padding:8px 12px; border-radius:10px; display:inline-block; font-weight:600;
  }}
  .field {{ margin-bottom:6px; }}
  .field b {{ color:#333; }}
</style>
""", unsafe_allow_html=True)

# =========================
# UTILS
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
    s = str(v).strip().lower()
    if any(k in s for k in ["oui","faisable","possible","ok"]): return "OUI"
    if "non" in s: return "NON"
    return "NR"

def dab_yes(v) -> Optional[bool]:
    if empty(v): return None
    s = str(v).strip().lower()
    if s in {"néant","neant","0","0€","0 €"}: return False
    f = to_float(s)
    if f is not None and f>0: return True
    return True

def geo_float(x)->Optional[float]:
    if pd.isna(x): return None
    s = str(x).strip()
    if s in ("","","/","-","—"): return None
    s = s.replace(",", ".")
    try: return float(s)
    except: return None

# =========================
# DATA
# =========================
@st.cache_data(show_spinner=False)
def load_excel()->pd.DataFrame:
    for p in ["annonces.xlsx","data/annonces.xlsx"]:
        if os.path.exists(p): return pd.read_excel(p)
    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL","")).strip()
    if url: return pd.read_excel(url)
    st.error("Aucun Excel trouvé. Place ‘annonces.xlsx’ ou définis EXCEL_URL.")
    return pd.DataFrame()

df = load_excel()
if df.empty: st.stop()

# Colonnes (V2)
COL_REGION="Région"; COL_DEPT="Département"; COL_EMPLACEMENT="Emplacement"; COL_TYPO="Typologie"
COL_DAB="Cession / Droit au bail"; COL_NB_LOTS="Nombre de lots"
COL_GLA="Surface GLA"; COL_REP_GLA="Répartition surface GLA"; COL_UTILE="Surface Utile"; COL_REP_UT="Répartition surface utile"
COL_LOYER="Loyer annuel"; COL_EXT="Extraction"; COL_GMAP="Lien Google Maps"
COL_REF="Référence annonce"; COL_LAT="Latitude"; COL_LON="Longitude"; COL_ACTIF="Actif"

if COL_ACTIF in df.columns:
    df = df[df[COL_ACTIF].apply(truthy_yes)].copy()

# =========================
# STATE
# =========================
st.session_state.setdefault("checked_refs", set())
st.session_state.setdefault("last_ref", None)
st.session_state.setdefault("drawer_open", False)

# =========================
# SIDEBAR (on garde simple pendant qu’on fixe carte/tiroir)
# =========================
with st.sidebar:
    st.markdown("<div class='smbg-logo'>", unsafe_allow_html=True)
    if LOGO: st.image(LOGO)
    else: st.markdown("<p style='text-align:center;color:white;font-weight:600;'>SMBG CONSEIL</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = df.copy()

    # Région → Départements imbriqués
    st.markdown("<div class='smbg-title'><b>Région</b></div>", unsafe_allow_html=True)
    reg2deps: Dict[str, List[str]] = {}
    if {COL_REGION, COL_DEPT}.issubset(df.columns):
        for r,d in df[[COL_REGION, COL_DEPT]].dropna().drop_duplicates().itertuples(index=False):
            reg2deps.setdefault(str(r), set()).add(str(d))
        reg2deps = {k: sorted(list(v)) for k,v in reg2deps.items()}
    for ridx, reg in enumerate(sorted(reg2deps.keys())):
        if st.checkbox(reg, key=f"reg_{ridx}"):
            filtered = filtered[filtered[COL_REGION].astype(str)==reg]
            st.markdown("<div class='smbg-indent two-col'>", unsafe_allow_html=True)
            deps = reg2deps[reg]
            sel_deps=[]
            for i,dep in enumerate(deps):
                if st.checkbox(dep, key=f"dep_{ridx}_{i}"):
                    sel_deps.append(dep)
            if sel_deps:
                filtered = filtered[filtered[COL_DEPT].astype(str).isin(sel_deps)]
            st.markdown("</div>", unsafe_allow_html=True)

    # Emplacement
    if COL_EMPLACEMENT in df.columns:
        st.markdown("<div class='smbg-title'><b>Emplacement</b></div>", unsafe_allow_html=True)
        vals = sorted([str(x) for x in df[COL_EMPLACEMENT].dropna().unique()])
        st.markdown("<div class='smbg-indent two-col'>", unsafe_allow_html=True)
        picked=[]
        for i,v in enumerate(vals):
            if st.checkbox(v, key=f"emp_{i}"): picked.append(v)
        st.markdown("</div>", unsafe_allow_html=True)
        if picked: filtered = filtered[filtered[COL_EMPLACEMENT].astype(str).isin(picked)]

    # Typologie
    if COL_TYPO in df.columns:
        st.markdown("<div class='smbg-title'><b>Typologie</b></div>", unsafe_allow_html=True)
        vals = sorted([str(x) for x in df[COL_TYPO].dropna().unique()])
        st.markdown("<div class='smbg-indent two-col'>", unsafe_allow_html=True)
        picked=[]
        for i,v in enumerate(vals):
            if st.checkbox(v, key=f"typ_{i}"): picked.append(v)
        st.markdown("</div>", unsafe_allow_html=True)
        if picked: filtered = filtered[filtered[COL_TYPO].astype(str).isin(picked)]

    # DAB (affiché seulement si au moins une valeur)
    show_dab = COL_DAB in df.columns and (~df[COL_DAB].apply(empty)).any()
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
    if mins and maxs and min(mins) < max(maxs):
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

    st.markdown(f"<div class='smbg-counter'>{len(filtered)} annonces visibles</div>", unsafe_allow_html=True)

# =========================
# CARTE (plein écran, sans scroll) + VOLET DROIT RÉTRACTILE
# =========================

# Données géo
df_geo = filtered.copy()
if {COL_LAT, COL_LON}.issubset(df_geo.columns):
    df_geo["_lat"] = df_geo[COL_LAT].apply(geo_float)
    df_geo["_lon"] = df_geo[COL_LON].apply(geo_float)
    df_geo = df_geo.dropna(subset=["_lat","_lon"])
else:
    df_geo = df_geo.iloc[0:0]

# Centre
center = [df_geo["_lat"].mean(), df_geo["_lon"].mean()] if not df_geo.empty else [46.6, 2.5]

m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")

bounds=[]
for _,row in df_geo.iterrows():
    ref = str(row.get(COL_REF, ""))
    lat, lon = float(row["_lat"]), float(row["_lon"])
    folium.Marker([lat,lon], tooltip=ref, popup=folium.Popup(ref, max_width=260)).add_to(m)
    bounds.append([lat,lon])
if bounds: folium.FitBounds(bounds).add_to(m)

# Affiche la carte – taille réellement forcée par CSS (100vh)
evt = st_folium(m, key="map", use_container_width=True, height=800)

# Récupère clic pin (compat 2 formats) + clic fond de carte
clicked_popup = None
if isinstance(evt, dict):
    if evt.get("last_object_clicked_popup"):
        clicked_popup = evt["last_object_clicked_popup"]
    elif evt.get("last_object_clicked") and isinstance(evt["last_object_clicked"], dict):
        clicked_popup = evt["last_object_clicked"].get("popup")
clicked_map = evt.get("last_clicked") if isinstance(evt, dict) else None

# Logique tiroir
if clicked_popup:
    st.session_state["last_ref"] = str(clicked_popup)
    st.session_state["drawer_open"] = True
elif clicked_map is not None:
    st.session_state["drawer_open"] = False

# Sélection ligne
detail = None
if st.session_state["drawer_open"] and COL_REF in filtered.columns and st.session_state.get("last_ref"):
    msk = filtered[COL_REF].astype(str) == st.session_state["last_ref"]
    if msk.any(): detail = filtered[msk].iloc[0]
    else: st.session_state["drawer_open"] = False

# Drawer
drawer_class = "drawer" if (st.session_state["drawer_open"] and detail is not None) else "drawer hidden"
st.markdown(f"<div class='{drawer_class}'>", unsafe_allow_html=True)

if st.session_state["drawer_open"] and detail is not None:
    # Référence
    ref = str(detail.get(COL_REF, ""))
    if ref: st.markdown(f"<span class='ref-banner'>Référence annonce : {ref}</span>", unsafe_allow_html=True); st.write("")

    # Google Maps
    g = detail.get(COL_GMAP, "")
    if g and not empty(g):
        st.link_button("Ouvrir Google Maps", str(g).strip(), type="primary")
    st.write("")

    # Adresse
    addr=[]
    for c in ["Rue","Code Postal","Ville"]:
        if c in filtered.columns and not empty(detail.get(c,None)): addr.append(str(detail[c]))
    if addr: st.markdown(f"<div class='field'><b>Adresse</b> : {' — '.join(addr)}</div>", unsafe_allow_html=True)

    # Emplacement / Typologie / Type
    for c in [COL_EMPLACEMENT, COL_TYPO, "Type"]:
        if c in filtered.columns and not empty(detail.get(c,None)):
            st.markdown(f"<div class='field'><b>{c}</b> : {detail[c]}</div>", unsafe_allow_html=True)

    # Surfaces & répartitions (info)
    if not empty(detail.get(COL_GLA,None)):
        st.markdown(f"<div class='field'><b>Surface GLA</b> : {detail[COL_GLA]}</div>", unsafe_allow_html=True)
    if not empty(detail.get(COL_REP_GLA,None)):
        st.markdown(f"<div class='field'><b>Répartition Surface GLA</b> : {detail[COL_REP_GLA]}</div>", unsafe_allow_html=True)
    if not empty(detail.get(COL_UTILE,None)):
        st.markdown(f"<div class='field'><b>Surface Utile</b> : {detail[COL_UTILE]}</div>", unsafe_allow_html=True)
    if not empty(detail.get(COL_REP_UT,None)):
        st.markdown(f"<div class='field'><b>Répartition Surface Utile</b> : {detail[COL_REP_UT]}</div>", unsafe_allow_html=True)

    # DAB
    if COL_DAB in filtered.columns and not empty(detail.get(COL_DAB,None)):
        st.markdown(f"<div class='field'><b>Cession / Droit au bail</b> : {detail[COL_DAB]}</div>", unsafe_allow_html=True)

    # Loyer
    if COL_LOYER in filtered.columns:
        ly = detail.get(COL_LOYER, None)
        if not empty(ly):
            s = str(ly)
            st.markdown(f"<div class='field'><b>Loyer annuel</b> : {{'Selon surface' if 'selon surface' in s.lower() else s}}</div>", unsafe_allow_html=True)

    # Extraction
    if COL_EXT in filtered.columns and not empty(detail.get(COL_EXT,None)):
        st.markdown(f"<div class='field'><b>Extraction</b> : {detail[COL_EXT]}</div>", unsafe_allow_html=True)

    # Région / Département
    for c in [COL_DEPT, COL_REGION]:
        if c in filtered.columns and not empty(detail.get(c,None)):
            st.markdown(f"<div class='field'><b>{c}</b> : {detail[c]}</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# Petit compteur debug (géocodage) en bas de page
st.caption(f"Annonces géocodées sur carte : {len(df_geo)} / {len(filtered)}")

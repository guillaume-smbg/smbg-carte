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
COPPER = "#B87333"  # orangé cuivré

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
# CSS — volets 275px, logo, cuivré, nested Region→Dept
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

  /* Logo : centré, taille maîtrisée, collé haut */
  .smbg-logo-wrap {{
    display:flex; justify-content:center; align-items:flex-start;
    margin: 0 0 8px 0;
  }}
  [data-testid="stSidebar"] img {{
    width: 38% !important;
    max-width: 110px !important;
    height: auto !important;
    margin: 2px auto 0 auto !important;
    display:block;
  }}

  /* Titres & labels cuivrés */
  .smbg-title, .smbg-actions-title, .smbg-counter {{ color: {COPPER} !important; }}
  [data-testid="stSidebar"] label p,
  [data-testid="stSidebar"] .stMarkdown p {{
    color: {COPPER} !important;
    margin: 0 0 4px 0 !important;
    font-size: 13px !important;
  }}

  /* Indentation hiérarchique */
  .smbg-indent {{ margin-left: 16px; }}

  /* Mini-scroll regroupant Région→Départements imbriqués */
  .nested-scroll {{
    max-height: 180px;
    overflow-y: auto;
    padding-right: 4px;
  }}

  /* Grille 2 colonnes pour départements */
  .dept-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 2px 8px;
    margin: 2px 0 8px 0;
  }}

  /* Inputs compacts */
  [data-testid="stSidebar"] input[type="text"] {{
    padding: 6px 8px !important;
    font-size: 13px !important;
    min-height: 32px !important;
  }}
  [data-testid="stSidebar"] button {{
    padding: 4px 8px !important;
    min-height: 32px !important;
    line-height: 1.2 !important;
    font-size: 13px !important;
  }}

  /* Conteneur principal + volet droit 275px */
  .block-container {{ max-width: 1600px; padding-top: .5rem; }}
  .details-panel {{ width: 275px; min-width: 275px; }}
  .ref-banner {{
    background:{BLUE_SMBG}; color:white; padding:8px 12px; border-radius:10px; display:inline-block;
    font-weight:600; letter-spacing:.2px;
  }}
  .field {{ margin-bottom: 6px; }}
  .field b {{ color:#333; }}
</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS (parsing & filtres)
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
# COLUMN MAP (V2 mise à jour)
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
# STATE
# =========================
st.session_state.setdefault("selection", set())
st.session_state.setdefault("checked_refs", set())

# =========================
# SIDEBAR (volet gauche)
# =========================
with st.sidebar:
    # --- Logo
    st.markdown("<div class='smbg-logo-wrap'>", unsafe_allow_html=True)
    if LOGO_PATH:
        st.image(LOGO_PATH)
    else:
        st.markdown("<p style='text-align:center;color:white;font-weight:600;'>SMBG CONSEIL</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = df.copy()

    # ===== Région → Départements imbriqués (dans un mini-scroll) =====
    st.markdown("<div class='smbg-title'><b>Région</b></div>", unsafe_allow_html=True)

    # Prépare le mapping Région -> [Départements]
    reg2deps: Dict[str, List[str]] = {}
    if COL_REGION in df.columns and COL_DEPT in df.columns:
        for r, d in df[[COL_REGION, COL_DEPT]].dropna().drop_duplicates().itertuples(index=False):
            reg2deps.setdefault(str(r), set()).add(str(d))
        # cast sets to sorted lists
        reg2deps = {k: sorted(list(v)) for k, v in reg2deps.items()}
    regions_sorted = sorted(reg2deps.keys())

    # Conteneur scrollable
    st.markdown("<div class='nested-scroll'>", unsafe_allow_html=True)

    selected_regions: List[str] = []
    selected_deps: List[str] = []

    for ridx, reg in enumerate(regions_sorted):
        r_key = f"reg_{ridx}"
        r_checked = st.checkbox(reg, key=r_key)
        if r_checked:
            selected_regions.append(reg)
            # Afficher les départements de cette région (indentés, grille 2 colonnes)
            st.markdown("<div class='smbg-indent'>", unsafe_allow_html=True)
            # on coupe la liste en 2 colonnes
            deps = reg2deps.get(reg, [])
            col1, col2 = st.columns(2)
            for i, dep in enumerate(deps):
                d_key = f"dep_{ridx}_{i}"
                with (col1 if i % 2 == 0 else col2):
                    if st.checkbox(dep, key=d_key):
                        selected_deps.append(dep)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)  # /nested-scroll

    # Application des filtres Région / Départements
    if selected_regions:
        filtered = filtered[filtered[COL_REGION].astype(str).isin(selected_regions)]
        if selected_deps:
            filtered = filtered[filtered[COL_DEPT].astype(str).isin(selected_deps)]
        # sinon, aucun dép coché → on garde tous les deps des régions cochées (déjà fait)

    # ===== Emplacement =====
    if COL_EMPLACEMENT in df.columns:
        st.markdown("<div class='smbg-title'><b>Emplacement</b></div>", unsafe_allow_html=True)
        vals = sorted([str(x) for x in df[COL_EMPLACEMENT].dropna().unique()])
        # grille compacte 2 colonnes
        st.markdown("<div class='smbg-indent'>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        sel_vals = []
        for i, opt in enumerate(vals):
            with (c1 if i % 2 == 0 else c2):
                if st.checkbox(opt, key=f"emp_{i}"): sel_vals.append(opt)
        st.markdown("</div>", unsafe_allow_html=True)
        if sel_vals:
            filtered = filtered[filtered[COL_EMPLACEMENT].astype(str).isin(sel_vals)]

    # ===== Typologie =====
    if COL_TYPOLOGIE in df.columns:
        st.markdown("<div class='smbg-title'><b>Typologie</b></div>", unsafe_allow_html=True)
        vals = sorted([str(x) for x in df[COL_TYPOLOGIE].dropna().unique()])
        st.markdown("<div class='smbg-indent'>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        sel_vals = []
        for i, opt in enumerate(vals):
            with (c1 if i % 2 == 0 else c2):
                if st.checkbox(opt, key=f"typ_{i}"): sel_vals.append(opt)
        st.markdown("</div>", unsafe_allow_html=True)
        if sel_vals:
            filtered = filtered[filtered[COL_TYPOLOGIE].astype(str).isin(sel_vals)]

    # ===== Cession / Droit au bail (visible si au moins une valeur non vide) =====
    show_dab = False
    if COL_DAB in df.columns:
        show_dab = bool((~df[COL_DAB].apply(is_empty_cell)).any())
    if show_dab:
        st.markdown("<div class='smbg-title'><b>Cession / Droit au bail</b></div>", unsafe_allow_html=True)
        choice = st.radio(" ", ["Oui", "Non", "Les deux"], horizontal=True, label_visibility="collapsed", key="dab_radio")
        if choice != "Les deux":
            flags = df[COL_DAB].apply(lambda v: True if dab_is_yes(v) is True else False)
            mask = flags if choice == "Oui" else ~flags
            filtered = filtered[mask.reindex(filtered.index).fillna(True)]

    # ===== Surface GLA (slider recouvrement N + O) =====
    st.markdown("<div class='smbg-title'><b>Surface GLA (m²)</b></div>", unsafe_allow_html=True)
    mins, maxs = [], []
    for _, row in df.iterrows():
        rmin, rmax = row_surface_interval(row, COL_GLA, COL_REP_GLA)
        if rmin is not None: mins.append(rmin)
        if rmax is not None: maxs.append(rmax)
    if mins and maxs and min(mins) < max(maxs):
        smin_glob = int(math.floor(min(mins))); smax_glob = int(math.ceil(max(maxs)))
        ssel = st.slider(" ", min_value=smin_glob, max_value=smax_glob, value=(smin_glob, smax_glob),
                         label_visibility="collapsed", key="sl_gla")
        keep_idx = []
        for idx, row in filtered.iterrows():
            rmin, rmax = row_surface_interval(row, COL_GLA, COL_REP_GLA)
            if rmin is None and rmax is None:
                keep_idx.append(idx)
            else:
                if (rmax >= ssel[0]) and (rmin <= ssel[1]): keep_idx.append(idx)
        filtered = filtered.loc[keep_idx]

    # ===== Loyer annuel (slider numérique, "selon surface" non exclu) =====
    if COL_LOYER_ANNUEL in df.columns:
        st.markdown("<div class='smbg-title'><b>Loyer annuel (€)</b></div>", unsafe_allow_html=True)
        vals = [to_float_clean(x) for x in df[COL_LOYER_ANNUEL].tolist()]
        nums = [v for v in vals if v is not None]
        if nums and min(nums) < max(nums):
            lmin = int(math.floor(min(nums))); lmax = int(math.ceil(max(nums)))
            lsel = st.slider("  ", min_value=lmin, max_value=lmax, value=(lmin, lmax),
                             label_visibility="collapsed", key="sl_loy")
            mask_num = filtered[COL_LOYER_ANNUEL].apply(to_float_clean)
            keep = (mask_num.isna()) | ((mask_num >= lsel[0]) & (mask_num <= lsel[1]))
            filtered = filtered[keep]

    # ===== Extraction =====
    if COL_EXTRACTION in df.columns:
        st.markdown("<div class='smbg-title'><b>Extraction</b></div>", unsafe_allow_html=True)
        ext_choice = st.radio("  ", ["Oui", "Non", "Les deux"], horizontal=True, label_visibility="collapsed", key="ext_radio")
        if ext_choice != "Les deux":
            norm = df[COL_EXTRACTION].apply(normalize_extraction)
            mask = norm.eq("OUI") if ext_choice == "Oui" else norm.eq("NON")
            filtered = filtered[mask.reindex(filtered.index).fillna(ext_choice == "Oui")]

    # ===== Liste d'annonces (recherche + (dé)cocher tout) =====
    st.markdown("<div class='smbg-title'><b>Annonces (cocher / décocher)</b></div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1,1])
    with c1:
        if st.button("Tout cocher"):
            if COL_REF in filtered.columns:
                st.session_state["checked_refs"] = set([str(x) for x in filtered[COL_REF].fillna("").tolist()])
            else:
                st.session_state["checked_refs"] = set([f"Annonce {i}" for i in filtered.index])
    with c2:
        if st.button("Tout décocher"): st.session_state["checked_refs"] = set()

    q = st.text_input("Filtrer la liste…", "", label_visibility="collapsed", placeholder="Rechercher une référence…")
    refs = [str(x) for x in (filtered[COL_REF] if COL_REF in filtered.columns else pd.Series([f"Annonce {i}" for i in filtered.index]))]
    checked = st.session_state.get("checked_refs", set())

    st.markdown("<div class='smbg-indent'>", unsafe_allow_html=True)
    st.markdown("<div class='nested-scroll'>", unsafe_allow_html=True)
    for i, r in enumerate(refs):
        if q and q.lower() not in r.lower(): continue
        key = f"chk_ref_{i}"
        val = (r in checked)
        new = st.checkbox(r, value=val, key=key)
        if new and (r not in checked): checked.add(r)
        if (not new) and (r in checked): checked.discard(r)
    st.session_state["checked_refs"] = checked
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ===== Actions (bas du volet) =====
    st.markdown("<div class='smbg-actions-title'><b>Actions</b></div>", unsafe_allow_html=True)
    a1, a2 = st.columns(2)
    with a1:
        if st.button("🔄 Réinitialiser"):
            for k in list(st.session_state.keys()):
                if k.startswith(("reg_", "dep_", "emp_", "typ_", "dab_", "sl_", "ext_", "chk_ref_")):
                    del st.session_state[k]
            st.session_state["checked_refs"] = set()
            st.rerun()
    with a2:
        st.button("🗺️ Partager la carte")

    b1, b2 = st.columns(2)
    with b1:
        st.button("📧 Envoyer sélection")
    with b2:
        st.button("🌐 Partager tout")

    st.markdown(f"<div class='smbg-counter'> {len(filtered)} annonces visibles</div>", unsafe_allow_html=True)

# =========================
# CENTRE : Carte + Volet droit
# =========================
left, right = st.columns([1, 0.0001], gap="large")

with left:
    df_map = filtered.dropna(subset=[COL_LAT, COL_LON]).copy() if {COL_LAT, COL_LON}.issubset(filtered.columns) else filtered.iloc[0:0].copy()
    center = [df_map[COL_LAT].astype(float).mean(), df_map[COL_LON].astype(float).mean()] if not df_map.empty else [46.6, 2.5]
    m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")
    for idx, row in df_map.iterrows():
        ref_txt = str(row.get(COL_REF, f"Annonce {idx}"))
        folium.Marker([float(row[COL_LAT]), float(row[COL_LON])], tooltip=ref_txt, popup=ref_txt).add_to(m)
    st_folium(m, height=680, width=None)

with right:
    st.markdown("<div class='details-panel'>", unsafe_allow_html=True)
    show_details = st.toggle("Afficher le volet de détails", value=True)
    if show_details and not filtered.empty:
        row = filtered.iloc[0]
        ref_val = str(row.get(COL_REF, ""))
        if ref_val: st.markdown(f"<span class='ref-banner'>Référence annonce : {ref_val}</span>", unsafe_allow_html=True)
        st.write("")
        gm = row.get(COL_GOOGLE, "")
        if gm and not is_empty_cell(gm): st.link_button("Ouvrir Google Maps", str(gm).strip(), type="primary")
        st.write("")
        adresse_parts = []
        for col in ["Rue", "Code Postal", "Ville"]:
            if col in filtered.columns and not is_empty_cell(row.get(col, None)): adresse_parts.append(str(row[col]))
        if adresse_parts: st.markdown(f"<div class='field'><b>Adresse</b> : {' — '.join(adresse_parts)}</div>", unsafe_allow_html=True)
        for col in [COL_EMPLACEMENT, COL_TYPOLOGIE, "Type"]:
            if col in filtered.columns and not is_empty_cell(row.get(col, None)):
                st.markdown(f"<div class='field'><b>{col}</b> : {row[col]}</div>", unsafe_allow_html=True)
        gla_val = row.get(COL_GLA, None)
        if not is_empty_cell(gla_val): st.markdown(f"<div class='field'><b>Surface GLA</b> : {gla_val}</div>", unsafe_allow_html=True)
        rep_gla = row.get(COL_REP_GLA, None)
        if not is_empty_cell(rep_gla): st.markdown(f"<div class='field'><b>Répartition Surface GLA</b> : {rep_gla}</div>", unsafe_allow_html=True)
        utile_val = row.get(COL_UTILE, None)
        if not is_empty_cell(utile_val): st.markdown(f"<div class='field'><b>Surface Utile</b> : {utile_val}</div>", unsafe_allow_html=True)
        rep_utile = row.get(COL_REP_UTILE, None)
        if not is_empty_cell(rep_utile): st.markdown(f"<div class='field'><b>Répartition Surface Utile</b> : {rep_utile}</div>", unsafe_allow_html=True)
        if COL_DAB in filtered.columns and not is_empty_cell(row.get(COL_DAB, None)):
            st.markdown(f"<div class='field'><b>Cession / Droit au bail</b> : {row[COL_DAB]}</div>", unsafe_allow_html=True)
        if COL_LOYER_ANNUEL in filtered.columns:
            ly = row.get(COL_LOYER_ANNUEL, None)
            if not is_empty_cell(ly):
                s = str(ly)
                st.markdown(f"<div class='field'><b>Loyer annuel</b> : {'Selon surface' if 'selon surface' in s.lower() else s}</div>", unsafe_allow_html=True)
        if COL_EXTRACTION in filtered.columns and not is_empty_cell(row.get(COL_EXTRACTION, None)):
            st.markdown(f"<div class='field'><b>Extraction</b> : {row[COL_EXTRACTION]}</div>", unsafe_allow_html=True)
        for col in [COL_DEPT, COL_REGION]:
            if col in filtered.columns and not is_empty_cell(row.get(col, None)):
                st.markdown(f"<div class='field'><b>{col}</b> : {row[col]}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

import os, re, math
from typing import Optional, Tuple, List

import pandas as pd
import numpy as np
import streamlit as st
from PIL import Image

from streamlit_folium import st_folium
import folium

# =========================
# CONFIG (couleurs via logo) + THEME
# =========================
COPPER = "#B87333"  # orangé cuivré du logo

LOGO_PATH_CANDIDATES = [
    "logo bleu crop.png", "Logo bleu crop.png",
    "assets/logo bleu crop.png", "assets/Logo bleu crop.png",
    "images/logo bleu crop.png", "static/logo bleu crop.png",
]

st.set_page_config(page_title="SMBG Carte — Sélection d’annonces", layout="wide")

def get_first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def hex_from_rgb(rgb) -> str:
    r, g, b = [int(x) for x in rgb]
    return "#{:02X}{:02X}{:02X}".format(r, g, b)

def get_dominant_color(path: str) -> str:
    """Couleur exacte du logo (dominante robuste, médiane)."""
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
# CSS (volets 300px, logo 50% plus petit, texte cuivre)
# =========================
st.markdown(f"""
<style>
  /* Sidebar (volet gauche) : largeur fixe 300px, fond = bleu du logo */
  [data-testid="stSidebar"] {{
    background: {BLUE_SMBG};
    width: 300px !important;
    min-width: 300px !important;
    padding: 8px 10px 12px 10px !important;
  }}
  /* petite marge top pour l'esthétique */
  [data-testid="stSidebar"]::before {{
    content: "";
    display:block;
    height: 6px;
  }}
  /* bouton de repli masqué (volet non rétractable) */
  [data-testid="collapsedControl"] {{ display:none !important; }}

  /* Logo : centré, 50% plus petit que précédemment, collé en haut avec petite marge */
  .smbg-logo-wrap {{
    display:flex; justify-content:center; align-items:flex-start;
    margin-top: 4px; margin-bottom: 8px;
  }}
  .smbg-logo-wrap img {{
    width: 45% !important;  /* ~50% plus petit que le plein */
    max-width: 140px;       /* borne haute raisonnable */
    height: auto;
  }}

  /* Titres & labels dans le volet gauche : texte cuivre */
  .smbg-filter-title, .smbg-filter-label, .smbg-actions-title, .smbg-counter {{
    color: {COPPER} !important;
  }}
  /* case à cocher compacte */
  .smbg-checkbox-grid label p, .smbg-checkbox-item label p {{
    margin: 0 0 2px 0 !important;
    color: #F8F8F8 !important;
  }}
  /* indentation hiérarchique des groupes */
  .smbg-indent {{ margin-left: 8px; }}
  .smbg-subindent {{ margin-left: 16px; }}

  /* Grilles compactes (Région/Departement) : colonnes multiples + scroll court */
  .smbg-chip-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px 8px;
    max-height: 160px;
    overflow-y: auto;
    padding: 2px 2px 6px 2px;
    background: rgba(255,255,255,0.06);
    border-radius: 8px;
  }}
  .smbg-chip {{
    display:flex; align-items:center;
  }}
  .smbg-chip label p {{
    font-size: 13px !important;
  }}

  /* Liste des annonces à cocher/décocher (ultra compacte) */
  .smbg-list-scroller {{
    max-height: 180px;
    overflow-y: auto;
    background: rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 6px;
  }}
  .smbg-list-item label p {{
    margin: 0 0 2px 0 !important;
    color: #F8F8F8 !important;
    font-size: 13px !important;
  }}

  /* Conteneur principal plus large */
  .block-container {{ max-width: 1600px; padding-top: 0.5rem; }}

  /* Volet droit (détails) 300px */
  .details-panel {{
    width: 300px; min-width: 300px;
  }}
  .ref-banner {{
    background:{BLUE_SMBG}; color:white; padding:8px 12px; border-radius:10px; display:inline-block;
    font-weight:600; letter-spacing:.2px;
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

def checkbox_grid(label: str, options: List[str], key_prefix: str, columns: int = 3) -> List[str]:
    """Grille compacte de cases à cocher (sans dropdown)."""
    st.markdown(f"<div class='smbg-filter-title'><b>{label}</b></div>", unsafe_allow_html=True)
    selected = []
    st.markdown("<div class='smbg-indent smbg-chip-grid'>", unsafe_allow_html=True)
    # On dessine en flux (Streamlit), grid est décor purement CSS
    for i, opt in enumerate(options):
        checked = st.checkbox(opt, key=f"{key_prefix}_{i}")
        if checked: selected.append(opt)
    st.markdown("</div>", unsafe_allow_html=True)
    return selected

# =========================
# DATA LOADING
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

# =========================
# SIDEBAR (volet gauche) : Logo + Filtres + Liste à cocher + Actions
# =========================
with st.sidebar:
    # Logo plus petit & collé en haut
    st.markdown("<div class='smbg-logo-wrap'>", unsafe_allow_html=True)
    if LOGO_PATH:
        st.image(LOGO_PATH)
    else:
        st.markdown("<p style='text-align:center;color:white;font-weight:600;'>SMBG CONSEIL</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Filtres dans l'ordre demandé
    filtered = df.copy()

    # 1) Région (cases à cocher, compact)
    if COL_REGION in df.columns:
        regions = sorted([str(x) for x in df[COL_REGION].dropna().unique()])
        sel_regions = checkbox_grid("Région", regions, "reg", columns=3)
        if sel_regions:
            filtered = filtered[filtered[COL_REGION].astype(str).isin(sel_regions)]

    # 2) Département (lié à Région)
    if COL_DEPT in df.columns:
        base = filtered if (COL_REGION in df.columns and sel_regions) else df
        depts = sorted([str(x) for x in base[COL_DEPT].dropna().unique()])
        sel_depts = checkbox_grid("Département", depts, "dep", columns=3)
        if sel_depts:
            filtered = filtered[filtered[COL_DEPT].astype(str).isin(sel_depts)]

    # 3) Emplacement
    if COL_EMPLACEMENT in df.columns:
        emps = sorted([str(x) for x in df[COL_EMPLACEMENT].dropna().unique()])
        sel_emps = checkbox_grid("Emplacement", emps, "emp", columns=3)
        if sel_emps:
            filtered = filtered[filtered[COL_EMPLACEMENT].astype(str).isin(sel_emps)]

    # 4) Typologie
    if COL_TYPOLOGIE in df.columns:
        typs = sorted([str(x) for x in df[COL_TYPOLOGIE].dropna().unique()])
        sel_typs = checkbox_grid("Typologie", typs, "typ", columns=3)
        if sel_typs:
            filtered = filtered[filtered[COL_TYPOLOGIE].astype(str).isin(sel_typs)]

    # 5) Cession / Droit au bail : n'apparaît que si au moins une valeur non vide dans toute la colonne
    show_dab_filter = False
    if COL_DAB in df.columns:
        non_empty_mask = ~df[COL_DAB].apply(is_empty_cell)
        show_dab_filter = bool(non_empty_mask.any())

    if show_dab_filter:
        st.markdown(f"<div class='smbg-filter-title'><b>Cession / Droit au bail</b></div>", unsafe_allow_html=True)
        dab_choice = st.radio(" ", ["Oui", "Non", "Les deux"], horizontal=True, label_visibility="collapsed", key="dab_radio")
        if dab_choice != "Les deux":
            dab_flags = df[COL_DAB].apply(dab_is_yes)  # True/False/None
            if dab_choice == "Oui":
                mask = dab_flags.eq(True)
            else:
                mask = dab_flags.ne(True)  # Non = False ou None
            filtered = filtered[mask.reindex(filtered.index).fillna(True)]
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # 6) Surface GLA (slider par recouvrement d'intervalle sur N + O)
    st.markdown(f"<div class='smbg-filter-title'><b>Surface GLA (m²)</b></div>", unsafe_allow_html=True)
    mins, maxs = [], []
    for _, row in df.iterrows():
        rmin, rmax = row_surface_interval(row, COL_GLA, COL_REP_GLA)
        if rmin is not None: mins.append(rmin)
        if rmax is not None: maxs.append(rmax)
    if mins and maxs and min(mins) < max(maxs):
        smin_glob = int(math.floor(min(mins))); smax_glob = int(math.ceil(max(maxs)))
        ssel = st.slider(" ", min_value=smin_glob, max_value=smax_glob, value=(smin_glob, smax_glob),
                         label_visibility="collapsed", key="sl_gla")
        # filtre recouvrement
        keep_idx = []
        for idx, row in filtered.iterrows():
            rmin, rmax = row_surface_interval(row, COL_GLA, COL_REP_GLA)
            if rmin is None and rmax is None:
                keep_idx.append(idx)
            else:
                if (rmax >= ssel[0]) and (rmin <= ssel[1]):
                    keep_idx.append(idx)
        filtered = filtered.loc[keep_idx]
    else:
        st.caption("*(Pas assez de valeurs exploitables — filtre inactif)*")

    # 7) Loyer annuel (slider numérique — “selon surface” non exclu)
    if COL_LOYER_ANNUEL in df.columns:
        st.markdown(f"<div class='smbg-filter-title'><b>Loyer annuel (€)</b></div>", unsafe_allow_html=True)
        vals = [to_float_clean(x) for x in df[COL_LOYER_ANNUEL].tolist()]
        nums = [v for v in vals if v is not None]
        if nums and min(nums) < max(nums):
            lmin = int(math.floor(min(nums))); lmax = int(math.ceil(max(nums)))
            lsel = st.slider("  ", min_value=lmin, max_value=lmax, value=(lmin, lmax),
                             label_visibility="collapsed", key="sl_loy")
            mask_num = filtered[COL_LOYER_ANNUEL].apply(to_float_clean)
            keep = (mask_num.isna()) | ((mask_num >= lsel[0]) & (mask_num <= lsel[1]))
            filtered = filtered[keep]
        else:
            st.caption("*(Pas assez de valeurs exploitables — filtre inactif)*")

    # 8) Extraction (Oui / Non / Les deux)
    if COL_EXTRACTION in df.columns:
        st.markdown(f"<div class='smbg-filter-title'><b>Extraction</b></div>", unsafe_allow_html=True)
        ext_choice = st.radio("  ", ["Oui", "Non", "Les deux"], horizontal=True, label_visibility="collapsed", key="ext_radio")
        if ext_choice != "Les deux":
            norm = df[COL_EXTRACTION].apply(normalize_extraction)
            if ext_choice == "Oui":
                mask = norm.eq("OUI")
            else:
                mask = norm.eq("NON")
            filtered = filtered[mask.reindex(filtered.index).fillna(ext_choice=="Oui")]

    # --- Liste d'annonces à cocher/décocher (compacte)
    st.markdown(f"<div class='smbg-filter-title'><b>Annonces (cocher / décocher)</b></div>", unsafe_allow_html=True)
    # Options = références (ou fallback ligne)
    refs = []
    if COL_REF in df.columns:
        refs = [str(x) for x in filtered[COL_REF].fillna("").tolist()]
    else:
        refs = [f"Annonce {i}" for i in filtered.index]

    # mini barre d'actions de la liste
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        if st.button("Tout cocher"):
            st.session_state.setdefault("checked_refs", set())
            st.session_state["checked_refs"] = set(refs)
    with c2:
        if st.button("Tout décocher"):
            st.session_state["checked_refs"] = set()
    with c3:
        q = st.text_input("Rechercher", "", label_visibility="collapsed", placeholder="Filtrer la liste...")

    # scroll + checkboxes ultra compacts
    checked = st.session_state.get("checked_refs", set())
    st.markdown("<div class='smbg-list-scroller'>", unsafe_allow_html=True)
    for i, r in enumerate(refs):
        if q and q.lower() not in r.lower():
            continue
        key = f"chk_ref_{i}"
        val = (r in checked)
        new = st.checkbox(r, value=val, key=key)
        if new and (r not in checked):
            checked.add(r)
        if (not new) and (r in checked):
            checked.discard(r)
    st.session_state["checked_refs"] = checked
    st.markdown("</div>", unsafe_allow_html=True)

    # Boutons d'actions (en bas du volet)
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
        st.button("🗺️ Partager la carte")  # génération d’URL filtrée à brancher si besoin

    b1, b2 = st.columns(2)
    with b1:
        st.button("📧 Envoyer sélection")  # mailto prérempli à brancher plus tard
    with b2:
        st.button("🌐 Partager tout")

    st.markdown(f"<div class='smbg-counter'> {len(filtered)} annonces visibles</div>", unsafe_allow_html=True)

# =========================
# COLONNES CENTRALES : Carte + Volet droit (300px, rétractable)
# =========================
left, right = st.columns([1, 0.0001], gap="large")

with left:
    # Carte
    if COL_LAT in filtered.columns and COL_LON in filtered.columns:
        df_map = filtered.dropna(subset=[COL_LAT, COL_LON]).copy()
    else:
        df_map = filtered.iloc[0:0].copy()

    if not df_map.empty:
        center = [df_map[COL_LAT].astype(float).mean(), df_map[COL_LON].astype(float).mean()]
    else:
        center = [46.6, 2.5]  # France

    m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")

    for idx, row in df_map.iterrows():
        ref_txt = str(row.get(COL_REF, f"Annonce {idx}"))
        folium.Marker(
            location=[float(row[COL_LAT]), float(row[COL_LON])],
            tooltip=ref_txt,
            popup=ref_txt
        ).add_to(m)

    st_folium(m, height=680, width=None)

with right:
    st.markdown("<div class='details-panel'>", unsafe_allow_html=True)
    show_details = st.toggle("Afficher le volet de détails", value=True)
    if show_details and not filtered.empty:
        row = filtered.iloc[0]

        # Référence
        ref_val = str(row.get(COL_REF, ""))
        if ref_val:
            st.markdown(f"<span class='ref-banner'>Référence annonce : {ref_val}</span>", unsafe_allow_html=True)
            st.write("")

        # Bouton Google Maps (libellé demandé)
        gm = row.get(COL_GOOGLE, "")
        if gm and not is_empty_cell(gm):
            st.link_button("Ouvrir Google Maps", str(gm).strip(), type="primary")

        st.write("")

        # Adresse (si présentes)
        adresse_parts = []
        for col in ["Rue", "Code Postal", "Ville"]:
            if col in filtered.columns and not is_empty_cell(row.get(col, None)):
                adresse_parts.append(str(row[col]))
        if adresse_parts:
            st.markdown(f"<div class='field'><b>Adresse</b> : {' — '.join(adresse_parts)}</div>", unsafe_allow_html=True)

        # Emplacement / Typologie / Type
        for col in [COL_EMPLACEMENT, COL_TYPOLOGIE, "Type"]:
            if col in filtered.columns and not is_empty_cell(row.get(col, None)):
                st.markdown(f"<div class='field'><b>{col}</b> : {row[col]}</div>", unsafe_allow_html=True)

        # Surfaces (GLA & Utile) + Répartitions (infos only)
        gla_val = row.get(COL_GLA, None)
        if not is_empty_cell(gla_val):
            st.markdown(f"<div class='field'><b>Surface GLA</b> : {gla_val}</div>", unsafe_allow_html=True)
        rep_gla = row.get(COL_REP_GLA, None)
        if not is_empty_cell(rep_gla):
            st.markdown(f"<div class='field'><b>Répartition Surface GLA</b> : {rep_gla}</div>", unsafe_allow_html=True)

        utile_val = row.get(COL_UTILE, None)
        if not is_empty_cell(utile_val):
            st.markdown(f"<div class='field'><b>Surface Utile</b> : {utile_val}</div>", unsafe_allow_html=True)
        rep_utile = row.get(COL_REP_UTILE, None)
        if not is_empty_cell(rep_utile):
            st.markdown(f"<div class='field'><b>Répartition Surface Utile</b> : {rep_utile}</div>", unsafe_allow_html=True)

        # Cession / DAB (affichage simple si présent)
        if COL_DAB in filtered.columns and not is_empty_cell(row.get(COL_DAB, None)):
            st.markdown(f"<div class='field'><b>Cession / Droit au bail</b> : {row[COL_DAB]}</div>", unsafe_allow_html=True)

        # Loyer annuel : numérique ou “Selon surface”
        if COL_LOYER_ANNUEL in filtered.columns:
            ly = row.get(COL_LOYER_ANNUEL, None)
            if not is_empty_cell(ly):
                s = str(ly)
                if "selon surface" in s.lower():
                    st.markdown(f"<div class='field'><b>Loyer annuel</b> : Selon surface</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='field'><b>Loyer annuel</b> : {s}</div>", unsafe_allow_html=True)

        # Extraction
        if COL_EXTRACTION in filtered.columns and not is_empty_cell(row.get(COL_EXTRACTION, None)):
            st.markdown(f"<div class='field'><b>Extraction</b> : {row[COL_EXTRACTION]}</div>", unsafe_allow_html=True)

        # Région / Département
        for col in [COL_DEPT, COL_REGION]:
            if col in filtered.columns and not is_empty_cell(row.get(col, None)):
                st.markdown(f"<div class='field'><b>{col}</b> : {row[col]}</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

import os, re, math
from typing import Optional, Tuple, List

import pandas as pd
import numpy as np
import streamlit as st

from streamlit_folium import st_folium
import folium

# =========================
# CONFIG & THEME
# =========================
BLUE_SMBG = "#0A2942"     # Bleu validé (figé)
COPPER    = "#B87333"     # Accent
LOGO_PATH_CANDIDATES = [
    "logo bleu crop.png", "Logo bleu crop.png",
    "assets/logo bleu crop.png", "assets/Logo bleu crop.png",
    "images/logo bleu crop.png", "static/logo bleu crop.png",
]

st.set_page_config(page_title="SMBG Carte — Sélection d’annonces", layout="wide")

# CSS global: volets fixés à 300px, logo centré, légère marge top
st.markdown(f"""
<style>
  /* Volet gauche (sidebar Streamlit) */
  [data-testid="stSidebar"] {{
    background: {BLUE_SMBG};
    width: 300px !important;
    min-width: 300px !important;
    padding-top: 12px !important;  /* légère marque top */
  }}
  [data-testid="stSidebar"] .stMarkdown p {{ margin: 0; }}
  [data-testid="stSidebar"] img {{
    display:block; margin: 0 auto 12px auto; max-width: 90%;
  }}
  /* cacher le bouton de repli de la sidebar */
  [data-testid="collapsedControl"] {{ display:none !important; }}

  /* Contenu principal largeur étendue */
  .block-container {{ max-width: 1600px; padding-top: 0.75rem; }}

  /* Colonne droite "volet de détails" à 300px */
  .details-panel {{
    width: 300px;
    min-width: 300px;
  }}
  /* Bannières et champs */
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
def get_first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def truthy_yes(x) -> bool:
    return str(x).strip().lower() in {"oui","yes","true","1","y"}

def is_empty_cell(v) -> bool:
    if pd.isna(v): return True
    s = str(v).strip()
    return s == "" or s in {"/", "-", "—"}

def to_float_clean(x) -> Optional[float]:
    """Retourne un float si possible (retire € espaces etc.), sinon None."""
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
    """
    Extrait (min,max) depuis du texte type "de 30 à 200 m²" / "30-200" / "30 à 200".
    Retourne (None,None) si rien d'exploitable.
    """
    if pd.isna(text): return (None, None)
    s = str(text).lower()
    nums = re.findall(r"[\d]+(?:[.,]\d+)?", s)
    if not nums:
        # peut-être que c'est une valeur simple numérique
        v = to_float_clean(s)
        return (v, v) if v is not None else (None, None)
    vals = []
    for n in nums:
        n = n.replace(",", ".")
        try:
            vals.append(float(n))
        except:
            pass
    if not vals:
        return (None, None)
    if len(vals) == 1:
        return (vals[0], vals[0])
    return (min(vals), max(vals))

def row_surface_interval(row, col_gla: Optional[str], col_rep_gla: Optional[str], col_nb_lots: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """
    Retourne (min,max) de surface GLA pour une ligne en tenant compte :
    - Surface GLA (N) si numérique
    - Répartition Surface GLA (O) si fourchette "de 30 à 200"
    - Nombre de lots (M) > 1 => on garde la fourchette la plus large trouvée
    """
    mins, maxs = [], []
    # Surface GLA brute
    if col_gla and col_gla in row.index:
        v = to_float_clean(row[col_gla])
        if v is not None:
            mins.append(v); maxs.append(v)
    # Répartition GLA
    if col_rep_gla and col_rep_gla in row.index and not is_empty_cell(row[col_rep_gla]):
        rmin, rmax = parse_surface_range(row[col_rep_gla])
        if rmin is not None: mins.append(rmin)
        if rmax is not None: maxs.append(rmax)
    if mins and maxs:
        return (min(mins), max(maxs))
    return (None, None)

def build_checkbox_group(label: str, options: List[str], key_prefix: str) -> List[str]:
    """Affiche une liste de cases à cocher (pas de menu déroulant) et retourne la liste sélectionnée."""
    st.markdown(f"**{label}**")
    selected = []
    for i, opt in enumerate(options):
        checked = st.checkbox(opt, key=f"{key_prefix}_{i}")
        if checked:
            selected.append(opt)
    st.markdown("<hr>", unsafe_allow_html=True)
    return selected

def normalize_extraction(value: str) -> str:
    """Oui / Non / Faisable → Oui compte comme capacité; 'faisable' => Oui."""
    if is_empty_cell(value): return "NR"
    s = str(value).strip().lower()
    if any(k in s for k in ["oui", "faisable", "possible", "ok"]):
        return "OUI"
    if "non" in s:
        return "NON"
    return "NR"

def dab_is_yes(value) -> Optional[bool]:
    """Pour Cession/DAB: True=Oui, False=Non, None=Non renseigné."""
    if is_empty_cell(value): return None
    s = str(value).strip().lower()
    if s in {"néant", "neant", "0", "0€", "0 €"}:
        return False
    f = to_float_clean(s)
    if f is not None and f > 0:
        return True
    # texte non 'néant' mais renseigné => on considère "Oui"
    return True

# =========================
# DATA LOADING
# =========================
@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    # 1) local  2) secrets.EXCEL_URL  3) env.EXCEL_URL
    for p in ["annonces.xlsx", "data/annonces.xlsx"]:
        if os.path.exists(p):
            return pd.read_excel(p)
    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    if url:
        return pd.read_excel(url)
    st.error("Aucun Excel trouvé. Place ‘annonces.xlsx’ à la racine (ou data/) ou définis EXCEL_URL.")
    return pd.DataFrame()

df = load_excel()
if df.empty:
    st.stop()

# =========================
# COLUMN MAP (selon ta V2 mise à jour)
# =========================
COL_REGION        = "Région"
COL_DEPT          = "Département"
COL_EMPLACEMENT   = "Emplacement"
COL_TYPOLOGIE     = "Typologie"
COL_DAB           = "Cession / Droit au bail"
COL_NB_LOTS       = "Nombre de lots"          # (M)
COL_GLA           = "Surface GLA"              # (N)
COL_REP_GLA       = "Répartition surface GLA"  # (O)
COL_UTILE         = "Surface Utile"            # (P)
COL_REP_UTILE     = "Répartition surface utile"# (Q)
COL_LOYER_ANNUEL  = "Loyer annuel"             # (R)
COL_EXTRACTION    = "Extraction"
COL_GOOGLE        = "Lien Google Maps"
COL_REF           = "Référence annonce"
COL_LAT           = "Latitude"
COL_LON           = "Longitude"
COL_ACTIF         = "Actif"

# Filtre Actif = oui
if COL_ACTIF in df.columns:
    df = df[df[COL_ACTIF].apply(truthy_yes)].copy()

# =========================
# SIDEBAR (volet gauche) : logo + filtres + actions
# =========================
with st.sidebar:
    # Logo
    logo = get_first_existing(LOGO_PATH_CANDIDATES)
    if logo:
        st.image(logo, use_container_width=True)
    else:
        st.markdown("<p style='text-align:center;color:white;font-weight:600;'>SMBG CONSEIL</p>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ---- Filtres (ordre imposé) ----
    filtered = df.copy()

    # Régions (cases à cocher)
    if COL_REGION in df.columns:
        regions = sorted([str(x) for x in filtered[COL_REGION].dropna().unique()])
        sel_regions = build_checkbox_group("Région", regions, "reg")
        if sel_regions:
            filtered = filtered[filtered[COL_REGION].astype(str).isin(sel_regions)]

    # Départements (dépend des régions)
    if COL_DEPT in df.columns:
        depts_source = filtered if sel_regions else df
        depts = sorted([str(x) for x in depts_source[COL_DEPT].dropna().unique()])
        sel_depts = build_checkbox_group("Département", depts, "dep")
        if sel_depts:
            filtered = filtered[filtered[COL_DEPT].astype(str).isin(sel_depts)]

    # Emplacement (indépendant)
    if COL_EMPLACEMENT in df.columns:
        emps = sorted([str(x) for x in df[COL_EMPLACEMENT].dropna().unique()])
        sel_emps = build_checkbox_group("Emplacement", emps, "emp")
        if sel_emps:
            filtered = filtered[filtered[COL_EMPLACEMENT].astype(str).isin(sel_emps)]

    # Typologie (indépendant)
    if COL_TYPOLOGIE in df.columns:
        typs = sorted([str(x) for x in df[COL_TYPOLOGIE].dropna().unique()])
        sel_typs = build_checkbox_group("Typologie", typs, "typ")
        if sel_typs:
            filtered = filtered[filtered[COL_TYPOLOGIE].astype(str).isin(sel_typs)]

    # Cession / Droit au bail (n'afficher le filtre que si la colonne contient au moins une valeur non vide)
    show_dab_filter = False
    if COL_DAB in df.columns:
        non_empty_mask = ~df[COL_DAB].apply(is_empty_cell)
        show_dab_filter = bool(non_empty_mask.any())

    dab_choice = "Les deux"
    if show_dab_filter:
        st.markdown("**Cession / Droit au bail**")
        dab_choice = st.radio(" ", ["Oui", "Non", "Les deux"], horizontal=True, label_visibility="collapsed", key="dab_radio")
        st.markdown("<hr>", unsafe_allow_html=True)
        if dab_choice != "Les deux":
            dab_flags = df[COL_DAB].apply(dab_is_yes)
            if dab_choice == "Oui":
                mask = dab_flags.eq(True)
            else:
                # "Non" => False OU None (non renseigné) considérés comme Non
                mask = dab_flags.ne(True)
            filtered = filtered[mask.reindex(filtered.index).fillna(True)]

    # Surface GLA (slider par recouvrement d'intervalle)
    st.markdown("**Surface GLA (m²)**")
    # calcul bornes globales
    mins, maxs = [], []
    for _, row in df.iterrows():
        rmin, rmax = row_surface_interval(row, COL_GLA, COL_REP_GLA, COL_NB_LOTS)
        if rmin is not None: mins.append(rmin)
        if rmax is not None: maxs.append(rmax)
    if mins and maxs and min(mins) < max(maxs):
        smin_glob = int(math.floor(min(mins)))
        smax_glob = int(math.ceil(max(maxs)))
        ssel = st.slider(" ", min_value=smin_glob, max_value=smax_glob, value=(smin_glob, smax_glob),
                         label_visibility="collapsed", key="sl_gla")
        st.markdown("<hr>", unsafe_allow_html=True)

        # filtre par recouvrement: (row_max >= sel_min) & (row_min <= sel_max)
        keep_idx = []
        for idx, row in filtered.iterrows():
            rmin, rmax = row_surface_interval(row, COL_GLA, COL_REP_GLA, COL_NB_LOTS)
            if rmin is None and rmax is None:
                keep_idx.append(idx)  # non renseigné: ne pas exclure
            else:
                if (rmax >= ssel[0]) and (rmin <= ssel[1]):
                    keep_idx.append(idx)
        filtered = filtered.loc[keep_idx]
    else:
        st.caption("*(Pas assez de valeurs numériques exploitables — filtre inactif)*")
        st.markdown("<hr>", unsafe_allow_html=True)

    # Loyer annuel (slider numérique — “selon surface” non exclus)
    if COL_LOYER_ANNUEL in df.columns:
        st.markdown("**Loyer annuel (€)**")
        vals = [to_float_clean(x) for x in df[COL_LOYER_ANNUEL].tolist()]
        nums = [v for v in vals if v is not None]
        if nums and min(nums) < max(nums):
            lmin = int(math.floor(min(nums)))
            lmax = int(math.ceil(max(nums)))
            lsel = st.slider("  ", min_value=lmin, max_value=lmax, value=(lmin, lmax),
                             label_visibility="collapsed", key="sl_loy")
            st.markdown("<hr>", unsafe_allow_html=True)
            # Appliquer uniquement aux lignes avec valeur numérique
            mask_num = filtered[COL_LOYER_ANNUEL].apply(to_float_clean)
            keep = (mask_num.isna()) | ((mask_num >= lsel[0]) & (mask_num <= lsel[1]))
            filtered = filtered[keep]
        else:
            st.caption("*(Pas assez de valeurs numériques exploitables — filtre inactif)*")
            st.markdown("<hr>", unsafe_allow_html=True)

    # Extraction (Oui / Non / Les deux)
    if COL_EXTRACTION in df.columns:
        st.markdown("**Extraction**")
        ext_choice = st.radio("  ", ["Oui", "Non", "Les deux"], horizontal=True, label_visibility="collapsed", key="ext_radio")
        st.markdown("<hr>", unsafe_allow_html=True)
        if ext_choice != "Les deux":
            norm = df[COL_EXTRACTION].apply(normalize_extraction)
            if ext_choice == "Oui":
                mask = norm.eq("OUI")
            else:
                mask = norm.eq("NON")
            filtered = filtered[mask.reindex(filtered.index).fillna(False if ext_choice=="Non" else True)]

    # Actions (en bas du volet)
    st.markdown("**Actions**")
    if st.button("🔄 Réinitialiser les filtres"):
        for k in list(st.session_state.keys()):
            if k.startswith(("reg_", "dep_", "emp_", "typ_", "dab_", "sl_", "ext_")):
                del st.session_state[k]
        st.rerun()

    st.caption(f"{len(filtered)} annonces visibles.")

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

    # Markers
    for idx, row in df_map.iterrows():
        ref_txt = str(row.get(COL_REF, f"Annonce {idx}"))
        folium.Marker(
            location=[float(row[COL_LAT]), float(row[COL_LON])],
            tooltip=ref_txt,
            popup=ref_txt
        ).add_to(m)

    st_folium(m, height=680, width=None)

# --- Volet droit (rétractable, 300px)
with right:
    st.markdown("<div class='details-panel'>", unsafe_allow_html=True)
    show_details = st.toggle("Afficher le volet de détails", value=True)
    if show_details:
        # Sélection par défaut: première ligne filtrée
        if not filtered.empty:
            row = filtered.iloc[0]
            # Référence
            ref_val = str(row.get(COL_REF, ""))
            if ref_val:
                st.markdown(f"<span class='ref-banner'>Référence annonce : {ref_val}</span>", unsafe_allow_html=True)
                st.write("")

            # Bouton Google Maps
            gm = row.get(COL_GOOGLE, "")
            if gm and not is_empty_cell(gm):
                st.link_button("Ouvrir Google Maps", str(gm).strip(), type="primary")

            st.write("")

            # Adresse
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

            # Surfaces
            # GLA + répartition (info)
            gla_val = row.get(COL_GLA, None)
            if not is_empty_cell(gla_val):
                st.markdown(f"<div class='field'><b>Surface GLA</b> : {gla_val}</div>", unsafe_allow_html=True)
            rep_gla = row.get(COL_REP_GLA, None)
            if not is_empty_cell(rep_gla):
                st.markdown(f"<div class='field'><b>Répartition Surface GLA</b> : {rep_gla}</div>", unsafe_allow_html=True)

            # Utile + répartition (info)
            utile_val = row.get(COL_UTILE, None)
            if not is_empty_cell(utile_val):
                st.markdown(f"<div class='field'><b>Surface Utile</b> : {utile_val}</div>", unsafe_allow_html=True)
            rep_utile = row.get(COL_REP_UTILE, None)
            if not is_empty_cell(rep_utile):
                st.markdown(f"<div class='field'><b>Répartition Surface Utile</b> : {rep_utile}</div>", unsafe_allow_html=True)

            # Cession / Droit au bail
            if COL_DAB in filtered.columns and not is_empty_cell(row.get(COL_DAB, None)):
                st.markdown(f"<div class='field'><b>Cession / Droit au bail</b> : {row[COL_DAB]}</div>", unsafe_allow_html=True)

            # Loyer annuel (montant ou "Selon surface")
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

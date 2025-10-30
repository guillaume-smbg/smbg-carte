import os
import io
import re
import math
import unicodedata
from typing import Optional, Dict, Tuple, List

import pandas as pd
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium


# -------------------------------------------------
# CONFIG DE BASE
# -------------------------------------------------

st.set_page_config(
    page_title="SMBG Carte",
    layout="wide",
)

LOGO_BLUE = "#05263d"
COPPER = "#b87333"
LEFT_PANEL_WIDTH_PX = 275
RIGHT_PANEL_WIDTH_PX = 275

DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"


# -------------------------------------------------
# CSS GLOBAL (FUTURA / BLEU / CUIVRE / PANNEAUX)
# -------------------------------------------------

GLOBAL_CSS = f"""
<style>
/* Police globale */
.stApp, .stMarkdown, .stButton, .stDataFrame, div, span, p, td, th, label {{
    font-family: 'Futura', sans-serif !important;
    color: #000;
}}

/* ====== PANNEAU GAUCHE (FILTRES) ====== */
.left-panel {{
    background-color: {LOGO_BLUE};
    color: #fff !important;
    padding: 16px;
    border-right: 1px solid rgba(255,255,255,0.15);
    border-radius: 12px;
    min-width: {LEFT_PANEL_WIDTH_PX}px;
    max-width: {LEFT_PANEL_WIDTH_PX}px;
    width: {LEFT_PANEL_WIDTH_PX}px;
    box-sizing: border-box;
}}
.left-panel * {{
    color: #fff !important;
    font-family: 'Futura', sans-serif !important;
    font-size: 13px;
    line-height: 1.4;
}}
.left-panel .group-title {{
    font-weight: 600;
    font-size: 14px;
    margin-top: 12px;
    margin-bottom: 6px;
    line-height: 1.3;
}}
.left-panel .copper-btn {{
    width: 100%;
    background-color: {COPPER};
    color: #fff !important;
    border: 0;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    padding: 8px 10px;
    text-align: center;
    cursor: pointer;
    line-height: 1.3;
    font-family: 'Futura', sans-serif;
    margin-bottom: 8px;
}}
.left-panel .copper-btn:hover {{
    filter: brightness(1.08);
}}

/* ====== CARTE (COLONNE CENTRALE) ====== */
.map-wrapper {{
    position: relative;
    background-color: #f5f5f5;
    border-radius: 12px;
    border: 1px solid #e0e0e0;
    overflow: hidden;
    height: 800px;
}}
.map-error {{
    font-family: 'Futura', sans-serif;
    font-size: 13px;
    color: #000;
    background:#fff3cd;
    border:1px solid #ffeeba;
    border-radius:6px;
    padding:12px;
    margin:16px;
}}

/* ====== PANNEAU DROIT (ANNONCE) ====== */
.right-panel-box {{
    background-color: #ffffff;
    color: #000;
    border-radius: 12px;
    border: 1px solid rgba(0,0,0,0.1);
    min-width: {RIGHT_PANEL_WIDTH_PX}px;
    max-width: {RIGHT_PANEL_WIDTH_PX}px;
    width: {RIGHT_PANEL_WIDTH_PX}px;
    box-sizing: border-box;
    padding: 0;
    display: flex;
    flex-direction: column;
    max-height: 800px;
    overflow: hidden; /* scroll interne uniquement dans le corps */
    font-family: 'Futura', sans-serif;
}}
.panel-banner {{
    background-color: {LOGO_BLUE};
    color: #fff;
    border-radius: 12px 12px 0 0;
    padding: 10px 12px;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.4;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
}}
.badge-nouveau {{
    display: inline-block;
    background-color: {COPPER};
    color: #fff !important;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    line-height: 1.2;
    white-space: nowrap;
}}
.panel-body {{
    padding: 12px;
    overflow-y: auto;
    flex: 1 1 auto;
    font-size: 13px;
    line-height: 1.4;
    color: #000;
}}
.addr-block {{
    font-size: 13px;
    line-height: 1.4;
    margin-bottom: 12px;
    color: #000;
}}
.addr-line1 {{
    font-weight: 600;
    color: #000;
}}
.addr-line2 {{
    color: #000;
}}
.gmaps-btn button {{
    background-color: {COPPER};
    color: #fff;
    border: 0;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    margin-bottom: 12px;
    font-family: 'Futura', sans-serif;
}}
.gmaps-btn button:hover {{
    filter: brightness(1.08);
}}

.panel-subtitle {{
    font-size: 13px;
    font-weight: 600;
    color: #000;
    margin-top: 8px;
    margin-bottom: 4px;
    font-family: 'Futura', sans-serif;
}}

/* ====== TABLEAU D'INFOS (COLONNES G → AD) ====== */
.detail-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    line-height: 1.4;
    font-family: 'Futura', sans-serif;
    margin-top: 8px;
}}
.detail-table tr td {{
    vertical-align: top;
    padding: 6px 8px;
    border-bottom: 1px solid #e0e0e0;
    color: #000;
    font-family: 'Futura', sans-serif;
    word-break: break-word;
}}
.detail-table tr td.label-col {{
    width: 40%;
    font-weight: 600;
    font-size: 12px;
    color: {LOGO_BLUE};
    font-family: 'Futura', sans-serif;
}}
.detail-table tr td.value-col {{
    width: 60%;
    font-weight: 400;
    font-size: 12px;
    color: #000;
    font-family: 'Futura', sans-serif;
}}
.placeholder-panel {{
    font-size: 13px;
    line-height: 1.4;
    color: #000;
    opacity: 0.7;
    background-color: #f8f8f8;
    border: 1px dashed #ccc;
    border-radius: 8px;
    padding: 12px;
    font-family: 'Futura', sans-serif;
}}
</style>
"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# -------------------------------------------------
# OUTILS GÉNÉRAUX
# -------------------------------------------------

def normalize_excel_url(url: str) -> str:
    """Transforme une URL GitHub /blob/ en /raw/ si besoin."""
    if not url:
        return url
    return re.sub(
        r"https://github\.com/(.+)/blob/([^ ]+)",
        r"https://github.com/\1/raw/\2",
        url.strip()
    )


@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    """
    Charge l'Excel depuis EXCEL_URL (secrets/env) ou depuis DEFAULT_LOCAL_PATH.
    """
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    excel_url = normalize_excel_url(excel_url)

    if excel_url:
        r = requests.get(excel_url, timeout=25)
        r.raise_for_status()
        return pd.read_excel(io.BytesIO(r.content))

    if os.path.exists(DEFAULT_LOCAL_PATH):
        return pd.read_excel(DEFAULT_LOCAL_PATH)

    st.error("Impossible de charger le fichier Excel.")
    st.stop()


def normalize_bool(val):
    """Convertit 'oui' / 'Oui ' / 1 / True en booléen True/False homogène."""
    if isinstance(val, str):
        return val.strip().lower() in ["oui", "yes", "true", "1", "vrai"]
    if isinstance(val, (int, float)):
        try:
            return int(val) == 1
        except Exception:
            return False
    if isinstance(val, bool):
        return val
    return False


def norm_txt(x: str) -> str:
    """Normalise texte pour filtres ('Centre-ville' => 'centre ville')."""
    if x is None:
        return ""
    s = str(x).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s)
    return s


def sanitize_value(v: object) -> str:
    """Affichage panneau droit : remplace -, /, ou vide par '' (donc on cache)."""
    if v is None:
        return ""
    s = str(v).strip()
    if s in ["", "-", "/"]:
        return ""
    return s


def to_number(value) -> Optional[float]:
    """
    Nettoie '1 200 m²', '36 000 €', etc. en float.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    s = (
        s.replace("€", "")
         .replace("euros", "")
         .replace("euro", "")
         .replace("m²", "")
         .replace("m2", "")
         .replace("mÂ²", "")
         .replace("\xa0", " ")
         .replace(" ", "")
         .replace(",", ".")
    )
    m = re.findall(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m[0])
    except Exception:
        return None


def clean_numeric_series(series: pd.Series) -> pd.Series:
    return series.map(to_number)


def clean_latlon_series(series: pd.Series) -> pd.Series:
    """Convertit latitude/longitude en float, support virgule."""
    return (
        series.astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False)
        .map(to_number)
    )


def find_col(df: pd.DataFrame, *candidates) -> str:
    """
    Tente de retrouver une colonne du df.
    Cherche correspondance exacte normalisée ou "tous les mots présents".
    """
    def _norm(x: str) -> str:
        if x is None:
            return ""
        y = str(x).strip().lower()
        y = unicodedata.normalize("NFKD", y).encode("ascii", "ignore").decode("ascii")
        y = re.sub(r"\s+", " ", y)
        return y

    norm_map = {c: _norm(c) for c in df.columns}
    for cand in candidates:
        cn = _norm(cand)
        # exact
        for c, n in norm_map.items():
            if n == cn:
                return c
        # fuzzy
        parts = cn.split()
        for c, n in norm_map.items():
            if all(part in n for part in parts):
                return c
    return ""


def is_recent(date_val, days=30) -> bool:
    """Badge 'Nouveau' si Date publication < X jours."""
    if pd.isna(date_val) or str(date_val).strip() == "":
        return False
    try:
        dt = pd.to_datetime(date_val, dayfirst=True, errors="coerce")
    except Exception:
        dt = pd.NaT
    if pd.isna(dt):
        return False
    now = pd.Timestamp.now(tz="Europe/Paris").normalize()
    delta = now - dt.normalize()
    return delta.days <= days


# -------------------------------------------------
# TABLEAU D'INFO (COLONNES G → AD)
# -------------------------------------------------

def build_listing_table(first_row: pd.Series, df_full: pd.DataFrame) -> str:
    """
    Construit le tableau HTML Champ / Valeur pour le panneau droit.
    Règle métier confirmée :
    - On prend les colonnes à partir de G jusqu'à AD inclus
      → concrètement : toutes les colonnes APRÈS la colonne "Lien Google Maps" (F),
        et AVANT les colonnes techniques type Latitude / Longitude / Actif / etc.
    - On garde l'ordre EXACT du fichier Excel.
    - On saute les valeurs vides / "-" / "/".
    """

    cols = list(df_full.columns)

    # repérer la colonne Google Maps (colonne F)
    col_gmaps_idx = None
    for idx, name in enumerate(cols):
        norm = name.strip().lower()
        if "google" in norm and "map" in norm:
            col_gmaps_idx = idx
            break

    if col_gmaps_idx is None:
        # fallback : on suppose F = index 5
        col_gmaps_idx = 5

    # localiser le début des colonnes techniques pour s'arrêter juste avant
    technical_starts = []
    for idx, name in enumerate(cols):
        n = name.strip().lower()
        if any(
            kw in n
            for kw in [
                "latitude", "longitude", "actif",
                "photo", "géocodage", "geocodage",
                "statut", "status",
                "date publication", "publication",
                "référence annonce", "reference annonce", "référence", "reference",
                "photos", "photo annonce", "photos annonce"
            ]
        ):
            technical_starts.append(idx)

    if technical_starts:
        end_idx = min(technical_starts) - 1
    else:
        end_idx = len(cols) - 1

    start_idx = col_gmaps_idx + 1  # => G théorique
    if start_idx < 0:
        start_idx = 0
    if end_idx < start_idx:
        end_idx = start_idx

    display_cols = cols[start_idx : end_idx + 1]

    rows_html = []
    for colname in display_cols:
        raw_val = sanitize_value(first_row.get(colname, ""))
        if raw_val == "":
            continue
        label = colname
        value = raw_val
        rows_html.append(
            f"<tr><td class='label-col'>{label}</td>"
            f"<td class='value-col'>{value}</td></tr>"
        )

    if not rows_html:
        return (
            "<div class='placeholder-panel'>"
            "Aucune information disponible pour cette annonce."
            "</div>"
        )

    return "<table class='detail-table'>" + "".join(rows_html) + "</table>"


# -------------------------------------------------
# GMAPS LINK (COLONNE F)
# -------------------------------------------------

def get_first_gmaps_link(row: pd.Series, gmaps_colname: str) -> Optional[str]:
    """Lien Google Maps : affiché comme bouton cuivre."""
    if not gmaps_colname:
        return None
    v = row.get(gmaps_colname, "")
    v_clean = str(v).strip()
    if v_clean and v_clean not in ["-", "/"]:
        return v_clean
    return None


# -------------------------------------------------
# ANTI-OVERLAP DES PINS
# -------------------------------------------------

def anti_overlap_positions(n: int, base_lat: float, base_lon: float) -> List[Tuple[float, float]]:
    """
    Quand plusieurs annonces partagent exactement la même coordonnée,
    on décale légèrement les points sur un cercle.
    """
    if n <= 1:
        return [(base_lat, base_lon)]
    r = 0.0006  # ~60 m
    out = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        out.append(
            (
                base_lat + r * math.sin(angle),
                base_lon + r * math.cos(angle),
            )
        )
    return out


# -------------------------------------------------
# PANNEAU DROIT
# -------------------------------------------------

def render_right_panel(
    selected_ref: Optional[str],
    df_full: pd.DataFrame,
    col_ref: str,
    col_addr_full: str,
    col_city: str,
    col_gmaps: str,
    col_date_pub: str,
):
    """
    Panneau droit fixe :
    - Bandeau bleu "Réf X" + badge "Nouveau"
    - Bouton cuivre "Cliquer ici" (Google Maps)
    - Adresse complète
    - Tableau colonnes G→AD
    """

    def normalize_ref_str(x: str) -> str:
        x = str(x).strip()
        if re.match(r"^\d+\.0+$", x):
            return x.split(".")[0]
        return x

    # rien sélectionné
    if not selected_ref:
        st.markdown('<div class="right-panel-box">', unsafe_allow_html=True)
        st.markdown(
            '<div class="panel-banner">Aucune sélection</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="panel-body"><div class="placeholder-panel">Sélectionnez une annonce sur la carte.</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # filtrer df_full sur la ref choisie
    mask = df_full[col_ref].astype(str).map(normalize_ref_str) == normalize_ref_str(selected_ref)
    sub = df_full[mask].copy()
    if sub.empty:
        st.markdown('<div class="right-panel-box">', unsafe_allow_html=True)
        st.markdown('<div class="panel-banner">Annonce introuvable</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="panel-body"><div class="placeholder-panel">Cliquez à nouveau sur la carte.</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    row = sub.iloc[0]

    # Référence propre (pas .0)
    ref_display = normalize_ref_str(row.get(col_ref, ""))

    # Badge "Nouveau"
    badge_html = ""
    if col_date_pub and col_date_pub in row and is_recent(row[col_date_pub]):
        badge_html = "<span class='badge-nouveau'>Nouveau</span>"

    # Lien GMaps
    gmaps_link = get_first_gmaps_link(row, col_gmaps)

    # Adresse
    adresse_full = sanitize_value(row.get(col_addr_full, "")) if col_addr_full else ""
    ville_txt = sanitize_value(row.get(col_city, "")) if col_city else ""

    # Tableau colonnes G→AD
    table_html = build_listing_table(row, df_full)

    # Rendu
    st.markdown('<div class="right-panel-box">', unsafe_allow_html=True)

    st.markdown(
        f'<div class="panel-banner">Réf. {ref_display}<div>{badge_html}</div></div>',
        unsafe_allow_html=True
    )

    st.markdown('<div class="panel-body">', unsafe_allow_html=True)

    if gmaps_link:
        st.markdown(
            f'<div class="gmaps-btn"><a href="{gmaps_link}" target="_blank" rel="noopener noreferrer"><button>Cliquer ici</button></a></div>',
            unsafe_allow_html=True
        )

    addr_html = "<div class='addr-block'>"
    if adresse_full:
        addr_html += f"<div class='addr-line1'>{adresse_full}</div>"
    if ville_txt:
        addr_html += f"<div class='addr-line2'>{ville_txt}</div>"
    addr_html += "</div>"
    st.markdown(addr_html, unsafe_allow_html=True)

    st.markdown("<div class='panel-subtitle'>Informations</div>", unsafe_allow_html=True)
    st.markdown(table_html, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # panel-body
    st.markdown('</div>', unsafe_allow_html=True)  # right-panel-box


# -------------------------------------------------
# MAIN
# -------------------------------------------------

def main():
    # ====== 1. CHARGER L'EXCEL ======
    df = load_excel()
    if df is None or df.empty:
        st.warning("Excel vide ou introuvable.")
        st.stop()

    # ====== 2. DÉTECTER LES COLONNES CLÉS ======
    col_lat        = find_col(df, "Latitude")
    col_lon        = find_col(df, "Longitude")
    col_actif      = find_col(df, "Actif")

    col_typo       = find_col(df, "Typologie", "Typologie d'actif")
    col_empl       = find_col(df, "Emplacement")
    col_extr       = find_col(df, "Extraction")

    col_loyer_ann  = find_col(df, "Loyer annuel", "Loyer annuel (€)", "Loyer annuel (euros)")
    col_surface    = find_col(df, "Surface GLA", "Surface totale", "Surface totale (m²)", "Surface")

    col_region     = find_col(df, "Région")
    col_dept       = find_col(df, "Département")

    col_ref        = find_col(df, "Référence annonce", "Reference annonce", "Référence", "Reference")
    col_gmaps      = find_col(df, "Lien Google Maps", "Google Maps", "Maps")
    col_addr_full  = find_col(df, "Adresse complète", "Adresse", "Adresse complète (affichage)")
    col_city       = find_col(df, "Ville")
    col_date_pub   = find_col(df, "Date publication", "Publication", "Date de publication")

    if not col_ref:
        st.error("Colonne 'Référence annonce' introuvable.")
        st.stop()

    # ====== 3. CRÉER LES COLONNES INTERNES ======
    # Actif -> bool
    if col_actif:
        df["_actif"] = df[col_actif].apply(normalize_bool)
    else:
        # Pas de colonne 'Actif' => tout est actif
        df["_actif"] = True

    # Latitude / Longitude nettoyées
    if col_lat:
        df["_lat"] = clean_latlon_series(df[col_lat])
    else:
        df["_lat"] = None

    if col_lon:
        df["_lon"] = clean_latlon_series(df[col_lon])
    else:
        df["_lon"] = None

    # Si TOUTES les lignes sont considérées inactives après normalisation,
    # on les force actives pour ne pas tout couper.
    if not df["_actif"].any():
        df["_actif"] = True

    # colonnes normalisées pour filtres textuels
    df["_typologie_n"] = df[col_typo].astype(str).map(norm_txt) if col_typo else ""
    df["_empl_n"]      = df[col_empl].astype(str).map(norm_txt) if col_empl else ""
    df["_extr_n"]      = df[col_extr].astype(str).map(norm_txt) if col_extr else ""

    # ====== 4. df_map = uniquement les lignes avec coord valides & actives
    df_map = df[
        df["_actif"]
        & df["_lat"].notna()
        & df["_lon"].notna()
    ].copy()

    # IMPORTANT : si df_map est vide, on ne stoppe PAS.
    # On affichera juste un message dans la map.

    # ====== 5. PRÉPA SLIDERS (surface / loyer)
    surf_global = clean_numeric_series(df[col_surface]).dropna() if col_surface else pd.Series([], dtype=float)
    loyer_global = clean_numeric_series(df[col_loyer_ann]).dropna() if col_loyer_ann else pd.Series([], dtype=float)

    smin, smax = (int(surf_global.min()), int(surf_global.max())) if not surf_global.empty else (None, None)
    lmin, lmax = (int(loyer_global.min()), int(loyer_global.max())) if not loyer_global.empty else (None, None)

    # ====== 6. LAYOUT 3 COLONNES STREAMLIT ======
    col_left, col_map_st, col_right = st.columns([1, 4, 1], gap="small")

    # ----- GAUCHE : PANNEAU FILTRES BLEU -----
    with col_left:
        st.markdown('<div class="left-panel">', unsafe_allow_html=True)

        working_df = df.copy()

        # Région / Département hiérarchique
        if col_region and col_dept:
            st.markdown('<div class="group-title">Région / Département</div>', unsafe_allow_html=True)

            regions = sorted([
                r for r in working_df[col_region].dropna().astype(str).unique()
                if r not in ["-", "/"]
            ])

            selected_regions = []
            selected_deps = []

            for reg in regions:
                if st.checkbox(reg, key=f"reg_{reg}"):
                    selected_regions.append(reg)

                    deps = sorted([
                        d for d in working_df[
                            working_df[col_region].astype(str) == reg
                        ][col_dept].dropna().astype(str).unique()
                        if d not in ["-", "/"]
                    ])

                    # indent pour les départements
                    for dep in deps:
                        pad_col, dep_col = st.columns([1, 10])
                        with pad_col:
                            st.write("")  # juste indentation visuelle
                        with dep_col:
                            if st.checkbox(dep, key=f"dep_{reg}_{dep}"):
                                selected_deps.append(dep)

            # filtrage post choix région/dépt
            if selected_regions:
                working_df = working_df[
                    working_df[col_region].astype(str).isin(selected_regions)
                ]
            if selected_deps:
                working_df = working_df[
                    working_df[col_dept].astype(str).isin(selected_deps)
                ]

        # Typologie
        if col_typo:
            st.markdown('<div class="group-title">Typologie d\'actif</div>', unsafe_allow_html=True)
            typos_raw = sorted([
                t for t in working_df[col_typo].dropna().astype(str).unique()
                if t not in ["-", "/", ""]
            ])
            sel_typos_norm = []
            for t in typos_raw:
                if st.checkbox(t, key=f"typo_{t}"):
                    sel_typos_norm.append(norm_txt(t))
            if sel_typos_norm:
                working_df = working_df[
                    working_df[col_typo].astype(str).map(norm_txt).isin(sel_typos_norm)
                ]

        # Extraction
        if col_extr:
            st.markdown('<div class="group-title">Extraction</div>', unsafe_allow_html=True)
            extr_opts = ["oui", "non", "faisable"]
            sel_extr = []
            for e in extr_opts:
                if st.checkbox(e, key=f"extr_{e}"):
                    sel_extr.append(norm_txt(e))
            if sel_extr:
                working_df = working_df[
                    working_df[col_extr].astype(str).map(norm_txt).isin(sel_extr)
                ]

        # Emplacement
        if col_empl:
            st.markdown('<div class="group-title">Emplacement</div>', unsafe_allow_html=True)
            vals = [
                e for e in working_df[col_empl].dropna().astype(str).unique()
                if e not in ["-", "/", ""]
            ]
            base_order = ["Centre-ville", "Périphérie"]
            ordered = [e for e in base_order if e in vals] + [e for e in vals if e not in base_order]

            sel_empl = []
            for e in ordered:
                if st.checkbox(e, key=f"empl_{e}"):
                    sel_empl.append(norm_txt(e))

            if sel_empl:
                working_df = working_df[
                    working_df[col_empl].astype(str).map(norm_txt).isin(sel_empl)
                ]

        # Sliders surface
        if smin is not None and smax is not None:
            if "surf_range" not in st.session_state:
                st.session_state["surf_range"] = (smin, smax)
            st.session_state["surf_range"] = st.slider(
                "Surface (m²)",
                min_value=smin,
                max_value=smax,
                value=st.session_state["surf_range"],
                step=1,
                key="surf_slider",
            )

        # Sliders loyer annuel
        if lmin is not None and lmax is not None:
            if "loyer_range" not in st.session_state:
                st.session_state["loyer_range"] = (lmin, lmax)
            st.session_state["loyer_range"] = st.slider(
                "Loyer annuel (€)",
                min_value=lmin,
                max_value=lmax,
                value=st.session_state["loyer_range"],
                step=1000,
                key="loyer_slider",
            )

        # Boutons action
        c1, c2 = st.columns(2)
        with c1:
            st.button("Réinitialiser les filtres", key="reset_dummy")  # TODO: impl reset
        with c2:
            st.button("Je suis intéressé", key="interest_btn")

        # Appliquer les sliders à working_df
        if "surf_range" in st.session_state and col_surface:
            rmin, rmax = st.session_state["surf_range"]
            working_df = working_df[
                working_df[col_surface].map(to_number).apply(
                    lambda v: True if v is None else (rmin <= v <= rmax)
                )
            ]

        if "loyer_range" in st.session_state and col_loyer_ann:
            rmin, rmax = st.session_state["loyer_range"]
            working_df = working_df[
                working_df[col_loyer_ann].map(to_number).apply(
                    lambda v: True if v is None else (rmin <= v <= rmax)
                )
            ]

        # On ne touche pas encore la session selected_ref ici
        filtered_df = working_df.copy()

        st.markdown('</div>', unsafe_allow_html=True)  # end left-panel

    # ====== CONSTRUCTION DES PINS À PARTIR DE filtered_df ======
    # On doit prendre seulement les lignes qui ont coord valides (df_map),
    # ET qui sont encore présentes après les filtres.
    merged = pd.merge(
        filtered_df,
        df_map[["_lat", "_lon", col_ref]].copy(),
        on=col_ref,
        how="inner",
    )

    # agrégation : 1 pin = 1 annonce
    def ref_agg(group: pd.DataFrame) -> pd.Series:
        out_d = {
            "_lat": group["_lat"].mean(),
            "_lon": group["_lon"].mean(),
        }
        # label ref propre
        ref_val = str(group.iloc[0][col_ref]).strip()
        if re.match(r"^\d+\.0+$", ref_val):
            ref_val = ref_val.split(".")[0]
        out_d["ref_label"] = ref_val
        return pd.Series(out_d)

    refs = (
        merged.groupby(col_ref, as_index=False)
        .apply(ref_agg)
        .reset_index(drop=True)
    )

    # gestion d'overlap
    refs["_lat_r"] = refs["_lat"].round(6)
    refs["_lon_r"] = refs["_lon"].round(6)

    rows_for_plot = []
    for (_, _), grp in refs.groupby(["_lat_r", "_lon_r"], sort=False):
        coords_circle = anti_overlap_positions(
            len(grp),
            float(grp.iloc[0]["_lat"]),
            float(grp.iloc[0]["_lon"]),
        )
        for (lat, lon), (_, r) in zip(coords_circle, grp.iterrows()):
            rr = r.copy()
            rr["_lat_plot"] = lat
            rr["_lon_plot"] = lon
            rows_for_plot.append(rr)

    plot_df = pd.DataFrame(rows_for_plot)

    # ====== SESSION STATE POUR L'ANNONCE SÉLECTIONNÉE ======
    if "selected_ref" not in st.session_state:
        st.session_state["selected_ref"] = None

    # ====== COLONNE CARTE (CENTRE) ======
    with col_map_st:
        st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)

        if plot_df.empty:
            st.markdown(
                '<div class="map-error">Aucune annonce affichable sur la carte avec les filtres ou les coordonnées actuelles.</div>',
                unsafe_allow_html=True,
            )
            clicked_ref = None
        else:
            # Construire la carte Folium
            FR_LAT, FR_LON, FR_ZOOM = 46.603354, 1.888334, 6
            m = folium.Map(
                location=[FR_LAT, FR_LON],
                zoom_start=FR_ZOOM,
                tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                attr="© OpenStreetMap contributors",
            )

            css_marker = (
                f"background:{LOGO_BLUE};"
                "color:#fff;"
                "border:2px solid #fff;"
                "width:28px; height:28px; line-height:28px;"
                "border-radius:50%; text-align:center;"
                "font-size:11px; font-weight:600;"
                "font-family:'Futura',sans-serif;"
                "box-shadow:0 2px 4px rgba(0,0,0,.4);"
            )

            layer = folium.FeatureGroup(name="Annonces").add_to(m)

            click_registry: Dict[Tuple[float, float], str] = {}

            for _, r in plot_df.iterrows():
                lat = float(r["_lat_plot"])
                lon = float(r["_lon_plot"])

                raw_label = str(r.get("ref_label", "")).strip()
                if re.match(r"^\d+\.0+$", raw_label):
                    raw_label = raw_label.split(".")[0]

                icon = folium.DivIcon(html=f'<div style="{css_marker}">{raw_label}</div>')

                layer.add_child(
                    folium.Marker(
                        location=[lat, lon],
                        icon=icon,
                    )
                )

                click_registry[(round(lat, 6), round(lon, 6))] = raw_label

            out = st_folium(m, height=800, width=None)

            clicked_ref = None
            if isinstance(out, dict):
                loc_info = out.get("last_object_clicked")
                if isinstance(loc_info, dict) and "lat" in loc_info and "lng" in loc_info:
                    lat_clicked = round(float(loc_info["lat"]), 6)
                    lon_clicked = round(float(loc_info["lng"]), 6)
                    key = (lat_clicked, lon_clicked)
                    clicked_ref = click_registry.get(key, None)

        if clicked_ref:
            st.session_state["selected_ref"] = clicked_ref

        st.markdown('</div>', unsafe_allow_html=True)  # end map-wrapper

    # ====== COLONNE DROITE (PANNEAU D'ANNONCE) ======
    with col_right:
        render_right_panel(
            st.session_state["selected_ref"],
            df,
            col_ref,
            col_addr_full,
            col_city,
            col_gmaps,
            col_date_pub,
        )


# -------------------------------------------------
# LANCEMENT
# -------------------------------------------------

if __name__ == "__main__":
    main()

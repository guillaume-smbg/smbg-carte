# app.py — SMBG Carte
# Streamlit + Excel (G→AF pour le volet droit ; H = bouton Google Maps "Cliquer ici")
# Colonnes techniques AG→AM: Latitude, Longitude, Geocode statut, Geocode date, Référence annonce, Photos annonce, Actif

import os
import io
import base64
import pathlib
from typing import List, Tuple, Dict

import streamlit as st
import pandas as pd
import yaml

# ---------- CONFIG DE PAGE ----------
st.set_page_config(page_title="SMBG Carte", layout="wide", page_icon="📍")

# ---------- CHARGEMENT SCHEMA ----------
# Le schema.yaml vient du repo ; il contient le range G:AF, H = Google Maps, colonnes techniques AG→AM, etc.
SCHEMA_PATH = pathlib.Path("schema.yaml")
if not SCHEMA_PATH.exists():
    st.error("Fichier schema.yaml introuvable dans le dépôt. Assure-toi de l’avoir à la racine.")
    st.stop()

with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    SCHEMA = yaml.safe_load(f)

# ---------- SECRETS ----------
EXCEL_URL = os.environ.get("EXCEL_URL") or st.secrets.get("EXCEL_URL", "")
R2_BASE_URL = os.environ.get("R2_BASE_URL") or st.secrets.get("R2_BASE_URL", "")

# ---------- OUTILS ----------
def excel_letter_to_index(letter: str) -> int:
    """Convertit une lettre Excel (A, B, ..., AA, AB) en index de colonne 0-based."""
    s = 0
    for c in letter.strip().upper():
        if not ("A" <= c <= "Z"):
            continue
        s = s * 26 + (ord(c) - 64)
    return s - 1

def slice_by_letters(df: pd.DataFrame, start_letter: str, end_letter: str) -> pd.DataFrame:
    start_idx = excel_letter_to_index(start_letter)
    end_idx = excel_letter_to_index(end_letter)
    return df.iloc[:, start_idx:end_idx+1]

def clean_value(v):
    if pd.isna(v):
        return ""
    return str(v).strip()

def value_is_hidden(v) -> bool:
    v = clean_value(v)
    return v in set(SCHEMA["right_panel"]["hide_values"])

def safe_col(df: pd.DataFrame, idx: int) -> pd.Series:
    return df.iloc[:, idx] if 0 <= idx < len(df.columns) else pd.Series([], dtype=object)

# ---------- FONTS : CHARGEMENT AUTOMATIQUE DES .TTF DANS assets/ ----------
def load_font_face(name: str, file_path: pathlib.Path, weight: str = "normal", style: str = "normal") -> str:
    if not file_path.exists():
        return ""
    data = file_path.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    mime = "font/ttf" if file_path.suffix.lower() == ".ttf" else "font/otf"
    return f"""
    @font-face {{
      font-family: '{name}';
      src: url(data:{mime};base64,{b64}) format('truetype');
      font-weight: {weight};
      font-style: {style};
      font-display: swap;
    }}
    """

def infer_weight_style_from_name(filename: str) -> Tuple[str, str]:
    """Déduit (weight, style) à partir du nom du fichier .ttf (heuristique robuste)."""
    f = filename.lower()
    weight = "400"
    style = "normal"
    # style
    if "italic" in f or "oblique" in f or "it" in f and "bold" in f:
        style = "italic"
    # poids
    if "thin" in f or "hairline" in f:
        weight = "100"
    elif "extralight" in f or "ultralight" in f:
        weight = "200"
    elif "light" in f:
        weight = "300"
    elif "regular" in f or "book" in f or "roman" in f:
        weight = "400"
    elif "medium" in f:
        weight = "500"
    elif "semibold" in f or "demibold" in f or "sb" in f:
        weight = "600"
    elif "bold" in f or "bd" in f:
        weight = "700"
    elif "extrabold" in f or "ultrabold" in f or "heavy" in f or "black" in f:
        weight = "800"
    elif "black" in f:
        weight = "900"
    # condensed/extended n'affecte pas le poids ici
    return weight, style

def inject_futura_fonts():
    assets_dir = pathlib.Path("assets")
    css_blocks = []
    if assets_dir.exists():
        # on charge TOUTES les .ttf / .otf du dossier
        for p in sorted(assets_dir.glob("*.ttf")) + sorted(assets_dir.glob("*.otf")):
            weight, style = infer_weight_style_from_name(p.name)
            css_blocks.append(load_font_face("Futura SMBG", p, weight=weight, style=style))
    # CSS global
    global_css = f"""
    <style>
    {''.join(css_blocks)}
    html, body, [class*="css"], .stMarkdown, .stText, .stButton, .stSelectbox, .stMultiSelect,
    .stDataFrame, .stMetric, .stCheckbox, .stRadio, .stTextInput, .stNumberInput, .stDateInput, .stLinkButton {{
      font-family: 'Futura SMBG', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;
    }}
    /* Anti-fuite soft */
    * {{ -webkit-user-select:none; -ms-user-select:none; user-select:none; }}
    img {{ -webkit-user-drag: none; user-drag: none; }}
    @media print {{
      body::before {{ content:"Impression désactivée"; }}
      body {{ display:none; }}
    }}
    </style>
    """
    st.markdown(global_css, unsafe_allow_html=True)

inject_futura_fonts()

# ---------- HEADER BRANDING ----------
def show_header():
    col1, col2 = st.columns([1, 4], vertical_alignment="center")
    with col1:
        candidates = [
            "assets/Logo bleu.png",
            "assets/logo_bleu.png",
            "assets/Logo transparent.png",
            "assets/logo_transparent.png"
        ]
        for c in candidates:
            p = pathlib.Path(c)
            if p.exists():
                st.image(str(p), use_container_width=True)
                break
    with col2:
        st.markdown("<div style='padding-top:4px; font-size:28px; font-weight:700;'>SMBG Carte — Sélection d’annonces</div>", unsafe_allow_html=True)
        # Slogan (optionnel)
        slogan_candidates = ["assets/Slogan bleu.png", "assets/slogan_bleu.png", "assets/Slogan transparent.png"]
        for sc in slogan_candidates:
            sp = pathlib.Path(sc)
            if sp.exists():
                st.image(str(sp), width=240)
                break

show_header()

# ---------- MODE (client / interne) ----------
DEFAULT_MODE = SCHEMA.get("modes", {}).get("default_mode", "client")
mode_param = st.query_params.get("mode", DEFAULT_MODE)
MODE = mode_param if mode_param in ("client", "interne") else DEFAULT_MODE
st.sidebar.markdown(f"**Mode :** `{MODE}`")

# ---------- CHARGEMENT EXCEL ----------
def load_excel(url: str) -> pd.DataFrame:
    if not url:
        st.error("EXCEL_URL manquant. Renseigne-le dans les *Secrets* Streamlit.")
        st.stop()
    try:
        if url.lower().endswith(".xlsx") or url.lower().endswith(".xls"):
            return pd.read_excel(url, engine="openpyxl")
        # GitHub raw peut être servi en octet-stream → on lit tout puis pandas
        resp = pd.read_excel(url, engine="openpyxl")
        return resp
    except Exception as e:
        st.error(f"Impossible de lire l'Excel depuis EXCEL_URL.\nDétail : {e}")
        st.stop()

df_all = load_excel(EXCEL_URL)

# ---------- FILTRE ACTIF ----------
# Colonnes techniques AG..AM : Latitude, Longitude, Geocode statut, Geocode date, Référence, Photos, Actif
lat_col = excel_letter_to_index(SCHEMA["technical_columns"]["latitude"])       # AG
lon_col = excel_letter_to_index(SCHEMA["technical_columns"]["longitude"])      # AH
geost_col = excel_letter_to_index(SCHEMA["technical_columns"]["geocode_status"])  # AI
geodt_col = excel_letter_to_index(SCHEMA["technical_columns"]["geocode_date"])   # AJ
ref_col = excel_letter_to_index(SCHEMA["technical_columns"]["reference"])      # AK
photos_col = excel_letter_to_index(SCHEMA["technical_columns"]["photos"])      # AL
active_col = excel_letter_to_index(SCHEMA["technical_columns"]["active"])      # AM

if 0 <= active_col < len(df_all.columns):
    active_mask = df_all.iloc[:, active_col].fillna("").astype(str).str.strip().str.lower() == "oui"
    df = df_all[active_mask].reset_index(drop=True)
else:
    df = df_all.copy()

# ---------- DÉTECTION REGION / DÉPARTEMENT ----------
region_cols = []
dept_cols = []
for c in df.columns:
    cl = str(c).strip().lower()
    if "région" in cl or "region" in cl:
        region_cols.append(c)
    if "départ" in cl or "depart" in cl or "dept" in cl:
        dept_cols.append(c)

region_col = region_cols[0] if region_cols else None
dept_col = dept_cols[0] if dept_cols else None

# ---------- FONCTIONS COMPTEURS DYNAMIQUES ----------
def current_other_filters(df_in: pd.DataFrame) -> pd.DataFrame:
    """Dans cette version de base, on n'a que Region/Departement. 
       Si tu ajoutes d'autres filtres (surface, typologie...), applique-les ici avant les compteurs."""
    return df_in

def region_counts(df_in: pd.DataFrame, selected_departments: List[str]) -> Dict[str, int]:
    # Applique d'abord les autres filtres (sauf région)
    base = current_other_filters(df_in)
    # Si des départements sont sélectionnés, restreindre
    if dept_col and selected_departments:
        base = base[base[dept_col].astype(str).str.strip().isin(selected_departments)]
    counts = {}
    if region_col:
        for val, sub in base.groupby(region_col, dropna=True):
            v = clean_value(val)
            if v and v != "/":
                counts[v] = len(sub)
    return counts

def dept_counts(df_in: pd.DataFrame, selected_regions: List[str]) -> Dict[str, int]:
    base = current_other_filters(df_in)
    if region_col and selected_regions:
        base = base[base[region_col].astype(str).str.strip().isin(selected_regions)]
    counts = {}
    if dept_col:
        for val, sub in base.groupby(dept_col, dropna=True):
            v = clean_value(val)
            if v and v != "/":
                counts[v] = len(sub)
    return counts

# ---------- SIDEBAR : FILTRES ----------
st.sidebar.header("Filtres")

selected_regions: List[str] = []
selected_depts: List[str] = []

# Options initiales (uniques présentes dans l'Excel — pas de liste nationale)
if region_col:
    regions_all = sorted([r for r in df[region_col].dropna().astype(str).str.strip().unique().tolist() if r and r != "/"])
else:
    regions_all = []

if dept_col:
    depts_all = sorted([d for d in df[dept_col].dropna().astype(str).str.strip().unique().tolist() if d and d != "/"])
else:
    depts_all = []

# Multiselects AVEC compteurs dynamiques (format_func)
# 1) Régions
if region_col:
    # Compteurs basés sur sélection de départements (si déjà cochés)
    rc = region_counts(df, selected_departments=[])
    # On affiche la liste complète avec compteurs initiaux
    def fmt_region(x):
        n = rc.get(x, 0)
        return f"{x} ({n})"
    selected_regions = st.sidebar.multiselect("Régions", options=regions_all, default=[], format_func=fmt_region)

# Restreindre DF selon régions sélectionnées
df_region = df.copy()
if region_col and selected_regions:
    df_region = df_region[df_region[region_col].astype(str).str.strip().isin(selected_regions)]

# 2) Départements (compteurs dépendants des régions choisies)
if dept_col:
    dc = dept_counts(df, selected_regions=selected_regions)
    # Départements pertinents après filtre région
    depts_filtered = sorted([d for d in df_region[dept_col].dropna().astype(str).str.strip().unique().tolist() if d and d != "/"])
    def fmt_dept(x):
        n = dc.get(x, 0)
        return f"{x} ({n})"
    selected_depts = st.sidebar.multiselect("Départements", options=depts_filtered, default=[], format_func=fmt_dept)

# Appliquer filtre départements
df_filtered = df_region.copy()
if dept_col and selected_depts:
    df_filtered = df_filtered[df_filtered[dept_col].astype(str).str.strip().isin(selected_depts)]

st.sidebar.caption(f"**{len(df_filtered)}** annonces après filtres Région / Département.")

# ---------- LAYOUT PRINCIPAL ----------
left, right = st.columns([1.1, 1.9], gap="large")

with left:
    st.subheader("Carte (aperçu)")
    st.info("Ici s'affichera la carte OSM (placeholder dans ce squelette).")

    # Liste rapide des annonces (Référence + Adresse)
    ref_series = safe_col(df_filtered, ref_col)
    # Adresse = colonne G (début de la zone affichée) ; si ton 'Adresse' n'est pas en G, adapte dans l'Excel
    addr_idx = excel_letter_to_index("G")
    addr_series = safe_col(df_filtered, addr_idx)
    mini = pd.DataFrame({
        "Référence": ref_series.astype(str) if not ref_series.empty else "",
        "Adresse": addr_series.astype(str) if not addr_series.empty else ""
    })
    st.dataframe(mini, use_container_width=True, hide_index=True)

with right:
    st.subheader("Volet droit — Détails")
    st.caption("Affiche G→AF (H devient bouton “Cliquer ici”). Masque `/`, `-` et vides. Référence annonce en en-tête.")
    # On affiche les 1–2 premières annonces comme aperçu
    preview_count = min(2, len(df_filtered))
    if preview_count == 0:
        st.warning("Aucune annonce ne correspond aux filtres actuels.")
    for i in range(preview_count):
        row = df_filtered.iloc[i]
        # Référence (cartouche)
        ref_val = clean_value(row.iloc[ref_col]) if 0 <= ref_col < len(df_filtered.columns) else ""
        if ref_val:
            st.markdown(f"**Référence annonce : {ref_val}**")

        # Parcours G..AF, H = Maps
        start_idx = excel_letter_to_index("G")
        end_idx = excel_letter_to_index("AF")
        gmaps_idx = excel_letter_to_index(SCHEMA["right_panel"]["google_maps_column_letter"])  # H

        # Colonnes loyer (N,O,P) à masquer en mode client
        rent_letters = SCHEMA.get("modes", {}).get("rent_columns_letters", [])
        rent_indices = [excel_letter_to_index(x) for x in rent_letters]

        for col_idx in range(start_idx, end_idx + 1):
            header = df_filtered.columns[col_idx]
            val = row.iloc[col_idx]

            # Google Maps (H)
            if col_idx == gmaps_idx:
                url = clean_value(val)
                if url and url != "/":
                    st.link_button(SCHEMA["branding"]["google_maps_button_label"], url, type="secondary")
                continue

            # Loyers masqués en mode client
            if MODE == "client" and col_idx in rent_indices:
                st.write(f"**{header}** : Demander le loyer")
                continue

            if value_is_hidden(val):
                continue

            st.write(f"**{header}** : {clean_value(val)}")

        st.divider()

# ---------- FIN ----------
st.success("Squelette SMBG Carte opérationnel. Ajoute ton Excel réel et tes photos R2 pour tester en conditions réelles.")

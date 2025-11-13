# -*- coding: utf-8 -*-
import os
import base64
import glob
import math
import re
from collections import defaultdict

import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

# ================== CONFIG GLOBALE ==================
st.set_page_config(
    layout="wide",
    page_title="Carte Interactive SMBG",
    initial_sidebar_state="expanded",
)

COLOR_SMBG_BLUE = "#05263D"
COLOR_SMBG_COPPER = "#C67B42"

LOGO_FILE_PATH = "assets/Logo bleu crop.png"   # logo PNG sur GitHub / projet
EXCEL_FILE_PATH = "data/Liste des lots.xlsx"   # fichier Excel des annonces

# Colonnes attendues dans le fichier Excel
REF_COL = "Référence annonce"
REGION_COL = "Région"
DEPT_COL = "Département"
EMPL_COL = "Emplacement"
TYPO_COL = "Typologie"
EXTRACTION_COL = "Extraction"
RESTAURATION_COL = "Restauration"
SURFACE_COL = "Surface GLA"
LOYER_COL = "Loyer annuel"
LAT_COL = "Latitude"
LON_COL = "Longitude"
ACTIF_COL = "Actif"  # "oui" / "non"

# Volet droit : de la colonne G à AL (H = lien Google Maps)
INDEX_START = 6           # index Excel de la lettre G (0-based après lecture pandas)
INDEX_END_EXCL = 38       # AL est 38 si le fichier n'a pas bougé
MAP_HEIGHT = 800


# ================== POLICE FUTURA ==================
def load_futura_css_from_assets() -> str:
    """Construit le @font-face pour toutes les variantes Futura trouvées dans /assets."""
    assets_dir = "assets"
    if not os.path.isdir(assets_dir):
        return ""

    preferred = [
        "FuturaT-Book.ttf",
        "FuturaT.ttf",
        "FuturaT-Medium.ttf",
        "FuturaT-Bold.ttf",
        "FuturaL-Book.ttf",
        "FuturaL-Medium.ttf",
        "FuturaL-Bold.ttf",
    ]
    files = [
        os.path.join(assets_dir, p)
        for p in preferred
        if os.path.exists(os.path.join(assets_dir, p))
    ]
    if not files:
        files = glob.glob(os.path.join(assets_dir, "*.ttf"))

    css_parts = []

    for fp in files[:4]:
        try:
            with open(fp, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            name = os.path.basename(fp).lower()
            if "bold" in name:
                weight = "700"
            elif "medium" in name:
                weight = "500"
            elif "light" in name:
                weight = "300"
            else:
                weight = "400"
            style = "italic" if ("italic" in name or "oblique" in name) else "normal"

            css_parts.append(
                f"@font-face {{"
                f"font-family:'Futura SMBG';"
                f"src:url(data:font/ttf;base64,{b64}) format('truetype');"
                f"font-weight:{weight};"
                f"font-style:{style};"
                f"font-display:swap;}}"
            )
        except Exception:
            pass

    css_parts.append(
        "*{font-family:'Futura SMBG', Futura, 'Futura PT', 'Century Gothic', Arial, sans-serif;}"
    )
    return "\n".join(css_parts)


def logo_base64() -> str:
    """Encode le logo en base64 pour l'afficher sans bouton d'agrandissement."""
    if not os.path.exists(LOGO_FILE_PATH):
        return ""
    with open(LOGO_FILE_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


# ================== HELPERS GÉNÉRAUX ==================
def parse_ref_display(ref_str: str) -> str:
    """
    Nettoie l'affichage de la référence :
    - 0005 -> 5
    - 0005.1 -> 5.1
    """
    s = str(ref_str).strip()
    if "." in s:
        left, right = s.split(".", 1)
        left = re.sub(r"^0+", "", left) or "0"
        return f"{left}.{right}"
    return re.sub(r"^0+", "", s) or "0"


def format_value(value, unit: str = "") -> str:
    """
    Formate les nombres arrondis avec espace mille + unité.
    Si la valeur est vide ou 'néant'/'-'/ '/', on renvoie "" pour masquer la ligne.
    """
    s = str(value).strip()
    if s.lower() in ("n/a", "nan", "", "none", "néant", "-", "/"):
        return ""
    try:
        num = float(
            s.replace("€", "")
            .replace("m²", "")
            .replace("m2", "")
            .replace(" ", "")
            .replace(",", ".")
        )
        txt = f"{num:,.0f}".replace(",", " ")
        return f"{txt} {unit}".strip() if unit else txt
    except Exception:
        return s


def jitter_group(df: pd.DataFrame, lat_col: str, lon_col: str,
                 base_radius_m: float = 12.0, step_m: float = 4.0) -> pd.DataFrame:
    """
    Pour des lots avec exactement les mêmes coordonnées GPS,
    décale légèrement les pins selon une spirale de Fermat (golden angle).
    """
    golden = math.pi * (3 - math.sqrt(5))
    out = []
    for i, (_, r) in enumerate(df.iterrows()):
        lat0, lon0 = r[lat_col], r[lon_col]
        radius = base_radius_m + i * step_m
        theta = i * golden
        rr = r.copy()
        rr["__jlat"] = lat0 + (radius * math.sin(theta)) / 111_320.0
        rr["__jlon"] = lon0 + (radius * math.cos(theta)) / (
            111_320.0 * max(0.2, math.cos(math.radians(lat0)))
        )
        out.append(rr)
    return pd.DataFrame(out) if out else df


def reset_all():
    """Reset dur de toute la session (filtres + sliders + sélection annonce)."""
    st.session_state.clear()
    st.rerun()


# État initial de la référence sélectionnée (pour le volet droit)
if "selected_ref" not in st.session_state:
    st.session_state["selected_ref"] = None
# ================== DATA ==================
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, dtype={REF_COL: str})
    df.columns = df.columns.str.strip()
    df[REF_COL] = (
        df[REF_COL].astype(str).str.replace(".0", "", regex=False).str.strip()
    )

    df[LAT_COL] = pd.to_numeric(df.get(LAT_COL, ""), errors="coerce")
    df[LON_COL] = pd.to_numeric(df.get(LON_COL, ""), errors="coerce")
    df["__SURF_NUM__"] = pd.to_numeric(df.get(SURFACE_COL, ""), errors="coerce")
    df["__LOYER_NUM__"] = pd.to_numeric(df.get(LOYER_COL, ""), errors="coerce")

    if ACTIF_COL in df.columns:
        df = df[df[ACTIF_COL].astype(str).str.lower().eq("oui")]

    df.dropna(subset=[LAT_COL, LON_COL], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


data_df = load_data(EXCEL_FILE_PATH)


# ================== CSS GLOBAL ==================
st.markdown(
    f"""
<style>
{load_futura_css_from_assets()}

/* Réserve la place du panneau droit */
[data-testid="stAppViewContainer"] .main .block-container {{
  padding-right: 380px;
}}

/* On retire le padding natif de la sidebar, on gère la marge manuellement */
aside[data-testid="stSidebar"] div[data-testid="stSidebarContent"] > div {{
  padding-top:0 !important;
  padding-bottom:0 !important;
}}
[data-testid="stSidebar"] .block-container {{
  padding-top:0 !important;
}}

/* Fond & texte sidebar */
[data-testid="stSidebar"] {{
  background:{COLOR_SMBG_BLUE};
  color:white;
}}

/* Suppression des boutons de rétractation */
[data-testid="stSidebarCollapseButton"],
button[kind="headerNoPadding"] {{
  display:none !important;
}}

/* Titres cuivre */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4 {{
  color:{COLOR_SMBG_COPPER} !important;
}}

/* Indentation départements 15 px */
.dept-wrap {{
  margin-left:15px;
}}

/* Curseur main sur les pins */
.smbg-divicon {{
  cursor:pointer;
}}

/* Popups Leaflet invisibles (mais événements toujours captés) */
.leaflet-popup,
.leaflet-popup-pane,
.leaflet-popup-content-wrapper,
.leaflet-popup-tip,
.leaflet-container a.leaflet-popup-close-button {{
  opacity:0 !important;
  width:0 !important;
  height:0 !important;
  padding:0 !important;
  margin:0 !important;
  border:0 !important;
  display:none !important;
}}

/* Panneau droit */
.details-panel {{
  position: fixed;
  top: 0;
  right: 0;
  width: 360px;
  height: 100vh;
  background:{COLOR_SMBG_BLUE};
  color:#fff;
  z-index:1000;
  padding:16px;
  box-shadow:-5px 0 15px rgba(0,0,0,0.35);
  overflow-y:auto;
}}
.maps-button {{
  width:100%;
  padding:9px;
  margin:8px 0 14px;
  background:{COLOR_SMBG_COPPER};
  color:#fff;
  border:none;
  border-radius:8px;
  cursor:pointer;
  text-align:center;
  font-weight:700;
}}
.details-panel table {{
  width:100%;
  border-collapse:collapse;
  font-size:13px;
}}
.details-panel tr {{
  border-bottom:1px solid #304f65;
}}
.details-panel td {{
  padding:6px 0;
  max-width:50%;
  overflow-wrap:break-word;
}}
</style>
""",
    unsafe_allow_html=True,
)


# ================== SIDEBAR ==================
with st.sidebar:
    # marge fixe de 25 px tout en haut
    st.markdown("<div style='height:25px'></div>", unsafe_allow_html=True)

    # Logo base64 collé en haut (aucun bouton d'agrandissement)
    b64_logo = logo_base64()
    if b64_logo:
        st.markdown(
            f"<img src='data:image/png;base64,{b64_logo}' "
            f"style='width:100%;height:auto;display:block;margin:0;'>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color:#fff;'>Logo introuvable</div>",
            unsafe_allow_html=True,
        )

    # petite marge sous le logo
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # --------- Région / Département imbriqués ---------
    st.markdown("**Région / Département**")

    regions = sorted(
        [
            x
            for x in data_df.get(REGION_COL, pd.Series())
            .dropna()
            .astype(str)
            .unique()
            if x.strip()
        ]
    )

    selected_regions: list[str] = []
    selected_depts_global: list[str] = []
    selected_depts_by_region: dict[str, list[str]] = defaultdict(list)

    for reg in regions:
        rk = f"chk_region_{reg}"
        rchecked = st.checkbox(reg, key=rk)
        if rchecked:
            selected_regions.append(reg)

            # Départements de cette région affichés UNIQUEMENT si la région est cochée
            pool = data_df[data_df[REGION_COL].astype(str).eq(reg)]
            depts = sorted(
                [
                    x
                    for x in pool.get(DEPT_COL, pd.Series())
                    .dropna()
                    .astype(str)
                    .unique()
                    if x.strip()
                ]
            )
            for d in depts:
                dk = f"chk_dept_{reg}_{d}"
                st.markdown("<div class='dept-wrap'>", unsafe_allow_html=True)
                dchecked = st.checkbox(d, key=dk)
                st.markdown("</div>", unsafe_allow_html=True)
                if dchecked:
                    selected_depts_global.append(d)
                    selected_depts_by_region[reg].append(d)

    st.markdown("---")

    # --------- Sliders Surface & Loyer ---------
    surf_min = (
        int(np.nanmin(data_df["__SURF_NUM__"]))
        if data_df["__SURF_NUM__"].notna().any()
        else 0
    )
    surf_max = (
        int(np.nanmax(data_df["__SURF_NUM__"]))
        if data_df["__SURF_NUM__"].notna().any()
        else 1000
    )
    smin, smax = st.slider(
        "Surface GLA (m²)",
        min_value=surf_min,
        max_value=surf_max,
        value=(surf_min, surf_max),
        step=1,
        key="slider_surface",
    )

    loyer_min = (
        int(np.nanmin(data_df["__LOYER_NUM__"]))
        if data_df["__LOYER_NUM__"].notna().any()
        else 0
    )
    loyer_max = (
        int(np.nanmax(data_df["__LOYER_NUM__"]))
        if data_df["__LOYER_NUM__"].notna().any()
        else 100000
    )
    lmin, lmax = st.slider(
        "Loyer annuel (€)",
        min_value=loyer_min,
        max_value=loyer_max,
        value=(loyer_min, loyer_max),
        step=1000,
        key="slider_loyer",
    )

    # --------- Cases à cocher Emplacement / Typologie / Extraction / Restauration ---------
    def draw_checks(title: str, column: str, prefix: str) -> list[str]:
        st.markdown(f"**{title}**")
        opts = sorted(
            [
                x
                for x in data_df.get(column, pd.Series())
                .dropna()
                .astype(str)
                .unique()
                if x.strip()
            ]
        )
        sels: list[str] = []
        for opt in opts:
            if st.checkbox(opt, key=f"chk_{prefix}_{opt}"):
                sels.append(opt)
        st.markdown("---")
        return sels

    emp_sel = draw_checks("Emplacement", EMPL_COL, "emp")
    typo_sel = draw_checks("Typologie", TYPO_COL, "typo")
    ext_sel = draw_checks("Extraction", EXTRACTION_COL, "ext")
    rest_sel = draw_checks("Restauration", RESTAURATION_COL, "rest")

    # --------- Bouton Reset ---------
    if st.button("Réinitialiser", use_container_width=True):
        reset_all()
# ================== APPLICATION DES FILTRES ==================
f = data_df.copy()

# Règle REG ∪ DEP :
# - si région cochée et aucun département sous cette région coché -> tous les départements de la région
# - si région cochée et certains départements cochés -> seulement ces départements
# - si département coché indépendamment -> il est pris en compte aussi
if selected_regions or selected_depts_global:
    cond_parts = []

    if selected_regions:
        reg_mask = pd.Series(False, index=f.index)
        for reg in selected_regions:
            reg_rows = f[REGION_COL].astype(str).eq(reg)
            depts_sel = selected_depts_by_region.get(reg, [])
            if depts_sel:
                reg_mask = reg_mask | (
                    reg_rows & f[DEPT_COL].astype(str).isin(depts_sel)
                )
            else:
                reg_mask = reg_mask | reg_rows
        cond_parts.append(reg_mask)

    if selected_depts_global:
        cond_parts.append(f[DEPT_COL].astype(str).isin(selected_depts_global))

    f = f[np.logical_or.reduce(cond_parts)] if cond_parts else f

# Sliders
f = f[
    (f["__SURF_NUM__"].isna() | ((f["__SURF_NUM__"] >= smin) & (f["__SURF_NUM__"] <= smax)))
    & (f["__LOYER_NUM__"].isna() | ((f["__LOYER_NUM__"] >= lmin) & (f["__LOYER_NUM__"] <= lmax)))
]

# Cases simples
if emp_sel:
    f = f[f[EMPL_COL].astype(str).isin(emp_sel)]
if typo_sel:
    f = f[f[TYPO_COL].astype(str).isin(typo_sel)]
if ext_sel:
    f = f[f[EXTRACTION_COL].astype(str).isin(ext_sel)]
if rest_sel:
    f = f[f[RESTAURATION_COL].astype(str).isin(rest_sel)]


# ================== CARTE FOLIUM ==================
tmp = f.copy()
tmp["__lat__"] = tmp[LAT_COL]
tmp["__lon__"] = tmp[LON_COL]

# Jitter pour les lots avec même coordonnée
jittered_groups: list[pd.DataFrame] = []
for (_, _grp) in tmp.groupby([LAT_COL, LON_COL], as_index=False):
    jittered_groups.append(
        jitter_group(_grp, "__lat__", "__lon__", base_radius_m=12.0, step_m=4.0)
    )

pins_df = pd.concat(jittered_groups, ignore_index=True) if jittered_groups else tmp.copy()

if pins_df.empty:
    center_lat, center_lon = 46.5, 2.5
else:
    center_lat = float(pins_df["__jlat"].mean())
    center_lon = float(pins_df["__jlon"].mean())

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=6,
    control_scale=True,
)


def add_pin(lat: float, lon: float, label: str, ref_value: str) -> None:
    """Ajoute un DivIcon plein SMBG + une zone cliquable exactement sur le pin."""
    icon_html = f"""
    <div class="smbg-divicon" style="
        width:30px;height:30px;border-radius:50%;
        background:{COLOR_SMBG_BLUE};
        display:flex;align-items:center;justify-content:center;
        color:#fff;font-weight:700;font-size:12px;
        border:1px solid #001a27;">
        {label}
    </div>"""

    # Marker avec popup technique (masquée visuellement par le CSS)
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(
            html=icon_html,
            class_name="smbg-divicon",
            icon_size=(30, 30),
            icon_anchor=(15, 15),
        ),
        popup=f"<div data-ref='{ref_value}'>{ref_value}</div>",
    ).add_to(m)

    # Cible cliquable invisible, strictement superposée
    folium.CircleMarker(
        location=[lat, lon],
        radius=15,
        color="#00000000",
        fill=True,
        fill_color="#00000000",
        fill_opacity=0.0,
        opacity=0.0,
        popup=f"<div data-ref='{ref_value}'>{ref_value}</div>",
    ).add_to(m)


if not pins_df.empty:
    pins_df["__ref_display__"] = pins_df[REF_COL].apply(parse_ref_display)
    for _, r in pins_df.iterrows():
        add_pin(
            float(r["__jlat"]),
            float(r["__jlon"]),
            r["__ref_display__"],
            str(r[REF_COL]),
        )

# On récupère UNIQUEMENT l'objet cliqué (marker / cercle invisible),
# pas de clic sur la carte "dans le vide".
map_output = st_folium(
    m,
    height=MAP_HEIGHT,
    width="100%",
    returned_objects=["last_object_clicked"],
    key="map",
)

if map_output and map_output.get("last_object_clicked"):
    obj = map_output["last_object_clicked"]
    ref_guess = None
    for k in ("popup", "popup_html"):
        if k in obj and obj[k]:
            txt = str(obj[k])
            mref = re.search(r"data-ref=['\"]([^'\"]+)['\"]", txt)
            ref_guess = mref.group(1) if mref else re.sub(r"<.*?>", "", txt).strip()
            break
    if ref_guess:
        st.session_state["selected_ref"] = ref_guess
# ================== VOLET DROIT ==================
html_parts = ["<div class='details-panel'>"]

sel_ref = st.session_state.get("selected_ref")

if sel_ref:
    rowset = data_df[
        data_df[REF_COL].astype(str).str.strip() == str(sel_ref).strip()
    ]
    if not rowset.empty:
        r = rowset.iloc[0]
        ref_title = parse_ref_display(sel_ref)

        html_parts.extend(
            [
                "<h3 style='margin:0 0 6px 0;'>🔍 Détails de l'annonce</h3>",
                f"<h4 style='color:{COLOR_SMBG_COPPER};margin:0 0 10px 0;'>Réf. : {ref_title}</h4>",
                "<h5 style='margin:6px 0 8px;'>📋 Données clés</h5>",
                "<table>",
            ]
        )

        all_cols = data_df.columns.tolist()
        if len(all_cols) >= INDEX_END_EXCL:
            cols_slice = all_cols[INDEX_START:INDEX_END_EXCL]
        else:
            cols_slice = all_cols[INDEX_START:]

        for idx, champ in enumerate(cols_slice, start=INDEX_START):
            sraw = str(r.get(champ, "")).strip()
            if sraw.lower() in ("", "néant", "-", "/"):
                continue

            # Colonne lien Google Maps (H ou champ texte type "lien google")
            if idx == (INDEX_START + 1) or champ.lower().strip() in (
                "lien google maps",
                "google maps",
                "lien google",
            ):
                html_parts.append(
                    "<tr>"
                    f"<td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>Lien Google Maps</td>"
                    f"<td><a class='maps-button' href='{sraw}' target='_blank'>Cliquer ici</a></td>"
                    "</tr>"
                )
                continue

            # Détection des unités
            if any(
                k in champ
                for k in [
                    "Loyer",
                    "Charges",
                    "garantie",
                    "Taxe",
                    "Marketing",
                    "Gestion",
                    "BP",
                    "annuel",
                    "Mensuel",
                    "foncière",
                    "Honoraires",
                ]
            ):
                unit = "€"
            elif any(
                k in champ
                for k in ["Surface", "GLA", "utile", "Vitrine", "Linéaire"]
            ):
                unit = "m²"
            else:
                unit = ""

            sval = format_value(sraw, unit)
            if not sval:
                continue

            html_parts.append(
                "<tr>"
                f"<td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>{champ}</td>"
                f"<td>{sval}</td>"
                "</tr>"
            )

        html_parts.extend(
            [
                "</table>",
                "<hr style='border:1px solid #eee;margin:12px 0;'>",
                "<h5 style='margin:6px 0 8px;'>📷 Photos</h5>",
                "<div class='small-note'>Les photos seront affichées ici dès qu'elles seront en ligne.</div>",
            ]
        )

html_parts.append("</div>")
st.markdown("".join(html_parts), unsafe_allow_html=True)

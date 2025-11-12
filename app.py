# -*- coding: utf-8 -*-
import os, base64, glob, math
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
import re

# =============================================
# CONFIG
# =============================================
st.set_page_config(layout="wide", page_title="Carte Interactive SMBG")

COLOR_SMBG_BLUE = "#05263D"
COLOR_SMBG_COPPER = "#C67B42"

LOGO_FILE_PATH_URL = "assets/Logo bleu crop.png"
EXCEL_FILE_PATH = "data/Liste des lots.xlsx"

# Noms attendus (adapter si besoin aux entêtes exactes)
REF_COL           = "Référence annonce"
REGION_COL        = "Région"
DEPT_COL          = "Département"
EMPL_COL          = "Emplacement"
TYPO_COL          = "Typologie"
EXTRACTION_COL    = "Extraction"
RESTAURATION_COL  = "Restauration"
SURFACE_COL       = "Surface GLA"
LOYER_COL         = "Loyer annuel"
LAT_COL           = "Latitude"
LON_COL           = "Longitude"
ACTIF_COL         = "Actif"  # "oui"/"non"

# =============================================
# POLICE FUTURA (depuis ./assets/*.ttf)
# =============================================
def _load_futura_css_from_assets():
    assets_dir = "assets"
    if not os.path.isdir(assets_dir):
        return ""
    preferred = [
        "FuturaT-Book.ttf", "FuturaT.ttf", "FuturaT-Medium.ttf", "FuturaT-Bold.ttf",
        "FuturaL-Book.ttf", "FuturaL-Medium.ttf", "FuturaL-Bold.ttf"
    ]
    files = [os.path.join(assets_dir, p) for p in preferred if os.path.exists(os.path.join(assets_dir, p))]
    if not files:
        files = glob.glob(os.path.join(assets_dir, "*.ttf"))
    css_blocks = []
    for fp in files[:4]:
        try:
            with open(fp, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            name = os.path.basename(fp).lower()
            weight = "400"; style = "normal"
            if "bold" in name: weight = "700"
            if "medium" in name: weight = "500"
            if "light" in name: weight = "300"
            if "italic" in name or "oblique" in name: style = "italic"
            css_blocks.append(
                f"@font-face {{font-family:'Futura SMBG';src:url(data:font/ttf;base64,{b64}) format('truetype');"
                f"font-weight:{weight};font-style:{style};font-display:swap;}}"
            )
        except Exception:
            pass
    css_blocks.append("*{font-family:'Futura SMBG', Futura, 'Futura PT', 'Century Gothic', Arial, sans-serif;}")
    return "\n".join(css_blocks)

# =============================================
# HELPERS
# =============================================
def reset_all_filters():
    for k in list(st.session_state.keys()):
        if k.startswith(("flt_", "map_")) or k in ("selected_ref", "last_clicked_coords"):
            del st.session_state[k]
    st.session_state["selected_ref"] = None
    st.session_state["last_clicked_coords"] = (0, 0)
    st.session_state["map_zoom"] = 6

if "selected_ref" not in st.session_state:
    st.session_state["selected_ref"] = None
if "last_clicked_coords" not in st.session_state:
    st.session_state["last_clicked_coords"] = (0, 0)
if "map_zoom" not in st.session_state:
    st.session_state["map_zoom"] = 6

def format_value(value, unit=""):
    s = str(value).strip()
    if s in ("N/A", "nan", "", "None", "None €", "None m²", "/"):
        return "Non renseigné"
    try:
        num = float(s.replace("€","").replace("m²","").replace("m2","").replace(" ", "").replace(",", "."))
        txt = f"{num:,.0f}".replace(",", " ")
        return f"{txt} {unit}".strip() if unit else txt
    except Exception:
        return s

def parse_ref_display(ref_str):
    """
    '0003' -> '3'
    '0005.1' -> '5.1'
    '0005.10' -> '5.10'
    """
    s = str(ref_str).strip()
    if "." in s:
        left, right = s.split(".", 1)
        left = re.sub(r"^0+", "", left) or "0"
        return f"{left}.{right}"
    else:
        return re.sub(r"^0+", "", s) or "0"

def base_ref(ref_str):
    """'0005.1' -> '0005' (partie base avant le point), '0003' -> '0003'."""
    s = str(ref_str).strip()
    return s.split(".")[0]

def meters_to_deg_lat(m):
    return m / 111_320.0

def meters_to_deg_lon(m, lat_deg):
    return m / (111_320.0 * max(0.2, math.cos(math.radians(lat_deg))))

def jitter_group(df, lat_col, lon_col, base_radius_m=12.0, step_m=4.0):
    """Décale légèrement les points d’un même groupe autour du centre."""
    golden_angle = math.pi * (3 - math.sqrt(5))
    out = []
    for i, (_, r) in enumerate(df.iterrows()):
        lat0 = r[lat_col]; lon0 = r[lon_col]
        radius_m = base_radius_m + i * step_m
        theta = i * golden_angle
        jlat = lat0 + meters_to_deg_lat(radius_m * math.sin(theta))
        jlon = lon0 + meters_to_deg_lon(radius_m * math.cos(theta), lat0)
        rr = r.copy()
        rr["__jlat"] = jlat
        rr["__jlon"] = jlon
        out.append(rr)
    return pd.DataFrame(out) if out else df

@st.cache_data
def load_data(file_path):
    df = pd.read_excel(file_path, dtype={REF_COL: str})
    df.columns = df.columns.str.strip()
    # normalisation de la référence
    df[REF_COL] = df[REF_COL].astype(str).str.replace(".0", "").str.strip()
    # numériques
    df[LAT_COL] = pd.to_numeric(df.get(LAT_COL, ""), errors="coerce")
    df[LON_COL] = pd.to_numeric(df.get(LON_COL, ""), errors="coerce")
    df["__SURF_NUM__"]  = pd.to_numeric(df.get(SURFACE_COL, ""), errors="coerce")
    df["__LOYER_NUM__"] = pd.to_numeric(df.get(LOYER_COL, ""), errors="coerce")
    # filtre actif
    if ACTIF_COL in df.columns:
        df = df[df[ACTIF_COL].astype(str).str.lower().eq("oui")]
    # drop coords vides
    df.dropna(subset=[LAT_COL, LON_COL], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

# =============================================
# CHARGEMENT
# =============================================
data_df = load_data(EXCEL_FILE_PATH)

# =============================================
# CSS global + panneau droit
# =============================================
st.markdown(f"""
<style>
{_load_futura_css_from_assets()}

/* Réserve 380px pour le panneau droit afin d'éviter un recouvrement */
[data-testid="stAppViewContainer"] .main .block-container {{
  padding-right: 380px;
}}

.details-panel {{
  position: fixed; top: 0; right: 0; width: 360px; height: 100vh;
  background-color: {COLOR_SMBG_BLUE}; color: white; z-index: 1000;
  padding: 16px; box-shadow: -5px 0 15px rgba(0,0,0,0.35); overflow-y: auto;
}}
[data-testid="stSidebar"] {{ background-color: {COLOR_SMBG_BLUE}; color: white; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {{ color: {COLOR_SMBG_COPPER} !important; }}
.stImage > button {{ display: none !important; }} /* supprime l’agrandissement du logo */

.maps-button {{
  width: 100%; padding: 9px; margin: 8px 0 14px 0; background-color: {COLOR_SMBG_COPPER};
  color: white; border: none; border-radius: 8px; cursor: pointer; text-align: center; font-weight: 700;
}}
.details-panel table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.details-panel tr {{ border-bottom: 1px solid #304f65; }}
.details-panel td {{ padding: 6px 0; max-width: 50%; overflow-wrap: break-word; }}
</style>
""", unsafe_allow_html=True)

# =============================================
# SIDEBAR — Filtres
# =============================================
with st.sidebar:
    st.image(LOGO_FILE_PATH_URL, use_column_width=True)
    st.markdown("")

    # Région
    regions = sorted([x for x in data_df.get(REGION_COL, pd.Series()).dropna().astype(str).unique() if x.strip()])
    region_sel = st.multiselect("Région", regions, key="flt_region")

    # Département (dépend des régions sélectionnées, sinon tous)
    if region_sel:
        depts_pool = data_df[data_df[REGION_COL].astype(str).isin(region_sel)]
    else:
        depts_pool = data_df
    depts = sorted([x for x in depts_pool.get(DEPT_COL, pd.Series()).dropna().astype(str).unique() if x.strip()])
    dept_sel = st.multiselect("Département", depts, key="flt_dept")

    # Sliders Surface & Loyer
    surf_min = int(np.nanmin(data_df["__SURF_NUM__"])) if data_df["__SURF_NUM__"].notna().any() else 0
    surf_max = int(np.nanmax(data_df["__SURF_NUM__"])) if data_df["__SURF_NUM__"].notna().any() else 1000
    smin, smax = st.slider("Surface GLA (m²)", min_value=surf_min, max_value=surf_max,
                           value=(surf_min, surf_max), step=1, key="flt_surface")

    loyer_min = int(np.nanmin(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 0
    loyer_max = int(np.nanmax(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 100000
    lmin, lmax = st.slider("Loyer annuel (€)", min_value=loyer_min, max_value=loyer_max,
                           value=(loyer_min, loyer_max), step=1000, key="flt_loyer")

    # Cases à cocher (multisélection)
    def _opts(col):
        return sorted([x for x in data_df.get(col, pd.Series()).dropna().astype(str).unique() if x.strip()])
    emp_sel  = st.multiselect("Emplacement", _opts(EMPL_COL), key="flt_emp")
    typo_sel = st.multiselect("Typologie",  _opts(TYPO_COL), key="flt_typo")
    ext_sel  = st.multiselect("Extraction", _opts(EXTRACTION_COL), key="flt_ext")
    rest_sel = st.multiselect("Restauration", _opts(RESTAURATION_COL), key="flt_rest")

    st.markdown("")
    st.info(f"Annonces chargées : **{len(data_df)}**")
    st.button("Réinitialiser tous les filtres", use_container_width=True, on_click=reset_all_filters)

# =============================================
# Application des filtres
# =============================================
filtered_df = data_df.copy()

# Région / Département (imbriqués)
if region_sel:
    filtered_df = filtered_df[filtered_df[REGION_COL].astype(str).isin(region_sel)]
if dept_sel:
    filtered_df = filtered_df[filtered_df[DEPT_COL].astype(str).isin(dept_sel)]

# Surface & Loyer
filtered_df = filtered_df[
    (filtered_df["__SURF_NUM__"].isna()  | ((filtered_df["__SURF_NUM__"]  >= smin) & (filtered_df["__SURF_NUM__"]  <= smax))) &
    (filtered_df["__LOYER_NUM__"].isna() | ((filtered_df["__LOYER_NUM__"] >= lmin) & (filtered_df["__LOYER_NUM__"] <= lmax)))
]

# Emplacement / Typologie / Extraction / Restauration
if emp_sel:
    filtered_df = filtered_df[filtered_df[EMPL_COL].astype(str).isin(emp_sel)]
if typo_sel:
    filtered_df = filtered_df[filtered_df[TYPO_COL].astype(str).isin(typo_sel)]
if ext_sel:
    filtered_df = filtered_df[filtered_df[EXTRACTION_COL].astype(str).isin(ext_sel)]
if rest_sel:
    filtered_df = filtered_df[filtered_df[RESTAURATION_COL].astype(str).isin(rest_sel)]

# =============================================
# Logique de zoom (un pin = base_ref à zoom global ; pins détaillés à zoom rapproché)
# =============================================
# On construit les marqueurs selon st.session_state["map_zoom"] connu
ZOOM_THRESHOLD = 12
render_mode = "base" if st.session_state["map_zoom"] < ZOOM_THRESHOLD else "lot"

# Prépare le DF pour les pins
pins_df = filtered_df.copy()
pins_df["__ref_display__"] = pins_df[REF_COL].apply(parse_ref_display)
pins_df["__base_ref__"]    = pins_df[REF_COL].apply(base_ref)

if render_mode == "base":
    # 1 pin par base_ref (ex. 0005 -> "5"), coords = moyenne
    grp = pins_df.groupby("__base_ref__", as_index=False).agg({
        LAT_COL: "mean", LON_COL: "mean"
    })
    grp["__ref_display__"] = grp["__base_ref__"].apply(lambda s: re.sub(r"^0+", "", str(s).strip()) or "0")
    pins_df = grp.rename(columns={LAT_COL: "__lat__", LON_COL: "__lon__"})
else:
    # 1 pin par lot + léger jitter pour éviter le recouvrement
    pins_df["__lat__"] = pins_df[LAT_COL]
    pins_df["__lon__"] = pins_df[LON_COL]
    pins_df = jitter_group(
        pins_df.sort_values([LAT_COL, LON_COL, REF_COL]),
        lat_col="__lat__", lon_col="__lon__", base_radius_m=14.0, step_m=5.0
    )

# =============================================
# Carte
# =============================================
MAP_HEIGHT = 800
if not pins_df.empty:
    center_lat = pins_df["__lat__"].mean()
    center_lon = pins_df["__lon__"].mean()
else:
    center_lat, center_lon = 46.5, 2.5  # France

m = folium.Map(location=[center_lat, center_lon], zoom_start=st.session_state["map_zoom"], control_scale=True)

def add_pin(lat, lon, label):
    html_pin = f"""
    <div style="width:30px;height:30px;border-radius:50%;
                background:{COLOR_SMBG_BLUE};
                display:flex;align-items:center;justify-content:center;
                color:#fff;font-weight:700;font-size:12px;border:1px solid #001a27;">
        {label}
    </div>"""
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(html=html_pin, class_name="smbg-divicon",
                            icon_size=(30,30), icon_anchor=(15,15))
    ).add_to(m)

if not pins_df.empty:
    if render_mode == "base":
        for _, r in pins_df.iterrows():
            add_pin(r["__lat__"], r["__lon__"], r["__ref_display__"])
    else:
        for _, r in pins_df.iterrows():
            add_pin(r["__jlat"], r["__jlon"], r["__ref_display__"])

# Render & récupérer le zoom/clic
map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=["last_clicked", "zoom"], key="map")

# Met à jour zoom -> déclenche re-rendu au prochain run
if map_output and "zoom" in map_output:
    new_zoom = int(map_output["zoom"])
    if new_zoom != st.session_state.get("map_zoom", 6):
        st.session_state["map_zoom"] = new_zoom
        st.rerun()

# Clic -> sélectionner la réf la plus proche
if map_output and map_output.get("last_clicked"):
    clicked = map_output["last_clicked"]
    clat, clon = clicked["lat"], clicked["lng"]
    if render_mode == "base":
        # closest base pin -> trouve une ligne de cette base pour le panneau
        pins_df["__dist_sq"] = (pins_df["__lat__"] - clat)**2 + (pins_df["__lon__"] - clon)**2
        row = pins_df.loc[pins_df["__dist_sq"].idxmin()]
        # choisit une première réf complète correspondante
        base_id = str(row["__base_ref__"])
        sel_row = filtered_df[filtered_df[REF_COL].str.startswith(base_id + ".") | filtered_df[REF_COL].eq(base_id)]
        if not sel_row.empty:
            st.session_state["selected_ref"] = sel_row.iloc[0][REF_COL]
    else:
        # closest detailed pin -> modèle direct par lot
        pins_df["__dist_sq"] = (pins_df["__jlat"] - clat)**2 + (pins_df["__jlon__"] - clon)**2 if "__jlon__" in pins_df.columns else (pins_df["__lon__"] - clon)**2
        row = pins_df.loc[pins_df["__dist_sq"].idxmin()]
        st.session_state["selected_ref"] = row[REF_COL] if REF_COL in row else None

# =============================================
# Volet droit — Colonnes G → AL (H = bouton), valeurs arrondies
# =============================================
# G (index 6) ... AL (index 37) inclus
INDEX_START = 6
INDEX_END_EXCL = 38  # python slice exclut la fin -> 38 = AL inclus

html = [f"<div class='details-panel'>"]
if st.session_state["selected_ref"]:
    sel = str(st.session_state["selected_ref"]).strip()
    rowset = data_df[data_df[REF_COL].astype(str).str.strip() == sel]
    if not rowset.empty:
        r = rowset.iloc[0]
        ref_title = parse_ref_display(sel)

        html.append("<h3 style='margin:0 0 6px 0;'>🔍 Détails de l'annonce</h3>")
        html.append(f"<h4 style='color:{COLOR_SMBG_COPPER};margin:0 0 10px 0;'>Réf. : {ref_title}</h4>")

        all_cols = data_df.columns.tolist()
        cols_slice = all_cols[INDEX_START:INDEX_END_EXCL] if len(all_cols) >= INDEX_END_EXCL else all_cols[INDEX_START:]
        html.append("<h5 style='margin:6px 0 8px;'>📋 Données clés</h5>")
        html.append("<table>")
        for idx, champ in enumerate(cols_slice, start=INDEX_START):
            val = r.get(champ, '')
            s = str(val).strip()
            if s in ('', '-', '/'):
                continue
            # Colonne H -> bouton Google Maps (index 7 si G=6)
            if idx == (INDEX_START + 1) or champ.lower().strip() in ['lien google maps','google maps','lien google']:
                html.append(
                    f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>Lien Google Maps</td>"
                    f"<td><a class='maps-button' href='{s}' target='_blank'>Cliquer ici</a></td></tr>"
                )
                continue
            unit = '€' if any(k in champ for k in ['Loyer','Charges','garantie','Taxe','Marketing','Gestion','BP','annuel','Mensuel','foncière','Honoraires']) \
                   else ('m²' if any(k in champ for k in ['Surface','GLA','utile','Vitrine','Linéaire']) else '')
            html.append(
                f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>{champ}</td>"
                f"<td>{format_value(s, unit)}</td></tr>"
            )
        html.append("</table>")

        # Photos (placeholder pour l’instant)
        html.append("<hr style='border:1px solid #eee;margin:12px 0;'>")
        html.append("<h5 style='margin:6px 0 8px;'>📷 Photos</h5>")
        html.append("<div class='small-note'>Les photos seront affichées ici dès qu'elles seront en ligne.</div>")

html.append("</div>")
st.markdown("".join(html), unsafe_allow_html=True)

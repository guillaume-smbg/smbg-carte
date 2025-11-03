# -*- coding: utf-8 -*-
import os, base64, glob
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
import re

# =============================================
# CONFIGURATION
# =============================================
st.set_page_config(layout="wide", page_title="Carte Interactive SMBG")

COLOR_SMBG_BLUE = "#05263D"
COLOR_SMBG_COPPER = "#C67B42"

LOGO_FILE_PATH_URL = "assets/Logo bleu crop.png"   # asset local
EXCEL_FILE_PATH = "data/Liste des lots.xlsx"

REF_COL = "Référence annonce"
COL_REGION = "Région"
COL_DEPARTEMENT = "Département"
COL_EMPLACEMENT = "Emplacement"
COL_TYPOLOGIE = "Typologie"
COL_RESTAURATION = "Restauration"
COL_SURFACE = "Surface GLA"
COL_LOYER = "Loyer annuel"
COL_SURFACES_LOTS = "Surfaces des lots"

# =============================================
# POLICE FUTURA (depuis ./assets/*.ttf, embarquée en base64)
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
            if "oblique" in name or "italic" in name: style = "italic"
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
    for key in list(st.session_state.keys()):
        if key.startswith(("flt_",)) or key in ("selected_ref", "last_clicked_coords"):
            del st.session_state[key]
    st.session_state["selected_ref"] = None
    st.session_state["last_clicked_coords"] = (0, 0)

if "selected_ref" not in st.session_state:
    st.session_state["selected_ref"] = None
if "last_clicked_coords" not in st.session_state:
    st.session_state["last_clicked_coords"] = (0, 0)

def format_value(value, unit=""):
    val_str = str(value).strip()
    if val_str in ("N/A", "nan", "", "None", "None €", "None m²", "/"):
        return "Non renseigné"
    try:
        num = float(val_str.replace("€","").replace("m²","").replace("m2","").replace(" ", "").replace(",", "."))
        txt = f"{num:,.0f}".replace(",", " ")
        return f"{txt} {unit}".strip() if unit else txt
    except Exception:
        return val_str

@st.cache_data
def load_data(file_path):
    df = pd.read_excel(file_path, dtype={REF_COL: str})
    df.columns = df.columns.str.strip()
    df[REF_COL] = df[REF_COL].astype(str).str.replace(".0", "").str.strip()
    df["Latitude"]  = pd.to_numeric(df.get("Latitude", 0), errors="coerce")
    df["Longitude"] = pd.to_numeric(df.get("Longitude", 0), errors="coerce")
    df.dropna(subset=["Latitude","Longitude"], inplace=True)
    # Loyer numérique pour slider
    df["__LOYER_NUM__"] = pd.to_numeric(df.get(COL_LOYER, ""), errors="coerce")
    return df

# =============================================
# LOAD
# =============================================
data_df = load_data(EXCEL_FILE_PATH)

# =============================================
# CSS (réserve l’espace du volet droit + styles SMBG)
# =============================================
st.markdown(f"""
<style>
{_load_futura_css_from_assets()}

/* Réserve 380px à droite pour que la carte ne soit pas recouverte */
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
# SIDEBAR (filtres rétablis)
# =============================================
with st.sidebar:
    st.image(LOGO_FILE_PATH_URL, use_column_width=True)
    st.markdown("")

    # Loyer slider
    loyer_min = int(np.nanmin(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 0
    loyer_max = int(np.nanmax(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 100000
    lmin, lmax = st.slider(
        "Loyer annuel (€)", min_value=loyer_min, max_value=loyer_max,
        value=(loyer_min, loyer_max), step=1000, key="flt_loyer"
    )

    # Emplacement / Typologie / Restauration
    opts_emp  = sorted([x for x in data_df[COL_EMPLACEMENT].dropna().astype(str).unique() if x.strip()])
    opts_typo = sorted([x for x in data_df[COL_TYPOLOGIE].dropna().astype(str).unique() if x.strip()])
    opts_rest = sorted([x for x in data_df[COL_RESTAURATION].dropna().astype(str).unique() if x.strip()])

    sel_emp  = st.multiselect("Emplacement", opts_emp, key="flt_emp")
    sel_typo = st.multiselect("Typologie", opts_typo, key="flt_typo")
    sel_rest = st.multiselect("Restauration", opts_rest, key="flt_rest")

    st.markdown("")
    st.info(f"Annonces sur la carte : **{len(data_df)}**")
    st.button("Réinitialiser tous les filtres", key="flt_reset", use_container_width=True, on_click=reset_all_filters)

# =============================================
# APPLICATION DES FILTRES
# =============================================
filtered_df = data_df.copy()

# Loyer
filtered_df = filtered_df[
    (filtered_df["__LOYER_NUM__"].isna()) |
    ((filtered_df["__LOYER_NUM__"] >= lmin) & (filtered_df["__LOYER_NUM__"] <= lmax))
]

# Emplacement
if sel_emp:
    filtered_df = filtered_df[filtered_df[COL_EMPLACEMENT].astype(str).isin(sel_emp)]

# Typologie
if sel_typo:
    filtered_df = filtered_df[filtered_df[COL_TYPOLOGIE].astype(str).isin(sel_typo)]

# Restauration
if sel_rest:
    filtered_df = filtered_df[filtered_df[COL_RESTAURATION].astype(str).isin(sel_rest)]

# Compteur après filtres
with st.sidebar:
    st.markdown("")
    st.info(f"Annonces sur la carte : **{len(filtered_df)}**")

# =============================================
# CARTE
# =============================================
MAP_HEIGHT = 800
df_to_map = filtered_df

def ref_label(refv):
    try:
        return str(int(float(refv)))
    except Exception:
        return str(refv)

if not df_to_map.empty:
    m = folium.Map(
        location=[df_to_map["Latitude"].mean(), df_to_map["Longitude"].mean()],
        zoom_start=6, control_scale=True
    )
    for _, row in df_to_map.iterrows():
        lat, lon = row["Latitude"], row["Longitude"]
        ref_disp = ref_label(row[REF_COL])
        html_pin = f"""
        <div style="width:30px;height:30px;border-radius:50%;
                    background:{COLOR_SMBG_BLUE};
                    display:flex;align-items:center;justify-content:center;
                    color:#fff;font-weight:700;font-size:12px;border:1px solid #001a27;">
            {ref_disp}
        </div>"""
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(html=html_pin, class_name="smbg-divicon",
                                 icon_size=(30,30), icon_anchor=(15,15))
        ).add_to(m)

    map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=["last_clicked"], key="map")
    if map_output and map_output.get("last_clicked"):
        clicked = map_output["last_clicked"]
        current_coords = (clicked["lat"], clicked["lng"])
        df_to_map["__dist_sq"] = (df_to_map["Latitude"] - current_coords[0])**2 + (df_to_map["Longitude"] - current_coords[1])**2
        closest_row = df_to_map.loc[df_to_map["__dist_sq"].idxmin()]
        st.session_state["selected_ref"] = closest_row[REF_COL]
else:
    st.info("⚠️ Aucun lot à afficher.")

# =============================================
# VOLET DROIT : G→AH (H bouton) + TABLEAU COMPLET
# =============================================
html = [f"<div class='details-panel'>"]
if st.session_state["selected_ref"]:
    sel = str(st.session_state["selected_ref"]).strip()
    rowset = data_df[data_df[REF_COL].astype(str).str.strip() == sel]
    if not rowset.empty:
        r = rowset.iloc[0]
        try:
            ref_title = str(int(float(sel)))
        except Exception:
            ref_title = sel

        html.append("<h3 style='margin:0 0 6px 0;'>🔍 Détails du Lot</h3>")
        html.append(f"<h4 style='color:{COLOR_SMBG_COPPER};margin:0 0 10px 0;'>Réf. : {ref_title}</h4>")

        # --- Tranche G→AH (index 6..33), H = bouton Google Maps ---
        all_cols = data_df.columns.tolist()
        cols_slice = all_cols[6:34] if len(all_cols) >= 34 else all_cols[6:]
        html.append("<h5 style='margin:6px 0 8px;'>📋 Données clés</h5>")
        html.append("<table>")
        for idx, champ in enumerate(cols_slice, start=6):
            val = r.get(champ, '')
            s = str(val).strip()
            if s in ('', '-', '/'):
                continue
            if idx == 7 or champ.lower().strip() in ['lien google maps','google maps','lien google']:
                html.append(
                    f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>Lien Google Maps</td>"
                    f"<td><a class='maps-button' href='{s}' target='_blank'>Cliquer ici</a></td></tr>"
                )
                continue
            unit = '€' if any(k in champ for k in ['Loyer','Charges','garantie','Taxe','Marketing','Gestion','BP','annuel','Mensuel','foncière']) \
                   else ('m²' if any(k in champ for k in ['Surface','GLA','utile']) else '')
            html.append(
                f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>{champ}</td>"
                f"<td>{format_value(s, unit)}</td></tr>"
            )
        html.append("</table>")

        # --- Tableau complet (transposé) dans le volet droit ---
        df_full = rowset.copy()
        for c in ['distance_sq','__dist_sq']:
            if c in df_full.columns:
                df_full.drop(columns=[c], inplace=True)
        tdf = df_full.T.reset_index()
        tdf.columns = ['Champ','Valeur']

        def _fmt_row(row):
            champ = str(row['Champ'])
            val = row['Valeur']
            unit = '€' if any(k in champ for k in ['Loyer','Charges','garantie','Taxe','Marketing','Gestion','BP','annuel','Mensuel','foncière']) \
                   else ('m²' if any(k in champ for k in ['Surface','GLA','utile']) else '')
            return format_value(val, unit)

        tdf['Valeur'] = tdf.apply(_fmt_row, axis=1)

        html.append("<hr style='border:1px solid #eee;margin:12px 0;'>")
        html.append("<h5 style='margin:6px 0 8px;'>📑 Annonce complète</h5>")
        html.append("<table>")
        for _, rr in tdf.iterrows():
            champ = str(rr['Champ'])
            val = str(rr['Valeur'])
            if champ in ['Latitude','Longitude']:
                continue
            html.append(
                f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>{champ}</td><td>{val}</td></tr>"
            )
        html.append("</table>")
html.append("</div>")
st.markdown("".join(html), unsafe_allow_html=True)

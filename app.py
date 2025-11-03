# -*- coding: utf-8 -*-
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

LOGO_FILE_PATH_URL = "https://raw.githubusercontent.com/guillaume-smbg/smbg-carte/main/assets/Logo%20bleu%20crop.png"
EXCEL_FILE_PATH = "data/Liste des lots.xlsx"

REF_COL = "Référence annonce"
COL_REGION = "Région"
COL_DEPARTEMENT = "Département"
COL_EMPLACEMENT = "Emplacement"
COL_TYPOLOGIE = "Typologie"
COL_RESTAURATION = "Restauration"
COL_SURFACE = "Surface GLA"
COL_LOYER = "Loyer annuel"
COL_NB_LOTS = "Nombre de lots"
COL_SURFACES_LOTS = "Surfaces des lots"
COL_LOYER_UNITAIRE = "Loyer en €/m²"

COL_SURFACE_MIN = "Surface Min"
COL_SURFACE_MAX = "Surface Max"
COL_LOYER_MIN = "Loyer Annuel Min"
COL_LOYER_MAX = "Loyer Annuel Max"

# =============================================
# UTILITAIRES
# =============================================
def reset_all_filters():
    for key in list(st.session_state.keys()):
        if key.startswith(("reg_", "dept_", "emp_", "type_", "rest_")) or key in ("surface_range", "loyer_range"):
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

def format_monetary_value(row):
    champ = row["Champ"]
    value = row["Valeur"]
    val_str = str(value).strip()
    if val_str in ("N/A", "nan", "", "None", "None €", "None m²", "/"):
        return "Non renseigné"
    is_money_col = any(k in champ.lower() for k in ["loyer","charges","garantie","foncière","taxe","marketing","gestion","bp","annuel","mensuel","prix"])
    is_surface_col = any(k in champ.lower() for k in ["surface","gla","utile"])
    try:
        num = float(str(value).replace("€","").replace("m²","").replace("m2","").replace(" ", "").replace(",", "."))
        txt = f"{num:,.0f}".replace(",", " ")
        if is_money_col:
            return f"€{txt}"
        if is_surface_col:
            return f"{txt} m²"
        return txt
    except Exception:
        return val_str

def extract_surface_bounds(row):
    s = str(row.get(COL_SURFACES_LOTS, "")).lower().replace("m²", "").replace("m2", "").strip()
    s = s.replace(",", ".").replace(" ", "")
    m = re.search(r"(\d+\.?\d*)\s*(?:à|-|–)\s*(\d+\.?\d*)", s)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        return pd.Series([min(a,b), max(a,b)])
    parts = re.findall(r"\d+\.?\d*", s)
    if parts:
        nums = [float(x) for x in parts]
        return pd.Series([min(nums), max(nums)])
    gla = pd.to_numeric(row.get(COL_SURFACE, 0), errors="coerce")
    if pd.notna(gla) and gla > 0:
        return pd.Series([gla, gla])
    return pd.Series([0.0, 0.0])

@st.cache_data
def load_data(file_path):
    df = pd.read_excel(file_path, dtype={REF_COL: str})
    df.columns = df.columns.str.strip()
    df[REF_COL] = df[REF_COL].astype(str).str.replace(".0", "").str.zfill(5)
    df[[COL_SURFACE_MIN, COL_SURFACE_MAX]] = df.apply(extract_surface_bounds, axis=1)
    df["Latitude"] = pd.to_numeric(df.get("Latitude", 0), errors="coerce")
    df["Longitude"] = pd.to_numeric(df.get("Longitude", 0), errors="coerce")
    df.dropna(subset=["Latitude", "Longitude"], inplace=True)
    return df

# =============================================
# CHARGEMENT
# =============================================
data_df = load_data(EXCEL_FILE_PATH)
filtered_df = data_df.copy()

# =============================================
# CSS
# =============================================
st.markdown(f"""
<style>
.details-panel {{
  position: fixed; top: 0; right: 0; width: 300px; height: 100vh;
  background-color: {COLOR_SMBG_BLUE}; color: white; z-index: 1000;
  padding: 15px; box-shadow: -5px 0 15px rgba(0,0,0,0.4); overflow-y: auto;
}}
[data-testid="stSidebar"] {{ background-color: {COLOR_SMBG_BLUE}; color: white; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {{ color: {COLOR_SMBG_COPPER} !important; }}
.stImage > button {{ display: none !important; }}
.maps-button {{
  width: 100%; padding: 8px; margin-bottom: 12px; background-color: {COLOR_SMBG_COPPER};
  color: white; border: none; border-radius: 6px; cursor: pointer; text-align: center; font-weight: bold;
}}
.details-panel table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.details-panel tr {{ border-bottom: 1px solid #304f65; }}
.details-panel td {{ padding: 5px 0; max-width: 50%; overflow-wrap: break-word; }}
</style>
""", unsafe_allow_html=True)

# =============================================
# SIDEBAR
# =============================================
with st.sidebar:
    st.image(LOGO_FILE_PATH_URL, use_column_width=True)
    st.markdown("---")
    st.info(f"Annonces chargées : **{len(data_df)}**")
    if st.button("Réinitialiser tous les filtres", use_container_width=True, type="secondary"):
        reset_all_filters()
        st.rerun()
    st.markdown("---")

# =============================================
# CARTE
# =============================================
MAP_HEIGHT = 800
df_to_map = filtered_df

def ref_label(ref5):
    try:
        return str(int(ref5))
    except Exception:
        return str(ref5)

if not df_to_map.empty:
    m = folium.Map(location=[df_to_map["Latitude"].mean(), df_to_map["Longitude"].mean()], zoom_start=6, control_scale=True)
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
# PANNEAU DROIT
# =============================================
html = [f"<div class='details-panel'>"]
if st.session_state["selected_ref"]:
    sel = st.session_state["selected_ref"].strip()
    rowset = data_df[data_df[REF_COL].str.strip() == sel]
    if not rowset.empty:
        r = rowset.iloc[0]
        try:
            ref_title = str(int(sel))
        except ValueError:
            ref_title = sel
        html.append(f"<h3>🔍 Détails du Lot</h3><h4 style='color:{COLOR_SMBG_COPPER};'>Réf. : {ref_title}</h4>")
        html.append("<hr style='border:1px solid #eee;'>")
        all_cols = data_df.columns.tolist()
        cols_slice = all_cols[6:34] if len(all_cols) >= 34 else all_cols[6:]
        html.append("<table>")
        for idx, champ in enumerate(cols_slice, start=6):
            val = r.get(champ, '')
            s = str(val).strip()
            if s in ('', '-', '/'):
                continue
            if idx == 7 or champ.lower().strip() in ['lien google maps','google maps','lien google']:
                html.append(f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>Lien Google Maps</td><td><a class='maps-button' href='{s}' target='_blank'>Cliquer ici</a></td></tr>")
                continue
            unit = '€' if any(k in champ for k in ['Loyer','Charges','garantie','Taxe','Marketing','Gestion','BP','annuel','Mensuel','foncière']) else ('m²' if any(k in champ for k in ['Surface','GLA','utile']) else '')
            html.append(f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>{champ}</td><td>{format_value(s, unit)}</td></tr>")
        html.append("</table>")
html.append("</div>")
st.markdown("".join(html), unsafe_allow_html=True)

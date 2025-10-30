import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from io import BytesIO
import requests
import math
import re
from typing import Dict, Tuple


st.set_page_config(
    page_title="SMBG Carte",
    layout="wide",
)

LOGO_BLUE = "#05263d"
COPPER = "#b87333"
PANEL_WIDTH_PX = 275

GLOBAL_CSS = f"""
<style>
.stApp {{
    background-color: #ffffff;
    font-family: 'Futura', sans-serif;
}}
header[data-testid="stHeader"] {{
    background: transparent;
}}
.main-layout {{
    display: grid;
    grid-template-columns: {PANEL_WIDTH_PX}px 1fr {PANEL_WIDTH_PX}px;
    grid-template-rows: 100vh;
    overflow: hidden;
    width: 100%;
    height: 100vh;
    margin: 0;
    box-sizing: border-box;
    background-color: #ffffff;
    font-family: 'Futura', sans-serif;
}}
.left-panel {{
    background-color: {LOGO_BLUE};
    color: #ffffff;
    padding: 16px;
    font-family: 'Futura', sans-serif;
    border-right: 1px solid rgba(255,255,255,0.15);
    overflow-y: auto;
}}
.left-panel * {{
    color: #ffffff !important;
    font-family: 'Futura', sans-serif !important;
}}
.section-title {{
    font-weight: 600;
    font-size: 15px;
    margin-bottom: 8px;
    line-height: 1.3;
}}
.copper-btn {{
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
.map-panel-wrapper {{
    position: relative;
    background-color: #f5f5f5;
    overflow: hidden;
    font-family: 'Futura', sans-serif;
}}
.map-inner {{
    position: absolute;
    inset: 0;
    padding: 0;
    margin: 0;
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
.right-panel {{
    background-color: #ffffff;
    color: #000000;
    padding: 16px;
    font-family: 'Futura', sans-serif;
    border-left: 1px solid rgba(0,0,0,0.1);
    overflow-y: auto;
}}
.right-panel * {{
    font-family: 'Futura', sans-serif !important;
    color: #000000;
}}
.ref-header {{
    background-color: {LOGO_BLUE};
    color: #ffffff;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.4;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 12px;
    font-family: 'Futura', sans-serif;
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
    font-family: 'Futura', sans-serif;
}}
.gmaps-link {{
    display: inline-block;
    background-color: {COPPER};
    color: #ffffff !important;
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    line-height: 1.3;
    padding: 6px 10px;
    border-radius: 6px;
    margin-bottom: 12px;
    font-family: 'Futura', sans-serif;
}}
.addr-block {{
    font-size: 13px;
    line-height: 1.4;
    font-family: 'Futura', sans-serif;
    margin-bottom: 12px;
}}
.addr-line1 {{
    font-weight: 600;
    color: #000000;
    font-family: 'Futura', sans-serif;
}}
.addr-line2 {{
    color: #000000;
    font-family: 'Futura', sans-serif;
}}
.detail-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    line-height: 1.4;
    font-family: 'Futura', sans-serif;
}}
.detail-table tr td {{
    vertical-align: top;
    padding: 6px 8px;
    border-bottom: 1px solid #e0e0e0;
    color: #000000;
    font-family: 'Futura', sans-serif;
}}
.label-col {{
    width: 40%;
    font-weight: 600;
    font-size: 12px;
    color: {LOGO_BLUE};
    font-family: 'Futura', sans-serif;
}}
.value-col {{
    width: 60%;
    font-weight: 400;
    font-size: 12px;
    color: #000000;
    font-family: 'Futura', sans-serif;
}}
.placeholder-panel {{
    font-size: 13px;
    line-height: 1.4;
    color: #000;
    opacity: 0.7;
    font-family: 'Futura', sans-serif;
    background-color: #f8f8f8;
    border: 1px dashed #ccc;
    border-radius: 8px;
    padding: 12px;
}}
</style>
"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

if "selected_ref" not in st.session_state:
    st.session_state["selected_ref"] = None
if "df" not in st.session_state:
    st.session_state["df"] = None

def load_excel_from_url(url: str) -> pd.DataFrame:
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.content
    df_local = pd.read_excel(BytesIO(data))
    return df_local

EXCEL_URL = st.secrets.get("EXCEL_URL", "")

load_error = None
if EXCEL_URL and st.session_state["df"] is None:
    try:
        st.session_state["df"] = load_excel_from_url(EXCEL_URL)
    except Exception as e:
        load_error = f"Erreur chargement Excel : {e}"

df_raw = st.session_state["df"]
if df_raw is None or (isinstance(df_raw, pd.DataFrame) and df_raw.empty):
    df_raw = pd.DataFrame({
        "Référence annonce": ["-"],
        "Latitude": [46.5],
        "Longitude": [2.5],
        "Adresse": [""],
        "Adresse complète": [""],
        "Ville": [""],
        "Lien Google Maps": [""],
        "Surface totale (m²)": [""],
        "Loyer mensuel (€)": [""],
        "Charges mensuelles (€)": [""],
        "Taxe foncière annuelle (€)": [""],
        "Commentaires": ["Aucune donnée disponible"],
        "Actif": ["non"],
        "Date publication": [""],
    })

REQUIRED_COLS = [
    "Référence annonce","Latitude","Longitude","Adresse","Adresse complète","Ville",
    "Lien Google Maps","Surface totale (m²)","Loyer mensuel (€)","Charges mensuelles (€)",
    "Taxe foncière annuelle (€)","Commentaires","Actif","Date publication",
]

for c in REQUIRED_COLS:
    if c not in df_raw.columns:
        df_raw[c] = ""

def _is_num(x):
    try:
        return not math.isnan(float(x))
    except:
        return False

df_active = df_raw[df_raw["Actif"].astype(str).str.lower().eq("oui")].copy()
df_active = df_active[
    df_active["Latitude"].apply(_is_num)
    & df_active["Longitude"].apply(_is_num)
].copy()

if df_active.empty:
    df_active = pd.DataFrame([{
        "Référence annonce": "Aucune",
        "Latitude": 46.5,
        "Longitude": 2.5,
        "Adresse": "",
        "Adresse complète": "",
        "Ville": "",
        "Lien Google Maps": "",
        "Surface totale (m²)": "",
        "Loyer mensuel (€)": "",
        "Charges mensuelles (€)": "",
        "Taxe foncière annuelle (€)": "",
        "Commentaires": "Aucune donnée disponible",
        "Actif": "non",
        "Date publication": "",
    }])

def normalize_ref_str(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if re.match(r"^\d+\.0+$", s):
        return s.split(".")[0]
    return s

df_active["ref_clean"] = df_active["Référence annonce"].apply(normalize_ref_str)

def sanitize_value(v):
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s in ["-", "/", ""]:
        return ""
    return s

def is_recent(date_val, days=30):
    if pd.isna(date_val) or str(date_val).strip() == "":
        return False
    try:
        dt = pd.to_datetime(date_val, dayfirst=True, errors="coerce")
    except:
        dt = pd.NaT
    if pd.isna(dt):
        return False
    now = pd.Timestamp.now(tz="Europe/Paris").normalize()
    delta = now - dt.normalize()
    return delta.days <= days

def build_info_table_for_row(row: pd.Series) -> str:
    EXCLUDE = {
        "Latitude","Longitude","Actif","Référence annonce",
        "Lien Google Maps","Adresse","Adresse complète","Ville","Date publication",
    }
    rows_html = []
    for colname, value in row.items():
        if colname in EXCLUDE:
            continue
        cleaned = sanitize_value(value)
        if cleaned == "":
            continue
        rows_html.append(
            f"<tr><td class='label-col'>{colname}</td>"
            f"<td class='value-col'>{cleaned}</td></tr>"
        )
    if not rows_html:
        return "<div class='placeholder-panel'>Aucune information disponible pour cette annonce.</div>"
    return "<table class='detail-table'>" + "".join(rows_html) + "</table>"

def render_right_panel(selected_ref, df_full, load_error_msg):
    if load_error_msg:
        st.markdown(
            f"<div style='color:#b00020;font-size:12px;font-weight:600;"
            f"font-family:Futura, sans-serif;margin-bottom:12px;'>"
            f"{load_error_msg}<br/>Vérifie EXCEL_URL."
            f"</div>",
            unsafe_allow_html=True,
        )

    if not selected_ref:
        st.markdown(
            "<div class='placeholder-panel'>"
            "Aucune sélection. Sélectionnez une annonce sur la carte."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    mask = df_full["Référence annonce"].astype(str) == str(selected_ref)
    sub = df_full[mask].copy()
    if sub.empty:
        st.markdown(
            "<div class='placeholder-panel'>Annonce introuvable.</div>",
            unsafe_allow_html=True,
        )
        return

    row = sub.iloc[0]

    ref_display = normalize_ref_str(row.get("Référence annonce", ""))
    gmaps_url = sanitize_value(row.get("Lien Google Maps", ""))
    adresse_full = sanitize_value(row.get("Adresse complète", "")) or sanitize_value(row.get("Adresse", ""))
    ville = sanitize_value(row.get("Ville", ""))
    date_pub = row.get("Date publication", "")

    badge_html = "<span class='badge-nouveau'>Nouveau</span>" if is_recent(date_pub) else ""

    st.markdown(
        f"<div class='ref-header'><div>Réf. {ref_display}</div><div>{badge_html}</div></div>",
        unsafe_allow_html=True,
    )

    if gmaps_url:
        st.markdown(
            f"<a class='gmaps-link' href='{gmaps_url}' target='_blank' rel='noopener noreferrer'>Cliquer ici</a>",
            unsafe_allow_html=True,
        )

    addr_html = "<div class='addr-block'>"
    if adresse_full:
        addr_html += f"<div class='addr-line1'>{adresse_full}</div>"
    if ville:
        addr_html += f"<div class='addr-line2'>{ville}</div>"
    addr_html += "</div>"
    st.markdown(addr_html, unsafe_allow_html=True)

    table_html = build_info_table_for_row(row)
    st.markdown(table_html, unsafe_allow_html=True)

def to_num_clean(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(" ", "").str.replace(",", "."),
        errors="coerce"
    )

def build_filters_ui(df_scope: pd.DataFrame):
    st.markdown("<div class='section-title'>Filtres</div>", unsafe_allow_html=True)

    if "Surface totale (m²)" in df_scope.columns:
        surf_series = to_num_clean(df_scope["Surface totale (m²)"])
        if not surf_series.dropna().empty:
            s_min = int(surf_series.min()); s_max = int(surf_series.max())
        else:
            s_min, s_max = 0, 1000
    else:
        s_min, s_max = 0, 1000
        surf_series = pd.Series([], dtype=float)

    if "Loyer mensuel (€)" in df_scope.columns:
        loy_series = to_num_clean(df_scope["Loyer mensuel (€)"])
        if not loy_series.dropna().empty:
            l_min = int(loy_series.min()); l_max = int(loy_series.max())
        else:
            l_min, l_max = 0, 50000
    else:
        l_min, l_max = 0, 50000
        loy_series = pd.Series([], dtype=float)

    surf_range = st.slider("Surface (m²)", s_min, s_max, (s_min, s_max), step=1)
    loyer_range = st.slider("Loyer mensuel (€)", l_min, l_max, (l_min, l_max), step=100)

    reset_clicked = st.button("Réinitialiser les filtres")

    st.markdown("<button class='copper-btn'>Partager toutes les annonces</button>", unsafe_allow_html=True)
    st.markdown("<button class='copper-btn'>Partager mes favoris</button>", unsafe_allow_html=True)
    st.markdown("<button class='copper-btn'>Je suis intéressé</button>", unsafe_allow_html=True)

    return {
        "surf_range": surf_range,
        "loyer_range": loyer_range,
        "reset": reset_clicked,
    }

def apply_filters(df_scope: pd.DataFrame, surf_range, loyer_range):
    out_df = df_scope.copy()
    if "Surface totale (m²)" in out_df.columns:
        vals_surface = to_num_clean(out_df["Surface totale (m²)"])
        mask_surface = ((vals_surface >= surf_range[0]) & (vals_surface <= surf_range[1])) | vals_surface.isna()
        out_df = out_df[mask_surface]
    if "Loyer mensuel (€)" in out_df.columns:
        vals_loyer = to_num_clean(out_df["Loyer mensuel (€)"])
        mask_loyer = ((vals_loyer >= loyer_range[0]) & (vals_loyer <= loyer_range[1])) | vals_loyer.isna()
        out_df = out_df[mask_loyer]
    return out_df

def anti_overlap_positions(df_points: pd.DataFrame, lat_col: str, lon_col: str) -> pd.DataFrame:
    if df_points.empty:
        df_points["_lat_plot"] = []
        df_points["_lon_plot"] = []
        return df_points
    grouped = {}
    for idx, r in df_points.iterrows():
        key = (round(float(r[lat_col]), 6), round(float(r[lon_col]), 6))
        grouped.setdefault(key, []).append(idx)
    new_lat = {}
    new_lon = {}
    for key, idxs in grouped.items():
        base_lat, base_lon = key
        n_same = len(idxs)
        if n_same == 1:
            i = idxs[0]
            new_lat[i] = base_lat
            new_lon[i] = base_lon
        else:
            radius = 0.0005
            for n, i in enumerate(idxs):
                ang = 2 * math.pi * (n / n_same)
                new_lat[i] = base_lat + radius * math.sin(ang)
                new_lon[i] = base_lon + radius * math.cos(ang)
    df_points = df_points.copy()
    df_points["_lat_plot"] = df_points.index.map(new_lat)
    df_points["_lon_plot"] = df_points.index.map(new_lon)
    return df_points

def build_map_and_registry(df_for_map: pd.DataFrame):
    m = folium.Map(location=[46.5, 2.5], zoom_start=6, tiles="OpenStreetMap")

    css_marker = (
        f"background:{LOGO_BLUE};color:#fff;border:2px solid #fff;"
        "width:28px;height:28px;line-height:28px;"
        "border-radius:50%;text-align:center;"
        "font-size:11px;font-weight:600;"
        "font-family:'Futura',sans-serif;"
        "box-shadow:0 2px 4px rgba(0,0,0,.4);"
    )

    registry: Dict[Tuple[float, float], str] = {}

    for _, r in df_for_map.iterrows():
        lat = float(r["_lat_plot"])
        lon = float(r["_lon_plot"])
        label_txt = normalize_ref_str(r.get("ref_clean", ""))

        icon = folium.DivIcon(
            html=f'<div style="{css_marker}">{label_txt}</div>',
            icon_size=(28, 28),
            icon_anchor=(14, 14),
            class_name="smbg-divicon"
        )

        folium.Marker(
            location=[lat, lon],
            icon=icon,
        ).add_to(m)

        registry[(round(lat,6), round(lon,6))] = label_txt

    return m, registry

# --------- RENDU UI ---------

st.markdown("<div class='main-layout'>", unsafe_allow_html=True)

# Colonne gauche
with st.container():
    st.markdown("<div class='left-panel'>", unsafe_allow_html=True)

    filters_state = build_filters_ui(df_active)
    if filters_state["reset"]:
        st.experimental_rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# Colonne carte
with st.container():
    # On affiche toujours le conteneur, même si la carte plante
    st.markdown("<div class='map-panel-wrapper'><div class='map-inner'>", unsafe_allow_html=True)

    clicked_ref = None
    try:
        df_filtered = apply_filters(df_active, filters_state["surf_range"], filters_state["loyer_range"])

        grouped = (
            df_filtered.sort_values("Référence annonce")
            .groupby("Référence annonce", as_index=False)
            .first()
        )

        work_refs = grouped[["Référence annonce", "ref_clean", "Latitude", "Longitude"]].dropna(subset=["Latitude","Longitude"]).copy()
        work_refs = anti_overlap_positions(work_refs, "Latitude", "Longitude")

        folium_map, registry = build_map_and_registry(work_refs)

        # IMPORTANT : version ultra-compatible
        folium_out = st_folium(folium_map, width=None, height=800)

        if isinstance(folium_out, dict) and "last_object_clicked" in folium_out:
            loc = folium_out["last_object_clicked"]
            if isinstance(loc, dict) and "lat" in loc and "lng" in loc:
                key = (round(float(loc["lat"]),6), round(float(loc["lng"]),6))
                if key in registry:
                    clicked_ref = registry[key]

        if clicked_ref:
            st.session_state["selected_ref"] = clicked_ref

    except Exception as map_err:
        st.markdown(
            f"<div class='map-error'>Erreur carte : {map_err}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div></div>", unsafe_allow_html=True)

# Colonne droite
with st.container():
    st.markdown("<div class='right-panel'>", unsafe_allow_html=True)

    render_right_panel(
        st.session_state.get("selected_ref"),
        df_raw,
        load_error,
    )

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

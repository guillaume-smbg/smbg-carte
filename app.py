# -*- coding: utf-8 -*-
import os, base64, glob, math, re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np

# -------------------- CONFIG --------------------
st.set_page_config(layout="wide", page_title="Carte Interactive SMBG")
COLOR_SMBG_BLUE   = "#05263D"
COLOR_SMBG_COPPER = "#C67B42"
LOGO_FILE_PATH_URL = "assets/Logo bleu crop.png"
EXCEL_FILE_PATH    = "data/Liste des lots.xlsx"

# Entêtes attendues
REF_COL          = "Référence annonce"
REGION_COL       = "Région"
DEPT_COL         = "Département"
EMPL_COL         = "Emplacement"
TYPO_COL         = "Typologie"
EXTRACTION_COL   = "Extraction"
RESTAURATION_COL = "Restauration"
SURFACE_COL      = "Surface GLA"
LOYER_COL        = "Loyer annuel"
LAT_COL          = "Latitude"
LON_COL          = "Longitude"
ACTIF_COL        = "Actif"  # "oui"/"non"

# Volet droit : colonnes G -> AL (H = bouton)
INDEX_START     = 6     # G
INDEX_END_EXCL  = 38    # AL (slice exclusif)

MAP_HEIGHT = 800

# -------------------- Police Futura --------------------
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
    css = []
    for fp in files[:4]:
        try:
            with open(fp, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            name = os.path.basename(fp).lower()
            weight = "400"; style = "normal"
            if "bold"   in name: weight = "700"
            if "medium" in name: weight = "500"
            if "light"  in name: weight = "300"
            if "italic" in name or "oblique" in name: style = "italic"
            css.append(
                f"@font-face {{font-family:'Futura SMBG';src:url(data:font/ttf;base64,{b64}) format('truetype');"
                f"font-weight:{weight};font-style:{style};font-display:swap;}}"
            )
        except Exception:
            pass
    css.append("*{font-family:'Futura SMBG', Futura, 'Futura PT', 'Century Gothic', Arial, sans-serif;}")
    return "\n".join(css)

# -------------------- Helpers --------------------
def parse_ref_display(ref_str):
    s = str(ref_str).strip()
    if "." in s:
        left, right = s.split(".", 1)
        left = re.sub(r"^0+", "", left) or "0"
        return f"{left}.{right}"
    return re.sub(r"^0+", "", s) or "0"

def format_value(value, unit=""):
    s = str(value).strip()
    if s.lower() in ("n/a", "nan", "", "none", "néant", "-", "/"):
        return ""
    try:
        num = float(s.replace("€","").replace("m²","").replace("m2","").replace(" ", "").replace(",", "."))
        txt = f"{num:,.0f}".replace(",", " ")
        return f"{txt} {unit}".strip() if unit else txt
    except Exception:
        return s

def meters_to_deg_lat(m): return m / 111_320.0
def meters_to_deg_lon(m, lat_deg): return m / (111_320.0 * max(0.2, math.cos(math.radians(lat_deg))))

def jitter_group(df, lat_col, lon_col, base_radius_m=12.0, step_m=4.0):
    golden = math.pi * (3 - math.sqrt(5))
    out = []
    for i, (_, r) in enumerate(df.iterrows()):
        lat0, lon0 = r[lat_col], r[lon_col]
        radius_m = base_radius_m + i * step_m
        theta = i * golden
        jlat = lat0 + meters_to_deg_lat(radius_m * math.sin(theta))
        jlon = lon0 + meters_to_deg_lon(radius_m * math.cos(theta), lat0)
        rr = r.copy(); rr["__jlat"] = jlat; rr["__jlon"] = jlon
        out.append(rr)
    return pd.DataFrame(out) if out else df

def reset_all():
    # remet TOUS les checkboxes et sliders à l'état initial
    for k in list(st.session_state.keys()):
        if k.startswith(("chk_", "slider_", "sel_", "selected_ref")):
            del st.session_state[k]
    st.session_state["selected_ref"] = None
    st.session_state["surface_bounds"] = None
    st.session_state["loyer_bounds"]   = None
    st.experimental_rerun()

# -------------------- Data --------------------
@st.cache_data
def load_data(path):
    df = pd.read_excel(path, dtype={REF_COL: str})
    df.columns = df.columns.str.strip()
    df[REF_COL] = df[REF_COL].astype(str).str.replace(".0", "", regex=False).str.strip()
    df[LAT_COL] = pd.to_numeric(df.get(LAT_COL, ""), errors="coerce")
    df[LON_COL] = pd.to_numeric(df.get(LON_COL, ""), errors="coerce")
    df["__SURF_NUM__"]  = pd.to_numeric(df.get(SURFACE_COL, ""), errors="coerce")
    df["__LOYER_NUM__"] = pd.to_numeric(df.get(LOYER_COL, ""), errors="coerce")
    if ACTIF_COL in df.columns:
        df = df[df[ACTIF_COL].astype(str).str.lower().eq("oui")]
    df.dropna(subset=[LAT_COL, LON_COL], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

data_df = load_data(EXCEL_FILE_PATH)

# -------------------- CSS (panneau droit + popup invisible + Futura) --------------------
st.markdown(f"""
<style>
{_load_futura_css_from_assets()}
/* Réserve la place du panneau droit */
[data-testid="stAppViewContainer"] .main .block-container {{ padding-right: 380px; }}
.details-panel {{
  position: fixed; top: 0; right: 0; width: 360px; height: 100vh;
  background-color: {COLOR_SMBG_BLUE}; color: white; z-index: 1000;
  padding: 16px; box-shadow: -5px 0 15px rgba(0,0,0,0.35); overflow-y: auto;
}}
[data-testid="stSidebar"] {{ background-color: {COLOR_SMBG_BLUE}; color: white; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {{ color: {COLOR_SMBG_COPPER} !important; }}
.stImage > button {{ display:none !important; }} /* pas d'agrandissement du logo */
.maps-button {{
  width:100%; padding:9px; margin:8px 0 14px; background:{COLOR_SMBG_COPPER};
  color:#fff; border:none; border-radius:8px; cursor:pointer; text-align:center; font-weight:700;
}}
.details-panel table {{ width:100%; border-collapse:collapse; font-size:13px; }}
.details-panel tr {{ border-bottom:1px solid #304f65; }}
.details-panel td {{ padding:6px 0; max-width:50%; overflow-wrap:break-word; }}
/* On cache visuellement les popups Folium pour éviter l'effet "bulle", tout en gardant l'événement clic */
.leaflet-popup { display:none !important; }
</style>
""", unsafe_allow_html=True)

# -------------------- SIDEBAR : cases imbriquées + sliders --------------------
with st.sidebar:
    st.image(LOGO_FILE_PATH_URL, use_column_width=True)
    st.markdown("")

    # Régions -> Départements imbriqués (cases)
    st.markdown("**Région / Département**")
    regions = sorted([x for x in data_df.get(REGION_COL, pd.Series()).dropna().astype(str).unique() if x.strip()])
    selected_regions = []
    selected_depts   = []

    for reg in regions:
        rkey = f"chk_region_{reg}"
        rchecked = st.checkbox(reg, key=rkey)
        if rchecked:
            selected_regions.append(reg)
        # Afficher les départements de CETTE région, avec indentation
        pool = data_df[data_df[REGION_COL].astype(str).eq(reg)]
        depts = sorted([x for x in pool.get(DEPT_COL, pd.Series()).dropna().astype(str).unique() if x.strip()])
        for d in depts:
            dkey = f"chk_dept_{reg}_{d}"
            dchecked = st.checkbox(f"    {d}", key=dkey)  # indentation visuelle
            if dchecked:
                selected_depts.append(d)
    st.markdown("---")

    # Sliders (bornes stockées pour reset dur)
    surf_min = int(np.nanmin(data_df["__SURF_NUM__"])) if data_df["__SURF_NUM__"].notna().any() else 0
    surf_max = int(np.nanmax(data_df["__SURF_NUM__"])) if data_df["__SURF_NUM__"].notna().any() else 1000
    if "surface_bounds" not in st.session_state:
        st.session_state["surface_bounds"] = (surf_min, surf_max)
    smin, smax = st.slider("Surface GLA (m²)", min_value=surf_min, max_value=surf_max,
                           value=st.session_state["surface_bounds"], step=1, key="slider_surface")

    loyer_min = int(np.nanmin(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 0
    loyer_max = int(np.nanmax(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 100000
    if "loyer_bounds" not in st.session_state:
        st.session_state["loyer_bounds"] = (loyer_min, loyer_max)
    lmin, lmax = st.slider("Loyer annuel (€)", min_value=loyer_min, max_value=loyer_max,
                           value=st.session_state["loyer_bounds"], step=1000, key="slider_loyer")

    # Autres critères (cases simples)
    def draw_checks(title, column, prefix):
        st.markdown(f"**{title}**")
        opts = sorted([x for x in data_df.get(column, pd.Series()).dropna().astype(str).unique() if x.strip()])
        sels = []
        for opt in opts:
            if st.checkbox(opt, key=f"chk_{prefix}_{opt}"):
                sels.append(opt)
        st.markdown("---")
        return sels

    emp_sel  = draw_checks("Emplacement",  EMPL_COL, "emp")
    typo_sel = draw_checks("Typologie",   TYPO_COL, "typo")
    ext_sel  = draw_checks("Extraction",  EXTRACTION_COL, "ext")
    rest_sel = draw_checks("Restauration",RESTAURATION_COL, "rest")

    if st.button("Réinitialiser", use_container_width=True):
        reset_all()

# -------------------- Application des filtres --------------------
filtered = data_df.copy()

# REG/DEP = UNION logique : (région ∈ R) OU (département ∈ D)
cond_reg = filtered[REGION_COL].astype(str).isin(selected_regions) if selected_regions else pd.Series([False]*len(filtered))
cond_dep = filtered[DEPT_COL].astype(str).isin(selected_depts)     if selected_depts   else pd.Series([False]*len(filtered))

if selected_regions or selected_depts:
    filtered = filtered[ cond_reg | cond_dep ]

# Sliders
filtered = filtered[
    (filtered["__SURF_NUM__"].isna()  | ((filtered["__SURF_NUM__"]  >= smin) & (filtered["__SURF_NUM__"]  <= smax))) &
    (filtered["__LOYER_NUM__"].isna() | ((filtered["__LOYER_NUM__"] >= lmin) & (filtered["__LOYER_NUM__"] <= lmax)))
]

# Cases
if emp_sel:
    filtered = filtered[filtered[EMPL_COL].astype(str).isin(emp_sel)]
if typo_sel:
    filtered = filtered[filtered[TYPO_COL].astype(str).isin(typo_sel)]
if ext_sel:
    filtered = filtered[filtered[EXTRACTION_COL].astype(str).isin(ext_sel)]
if rest_sel:
    filtered = filtered[filtered[RESTAURATION_COL].astype(str).isin(rest_sel)]

# -------------------- Carte : tous les pins, clic pin uniquement --------------------
tmp = filtered.copy()
tmp["__lat__"] = tmp[LAT_COL]; tmp["__lon__"] = tmp[LON_COL]
jittered = []
for (_, grp) in tmp.groupby([LAT_COL, LON_COL], as_index=False):
    jittered.append(jitter_group(grp, "__lat__", "__lon__", base_radius_m=12.0, step_m=4.0))
pins_df = pd.concat(jittered, ignore_index=True) if jittered else tmp.copy()

if pins_df.empty:
    center_lat, center_lon = 46.5, 2.5
else:
    center_lat = float(pins_df["__jlat"].mean())
    center_lon = float(pins_df["__jlon"].mean())

m = folium.Map(location=[center_lat, center_lon], zoom_start=6, control_scale=True)

def add_pin(lat, lon, label, ref_value):
    # On met une popup *technique* (capturée par st_folium) et on la rend invisible par CSS
    popup_html = f"<div data-ref='{ref_value}'>{ref_value}</div>"
    icon_html = f"""
    <div style="width:30px;height:30px;border-radius:50%;
                background:{COLOR_SMBG_BLUE};
                display:flex;align-items:center;justify-content:center;
                color:#fff;font-weight:700;font-size:12px;border:1px solid #001a27;">
        {label}
    </div>"""
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(html=icon_html, class_name="smbg-divicon", icon_size=(30,30), icon_anchor=(15,15)),
        popup=popup_html  # permet de capter le clic marker via last_object_clicked
    ).add_to(m)

if not pins_df.empty:
    pins_df["__ref_display__"] = pins_df[REF_COL].apply(parse_ref_display)
    for _, r in pins_df.iterrows():
        add_pin(float(r["__jlat"]), float(r["__jlon"]), r["__ref_display__"], r[REF_COL])

# On NE capte PAS le clic carte ; uniquement le clic marker
map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=["last_object_clicked"], key="map")

# last_object_clicked -> contient la popup du marker cliqué
if map_output and map_output.get("last_object_clicked"):
    obj = map_output["last_object_clicked"]
    # Selon versions, la popup est sous 'popup' ou 'popup_html'
    ref_guess = None
    for k in ("popup", "popup_html"):
        if k in obj and obj[k]:
            # extraire la référence depuis data-ref ou le texte
            txt = str(obj[k])
            mref = re.search(r"data-ref=['\"]([^'\"]+)['\"]", txt)
            ref_guess = mref.group(1) if mref else re.sub(r"<.*?>", "", txt).strip()
            break
    if ref_guess:
        st.session_state["selected_ref"] = ref_guess

# -------------------- VOLET DROIT --------------------
html = [f"<div class='details-panel'>"]
sel_ref = st.session_state.get("selected_ref")
if sel_ref:
    rowset = data_df[data_df[REF_COL].astype(str).str.strip() == str(sel_ref).strip()]
    if not rowset.empty:
        r = rowset.iloc[0]
        ref_title = parse_ref_display(sel_ref)
        html.append("<h3 style='margin:0 0 6px 0;'>🔍 Détails de l'annonce</h3>")
        html.append(f"<h4 style='color:{COLOR_SMBG_COPPER};margin:0 0 10px 0;'>Réf. : {ref_title}</h4>")

        all_cols  = data_df.columns.tolist()
        cols_slice = all_cols[INDEX_START:INDEX_END_EXCL] if len(all_cols) >= INDEX_END_EXCL else all_cols[INDEX_START:]
        html.append("<h5 style='margin:6px 0 8px;'>📋 Données clés</h5>")
        html.append("<table>")
        for idx, champ in enumerate(cols_slice, start=INDEX_START):
            val  = r.get(champ, '')
            sraw = str(val).strip()
            if sraw.lower() in ("", "néant", "-", "/"):
                continue
            # H = bouton Google Maps
            if idx == (INDEX_START + 1) or champ.lower().strip() in ['lien google maps','google maps','lien google']:
                html.append(
                    f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>Lien Google Maps</td>"
                    f"<td><a class='maps-button' href='{sraw}' target='_blank'>Cliquer ici</a></td></tr>"
                ); continue
            unit = '€' if any(k in champ for k in ['Loyer','Charges','garantie','Taxe','Marketing','Gestion','BP','annuel','Mensuel','foncière','Honoraires']) \
                   else ('m²' if any(k in champ for k in ['Surface','GLA','utile','Vitrine','Linéaire']) else '')
            sval = format_value(sraw, unit)
            if not sval:
                continue
            html.append(
                f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>{champ}</td><td>{sval}</td></tr>"
            )
        html.append("</table>")

        html.append("<hr style='border:1px solid #eee;margin:12px 0;'>")
        html.append("<h5 style='margin:6px 0 8px;'>📷 Photos</h5>")
        html.append("<div class='small-note'>Les photos seront affichées ici dès qu'elles seront en ligne.</div>")

html.append("</div>")
st.markdown("".join(html), unsafe_allow_html=True)

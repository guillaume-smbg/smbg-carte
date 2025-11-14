# -*- coding: utf-8 -*-
import os, base64, glob, math, re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
from collections import defaultdict

# ===== CONFIG =====
st.set_page_config(layout="wide", page_title="Carte Interactive SMBG", initial_sidebar_state="expanded")
COLOR_SMBG_BLUE   = "#05263D"
COLOR_SMBG_COPPER = "#C67B42"
LOGO_FILE_PATH    = "assets/Logo bleu crop.png"   # on l’encode en base64 pour supprimer tout bouton
EXCEL_FILE_PATH   = "data/Liste des lots.xlsx"
SIDEBAR_WIDTH     = "275px" # Largeur fixe demandée
DETAIL_PANEL_WIDTH= "275px" # Largeur fixe demandée

# Colonnes attendues
REF_COL="Référence annonce"; REGION_COL="Région"; DEPT_COL="Département"
EMPL_COL="Emplacement"; TYPO_COL="Typologie"; EXTRACTION_COL="Extraction"; RESTAURATION_COL="Restauration"
SURFACE_COL="Surface GLA"; LOYER_COL="Loyer annuel"; LAT_COL="Latitude"; LON_COL="Longitude"; ACTIF_COL="Actif"
# On suppose que les colonnes de détails sont de l'index 6 (G) à 38 (AL)
INDEX_START, INDEX_END_EXCL = 6, 38
MAP_HEIGHT = 800

# ===== Police Futura =====
def _load_futura_css_from_assets():
    assets_dir = "assets"
    if not os.path.isdir(assets_dir): return ""
    preferred = ["FuturaT-Book.ttf","FuturaT.ttf","FuturaT-Medium.ttf","FuturaT-Bold.ttf",
                 "FuturaL-Book.ttf","FuturaL-Medium.ttf","FuturaL-Bold.ttf"]
    files = [os.path.join(assets_dir,p) for p in preferred if os.path.exists(os.path.join(assets_dir,p))]
    if not files: files = glob.glob(os.path.join(assets_dir,"*.ttf"))
    css=[]
    for fp in files[:4]:
        try:
            b64 = base64.b64encode(open(fp,"rb").read()).decode("ascii")
            name=os.path.basename(fp).lower()
            weight="700" if "bold" in name else "500" if "medium" in name else "300" if "light" in name else "400"
            style="italic" if ("italic" in name or "oblique" in name) else "normal"
            css.append(
                f"@font-face {{font-family:'Futura SMBG';src:url(data:font/ttf;base64,{b64}) format('truetype');"
                f"font-weight:{weight};font-style:{style};font-display:swap;}}"
            )
        except: pass
    css.append("*{font-family:'Futura SMBG', Futura, 'Futura PT', 'Century Gothic', Arial, sans-serif;}")
    return "\n".join(css)

# ===== Helpers =====
def parse_ref_display(ref_str):
    s=str(ref_str).strip()
    if "." in s:
        left,right=s.split(".",1); left=re.sub(r"^0+","",left) or "0"; return f"{left}.{right}"
    return re.sub(r"^0+","",s) or "0"

def format_value(value, unit=""):
    """Formate une valeur, gère le masquage si vide, néant, -, /, ou 0 (valeur ou texte)."""
    s=str(value).strip()
    if s.lower() in ("n/a","nan","","none","néant","-","/"): return ""
    try:
        num=float(s.replace("€","").replace("m²","").replace("m2","").replace(" ","").replace(",","."))
        if num == 0.0: return "" 
        txt=f"{num:,.0f}".replace(",", " ")
        return f"{txt} {unit}".strip() if unit else txt
    except: 
        return s

def reset_all():
    # Décocher/réinitialiser tous les filtres (cases et sliders)
    # L'utilisation de st.session_state.clear() est la façon la plus simple de réinitialiser tous les widgets.
    st.session_state.clear() 
    st.rerun()

# Initialisation de l'état
if "selected_ref" not in st.session_state:
    st.session_state["selected_ref"]=None

# ===== Data =====
@st.cache_data
def load_data(path):
    df=pd.read_excel(path, dtype={REF_COL:str})
    df.columns=df.columns.str.strip()
    df[REF_COL]=df[REF_COL].astype(str).str.replace(".0","",regex=False).str.strip()
    df[LAT_COL]=pd.to_numeric(df.get(LAT_COL,""), errors="coerce")
    df[LON_COL]=pd.to_numeric(df.get(LON_COL,""), errors="coerce")
    df["__SURF_NUM__"]=pd.to_numeric(df.get(SURFACE_COL,""), errors="coerce")
    df["__LOYER_NUM__"]=pd.to_numeric(df.get(LOYER_COL,""), errors="coerce")
    if ACTIF_COL in df.columns:
        df=df[df[ACTIF_COL].astype(str).str.lower().eq("oui")]
    df.dropna(subset=[LAT_COL,LON_COL], inplace=True)
    df.reset_index(drop=True,inplace=True)
    return df

data_df=load_data(EXCEL_FILE_PATH)

# ===== CSS global (Layout 3 zones, Rétractation, 275px, PINS CORRIGÉS) =====
def logo_base64():
    if not os.path.exists(LOGO_FILE_PATH): return ""
    return base64.b64encode(open(LOGO_FILE_PATH,"rb").read()).decode("ascii")

st.markdown(f"""
<style>
{_load_futura_css_from_assets()}

/* Panneau droit réservé : Ajustement de la marge du contenu principal */
[data-testid="stAppViewContainer"] .main .block-container {{ 
    padding-right: calc({DETAIL_PANEL_WIDTH} + 20px); 
}}

/* Sidebar : Largeur fixe 275px, fond bleu, aucun bouton collapse */
[data-testid="stSidebar"] {{ 
    width: {SIDEBAR_WIDTH} !important;
    background:{COLOR_SMBG_BLUE}; 
    color:white; 
}}
[data-testid="stSidebar"] .block-container {{ padding-top:0 !important; }}
[data-testid="stSidebarCollapseButton"], button[kind="headerNoPadding"] {{ display:none !important; }}

/* Indentation départements 15px */
.dept-wrap {{ margin-left:15px; }}

/* --- PINS CORRIGÉS : STYLE CIRCULAIRE BLEU SMBG (L'ÉLÉMENT MANQUANT) --- */

/* Icône main au survol */
.smbg-divicon {{ cursor:pointer; }}

/* Le style du cercle lui-même */
.smbg-divicon > div {{
    width:30px;height:30px;border-radius:50%;
    background:{COLOR_SMBG_BLUE}; display:flex;align-items:center;justify-content:center;
    color:#fff;font-weight:700;font-size:12px;border:1px solid #001a27;
    box-shadow: 1px 1px 3px rgba(0,0,0,0.5);
}}
/* -------------------------------------------------------------------------- */

/* Suppression VISUELLE TOTALE des popups Leaflet (pour gérer le clic sans interface) */
.leaflet-popup, .leaflet-popup-pane,
.leaflet-popup-content-wrapper, .leaflet-popup-tip,
.leaflet-container a.leaflet-popup-close-button {{
  opacity:0 !important; width:0 !important; height:0 !important;
  padding:0 !important; margin:0 !important; border:0 !important; display:none !important;
}}

/* Panneau droit RÉTRACTABLE (caché par défaut, largeur 275px) */
.details-panel-container {{
  position: fixed; top: 0; right: 0; 
  width: 0; 
  height: 100vh;
  background:{COLOR_SMBG_BLUE}; color:#fff; z-index:1000;
  overflow-y:auto; overflow-x:hidden;
  transition: width 0.3s ease-in-out; 
  box-shadow: -5px 0 15px rgba(0,0,0,0.35);
}}
.details-panel-open {{
    width: {DETAIL_PANEL_WIDTH};
    padding:16px;
}}
.details-panel-container:not(.details-panel-open) > * {{ display:none; }}

/* Style des éléments du panneau droit */
.maps-button {{
  width:100%; padding:9px; margin:8px 0 14px; background:{COLOR_SMBG_COPPER};
  color:#fff; border:none; border-radius:8px; cursor:pointer; text-align:center; font-weight:700;
  text-decoration:none; display:inline-block;
}}
.details-panel-container table {{ width:100%; border-collapse:collapse; font-size:13px; }}
.details-panel-container tr {{ border-bottom:1px solid #304f65; }}
.details-panel-container td {{ padding:6px 0; max-width:50%; overflow-wrap:break-word; }}
</style>
""", unsafe_allow_html=True)

# ===== SIDEBAR (Filtres) =====
with st.sidebar:
    st.markdown("<div style='height:25px'></div>", unsafe_allow_html=True)

    b64 = logo_base64()
    if b64:
        st.markdown(
            f"<img src='data:image/png;base64,{b64}' "
            f"style='width:100%;height:auto;display:block;margin:0;'>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div style='color:#fff;'>Logo introuvable</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    st.markdown("**Région / Département**")
    regions = sorted([x for x in data_df.get(REGION_COL,pd.Series()).dropna().astype(str).unique() if x.strip()])

    selected_regions = []
    selected_depts_global = []
    selected_depts_by_region = defaultdict(list)

    # Logique de filtres imbriqués
    for reg in regions:
        rk = f"chk_region_{reg}"
        rchecked = st.checkbox(reg, key=rk)
        if rchecked:
            selected_regions.append(reg)
            pool = data_df[data_df[REGION_COL].astype(str).eq(reg)]
            depts = sorted([x for x in pool.get(DEPT_COL,pd.Series()).dropna().astype(str).unique() if x.strip()])
            for d in depts:
                dk = f"chk_dept_{reg}_{d}"
                st.markdown("<div class='dept-wrap'>", unsafe_allow_html=True)
                dchecked = st.checkbox(d, key=dk)
                st.markdown("</div>", unsafe_allow_html=True)
                if dchecked:
                    selected_depts_global.append(d)
                    selected_depts_by_region[reg].append(d)

    st.markdown("---")

    # Sliders
    surf_min=int(np.nanmin(data_df["__SURF_NUM__"])) if data_df["__SURF_NUM__"].notna().any() else 0
    surf_max=int(np.nanmax(data_df["__SURF_NUM__"])) if data_df["__SURF_NUM__"].notna().any() else 1000
    smin,smax=st.slider("Surface GLA (m²)", min_value=surf_min, max_value=surf_max, value=(surf_min,surf_max), step=1, key="slider_surface")

    loyer_min=int(np.nanmin(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 0
    loyer_max=int(np.nanmax(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 100000
    l_step = 1000 if loyer_max > 50000 else 100 
    lmin,lmax=st.slider("Loyer annuel (€)", min_value=loyer_min, max_value=loyer_max, value=(loyer_min,loyer_max), step=l_step, key="slider_loyer")

    def draw_checks(title, column, prefix):
        st.markdown(f"**{title}**")
        opts=sorted([x for x in data_df.get(column,pd.Series()).dropna().astype(str).unique() if x.strip()])
        sels=[]
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

# ===== APPLICATION DES FILTRES =====
f = data_df.copy()

# Filtre Région / Département
if selected_regions:
    mask_false = pd.Series(False, index=f.index)
    reg_mask = mask_false.copy()
    for reg in selected_regions:
        reg_rows = f[REGION_COL].astype(str).eq(reg)
        depts_sel = selected_depts_by_region.get(reg, [])
        if depts_sel:
            reg_mask = reg_mask | ( reg_rows & f[DEPT_COL].astype(str).isin(depts_sel) )
        else:
            reg_mask = reg_mask | reg_rows
    f = f[reg_mask]

# Autres filtres
f = f[
    (f["__SURF_NUM__"].isna() | ((f["__SURF_NUM__"]>=smin) & (f["__SURF_NUM__"]<=smax))) &
    (f["__LOYER_NUM__"].isna()| ((f["__LOYER_NUM__"]>=lmin) & (f["__LOYER_NUM__"]<=lmax)))
]
if emp_sel:  f = f[f[EMPL_COL].astype(str).isin(emp_sel)]
if typo_sel: f = f[f[TYPO_COL].astype(str).isin(typo_sel)]
if ext_sel:  f = f[f[EXTRACTION_COL].astype(str).isin(ext_sel)]
if rest_sel: f = f[f[RESTAURATION_COL].astype(str).isin(rest_sel)]

# ===== CARTE (Pins sans Jitter/Popup) =====
pins_df = f.copy()

if pins_df.empty: center_lat,center_lon,zoom_start=46.5,2.5,6
else: center_lat=float(pins_df[LAT_COL].mean()); center_lon=float(pins_df[LON_COL].mean()); zoom_start=6

m=folium.Map(location=[center_lat,center_lon], zoom_start=zoom_start, control_scale=True)

def add_pin(lat, lon, label, ref_value):
    icon_html=f"""
    <div class="smbg-divicon">
        <div>{label}</div>
    </div>"""
    # Marker DivIcon (Pin visible)
    folium.Marker(
        location=[lat,lon],
        icon=folium.DivIcon(html=icon_html, class_name="smbg-divicon", icon_size=(30,30), icon_anchor=(15,15)),
        popup=f"<div data-ref='{ref_value}'>{ref_value}</div>" # Popup technique invisible
    ).add_to(m)
    # CircleMarker (Zone de clic)
    folium.CircleMarker(
        location=[lat, lon], radius=15, color="#00000000",
        fill=True, fill_color="#00000000", fill_opacity=0.0, opacity=0.0,
        popup=f"<div data-ref='{ref_value}'>{ref_value}</div>" # Popup technique invisible
    ).add_to(m)

if not pins_df.empty:
    pins_df["__ref_display__"]=pins_df[REF_COL].apply(parse_ref_display)
    for _,r in pins_df.iterrows():
        add_pin(float(r[LAT_COL]), float(r[LON_COL]), r["__ref_display__"], r[REF_COL])

# Écoute de la carte
map_output = st_folium(
    m, 
    height=MAP_HEIGHT, 
    width="100%", 
    returned_objects=["last_object_clicked", "last_clicked"], 
    key="map"
)

# --- Logique de gestion du Clic (Ouverture/Fermeture du Panneau) ---
ref_clicked = None
if map_output and map_output.get("last_object_clicked"):
    obj=map_output["last_object_clicked"]
    ref_guess=None
    for k in ("popup","popup_html"):
        if k in obj and obj[k]:
            txt=str(obj[k]); mref=re.search(r"data-ref=['\"]([^'\"]+)['\"]", txt)
            ref_guess=mref.group(1) if mref else re.sub(r"<.*?>","",txt).strip()
            break
    if ref_guess:
        st.session_state["selected_ref"]=ref_guess 
        ref_clicked = ref_guess 

elif map_output and map_output.get("last_clicked") and not ref_clicked:
    # Clic sur la carte (hors pin)
    st.session_state["selected_ref"] = None

# ===== VOLET DROIT (Panneau de Détails) =====
sel_ref = st.session_state.get("selected_ref")
is_open = False 
html_content = []

if sel_ref:
    row=data_df[data_df[REF_COL].astype(str).str.strip()==str(sel_ref).strip()]
    
    if not row.empty:
        is_open = True
        r=row.iloc[0]; ref_title=parse_ref_display(sel_ref)
        
        # Début du contenu
        html_content+=["<h3 style='margin:0 0 6px 0;'>🔍 Détails de l'annonce</h3>",
                       f"<h4 style='color:{COLOR_SMBG_COPPER};margin:0 0 10px 0;'>Réf. : {ref_title}</h4>",
                       "<h5 style='margin:6px 0 8px;'>📋 Données clés</h5>","<table>"]
        
        all_cols=data_df.columns.tolist()
        cols_slice=all_cols[INDEX_START:INDEX_END_EXCL] if len(all_cols)>=INDEX_END_EXCL else all_cols[INDEX_START:]
        
        for champ in cols_slice:
            sraw=str(r.get(champ,"")).strip()
            
            is_google_maps = champ.lower().strip() in ["lien google maps","google maps","lien google"]
            
            if is_google_maps:
                if sraw:
                    html_content.append(f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>Lien Google Maps</td>"
                                f"<td><a class='maps-button' href='{sraw}' target='_blank'>Cliquer ici</a></td></tr>")
                continue
            
            unit = "€" if any(k in champ for k in ["Loyer","Charges","garantie","Taxe","Marketing","Gestion","BP","annuel","Mensuel","foncière","Honoraires"]) \
                   else ("m²" if any(k in champ for k in ["Surface","GLA","utile","Vitrine","Linéaire"]) else "")
            
            sval=format_value(sraw, unit)
            
            if not sval: continue # Masqué si vide, néant, -, /, 0
            
            html_content.append(f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>{champ}</td><td>{sval}</td></tr>")
        
        # Fin du contenu
        html_content+=["</table>",
                       "<hr style='border:1px solid #304f65;margin:12px 0;'>",
                       "<h5 style='margin:6px 0 8px;'>📷 Photos</h5>",
                       "<div class='small-note'>Les photos seront affichées ici dès qu'elles seront en ligne.</div>"]

# Affichage du panneau
panel_class = "details-panel-container " + ("details-panel-open" if is_open else "")
st.markdown(f"<div class='{panel_class}'>{''.join(html_content)}</div>", unsafe_allow_html=True)

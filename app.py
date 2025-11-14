# -*- coding: utf-8 -*-
import os, base64, glob, math, re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
from collections import defaultdict
from folium.plugins import DivIcon # Maintenant l'importation est correcte

# ===== CONFIG =====
# Largeurs fixes : 275px pour la sidebar et le panneau droit (ajustement CSS)
st.set_page_config(layout="wide", page_title="Carte Interactive SMBG", initial_sidebar_state="expanded")
COLOR_SMBG_BLUE   = "#05263D"
COLOR_SMBG_COPPER = "#C67B42"
PANEL_WIDTH       = "275px" # Largeur fixe pour la consigne
LOGO_FILE_PATH    = "assets/Logo bleu crop.png"   # on l’encode en base64 pour supprimer tout bouton
EXCEL_FILE_PATH   = "data/Liste des lots.xlsx"

# Colonnes attendues
REF_COL="Référence annonce"; REGION_COL="Région"; DEPT_COL="Département"
EMPL_COL="Emplacement"; TYPO_COL="Typologie"; EXTRACTION_COL="Extraction"; RESTAURATION_COL="Restauration"
SURFACE_COL="Surface GLA"; LOYER_COL="Loyer annuel"; LAT_COL="Latitude"; LON_COL="Longitude"; ACTIF_COL="Actif"

# Volet droit : G -> AL (H = bouton Google)
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
    s=str(value).strip()
    if s.lower() in ("n/a","nan","","none","néant","-","/"): return ""
    try:
        # Masquer si la valeur est numériquement 0
        num_clean=s.replace("€","").replace("m²","").replace("m2","").replace(" ","").replace(",",".").strip()
        if num_clean and float(num_clean)==0: return ""
        
        num=float(num_clean)
        txt=f"{num:,.0f}".replace(",", " "); return f"{txt} {unit}".strip() if unit else txt
    except: return s

# --- RESTAURATION DE LA LOGIQUE JITTER (car présente dans votre version "fonctionnelle") ---
def jitter_group(df, lat_col, lon_col, base_radius_m=12.0, step_m=4.0):
    golden = math.pi*(3-math.sqrt(5)); out=[]
    for i,(_,r) in enumerate(df.iterrows()):
        lat0,lon0=r[lat_col],r[lon_col]; radius=base_radius_m+i*step_m; th=i*golden
        rr=r.copy()
        rr["__jlat"]=lat0+(radius*math.sin(th))/111_320.0
        rr["__jlon"]=lon0+(radius*math.cos(th))/(111_320.0*max(0.2,math.cos(math.radians(lat0))))
        out.append(rr)
    return pd.DataFrame(out) if out else df

def reset_all():
    # Correction: réinitialisation des sliders/checkboxes et de l'état sélectionné
    for k in list(st.session_state.keys()):
        if k.startswith(("chk_","slider_")):
            del st.session_state[k]
    st.session_state["selected_ref"]=None
    # Conserver le zoom/centre
    st.rerun()

if "selected_ref" not in st.session_state:
    st.session_state["selected_ref"]=None
if "center_coords" not in st.session_state:
    st.session_state["center_coords"] = [46.5, 2.5]
if "zoom_level" not in st.session_state:
    st.session_state["zoom_level"] = 6

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

# ===== CSS global (logo, sidebar, pas de popups) =====
# Logo en base64 pour supprimer tout bouton
def logo_base64():
    if not os.path.exists(LOGO_FILE_PATH): return ""
    return base64.b64encode(open(LOGO_FILE_PATH,"rb").read()).decode("ascii")

st.markdown(f"""
<style>
{_load_futura_css_from_assets()}

/* Panneau droit réservé : 275px */
[data-testid="stAppViewContainer"] .main .block-container {{ padding-right: {PANEL_WIDTH}; }}

/* Sidebar : marge haute 25px, aucun bouton collapse, fond bleu, largeur 275px */
[data-testid="stSidebar"] {{ 
    width: {PANEL_WIDTH} !important; 
    min-width: {PANEL_WIDTH} !important;
    max-width: {PANEL_WIDTH} !important;
    background:{COLOR_SMBG_BLUE}; 
    color:white; 
}}
[data-testid="stSidebar"] .block-container {{ padding-top:0 !important; }}
[data-testid="stSidebarCollapseButton"], button[kind="headerNoPadding"] {{ display:none !important; }}

/* Indentation départements 15px */
.dept-wrap {{ margin-left:15px; }}

/* Icône main sur nos pins */
.smbg-divicon {{ cursor:pointer; }}

/* Suppression VISUELLE TOTALE des popups Leaflet (technique) */
.leaflet-popup, .leaflet-popup-pane,
.leaflet-popup-content-wrapper, .leaflet-popup-tip,
.leaflet-container a.leaflet-popup-close-button {{
  opacity:0 !important; width:0 !important; height:0 !important;
  padding:0 !important; margin:0 !important; border:0 !important; display:none !important;
}}

/* Panneau droit rétractable (275px) */
.details-panel {{
  position: fixed; top: 0; right: 0; width: {PANEL_WIDTH}; height: 100vh;
  background:{COLOR_SMBG_BLUE}; color:#fff; z-index:1000;
  padding:16px; box-shadow:-5px 0 15px rgba(0,0,0,0.35); overflow-y:auto;
  transform: translateX({PANEL_WIDTH}); /* Caché par défaut */
  transition: transform 0.3s ease-in-out;
}}
.details-panel.open {{
    transform: translateX(0); /* Ouvert */
}}
.maps-button {{
  width:100%; padding:9px; margin:8px 0 14px; background:{COLOR_SMBG_COPPER};
  color:#fff; border:none; border-radius:8px; cursor:pointer; text-align:center; font-weight:700;
}}
.details-panel table {{ width:100%; border-collapse:collapse; font-size:13px; }}
.details-panel tr {{ border-bottom:1px solid #304f65; }}
.details-panel td {{ padding:6px 0; max-width:50%; overflow-wrap:break-word; }}
</style>
""", unsafe_allow_html=True)

# ===== SIDEBAR =====
with st.sidebar:
    st.markdown("<div style='height:25px'></div>", unsafe_allow_html=True)

    b64 = logo_base64()
    if b64:
        st.markdown(
            f"<img src='data:image/png;base64,{b64}' alt='Logo SMBG' "
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

    for reg in regions:
        rk = f"chk_region_{reg}"
        rchecked = st.checkbox(reg, key=rk, value=st.session_state.get(rk, False))
        if rchecked:
            selected_regions.append(reg)
            pool = data_df[data_df[REGION_COL].astype(str).eq(reg)]
            depts = sorted([x for x in pool.get(DEPT_COL,pd.Series()).dropna().astype(str).unique() if x.strip()])
            for d in depts:
                dk = f"chk_dept_{reg}_{d}"
                st.markdown("<div class='dept-wrap'>", unsafe_allow_html=True)
                dchecked = st.checkbox(d, key=dk, value=st.session_state.get(dk, False))
                st.markdown("</div>", unsafe_allow_html=True)
                if dchecked:
                    selected_depts_global.append(d)
                    selected_depts_by_region[reg].append(d)

    st.markdown("---")

    surf_min=int(np.nanmin(data_df["__SURF_NUM__"])) if data_df["__SURF_NUM__"].notna().any() else 0
    surf_max=int(np.nanmax(data_df["__SURF_NUM__"])) if data_df["__SURF_NUM__"].notna().any() else 1000
    if surf_min > surf_max: surf_min, surf_max = 0, 1000
    if "slider_surface" not in st.session_state:
         st.session_state["slider_surface"] = (surf_min,surf_max)
    
    smin,smax=st.slider("Surface GLA (m²)", min_value=surf_min, max_value=surf_max, 
                        value=st.session_state["slider_surface"], step=1, key="slider_surface")

    loyer_min=int(np.nanmin(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 0
    loyer_max=int(np.nanmax(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 100000
    if loyer_min > loyer_max: loyer_min, loyer_max = 0, 100000
    if "slider_loyer" not in st.session_state:
         st.session_state["slider_loyer"] = (loyer_min,loyer_max)

    lmin,lmax=st.slider("Loyer annuel (€)", min_value=loyer_min, max_value=loyer_max, 
                        value=st.session_state["slider_loyer"], step=1000, key="slider_loyer")

    def draw_checks(title, column, prefix):
        st.markdown(f"**{title}**")
        opts=sorted([x for x in data_df.get(column,pd.Series()).dropna().astype(str).unique() if x.strip()])
        sels=[]
        for opt in opts:
            ck = f"chk_{prefix}_{opt}"
            if st.checkbox(opt, key=ck, value=st.session_state.get(ck, False)):
                sels.append(opt)
        st.markdown("---")
        return sels

    emp_sel  = draw_checks("Emplacement",  EMPL_COL, "emp")
    typo_sel = draw_checks("Typologie",   TYPO_COL, "typo")
    ext_sel  = draw_checks("Extraction",  EXTRACTION_COL, "ext")
    rest_sel = draw_checks("Restauration",RESTAURATION_COL, "rest")

    if st.button("Réinitialiser", use_container_width=True):
        reset_all()

# ===== FILTRES =====
f = data_df.copy()

if selected_regions or selected_depts_global:
    cond_parts = []
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
        cond_parts.append(reg_mask)

    f = f[ np.logical_or.reduce(cond_parts) ] if cond_parts else f

f = f[
    (f["__SURF_NUM__"].isna() | ((f["__SURF_NUM__"]>=smin) & (f["__SURF_NUM__"]<=smax))) &
    (f["__LOYER_NUM__"].isna()| ((f["__LOYER_NUM__"]>=lmin) & (f["__LOYER_NUM__"]<=lmax)))
]
if emp_sel:  f = f[f[EMPL_COL].astype(str).isin(emp_sel)]
if typo_sel: f = f[f[TYPO_COL].astype(str).isin(typo_sel)]
if ext_sel:  f = f[f[EXTRACTION_COL].astype(str).isin(ext_sel)]
if rest_sel: f = f[f[RESTAURATION_COL].astype(str).isin(rest_sel)]

# ===== CARTE (Restauration du Jitter et Pin) =====
tmp=f.copy()
tmp["__lat__"], tmp["__lon__"]=tmp[LAT_COL], tmp[LON_COL]

# --- RESTAURATION DE L'APPLICATION DU JITTER ---
jittered=[]
for (_,_grp) in tmp.groupby([LAT_COL,LON_COL], as_index=False):
    # Appel de la fonction jitter_group restaurée
    jittered.append(jitter_group(_grp,"__lat__","__lon__", base_radius_m=12.0, step_m=4.0))
pins_df=pd.concat(jittered, ignore_index=True) if jittered else tmp.copy()


if pins_df.empty: 
    center_lat,center_lon=st.session_state["center_coords"]
    zoom_level = st.session_state["zoom_level"]
else: 
    # Utilisation des coordonnées jittered pour le centrage
    center_lat=float(pins_df["__jlat"].mean()); center_lon=float(pins_df["__jlon"].mean())
    zoom_level = st.session_state["zoom_level"]

m=folium.Map(location=[center_lat,center_lon], zoom_start=zoom_level, control_scale=True)

def add_pin(lat, lon, label, ref_value):
    icon_html=f"""
    <div class="smbg-divicon" style="width:30px;height:30px;border-radius:50%;
         background:{COLOR_SMBG_BLUE}; display:flex;align-items:center;justify-content:center;
         color:#fff;font-weight:700;font-size:12px;border:1px solid #001a27;">
        {label}
    </div>"""
    # Marker + popup technique (invisible) pour récupérer l’event
    folium.Marker(
        location=[lat,lon],
        icon=DivIcon(html=icon_html, class_name="smbg-divicon", icon_size=(30,30), icon_anchor=(15,15)),
        popup=f"<div data-ref='{ref_value}'>{ref_value}</div>"
    ).add_to(m)
    # Cible cliquable (sécurité) exactement sur le pin (avec popup technique invisible)
    folium.CircleMarker(
        location=[lat, lon], radius=15, color="#00000000",
        fill=True, fill_color="#00000000", fill_opacity=0.0, opacity=0.0,
        popup=f"<div data-ref='{ref_value}'>{ref_value}</div>"
    ).add_to(m)

if not pins_df.empty:
    pins_df["__ref_display__"]=pins_df[REF_COL].apply(parse_ref_display)
    for _,r in pins_df.iterrows():
        # Utilisation des coordonnées Jittered
        add_pin(float(r["__jlat"]), float(r["__jlon"]), r["__ref_display__"], r[REF_COL])

map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=["last_object_clicked", "last_click"], key="map")

ref_guess=None
if map_output and map_output.get("last_object_clicked"):
    obj=map_output["last_object_clicked"]
    # Extraction de la référence du popup technique
    for k in ("popup","popup_html"):
        if k in obj and obj[k]:
            txt=str(obj[k]); mref=re.search(r"data-ref=['\"]([^'\"]+)['\"]", txt)
            ref_guess=mref.group(1) if mref else None # Seule l'extraction par data-ref est fiable
            break
            
if ref_guess:
    st.session_state["selected_ref"] = ref_guess
    st.session_state["center_coords"] = [map_output["center"]["lat"], map_output["center"]["lng"]]
    st.session_state["zoom_level"] = map_output["zoom"]
    st.rerun() 
elif map_output and map_output.get("last_click") and st.session_state.get("selected_ref") is not None:
    # Clic sur la carte hors pin -> Ferme le panneau
    st.session_state["selected_ref"] = None
    st.session_state["center_coords"] = [map_output["center"]["lat"], map_output["center"]["lng"]]
    st.session_state["zoom_level"] = map_output["zoom"]
    st.rerun() 
else:
    # Mémoriser la position si la carte a bougé
    if map_output and map_output.get("center") and map_output.get("zoom"):
        st.session_state["center_coords"] = [map_output["center"]["lat"], map_output["center"]["lng"]]
        st.session_state["zoom_level"] = map_output["zoom"]


# ===== VOLET DROIT (Restauration) =====
sel_ref=st.session_state.get("selected_ref")
panel_class = "open" if sel_ref else "" 

html=[f"<div class='details-panel {panel_class}'>"]
if sel_ref:
    row=data_df[data_df[REF_COL].astype(str).str.strip()==str(sel_ref).strip()]
    if not row.empty:
        r=row.iloc[0]; ref_title=parse_ref_display(sel_ref)
        html+=["<h3 style='margin:0 0 6px 0;'>🔍 Détails de l'annonce</h3>",
               f"<h4 style='color:{COLOR_SMBG_COPPER};margin:0 0 10px 0;'>Réf. : {ref_title}</h4>",
               "<h5 style='margin:6px 0 8px;'>📋 Données clés</h5>","<table>"]
        all_cols=data_df.columns.tolist()
        cols_slice=all_cols[INDEX_START:INDEX_END_EXCL] if len(all_cols)>=INDEX_END_EXCL else all_cols[INDEX_START:]

        for idx,champ in enumerate(cols_slice, start=INDEX_START):
            sraw=str(r.get(champ,"")).strip()
            
            if (idx==(INDEX_START+1) or champ.strip().lower() in ["lien google maps","google maps","lien google"]) and sraw:
                html.append(f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>Lien Google Maps</td>"
                            f"<td><a class='maps-button' href='{sraw}' target='_blank'>Cliquer ici</a></td></tr>")
                continue
            
            unit = "€" if any(k in champ for k in ["Loyer","Charges","garantie","Taxe","Marketing","Gestion","BP","annuel","Mensuel","foncière","Honoraires"]) \
                   else ("m²" if any(k in champ for k in ["Surface","GLA","utile","Vitrine","Linéaire"]) else "")
            sval=format_value(sraw, unit)
            
            if not sval: continue 
            
            html.append(f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>{champ}</td><td>{sval}</td></tr>")
            
        html+=["</table>",
               "<hr style='border:1px solid #eee;margin:12px 0;'>",
               "<h5 style='margin:6px 0 8px;'>📷 Photos</h5>",
               "<div class='small-note'>Les photos seront affichées ici dès qu'elles seront en ligne.</div>"]

html.append("</div>")
st.markdown("".join(html), unsafe_allow_html=True)

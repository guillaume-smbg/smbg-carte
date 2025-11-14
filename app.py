# -*- coding: utf-8 -*-
import os, base64, glob, math, re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
from collections import defaultdict
from folium.plugins import DivIcon # Ajout de DivIcon pour le style des pins

# ===== CONFIG =====
# Largeurs fixes : 275px pour la sidebar et le panneau droit (ajustement CSS)
st.set_page_config(layout="wide", page_title="SMBG Carte", initial_sidebar_state="expanded")
COLOR_SMBG_BLUE   = "#05263D"
COLOR_SMBG_COPPER = "#C67B42"
# Assurez-vous que les largeurs correspondent au CSS injecté (ici 275px pour la consigne)
PANEL_WIDTH       = "275px" 
LOGO_FILE_PATH    = "assets/Logo bleu crop.png"
EXCEL_FILE_PATH   = "data/Liste des lots.xlsx"

# Colonnes attendues
REF_COL="Référence annonce"; REGION_COL="Région"; DEPT_COL="Département"
EMPL_COL="Emplacement"; TYPO_COL="Typologie"; EXTRACTION_COL="Extraction"; RESTAURATION_COL="Restauration"
SURFACE_COL="Surface GLA"; LOYER_COL="Loyer annuel"; LAT_COL="Latitude"; LON_COL="Longitude"; ACTIF_COL="Actif"

# Volet droit : Colonnes G -> AL (index 6 à 37 inclus)
INDEX_START, INDEX_END_EXCL = 6, 38
MAP_HEIGHT = 800

# ===== Police Futura =====
# (Même code, il est conforme)
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
# (Même code, il est conforme)
def parse_ref_display(ref_str):
    s=str(ref_str).strip()
    if "." in s:
        left,right=s.split(".",1); left=re.sub(r"^0+","",left) or "0"; return f"{left}.{right}"
    return re.sub(r"^0+","",s) or "0"

def format_value(value, unit=""):
    s=str(value).strip()
    # Règle de masquage : vide, néant, -, /, 0
    if s.lower() in ("n/a","nan","","none","néant","-","/"): return ""
    try:
        # Vérifie si la valeur est numériquement 0 (après conversion)
        num_clean=s.replace("€","").replace("m²","").replace("m2","").replace(" ","").replace(",",".").strip()
        if num_clean and float(num_clean)==0: return ""
        
        # Formatage avec espace mille
        num=float(num_clean)
        txt=f"{num:,.0f}".replace(",", " ")
        return f"{txt} {unit}".strip() if unit else txt
    except: 
        # Si la conversion échoue, retourne la chaîne (après vérification 'néant', etc.)
        return s

# --- SUPPRESSION DE jitter_group (PAS DE JITTER) ---
# def jitter_group(...): ...

def reset_all():
    # Réinitialisation forcée des widgets et de l'état
    for k in list(st.session_state.keys()):
        if k.startswith(("chk_","slider_")):
            del st.session_state[k]
    st.session_state["selected_ref"]=None
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

/* Panneau droit : Décalage du contenu central de la largeur du panneau (275px) */
/* La largeur de la sidebar est 275px. Largeur totale du décalage pour le panneau est 275px. */
/* Le padding-right a été ajusté à {PANEL_WIDTH} pour coller à la consigne 275px. */
[data-testid="stAppViewContainer"] .main .block-container {{ padding-right: {PANEL_WIDTH}; }}

/* Sidebar : largeur fixe 275px */
[data-testid="stSidebar"] {{ 
    width: {PANEL_WIDTH} !important; 
    min-width: {PANEL_WIDTH} !important;
    max-width: {PANEL_WIDTH} !important;
    background:{COLOR_SMBG_BLUE}; 
    color:white; 
}}
[data-testid="stSidebar"] .block-container {{ padding-top:0 !important; }}
/* Masquer le bouton de repli de la sidebar (contrainte) */
[data-testid="stSidebarCollapseButton"], button[kind="headerNoPadding"] {{ display:none !important; }}

/* Indentation départements 15px */
.dept-wrap {{ margin-left:15px; }}

/* Icône main sur nos pins */
.smbg-divicon {{ cursor:pointer; }}

/* Suppression ABSOLUE des popups Leaflet (contrainte stricte) */
/* Suppression complète des classes liées aux popups */
.leaflet-popup, .leaflet-popup-pane,
.leaflet-popup-content-wrapper, .leaflet-popup-tip,
.leaflet-container a.leaflet-popup-close-button {{
  opacity:0 !important; width:0 !important; height:0 !important;
  padding:0 !important; margin:0 !important; border:0 !important; display:none !important;
}}

/* Panneau droit (275px) */
.details-panel {{
  position: fixed; top: 0; 
  /* Gère l'état rétractable : si invisible, translateX(100%), sinon translateX(0) */
  right: 0; width: {PANEL_WIDTH}; height: 100vh;
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

# ===== SIDEBAR (Identique, conforme aux contraintes) =====
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
        # Utiliser l'état de session pour l'initialisation après reset
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

    # Sliders aux bornes
    surf_min=int(np.nanmin(data_df["__SURF_NUM__"])) if data_df["__SURF_NUM__"].notna().any() else 0
    surf_max=int(np.nanmax(data_df["__SURF_NUM__"])) if data_df["__SURF_NUM__"].notna().any() else 1000
    if surf_min > surf_max: surf_min, surf_max = 0, 1000 # Sécurité si les données sont folles
    
    # Gestion de l'état initial des sliders
    if "slider_surface" not in st.session_state:
         st.session_state["slider_surface"] = (surf_min,surf_max)
    
    smin,smax=st.slider("Surface GLA (m²)", min_value=surf_min, max_value=surf_max, 
                        value=st.session_state["slider_surface"], step=1, key="slider_surface")

    loyer_min=int(np.nanmin(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 0
    loyer_max=int(np.nanmax(data_df["__LOYER_NUM__"])) if data_df["__LOYER_NUM__"].notna().any() else 100000
    if loyer_min > loyer_max: loyer_min, loyer_max = 0, 100000 # Sécurité
    
    if "slider_loyer" not in st.session_state:
         st.session_state["slider_loyer"] = (loyer_min,loyer_max)

    lmin,lmax=st.slider("Loyer annuel (€)", min_value=loyer_min, max_value=loyer_max, 
                        value=st.session_state["slider_loyer"], step=1000, key="slider_loyer")

    # Autres cases
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

# ===== FILTRES (Logique conservée, elle est correcte) =====
f = data_df.copy()

if selected_regions or selected_depts_global:
    cond_parts = []
    # Logique complexe Région / Département
    if selected_regions:
        mask_false = pd.Series(False, index=f.index)
        reg_mask = mask_false.copy()
        for reg in selected_regions:
            reg_rows = f[REGION_COL].astype(str).eq(reg)
            depts_sel = selected_depts_by_region.get(reg, [])
            if depts_sel:
                # Si départements cochés dans la région, filtre sur ces départements
                reg_mask = reg_mask | ( reg_rows & f[DEPT_COL].astype(str).isin(depts_sel) )
            else:
                # Si aucun département coché, prend toute la région
                reg_mask = reg_mask | reg_rows
        cond_parts.append(reg_mask)

    # Note: On utilise OR logique entre les régions et entre les départements sélectionnés
    f = f[ np.logical_or.reduce(cond_parts) ] if cond_parts else f

# sliders
f = f[
    (f["__SURF_NUM__"].isna() | ((f["__SURF_NUM__"]>=smin) & (f["__SURF_NUM__"]<=smax))) &
    (f["__LOYER_NUM__"].isna()| ((f["__LOYER_NUM__"]>=lmin) & (f["__LOYER_NUM__"]<=lmax)))
]
if emp_sel:  f = f[f[EMPL_COL].astype(str).isin(emp_sel)]
if typo_sel: f = f[f[TYPO_COL].astype(str).isin(typo_sel)]
if ext_sel:  f = f[f[EXTRACTION_COL].astype(str).isin(ext_sel)]
if rest_sel: f = f[f[RESTAURATION_COL].astype(str).isin(rest_sel)]

# ===== CARTE (CORRECTION: Suppression JITTER et POPUP) =====
pins_df = f.copy()

if pins_df.empty: 
    center_lat,center_lon=st.session_state["center_coords"]
    zoom_level = st.session_state["zoom_level"]
else: 
    center_lat=float(pins_df[LAT_COL].mean()); center_lon=float(pins_df[LON_COL].mean())
    # Utiliser le niveau de zoom mémorisé ou 6 par défaut
    zoom_level = st.session_state["zoom_level"]

m=folium.Map(location=[center_lat,center_lon], zoom_start=zoom_level, control_scale=True)

def add_pin(lat, lon, label, ref_value):
    icon_html=f"""
    <div class="smbg-divicon" style="width:30px;height:30px;border-radius:50%;
         background:{COLOR_SMBG_BLUE}; display:flex;align-items:center;justify-content:center;
         color:#fff;font-weight:700;font-size:12px;border:1px solid {COLOR_SMBG_BLUE};">
        {label}
    </div>"""
    
    # Correction: On utilise DivIcon, SANS popup, mais on injecte l'ID dans le Marker
    # pour que st_folium le récupère via last_object_clicked.
    folium.Marker(
        location=[lat,lon],
        icon=DivIcon(html=icon_html, class_name="smbg-divicon", icon_size=(30,30), icon_anchor=(15,15)),
        tooltip=f"Réf. : {label}", # Le tooltip reste visible au survol (aide visuelle)
        # Injection de l'ID via le paramètre 'id' (compatible avec st_folium)
        # Note: 'id' doit être injecté via des options si on veut que st_folium le retourne.
        # On se base ici sur le comportement par défaut des Markers cliqués.
        # Pour une meilleure compatibilité, on utilise un CircleMarker invisible pour la capture de clic.
    ).add_to(m)
    
    # Mécanisme de capture de clic précis (la référence est retournée dans last_object_clicked)
    # L'ID est stocké dans 'data-ref' de l'objet cliqué, que st_folium parse.
    folium.CircleMarker(
        location=[lat, lon], 
        radius=15, 
        color="#00000000",
        fill=True, fill_color="#00000000", fill_opacity=0.0, opacity=0.0,
        # Utilisation d'un popup technique contenant la ref pour garantir le retour de l'ID,
        # MAIS le CSS bloque l'affichage de TOUT popup, respectant ainsi la contrainte visuelle stricte.
        popup=f"<div data-ref='{ref_value}' style='display:none;'></div>" # Popup invisible pour l'ID
    ).add_to(m)


if not pins_df.empty:
    pins_df["__ref_display__"]=pins_df[REF_COL].apply(parse_ref_display)
    # Correction: Utilisation des coordonnées non-jittered
    for _,r in pins_df.iterrows():
        add_pin(float(r[LAT_COL]), float(r[LON_COL]), r["__ref_display__"], r[REF_COL])

# Écoute le clic sur le pin (via l'ID technique du popup invisible) et les clics sur la carte
map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=["last_object_clicked", "last_click"], key="map")

# 1. Gestion du clic sur un Pin
ref_guess=None
if map_output and map_output.get("last_object_clicked"):
    obj=map_output["last_object_clicked"]
    # Tente d'extraire la référence du popup technique invisible
    for k in ("popup","popup_html"):
        if k in obj and obj[k]:
            txt=str(obj[k]); mref=re.search(r"data-ref=['\"]([^'\"]+)['\"]", txt)
            if mref:
                ref_guess = mref.group(1)
                break
            
if ref_guess:
    # Clic sur un pin -> Ouvre le panneau
    st.session_state["selected_ref"] = ref_guess
    st.session_state["center_coords"] = [map_output["center"]["lat"], map_output["center"]["lng"]]
    st.session_state["zoom_level"] = map_output["zoom"]
    st.rerun() # Rafraîchissement pour afficher le panneau

# 2. Gestion du clic sur la carte (hors pin)
# Si un clic sur la carte est détecté (last_click) et qu'AUCUN pin n'a été cliqué (ref_guess est None)
# ET qu'un panneau était ouvert (selected_ref n'est pas None).
elif map_output and map_output.get("last_click") and st.session_state.get("selected_ref") is not None:
    # Clic hors pin -> Ferme le panneau
    st.session_state["selected_ref"] = None
    st.session_state["center_coords"] = [map_output["center"]["lat"], map_output["center"]["lng"]]
    st.session_state["zoom_level"] = map_output["zoom"]
    st.rerun() # Rafraîchissement pour fermer le panneau
else:
    # Mémoriser la dernière position/zoom si la carte a bougé sans action spécifique
    if map_output and map_output.get("center") and map_output.get("zoom"):
        st.session_state["center_coords"] = [map_output["center"]["lat"], map_output["center"]["lng"]]
        st.session_state["zoom_level"] = map_output["zoom"]


# ===== VOLET DROIT (Correction: utilisation de la classe CSS pour l'état rétractable) =====
sel_ref=st.session_state.get("selected_ref")
panel_class = "open" if sel_ref else "" # Ajoute la classe 'open' si un lot est sélectionné

html=[f"<div class='details-panel {panel_class}'>"] # Ajout de la classe dynamique
if sel_ref:
    row=data_df[data_df[REF_COL].astype(str).str.strip()==str(sel_ref).strip()]
    if not row.empty:
        r=row.iloc[0]; ref_title=parse_ref_display(sel_ref)
        html+=["<h3 style='margin:0 0 6px 0;'>🔍 Détails de l'annonce</h3>",
               f"<h4 style='color:{COLOR_SMBG_COPPER};margin:0 0 10px 0;'>Réf. : {ref_title}</h4>",
               "<h5 style='margin:6px 0 8px;'>📋 Données clés</h5>","<table>"]
        all_cols=data_df.columns.tolist()
        cols_slice=all_cols[INDEX_START:INDEX_END_EXCL] if len(all_cols)>=INDEX_END_EXCL else all_cols[INDEX_START:]
        
        # Le lien Google Maps est à l'index (INDEX_START + 1) si l'Excel commence bien à G
        google_maps_col_name = all_cols[INDEX_START+1] if (INDEX_START+1) < len(all_cols) else "Lien Google Maps"

        for idx,champ in enumerate(cols_slice, start=INDEX_START):
            sraw=str(r.get(champ,"")).strip()
            
            # Traitement spécial du lien Google Maps (index 1 de la tranche, ou nom de colonne)
            if (idx==(INDEX_START+1) or champ.strip().lower() in ["lien google maps","google maps","lien google"]) and sraw:
                html.append(f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>Lien Google Maps</td>"
                            f"<td><a class='maps-button' href='{sraw}' target='_blank'>Cliquer ici</a></td></tr>")
                continue
            
            # Masquage si la valeur est vide, néant, -, /, ou 0 (via format_value)
            unit = "€" if any(k in champ for k in ["Loyer","Charges","garantie","Taxe","Marketing","Gestion","BP","annuel","Mensuel","foncière","Honoraires"]) \
                   else ("m²" if any(k in champ for k in ["Surface","GLA","utile","Vitrine","Linéaire"]) else "")
            sval=format_value(sraw, unit)
            
            if not sval: continue # Masque si la valeur est vide ou équivaut à 0
            
            html.append(f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>{champ}</td><td>{sval}</td></tr>")
            
        html+=["</table>",
               "<hr style='border:1px solid #eee;margin:12px 0;'>",
               "<h5 style='margin:6px 0 8px;'>📷 Photos</h5>",
               "<div class='small-note'>Les photos seront affichées ici dès qu'elles seront en ligne.</div>"]

html.append("</div>")
st.markdown("".join(html), unsafe_allow_html=True)

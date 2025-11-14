# -*- coding: utf-8 -*-
import os, base64, glob, math, re
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
from collections import defaultdict

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
st.set_page_config(layout="wide", page_title="SMBG Carte", initial_sidebar_state="expanded")

# --- Identité Visuelle SMBG ---
COLOR_SMBG_BLUE   = "#05263D"
COLOR_SMBG_COPPER = "#C67B42"
SIDEBAR_WIDTH     = "275px" # Largeur du volet gauche
DETAIL_PANEL_WIDTH= "275px" # Largeur du panneau droit rétractable
MAP_HEIGHT        = 800     # Hauteur de la carte

# --- Fichiers & Données ---
LOGO_FILE_PATH    = "assets/Logo bleu crop.png"
EXCEL_FILE_PATH   = "data/Liste des lots.xlsx"

# --- Colonnes attendues (utilisées pour la cohérence du code) ---
REF_COL="Référence annonce"; REGION_COL="Région"; DEPT_COL="Département"
EMPL_COL="Emplacement"; TYPO_COL="Typologie"; EXTRACTION_COL="Extraction"; RESTAURATION_COL="Restauration"
SURFACE_COL="Surface GLA"; LOYER_COL="Loyer annuel"; LAT_COL="Latitude"; LON_COL="Longitude"; ACTIF_COL="Actif"

# Volet droit : colonnes à afficher (typiquement de G à AL dans Excel)
# On suppose que ces colonnes suivent les colonnes principales après LOYER_COL.
# Pour l'exemple, nous allons chercher les colonnes entre l'index après LOYER_COL jusqu'à la colonne "Lien Google Maps".
# Le fichier Excel est censé fournir un nom exact pour "Lien Google Maps".
GOOGLE_MAPS_LINK_COL = "Lien Google Maps"
# Index de départ/fin (exclus) des colonnes à afficher dans le panneau de détails
# On va les définir dynamiquement après le chargement des données.
DETAIL_COLS_START_IDX = 0
DETAIL_COLS_END_IDX = 0


# ==============================================================================
# 2. FONCTIONS UTILES (HELPERS)
# ==============================================================================

# --- Gestion de la Police Futura ---
def _load_futura_css_from_assets():
    """Charge les polices Futura depuis le dossier assets/ et crée la règle CSS."""
    assets_dir = "assets"
    if not os.path.isdir(assets_dir): return ""
    # Ordre de préférence et noms typiques
    preferred = ["FuturaT-Book.ttf","FuturaT.ttf","FuturaT-Medium.ttf","FuturaT-Bold.ttf",
                 "FuturaL-Book.ttf","FuturaL-Medium.ttf","FuturaL-Bold.ttf"]
    files = [os.path.join(assets_dir,p) for p in preferred if os.path.exists(os.path.join(assets_dir,p))]
    if not files: files = glob.glob(os.path.join(assets_dir,"*.ttf")) # Fallback si les noms exacts ne sont pas là
    css=[]
    # Limiter à quelques fichiers pour l'exemple
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
    # Application de la police à toute l'application
    css.append(
        "*{font-family:'Futura SMBG', Futura, 'Futura PT', 'Century Gothic', Arial, sans-serif;}"
    )
    return "\n".join(css)

# --- Formatage de la Référence (Ex: 0005.1 -> 5.1) ---
def parse_ref_display(ref_str):
    """Supprime les zéros non significatifs à gauche de la partie entière."""
    s=str(ref_str).strip()
    if "." in s:
        left,right=s.split(".",1); left=re.sub(r"^0+","",left) or "0"; return f"{left}.{right}"
    return re.sub(r"^0+","",s) or s # On retourne 's' si c'est juste '0' ou un nombre sans décimale

# --- Formatage des valeurs (monétaire, surface) ---
def format_value(value, unit=""):
    """Formate une valeur numérique avec espace mille et unité, si possible."""
    s=str(value).strip()
    # Règle de masquage : vide, néant, -, /, ou 0
    if s.lower() in ("n/a","nan","","none","néant","-","/"): return ""
    try:
        # Nettoyage et conversion en nombre
        num=float(s.replace("€","").replace("m²","").replace("m2","").replace(" ","").replace(",","."))
        if num == 0.0: return "" # Règle de masquage: 0 ou valeur 0
        # Formatage avec espace mille
        txt=f"{num:,.0f}".replace(",", " ")
        return f"{txt} {unit}".strip() if unit else txt
    except: return s

# --- Réinitialisation de l'état ---
def reset_all():
    """Réinitialise les filtres et l'état de la carte."""
    # Réinitialisation des filtres (géré par Streamlit si on efface la session state)
    st.session_state.clear()
    st.rerun()

# ==============================================================================
# 3. GESTION DES DONNÉES
# ==============================================================================

@st.cache_data
def load_data(path):
    """Charge et prépare les données depuis le fichier Excel."""
    global DETAIL_COLS_START_IDX, DETAIL_COLS_END_IDX, GOOGLE_MAPS_LINK_COL

    df=pd.read_excel(path, dtype={REF_COL:str})
    df.columns=df.columns.str.strip()
    
    # Prétraitement de la Référence
    df[REF_COL]=df[REF_COL].astype(str).str.replace(".0","",regex=False).str.strip()
    
    # Conversion des colonnes numériques
    df[LAT_COL]=pd.to_numeric(df.get(LAT_COL,""), errors="coerce")
    df[LON_COL]=pd.to_numeric(df.get(LON_COL,""), errors="coerce")
    df["__SURF_NUM__"]=pd.to_numeric(df.get(SURFACE_COL,""), errors="coerce")
    df["__LOYER_NUM__"]=pd.to_numeric(df.get(LOYER_COL,""), errors="coerce")
    
    # Filtration stricte des lots Actifs ('oui') et avec coordonnées
    if ACTIF_COL in df.columns:
        df=df[df[ACTIF_COL].astype(str).str.lower().eq("oui")]
    df.dropna(subset=[LAT_COL,LON_COL], inplace=True)
    df.reset_index(drop=True,inplace=True)

    # Définition dynamique des colonnes de détails (de G à AL dans l'Excel)
    # On utilise les colonnes après 'Loyer annuel' jusqu'à la dernière colonne.
    main_cols = [REF_COL, REGION_COL, DEPT_COL, SURFACE_COL, LOYER_COL]
    
    # Trouver l'index de la colonne après LOYER_COL
    try:
        start_col_name = LOYER_COL
        start_idx = df.columns.tolist().index(start_col_name) + 1
        DETAIL_COLS_START_IDX = start_idx
        DETAIL_COLS_END_IDX = len(df.columns)
        
        # Vérification et détection de la colonne Google Maps si elle est dans la plage
        if GOOGLE_MAPS_LINK_COL not in df.columns:
            # Fallback si le nom exact n'existe pas, on cherche par mots-clés
            google_cols = [c for c in df.columns if any(k in c.lower() for k in ["lien google maps", "google maps", "lien google"])]
            if google_cols: GOOGLE_MAPS_LINK_COL = google_cols[0]
            
    except ValueError:
        st.error(f"Erreur : Colonne '{LOYER_COL}' non trouvée. Le panneau de détails ne peut pas être défini.")
        DETAIL_COLS_START_IDX = len(df.columns) # Pour cacher le panneau
        
    return df

# Chargement initial des données
data_df = load_data(EXCEL_FILE_PATH)

# Initialisation de l'état de l'annonce sélectionnée
if "selected_ref" not in st.session_state:
    st.session_state["selected_ref"] = None

# ==============================================================================
# 4. CSS GLOBAL (Layout 3 zones, Couleurs, Futura, Sidebar, Panel Droit)
# ==============================================================================

def logo_base64():
    """Encode le logo en base64 pour éviter le bouton d'agrandissement de Streamlit."""
    if not os.path.exists(LOGO_FILE_PATH): return ""
    return base64.b64encode(open(LOGO_FILE_PATH,"rb").read()).decode("ascii")

st.markdown(f"""
<style>
{_load_futura_css_from_assets()}

/* 3. Layout : Volet Gauche (Sidebar) + Zone Centrale (Carte) + Volet Droit (Panel) */

/* Largeur fixe du Volet Gauche et fond */
[data-testid="stSidebar"] {{
    width: {SIDEBAR_WIDTH} !important;
    background:{COLOR_SMBG_BLUE};
    color:white;
}}
/* Suppression du bouton de repli de la sidebar */
[data-testid="stSidebarCollapseButton"] {{ display:none !important; }}

/* Panneau droit rétractable : marges ajustées pour la carte */
/* La marge droite du contenu principal est la largeur du panneau droit (+ un petit padding) */
[data-testid="stAppViewContainer"] .main .block-container {{
    padding-right: calc({DETAIL_PANEL_WIDTH} + 20px);
}}

/* Le div du panneau droit est positionné fixe à droite, caché par défaut (width:0) */
.details-panel-container {{
    position: fixed; top: 0; right: 0;
    width: 0; height: 100vh;
    background:{COLOR_SMBG_BLUE}; color:#fff; z-index:1000;
    overflow-y:auto; overflow-x:hidden;
    transition: width 0.3s ease-in-out; /* Effet de glissement */
    box-shadow: -5px 0 15px rgba(0,0,0,0.35);
}}
/* Classe pour déplier le panneau */
.details-panel-open {{
    width: {DETAIL_PANEL_WIDTH};
    padding:16px;
}}
/* Le contenu reste caché tant que la largeur est à 0 */
.details-panel-container:not(.details-panel-open) > * {{ display:none; }}


/* 3. Design Sidebar et Logo */

/* Sidebar : marge haute 25px, aucun bouton collapse, fond bleu, titres cuivre */
[data-testid="stSidebar"] .block-container {{ padding-top:0 !important; }}

/* Marge haute pour le logo de 25px (gérée par le div vide en Python) */

/* Suppression du bouton d'agrandissement du logo */
button[kind="headerNoPadding"] {{ display:none !important; }}

/* Indentation départements 15px */
.dept-wrap {{ margin-left:15px; }}

/* 6. Style des Pins */
/* Icône main sur nos pins + style du pin */
.smbg-divicon {{ cursor:pointer; }}
.smbg-divicon > div {{
    width:30px;height:30px;border-radius:50%;
    background:{COLOR_SMBG_BLUE}; display:flex;align-items:center;justify-content:center;
    color:#fff;font-weight:700;font-size:12px;border:1px solid #001a27;
    box-shadow: 1px 1px 3px rgba(0,0,0,0.5);
}}

/* 6. & 9. Strictement AUCUN POPUP Leaflet */
.leaflet-popup, .leaflet-popup-pane,
.leaflet-popup-content-wrapper, .leaflet-popup-tip,
.leaflet-container a.leaflet-popup-close-button {{
  opacity:0 !important; width:0 !important; height:0 !important;
  padding:0 !important; margin:0 !important; border:0 !important; display:none !important;
}}

/* 8. Design du Panneau de Détails */
.maps-button {{
  width:100%; padding:9px; margin:8px 0 14px; background:{COLOR_SMBG_COPPER};
  color:#fff; border:none; border-radius:8px; cursor:pointer; text-align:center; font-weight:700;
  text-decoration:none; display:inline-block; /* Pour que le <a> ressemble à un bouton */
}}
.details-panel-container table {{ width:100%; border-collapse:collapse; font-size:13px; }}
.details-panel-container tr {{ border-bottom:1px solid #304f65; }}
.details-panel-container td {{ padding:6px 0; max-width:50%; overflow-wrap:break-word; }}
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# 5. SIDEBAR (VOLET GAUCHE)
# ==============================================================================
with st.sidebar:
    # Marge fixe de 25 px en haut (point 3 & 4)
    st.markdown("<div style='height:25px'></div>", unsafe_allow_html=True)

    # Logo via base64 (aucun bouton d’agrandissement)
    b64 = logo_base64()
    if b64:
        st.markdown(
            f"<img src='data:image/png;base64,{b64}' "
            f"style='width:100%;height:auto;display:block;margin:0;'>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div style='color:#fff;'>Logo SMBG introuvable</div>", unsafe_allow_html=True)

    # Petite marge de 10 px sous le logo
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # --- Initialisation des listes de sélection ---
    selected_regions = []
    selected_depts_global = []
    selected_depts_by_region = defaultdict(list)
    
    st.markdown("**Région / Département**")
    regions = sorted([x for x in data_df.get(REGION_COL,pd.Series()).dropna().astype(str).unique() if x.strip()])

    # --- Filtres Région/Département (Logique imbriquée) ---
    for reg in regions:
        # Checkbox Région
        rk = f"chk_region_{reg}"
        rchecked = st.checkbox(reg, key=rk)
        if rchecked:
            selected_regions.append(reg)
            
            # Afficher les départements seulement si la région est cochée
            pool = data_df[data_df[REGION_COL].astype(str).eq(reg)]
            depts = sorted([x for x in pool.get(DEPT_COL,pd.Series()).dropna().astype(str).unique() if x.strip()])
            
            for d in depts:
                # Checkbox Département (avec indentation de 15px)
                dk = f"chk_dept_{reg}_{d}"
                st.markdown("<div class='dept-wrap'>", unsafe_allow_html=True)
                dchecked = st.checkbox(d, key=dk)
                st.markdown("</div>", unsafe_allow_html=True)
                
                if dchecked:
                    selected_depts_global.append(d)
                    selected_depts_by_region[reg].append(d)

    st.markdown("---")

    # --- Sliders Surface et Loyer ---
    
    # Surface GLA (m²)
    s_data = data_df["__SURF_NUM__"].dropna()
    surf_min = int(s_data.min()) if not s_data.empty else 0
    surf_max = int(s_data.max()) if not s_data.empty else 1000
    smin, smax = st.slider(
        "Surface GLA (m²)",
        min_value=surf_min, max_value=surf_max,
        value=(surf_min, surf_max), step=1, key="slider_surface"
    )

    # Loyer annuel (€)
    l_data = data_df["__LOYER_NUM__"].dropna()
    loyer_min = int(l_data.min()) if not l_data.empty else 0
    loyer_max = int(l_data.max()) if not l_data.empty else 100000
    # Ajustement de l'incrément pour le loyer
    l_step = 1000 if loyer_max > 50000 else 100
    lmin, lmax = st.slider(
        "Loyer annuel (€)",
        min_value=loyer_min, max_value=loyer_max,
        value=(loyer_min, loyer_max), step=l_step, key="slider_loyer"
    )

    # --- Cases à cocher supplémentaires ---
    def draw_checks(title, column, prefix):
        st.markdown(f"**{title}**")
        opts=sorted([x for x in data_df.get(column,pd.Series()).dropna().astype(str).unique() if x.strip()])
        sels=[]
        for opt in opts:
            # On utilise le nom de l'option comme label et key
            if st.checkbox(opt, key=f"chk_{prefix}_{opt}"):
                sels.append(opt)
        st.markdown("---")
        return sels

    emp_sel  = draw_checks("Emplacement",  EMPL_COL, "emp")
    typo_sel = draw_checks("Typologie",   TYPO_COL, "typo")
    ext_sel  = draw_checks("Extraction",  EXTRACTION_COL, "ext")
    rest_sel = draw_checks("Restauration",RESTAURATION_COL, "rest")
    
    # --- Bouton Réinitialiser ---
    if st.button("Réinitialiser", use_container_width=True):
        reset_all()

# ==============================================================================
# 6. APPLICATION DES FILTRES
# ==============================================================================
f = data_df.copy()

# 1. Filtre Région / Département
if selected_regions or selected_depts_global:
    cond_parts = []
    
    # Masque basé sur les régions cochées et leurs départements
    reg_mask = pd.Series(False, index=f.index)
    for reg in selected_regions:
        reg_rows = f[REGION_COL].astype(str).eq(reg)
        depts_sel = selected_depts_by_region.get(reg, [])
        
        if depts_sel:
            # Région cochée, et certains départements cochés -> Union logique des départements
            reg_mask = reg_mask | ( reg_rows & f[DEPT_COL].astype(str).isin(depts_sel) )
        else:
            # Région cochée, mais AUCUN département coché -> Toute la région
            reg_mask = reg_mask | reg_rows
    
    # On ajoute le masque des régions (qui couvre le cas "région + tous départements" et "région + certains départements")
    if selected_regions:
        cond_parts.append(reg_mask)

    # On combine les conditions avec un OR logique pour inclure tous les lots filtrés.
    f = f[ np.logical_or.reduce(cond_parts) ] if cond_parts else f

# 2. Sliders Surface et Loyer
f = f[
    (f["__SURF_NUM__"].isna() | ((f["__SURF_NUM__"]>=smin) & (f["__SURF_NUM__"]<=smax))) &
    (f["__LOYER_NUM__"].isna()| ((f["__LOYER_NUM__"]>=lmin) & (f["__LOYER_NUM__"]<=lmax)))
]

# 3. Autres Cases à Cocher
if emp_sel:  f = f[f[EMPL_COL].astype(str).isin(emp_sel)]
if typo_sel: f = f[f[TYPO_COL].astype(str).isin(typo_sel)]
if ext_sel:  f = f[f[EXTRACTION_COL].astype(str).isin(ext_sel)]
if rest_sel: f = f[f[RESTAURATION_COL].astype(str).isin(rest_sel)]


# ==============================================================================
# 7. CARTE (PIN, ABSENCE DE JITTER/POPUP, GESTION DU CLIC)
# ==============================================================================

pins_df = f.copy()

# Centre de la carte basé sur les lots filtrés ou par défaut (France)
if pins_df.empty:
    center_lat,center_lon = 46.5, 2.5
    zoom_level = 6
else:
    center_lat = float(pins_df[LAT_COL].mean())
    center_lon = float(pins_df[LON_COL].mean())
    zoom_level = 6 # Zoom par défaut, Streamlit/Folium ajusteront si nécessaire

m = folium.Map(location=[center_lat,center_lon], zoom_start=zoom_level, control_scale=True)

# --- Fonction d'ajout de Pin (sans Jitter ni Popup visible) ---
def add_pin(m, lat, lon, label, ref_value):
    """Ajoute un marqueur DivIcon à l'emplacement exact et un CircleMarker pour la zone de clic."""
    
    # 1. Le DivIcon visible (le pin SMBG circulaire)
    icon_html=f"""
    <div class="smbg-divicon">
        <div>{label}</div>
    </div>"""
    folium.Marker(
        location=[lat,lon],
        icon=folium.DivIcon(html=icon_html, class_name="smbg-divicon", icon_size=(30,30), icon_anchor=(15,15)),
        # On utilise un popup TECHNIQUE (invisible via CSS) pour véhiculer la référence au st_folium
        popup=f"<div data-ref='{ref_value}'>{ref_value}</div>"
    ).add_to(m)
    
    # 2. Le CircleMarker cliquable (pour assurer une zone de clic facile sur le pin)
    folium.CircleMarker(
        location=[lat, lon], radius=15, color="#00000000",
        fill=True, fill_color="#00000000", fill_opacity=0.0, opacity=0.0,
        # Ce popup invisible est aussi nécessaire pour que st_folium intercepte l'événement
        popup=f"<div data-ref='{ref_value}'>{ref_value}</div>"
    ).add_to(m)


if not pins_df.empty:
    # 5. Affichage des Références formatées sur les pins
    pins_df["__ref_display__"] = pins_df[REF_COL].apply(parse_ref_display)
    
    # 6. Pas de Jitter : positionnement exact
    for _,r in pins_df.iterrows():
        add_pin(m, float(r[LAT_COL]), float(r[LON_COL]), r["__ref_display__"], r[REF_COL])

# Affichage de la carte et écoute de l'objet cliqué
map_output = st_folium(
    m, 
    height=MAP_HEIGHT, 
    width="100%", 
    returned_objects=["last_object_clicked", "last_clicked"], 
    key="map"
)

# --- Logique de gestion du Clic (Pin vs. Hors Pin) ---

# Règle 1: Clic sur Pin (via last_object_clicked)
ref_clicked = None
if map_output and map_output.get("last_object_clicked"):
    obj = map_output["last_object_clicked"]
    # Tenter d'extraire la référence cachée dans le popup technique
    for k in ("popup", "popup_html"):
        if k in obj and obj[k]:
            txt = str(obj[k]); mref = re.search(r"data-ref=['\"]([^'\"]+)['\"]", txt)
            ref_clicked = mref.group(1) if mref else None
            break
            
    if ref_clicked:
        # Clic sur un pin -> mettre à jour la référence et laisser le panneau s'ouvrir
        st.session_state["selected_ref"] = ref_clicked
    else:
        # Clic sur une zone (CircleMarker/Marker) qui n'a pas transmis de référence
        # C'est un cas qui ne devrait pas arriver si le setup est correct, mais on réinitialise par sécurité
        st.session_state["selected_ref"] = None

# Règle 2: Clic sur la carte (hors pin)
elif map_output and map_output.get("last_clicked"):
    # Si on a un événement 'last_clicked' (clic général sur la carte)
    # Et si l'on n'a PAS détecté de clic sur pin via 'last_object_clicked'
    
    # On compare la référence de la session (si elle existe) avec la référence du clic actuel.
    # Dans le cas où last_object_clicked est None et last_clicked est présent,
    # c'est un clic sur la carte, donc on replie le panneau.
    st.session_state["selected_ref"] = None

# On s'assure que 'selected_ref' reste la seule source de vérité pour le panneau droit.
sel_ref = st.session_state.get("selected_ref")


# ==============================================================================
# 8. VOLET DROIT (PANNEAU DE DÉTAILS RÉTRACTABLE)
# ==============================================================================

# On génère le contenu HTML du panneau
html_content = []
is_open = False # Est-ce que le panneau doit être ouvert ?

if sel_ref:
    # Trouver la ligne correspondante dans les données (même si le filtre la cacherait)
    row = data_df[data_df[REF_COL].astype(str).str.strip() == str(sel_ref).strip()]
    
    if not row.empty:
        is_open = True
        r = row.iloc[0]; ref_title = parse_ref_display(sel_ref)
        
        html_content += [
            "<h3 style='margin:0 0 6px 0;'>🔍 Détails de l'annonce</h3>",
            f"<h4 style='color:{COLOR_SMBG_COPPER};margin:0 0 10px 0;'>Réf. : {ref_title}</h4>",
            "<h5 style='margin:6px 0 8px;'>📋 Données clés</h5>",
            "<table>"
        ]
        
        all_cols = data_df.columns.tolist()
        # On utilise les index définis dynamiquement au chargement
        cols_slice = all_cols[DETAIL_COLS_START_IDX:DETAIL_COLS_END_IDX]
        
        for champ in cols_slice:
            sraw = str(r.get(champ,"")).strip()
            
            # Traitement spécial pour le Lien Google Maps
            if champ == GOOGLE_MAPS_LINK_COL:
                if sraw: # On n'affiche le bouton que s'il y a un lien
                    html_content.append(
                        f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>Lien Google Maps</td>"
                        f"<td><a class='maps-button' href='{sraw}' target='_blank'>Cliquer ici</a></td></tr>"
                    )
                continue
            
            # Détection de l'unité pour le formatage
            unit = ""
            if any(k in champ.lower() for k in ["loyer","charges","garantie","taxe","marketing","gestion","annuel","mensuel","foncière","honoraires"]):
                unit = "€"
            elif any(k in champ.lower() for k in ["surface","gla","utile","vitrine","linéaire"]):
                unit = "m²"
                
            # Formatage et règle de masquage si vide / 0
            sval = format_value(sraw, unit)
            
            if not sval: continue # Masquer la ligne si la valeur est vide, néant, -, /, ou 0
            
            html_content.append(f"<tr><td style='color:{COLOR_SMBG_COPPER};font-weight:bold;'>{champ}</td><td>{sval}</td></tr>")
            
        html_content += [
            "</table>",
            "<hr style='border:1px solid #304f65;margin:12px 0;'>",
            "<h5 style='margin:6px 0 8px;'>📷 Photos</h5>",
            "<div class='small-note'>Les photos seront affichées ici dès qu'elles seront en ligne.</div>"
        ]

# Affichage du panneau (ou du conteneur replié)
panel_class = "details-panel-container " + ("details-panel-open" if is_open else "")
st.markdown(f"<div class='{panel_class}'>{''.join(html_content)}</div>", unsafe_allow_html=True)

# Fin du fichier app.py

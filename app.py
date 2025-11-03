import pandas as pd 
import streamlit as st 
import folium 
from streamlit_folium import st_folium 
import numpy as np 
import re 
import os
import io

# --- FICHIERS ET COULEURS ---
COLOR_SMBG_BLUE = "#05263D" 
COLOR_SMBG_COPPER = "#C67B42" 

# Utilisation de l'URL brute pour charger le logo
# Assurez-vous que cette URL pointe vers votre logo
LOGO_FILE_PATH_URL = 'https://raw.githubusercontent.com/guillaume-smbg/smbg-carte/main/assets/Logo%20bleu%20crop.png'
# Pour le test, conservez l'emplacement de votre fichier Excel
EXCEL_FILE_PATH = 'data/Liste des lots.xlsx' 

# Clé de réinitialisation pour les filtres
RESET_KEY = 'reset_filters'
# --------------------

# --- 0. Configuration et Initialisation --- 
st.set_page_config(layout="wide", page_title="Carte Interactive SMBG") 

# --- Colonnes Essentielles --- 
REF_COL = 'Référence annonce' 
COL_REGION = 'Région'
COL_DEPARTEMENT = 'Département'
COL_EMPLACEMENT = 'Emplacement'
COL_TYPOLOGIE = 'Typologie'
COL_RESTAURATION = 'Restauration'
COL_SURFACE = 'Surface GLA' 
COL_LOYER = 'Loyer annuel' 

# COLONNES POUR L'INTERVALLE DE SURFACE ET LOYER
COL_NB_LOTS = 'Nombre de lots' 
COL_SURFACES_LOTS = 'Surfaces des lots' # Colonne N
COL_LOYER_UNITAIRE = 'Loyer en €/m²'   # Colonne T

# Nouvelles colonnes de travail pour les bornes Min/Max
COL_SURFACE_MIN = 'Surface Min' 
COL_SURFACE_MAX = 'Surface Max'
COL_LOYER_MIN = 'Loyer Annuel Min'
COL_LOYER_MAX = 'Loyer Annuel Max'
# ----------------------------------------------------------------------

# --- Fonction de réinitialisation ---
def reset_all_filters():
    """Réinitialise tous les états de session liés aux filtres."""
    for key in list(st.session_state.keys()):
        if key.startswith('reg_') or key.startswith('dept_') or \
           key.startswith('emp_') or key.startswith('type_') or \
           key.startswith('rest_') or key == 'surface_range' or key == 'loyer_range':
            del st.session_state[key]
    st.session_state['selected_ref'] = None
    st.session_state['last_clicked_coords'] = (0, 0)

# Initialisation de la session state
if 'selected_ref' not in st.session_state: 
    st.session_state['selected_ref'] = None 
if 'last_clicked_coords' not in st.session_state: 
    st.session_state['last_clicked_coords'] = (0, 0) 
if RESET_KEY not in st.session_state:
    st.session_state[RESET_KEY] = False


# --- Fonctions utilitaires de formatage --- 

def format_value(value, unit=""): 
    val_str = str(value).strip() 
    if val_str in ('N/A', 'nan', '', 'None', 'None €', 'None m²', '/'): 
        return "Non renseigné" 
    if any(c.isalpha() for c in val_str) and not any(c.isdigit() for c in val_str): 
        return val_str 
    try: 
        num_value = float(value) 
        if num_value != round(num_value, 2): 
            val_str = f"{num_value:,.2f}" 
            val_str = val_str.replace(',', ' ') 
            val_str = val_str.replace('.', ',') 
        else: 
            val_str = f"{num_value:,.0f}" 
            val_str = val_str.replace(',', ' ') 
        if unit and not val_str.lower().endswith(unit.lower().strip()): 
            return f"{val_str} {unit}" 
    except (ValueError, TypeError): 
        pass 
    return val_str 

def format_monetary_value(row): 
    money_keywords = ['Loyer', 'Charges', 'garantie', 'foncière', 'Taxe', 'Marketing', 'Gestion', 'BP', 'annuel', 'Mensuel', 'Prix', 'm²'] 
    champ = row['Champ'] 
    value = row['Valeur'] 
    is_numeric = pd.api.types.is_numeric_dtype(pd.Series(value)) 
    val_str = str(value).strip()
    if val_str in ('N/A', 'nan', '', 'None', 'None €', 'None m²', '/'): 
        return "Non renseigné" 
    is_money_col = any(keyword.lower() in champ.lower() for keyword in money_keywords) 
    if is_money_col and is_numeric: 
        try: 
            float_value = float(value) 
            formatted_value = f"{float_value:,.0f}" 
            formatted_value = formatted_value.replace(",", " ") 
            return f"€{formatted_value}" 
        except (ValueError, TypeError): 
            pass 
    is_surface_col = any(keyword.lower() in champ.lower() for keyword in ['Surface', 'GLA', 'utile']) 
    if is_surface_col and is_numeric: 
        try:
            float_value = float(value) 
            formatted_value = f"{float_value:,.0f}" 
            formatted_value = formatted_value.replace(",", " ") 
            return f"{formatted_value} m²" 
        except (ValueError, TypeError): 
            pass 
    if champ in ['Latitude', 'Longitude'] and is_numeric: 
        try: 
            return f"{float(value):.4f}" 
        except (ValueError, TypeError): 
            pass 
    return val_str 

# --- Fonction de prétraitement pour l'extraction des bornes de Surface (N) ---
def extract_surface_bounds(row):
    """Extrait les surfaces Min et Max à partir de 'Surfaces des lots' (N) ou 'Surface GLA' (L)."""
    surfaces_str = str(row.get(COL_SURFACES_LOTS, '')).lower().strip().replace('m2', '').replace('m²', '')
    
    # Remplacer la virgule des décimales par un point, et supprimer les espaces pour la conversion
    surfaces_str_clean = surfaces_str.replace(',', '.').replace(' ', '')
    
    # 1. Tenter d'extraire l'intervalle (ex: "170 à 1200" ou "170-1200")
    match_interval = re.search(r'(\d+\.?\d*)\s*(?:à|-)\s*(\d+\.?\d*)', surfaces_str_clean)
    if match_interval:
        min_s = float(match_interval.group(1))
        max_s = float(match_interval.group(2))
        return pd.Series([min(min_s, max_s), max(min_s, max_s)])
    
    # 2. Tenter d'extraire une liste de surfaces (ex: "170,450,1200")
    surfaces_list = re.findall(r'\d+\.?\d*', surfaces_str_clean)
    if surfaces_list:
        numeric_surfaces = [float(s) for s in surfaces_list]
        if numeric_surfaces:
            return pd.Series([min(numeric_surfaces), max(numeric_surfaces)])
            
    # 3. Utiliser la Surface GLA (Lot unique)
    gla = row.get(COL_SURFACE, 0)
    gla_val = pd.to_numeric(gla, errors='coerce')
    if pd.notna(gla_val) and gla_val > 0:
        return pd.Series([gla_val, gla_val])

    # 4. Valeur par défaut
    return pd.Series([0.0, 0.0])


@st.cache_data 
def load_data(file_path): 
    try: 
        df = pd.read_excel(file_path, dtype={REF_COL: str}) 
        df.columns = df.columns.str.strip() 
        
        # Renommage des colonnes (Gestion des variations dans le fichier)
        df = df.rename(columns={
            'Typologie du bien': COL_TYPOLOGIE,
            'Nombre de lots': COL_NB_LOTS, 
            'Surfaces des lots': COL_SURFACES_LOTS,
            'Loyer en m² / an': COL_LOYER_UNITAIRE, # Supporte un autre nom commun
            'Loyer au m²': COL_LOYER_UNITAIRE       # Supporte un autre nom commun
        }, errors='ignore')
            
        required_cols = [REF_COL, 'Latitude', 'Longitude', COL_REGION, COL_DEPARTEMENT, COL_EMPLACEMENT, COL_TYPOLOGIE, COL_RESTAURATION, COL_SURFACE, COL_LOYER, COL_NB_LOTS, COL_SURFACES_LOTS, COL_LOYER_UNITAIRE]
        for col in required_cols:
            if col not in df.columns:
                df[col] = np.nan
        
        # --- 1. Conversion des loyers unitaires (T) ---
        df[COL_LOYER_UNITAIRE] = pd.to_numeric(df[COL_LOYER_UNITAIRE], errors='coerce').fillna(0)
        
        # --- 2. CRÉATION DES BORNES MIN/MAX DE SURFACE (N) ---
        df[[COL_SURFACE_MIN, COL_SURFACE_MAX]] = df.apply(extract_surface_bounds, axis=1)
        df[COL_SURFACE_MIN] = pd.to_numeric(df[COL_SURFACE_MIN], errors='coerce').fillna(0)
        df[COL_SURFACE_MAX] = pd.to_numeric(df[COL_SURFACE_MAX], errors='coerce').fillna(0)
        
        # --- 3. CRÉATION DES BORNES DE LOYER ANNUEL (Loyer Min/Max) ---
        
        # Calculer le loyer annuel minimum et maximum à partir de Loyer/m² * Surface
        df[COL_LOYER_MIN] = df[COL_SURFACE_MIN] * df[COL_LOYER_UNITAIRE]
        df[COL_LOYER_MAX] = df[COL_SURFACE_MAX] * df[COL_LOYER_UNITAIRE]
        
        # Pour les lots dont le loyer unitaire est nul, utiliser la colonne Loyer annuel (L) si elle est renseignée (lot unique)
        mask_loyer_direct = (df[COL_LOYER_UNITAIRE] == 0) & (pd.to_numeric(df[COL_LOYER], errors='coerce').notna())
        
        loyer_annuel_numeric = pd.to_numeric(df[COL_LOYER], errors='coerce').fillna(0)
        
        # Si le loyer annuel (L) est renseigné et que le loyer unitaire (T) est vide, on utilise (L) pour Min et Max
        df.loc[mask_loyer_direct, COL_LOYER_MIN] = loyer_annuel_numeric
        df.loc[mask_loyer_direct, COL_LOYER_MAX] = loyer_annuel_numeric
        
        # Remplir les NaN restants (annonces sans surface ni loyer) par 0
        df[COL_LOYER_MIN] = df[COL_LOYER_MIN].fillna(0)
        df[COL_LOYER_MAX] = df[COL_LOYER_MAX].fillna(0)
        
        # --- 4. Nettoyage final pour la cartographie ---
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce') 
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce') 
        df[REF_COL] = df[REF_COL].astype(str).str.strip() 
        df[REF_COL] = df[REF_COL].apply(lambda x: x.split('.')[0] if isinstance(x, str) else str(x).split('.')[0]) 
        df[REF_COL] = df[REF_COL].str.zfill(5) 
        
        # Nettoyage final des lignes sans coordonnées
        df.dropna(subset=['Latitude', 'Longitude'], inplace=True) 
        
        if COL_RESTAURATION in df.columns:
            df[COL_RESTAURATION] = df[COL_RESTAURATION].fillna('Non renseigné').astype(str)

        return df, None 
    except Exception as e: 
        return pd.DataFrame(), f"❌ Erreur critique lors du chargement: {e}" 

# --- Chargement des données --- 
data_df, error_message = load_data(EXCEL_FILE_PATH) 

# --- CSS / HTML pour le volet flottant et la barre latérale (inchangé) --- 
CUSTOM_CSS = f""" 
<style> 
/* Style du Panneau de Détails Droit (bleu SMBG) */
.details-panel {{ 
    position: fixed; 
    top: 0; 
    right: 0; 
    width: 300px; 
    height: 100vh; 
    background-color: {COLOR_SMBG_BLUE};
    color: white;
    z-index: 1000; 
    padding: 15px; 
    box-shadow: -5px 0 15px rgba(0,0,0,0.4); 
    overflow-y: auto; 
    transition: transform 0.4s ease-in-out; 
}} 

/* 🎨 Style de la Barre Latérale Gauche (st.sidebar) */
[data-testid="stSidebar"] {{
    background-color: {COLOR_SMBG_BLUE};
    color: white; 
}}

/* 🎨 Style des Headers de la Barre Latérale en cuivré SMBG */
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {{
    color: {COLOR_SMBG_COPPER} !important;
}}

/* 🎨 Couleur des cases à cocher */
[data-testid="stSidebar"] label span {{
    color: white !important;
}}
[data-testid="stSidebar"] label span strong {{
    color: white !important; 
}}

/* ❌ Suppression de la flèche (bouton hamburger) */
[data-testid="stSidebar"] > div:first-child > div:first-child {{
    display: none !important;
}}

/* ⬆️ Marge Triple / Logo descendu */
[data-testid="stSidebar"] > div:first-child {{
    padding-top: 30px !important; 
}}

/* ❌ Supprime les contrôles par défaut (bouton agrandir) de Streamlit sur les images */
.stImage > button {{
    display: none !important;
}}

/* 🎨 Style du Bouton Réinitialiser */
button[kind="secondary"] {{
    background-color: {COLOR_SMBG_COPPER} !important;
    border-color: {COLOR_SMBG_COPPER} !important;
    color: white !important;
}}

/* Styles du Bouton Google Maps */
.maps-button {{ 
    width: 100%; 
    padding: 10px; 
    margin-bottom: 15px; 
    background-color: {COLOR_SMBG_COPPER}; 
    color: white; 
    border: none; 
    border-radius: 5px; 
    cursor: pointer; 
    font-weight: bold; 
    text-align: center; 
    display: block;
}} 

/* Styles pour le tableau détaillé dans le volet */
.details-panel table {{
    width: 100%; 
    border-collapse: collapse; 
    font-size: 13px;
}}
.details-panel tr {{
    border-bottom: 1px solid #304f65; 
}}
.details-panel td {{
    padding: 5px 0;
    max-width: 50%; 
    overflow-wrap: break-word;
}}
</style> 
""" 
st.markdown(CUSTOM_CSS, unsafe_allow_html=True) 
# -------------------------------------------------------------------------

# --- 1. Préparation des variables de mise en page et de filtrage --- 

selected_ref_clean = st.session_state['selected_ref'].strip() if st.session_state['selected_ref'] else None 
if selected_ref_clean == 'None': 
    selected_ref_clean = None 
    st.session_state['selected_ref'] = None 

show_details = selected_ref_clean and not data_df[data_df[REF_COL].str.strip() == selected_ref_clean].empty 
panel_class = "details-panel-open" if show_details else "details-panel-closed" 

filtered_df = data_df.copy()

# --- 2. Panneau de Contrôle Gauche (Dans le st.sidebar) --- 

with st.sidebar: 
    # 🎨 Logo 
    st.image(LOGO_FILE_PATH_URL, use_column_width=True) 
    
    st.markdown("---")
    st.info(f"Annonces chargées : **{len(data_df)}**") 
    
    # ➕ Bouton de réinitialisation des filtres
    if st.button("Réinitialiser tous les filtres", use_container_width=True, type="secondary"):
        reset_all_filters()
        st.rerun()

    st.markdown("---") 

    # --- 2.1. FILTRE 1: RÉGION / DÉPARTEMENT ---
    
    selected_regions = []
    selected_depts = []
    
    if COL_REGION in data_df.columns and COL_DEPARTEMENT in data_df.columns:
        st.subheader("Région et Départements")
        
        regions = data_df[COL_REGION].dropna().unique()
        
        for region in sorted(regions):
            region_key = f"reg_{region}"
            
            if region_key not in st.session_state:
                st.session_state[region_key] = False

            is_region_selected = st.checkbox(label=f"**{region}**", key=region_key)
            
            if is_region_selected:
                selected_regions.append(region)
            
            departements = data_df[data_df[COL_REGION] == region][COL_DEPARTEMENT].dropna().unique()
            
            show_dept_list = is_region_selected or any(st.session_state.get(f"dept_{dept}", False) for dept in departements)
            
            if show_dept_list:
                for dept in sorted(departements):
                    dept_key = f"dept_{dept}"
                    
                    if dept_key not in st.session_state:
                         st.session_state[dept_key] = False
                    
                    col_indent, col_dept = st.columns([0.1, 0.9])
                    with col_dept:
                        st.checkbox(label=f"{dept}", key=dept_key) 
                        
                        if st.session_state[dept_key]:
                             selected_depts.append(dept)

        if selected_regions or selected_depts:
            region_indices = data_df[data_df[COL_REGION].isin(selected_regions)].index
            dept_indices = data_df[data_df[COL_DEPARTEMENT].isin(selected_depts)].index
            
            combined_geo_indices = region_indices.union(dept_indices)
            
            filtered_df = filtered_df.loc[filtered_df.index.intersection(combined_geo_indices)].copy()
            
    
    st.markdown("---")

    # --- 2.2. FILTRES 2: CASES À COCHER INDIVIDUELLES ---
    st.subheader("Caractéristiques du Lot")
    
    selected_charac_map = {
        COL_EMPLACEMENT: [],
        COL_TYPOLOGIE: [], 
        COL_RESTAURATION: []
    }
    
    if COL_EMPLACEMENT in data_df.columns:
        st.markdown(f'**{COL_EMPLACEMENT} :**')
        options_emp = data_df[COL_EMPLACEMENT].dropna().unique()
        for option in sorted(options_emp):
            key_emp = f'emp_{option}'
            if key_emp not in st.session_state: st.session_state[key_emp] = False
            if st.checkbox(f'{option}', key=key_emp):
                selected_charac_map[COL_EMPLACEMENT].append(option)
    
    if COL_TYPOLOGIE in data_df.columns: 
        st.markdown(f'**{COL_TYPOLOGIE} :**')
        options_type = data_df[COL_TYPOLOGIE].dropna().unique()
        for option in sorted(options_type):
            key_type = f'type_{option}'
            if key_type not in st.session_state: st.session_state[key_type] = False
            if st.checkbox(f'{option}', key=key_type):
                selected_charac_map[COL_TYPOLOGIE].append(option)

    if COL_RESTAURATION in data_df.columns:
        st.markdown(f'**{COL_RESTAURATION} :**')
        options_restauration = data_df[COL_RESTAURATION].dropna().unique()
        for option in sorted(options_restauration):
            key_rest = f'rest_{option}'
            if key_rest not in st.session_state: st.session_state[key_rest] = False
            if st.checkbox(f'{option}', key=key_rest):
                selected_charac_map[COL_RESTAURATION].append(option)
                
    for col, selected_options in selected_charac_map.items():
        if selected_options and not filtered_df.empty:
            filtered_df = filtered_df[filtered_df[col].isin(selected_options)]

    st.markdown("---")

    # --- 2.3. FILTRES 3: SLIDERS (Surface GLA et Loyer) ---
    st.subheader("Valeurs Numériques (Filtre par Intervalle)")
    
    # 2.3.1. Surface GLA (Filtrage par chevauchement d'intervalle)
    if COL_SURFACE_MIN in data_df.columns and COL_SURFACE_MAX in data_df.columns:
        
        # On utilise uniquement les lignes qui ont une Surface Max > 0 pour les bornes du slider
        df_surface_valid = data_df[data_df[COL_SURFACE_MAX] > 0]
        
        if not df_surface_valid.empty:
            min_s_total = float(df_surface_valid[COL_SURFACE_MIN].min()) 
            max_s_total = float(df_surface_valid[COL_SURFACE_MAX].max())

            if 'surface_range' not in st.session_state:
                 st.session_state['surface_range'] = (min_s_total, max_s_total)

            if min_s_total < max_s_total:
                surface_range = st.slider(
                    f'{COL_SURFACE} disponible (m²)',
                    min_value=min_s_total,
                    max_value=max_s_total,
                    value=st.session_state['surface_range'],
                    step=10.0,
                    format="%.0f m²",
                    key='surface_range'
                )
                
                filtre_min_user = surface_range[0]
                filtre_max_user = surface_range[1]
                
                # Condition pour l'inclusion : (Lot_Min <= Filtre_Max) ET (Lot_Max >= Filtre_Min)
                filtered_df = filtered_df[
                    (filtered_df[COL_SURFACE_MIN] <= filtre_max_user) & 
                    (filtered_df[COL_SURFACE_MAX] >= filtre_min_user)
                ]

    # 2.3.2. Loyer Annuel (Filtrage par chevauchement d'intervalle)
    if COL_LOYER_MIN in data_df.columns and COL_LOYER_MAX in data_df.columns:
        
        min_l_initial = float(data_df[COL_LOYER_MIN].min()) 
        max_l_initial = float(data_df[COL_LOYER_MAX].max())

        if max_l_initial > 0: # S'il y a au moins un loyer > 0
            
            # La borne min du slider doit être 0 si 0 est présent, sinon la plus petite valeur > 0
            min_l_display = 0.0 
            if min_l_initial > 0 :
                 min_l_display = min_l_initial
            
            # Initialisation du slider (avec 0 si nécessaire)
            if 'loyer_range' not in st.session_state:
                 st.session_state['loyer_range'] = (min_l_display, max_l_initial)

            if min_l_display < max_l_initial:
                loyer_range = st.slider(
                    f'Loyer Annuel disponible (€)',
                    min_value=min_l_display,
                    max_value=max_l_initial,
                    value=st.session_state['loyer_range'],
                    step=100.0,
                    format="%.0f €",
                    key='loyer_range'
                )
                
                filtre_min_user = loyer_range[0]
                filtre_max_user = loyer_range[1]
                
                # Condition d'inclusion par défaut (filtre min est à 0) : 
                is_at_min_default = (filtre_min_user <= min_l_display)
                
                if is_at_min_default:
                    # Inclure tous les lots qui chevauchent la plage, y compris ceux dont la borne est 0
                    filtered_df = filtered_df[
                        (filtered_df[COL_LOYER_MIN] <= filtre_max_user) & 
                        (filtered_df[COL_LOYER_MAX] >= filtre_min_user)
                    ]
                else:
                    # Si l'utilisateur a monté le filtre min, les loyers à 0 sont exclus
                     filtered_df = filtered_df[
                        (filtered_df[COL_LOYER_MIN] <= filtre_max_user) & 
                        (filtered_df[COL_LOYER_MAX] >= filtre_min_user) &
                        (filtered_df[COL_LOYER_MAX] > 0)
                    ]
                
    st.markdown("---")
    st.info(f"Annonces filtrées : **{len(filtered_df)}**")
    
    if error_message: 
        st.error(error_message) 
    elif data_df.empty: 
        st.warning("Le DataFrame est vide.") 
# --- FIN st.sidebar ---

# --- 3. Zone de la Carte (Corps Principal) --- 

MAP_HEIGHT = 800 

df_to_map = filtered_df

if not df_to_map.empty: 
    centre_lat = df_to_map['Latitude'].mean() 
    centre_lon = df_to_map['Longitude'].mean() 
    
    m = folium.Map(location=[centre_lat, centre_lon], zoom_start=6, control_scale=True) 

    for index, row in df_to_map.iterrows(): 
        lat = row['Latitude'] 
        lon = row['Longitude'] 
        
        # --- CORRECTION : Suppression du popup ---
        
# --- PINS BLEUS SMBG AVEC NUMÉRO DE RÉFÉRENCE ---
ref_disp = None
try:
    ref_disp = str(int(row[REF_COL]))
except Exception:
    ref_disp = str(row[REF_COL])
html_pin = f"""
<div style="width:30px;height:30px;border-radius:50%;
            background:{COLOR_SMBG_BLUE};
            display:flex;align-items:center;justify-content:center;
            color:#fff;font-weight:700;font-size:12px;border:1px solid #001a27;">
    {ref_disp}
</div>
"""
folium.Marker(
    location=[lat, lon],
    icon=folium.DivIcon(html=html_pin, class_name="smbg-divicon", icon_size=(30,30), icon_anchor=(15,15))
).add_to(m)
map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=['last_clicked'], key="main_map") 

    # --- Logique de détection de clic --- 
    if map_output and map_output.get("last_clicked"): 
        clicked_coords = map_output["last_clicked"] 
        current_coords = (clicked_coords['lat'], clicked_coords['lng']) 
        
        data_df['distance_sq'] = (data_df['Latitude'] - current_coords[0])**2 + (data_df['Longitude'] - current_coords[1])**2 
        closest_row = data_df.loc[data_df['distance_sq'].idxmin()] 
        min_distance_sq = data_df['distance_sq'].min() 
        
        DISTANCE_THRESHOLD = 0.01 

        if current_coords != st.session_state['last_clicked_coords']: 
            st.session_state['last_clicked_coords'] = current_coords 
            
            if min_distance_sq > DISTANCE_THRESHOLD: 
                if st.session_state['selected_ref'] is not None: 
                    st.session_state['selected_ref'] = None 
                    st.rerun() 
            else: 
                new_ref = closest_row[REF_COL] 
                if new_ref != st.session_state['selected_ref']: 
                    st.session_state['selected_ref'] = new_ref 
                    st.rerun() 
             
else: 
    st.info("⚠️ Aucun lot ne correspond aux critères de filtre.") 


# --- 4. Panneau de Détails Droit (Injection HTML Flottant) --- 

html_content = f""" 
<div class="details-panel {panel_class}"> 
""" 
if show_details: 
    selected_data_series = data_df[data_df[REF_COL].str.strip() == selected_ref_clean] 
    
    if len(selected_data_series) > 0: 
        selected_data = selected_data_series.iloc[0].copy() 
        
        try: 
            display_title_ref = str(int(selected_ref_clean)) 
        except ValueError: 
            display_title_ref = selected_ref_clean 
            
        html_content += f""" 
            <h3 style="color:white; margin-top: 0;">🔍 Détails du Lot</h3> 
            <hr style="border: 1px solid #ccc; margin: 5px 0;"> 
            <h4 style="color: {COLOR_SMBG_COPPER};">Réf. : {display_title_ref}</h4> 
        """ 
        
        lien_maps = selected_data.get('Lien Google Maps', None) 
        
        if lien_maps and pd.notna(lien_maps) and str(lien_maps).lower().strip() not in ('nan', 'n/a', 'none', ''): 
            html_content += f"""
                <a href="{lien_maps}" target="_blank" style="text-decoration: none;">
                    <button class="maps-button">
                        🌍 Voir sur Google Maps
                    </button>
                </a>
            """
            
        adresse = selected_data.get('Adresse', 'N/A') 
        code_postal = selected_data.get('Code Postal', '') 
        ville = selected_data.get('Ville', '') 
        
        html_content += f'<p style="font-weight: bold; color: {COLOR_SMBG_COPPER}; margin: 10px 0 5px;">📍 Adresse complète</p>' 
        adresse_str = str(adresse).strip() 
        code_ville_str = f"{code_postal} - {ville}".strip() 
        
        html_content += f'<p style="margin: 0; font-size: 14px; color: white;">' 
        if adresse_str not in ('N/A', 'nan', ''): 
             html_content += f'{adresse_str}<br>' 
        
        if code_ville_str not in ('N/A - N/A', 'nan - nan', '-'): 
             html_content += f'{code_ville_str}' 
        
        html_content += '</p>' 


        html_content += '<hr style="border: 1px solid #eee; margin: 15px 0;">' 
        
        
html_content += '<hr style="border: 1px solid #eee; margin: 15px 0;">'
html_content += '<h5 style="color: white; margin-top: 20px; margin-bottom: 10px;">📋 Données de l\'annonce</h5>'

# === Affichage strict G → AH (indices 6..33), avec H (index 7) en bouton ===
all_cols = data_df.columns.tolist()
cols_slice = all_cols[6:34] if len(all_cols) >= 34 else all_cols[6:]
html_content += '<table style="width:100%; border-collapse: collapse; font-size: 13px;">'
for idx, champ in enumerate(cols_slice, start=6):
    valeur = selected_data.get(champ, '')
    # masquer vides / '-' / '/'
    if str(valeur).strip() in ['', '-', '/']:
        continue
    # Colonne H (index 7) -> bouton Google Maps
    if idx == 7 or champ.lower().strip() in ['lien google maps','google maps','lien google']:
        url = str(valeur).strip()
        if url:
            html_content += f"""
            <tr style="border-bottom:1px solid #304f65;">
                <td style="font-weight:bold; color:{COLOR_SMBG_COPPER}; padding:5px 0;">Lien Google Maps</td>
                <td style="text-align:right; padding:5px 0;">
                    <a class="maps-button" href="{url}" target="_blank">Cliquer ici</a>
                </td>
            </tr>"""
        continue
    # Détermination de l'unité et arrondi à 0 décimale
    unit = ''
    if any(k in champ for k in ['Loyer','Charges','garantie','foncière','Taxe','Marketing','Gestion','BP','annuel','Mensuel']) and '€' not in champ:
        unit = '€'
    elif any(k in champ for k in ['Surface','GLA','utile']) and 'm²' not in champ:
        unit = 'm²'
    try:
        # on tente un cast; si ok, arrondi 0 et séparateurs
        v = str(valeur).replace('€','').replace('m²','').replace('m2','').replace(' ', '').replace(',', '.')
        num = float(v)
        txt = f"{num:,.0f}".replace(',', ' ')
        valeur_fmt = f"{txt} {unit}".strip() if unit else txt
    except Exception:
        valeur_fmt = str(valeur)
    html_content += f"""
    <tr style="border-bottom:1px solid #304f65;">
        <td style="font-weight:bold; color:{COLOR_SMBG_COPPER}; padding:5px 0; max-width:50%; overflow-wrap:break-word;">{champ}</td>
        <td style="text-align:right; padding:5px 0; max-width:50%; overflow-wrap:break-word; color:white;">{valeur_fmt}</td>
    </tr>"""
html_content += "</table>"
"
        
    else: 
        html_content += "<p style='color: white;'>❌ Erreur: Référence non trouvée.</p>" 
        
else: 
    pass 

html_content += '</div>' 
st.markdown(html_content, unsafe_allow_html=True) 


# --- 5. Affichage de l'Annonce Sélectionnée (Tableau complet en bas) --- 
st.markdown("---") 
st.header("📋 Annonce du Lot Sélectionné (Tableau complet)") 

dataframe_container = st.container() 

with dataframe_container: 
    if show_details: 
        selected_row_df = data_df[data_df[REF_COL].str.strip() == selected_ref_clean].copy() 
        
        if not selected_row_df.empty: 
            if 'distance_sq' in selected_row_df.columns: 
                display_df = selected_row_df.drop(columns=['distance_sq']) 
            else: 
                display_df = selected_row_df 
                
            all_cols = display_df.columns.tolist() 
            
            # Exclusion des colonnes de travail et des redondances pour le tableau du bas
            cols_to_remove_from_bottom_table = ['Typologie du bien', COL_SURFACE_MIN, COL_SURFACE_MAX, COL_LOYER_MIN, COL_LOYER_MAX, 'Lien Google Maps']
            for col in cols_to_remove_from_bottom_table:
                if col in all_cols:
                    all_cols.remove(col)
                    
            display_df = display_df[all_cols]
            
            # Tentative de centrage sur les informations clés
            try: 
                adresse_index = all_cols.index('Adresse') 
                commentaires_index = all_cols.index('Commentaires') 
                cols_to_keep = all_cols[adresse_index : commentaires_index + 1] 
                display_df = display_df[cols_to_keep] 
            except ValueError: 
                pass 

            transposed_df = display_df.T.reset_index() 
            transposed_df.columns = ['Champ', 'Valeur'] 
            
            # Formatage des valeurs monétaires et de surface
            transposed_df['Valeur'] = transposed_df.apply(format_monetary_value, axis=1) 
            
            st.dataframe(transposed_df, hide_index=True, use_container_width=True) 
            
        else: 
            st.warning(f"Référence **{selected_ref_clean}** introuvable dans les données.") 
    else: 
        st.info("Cliquez sur un marqueur sur la carte pour afficher l'annonce complète ici.")
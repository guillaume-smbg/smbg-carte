import pandas as pd 
import streamlit as st 
import folium 
from streamlit_folium import st_folium 
import numpy as np 
from folium.features import DivIcon

# --- FICHIERS ET COULEURS ---
COLOR_SMBG_BLUE = "#05263D" 
COLOR_SMBG_COPPER = "#C67B42" 

# Utilisation de l'URL brute pour charger le logo
LOGO_FILE_PATH_URL = 'https://raw.githubusercontent.com/guillaume-smbg/smbg-carte/main/assets/Logo%20bleu%20crop.png'
EXCEL_FILE_PATH = 'data/Liste des lots.xlsx' 

# Clé de réinitialisation pour les filtres
RESET_KEY = 'reset_filters'
# --------------------

# --- 0. Configuration et Initialisation --- 
st.set_page_config(layout="wide", page_title="Carte Interactive") 

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
    
# Initialisation de la session state (inchangée)
if 'selected_ref' not in st.session_state: 
    st.session_state['selected_ref'] = None 
if 'last_clicked_coords' not in st.session_state: 
    st.session_state['last_clicked_coords'] = (0, 0) 
if RESET_KEY not in st.session_state:
    st.session_state[RESET_KEY] = False

# --- Colonnes Essentielles (Mise à jour COL_TYPOLOGIE = 'Typologie') --- 
REF_COL = 'Référence annonce' 
COL_REGION = 'Région'
COL_DEPARTEMENT = 'Département'
COL_EMPLACEMENT = 'Emplacement'
COL_TYPOLOGIE = 'Typologie' # <- CORRIGÉ pour refléter le nom de la colonne J
COL_RESTAURATION = 'Restauration'
COL_SURFACE = 'Surface GLA' 
COL_LOYER = 'Loyer annuel' 
# ----------------------------------------------------------------------

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
    color: white; /* Couleur du texte par défaut */
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
    color: white !important; /* pour les labels en gras */
}}

/* ❌ Suppression de la flèche (bouton hamburger) */
[data-testid="stSidebar"] > div:first-child > div:first-child {{
    display: none !important;
}}

/* ⬆️ Marge Triple / Logo descendu */
[data-testid="stSidebar"] > div:first-child {{
    /* Augmente le padding supérieur pour faire descendre le logo */
    padding-top: 30px !important; 
}}
/* ⬆️ Remonte le bloc en dessous du logo (espace réduit) et supprime les contrôles Streamlit sur l'image */
.sidebar-logo-container img {{
    /* Règle l'espace juste pour l'image (en remplacement de .stImage) */
    margin-bottom: 5px !important; 
}}
/* ❌ Supprime les contrôles par défaut (bouton agrandir) de Streamlit sur les images */
.stImage > button {{
    display: none !important;
}}

/* 🎨 Style du Bouton Réinitialiser (Forcé en style SMBG Cuivré) */
button[kind="secondary"] {{
    background-color: {COLOR_SMBG_COPPER} !important;
    border-color: {COLOR_SMBG_COPPER} !important;
    color: white !important;
}}
/* S'assurer que le style est maintenu au survol (hover) */
button[kind="secondary"]:hover {{
    background-color: #A36437 !important; /* Cuivré légèrement plus foncé */
    border-color: #A36437 !important;
    color: white !important;
}}

/* Styles du Bouton Google Maps (inchangé) */
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

/* Styles pour le tableau détaillé dans le volet (inchangé) */
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

# --- Fonctions utilitaires (inchangées) --- 

def format_value(value, unit=""): 
    # ... (Fonction inchangée)
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
    # ... (Fonction inchangée)
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

@st.cache_data 
def load_data(file_path): 
    # ... (Fonction inchangée)
    try: 
        df = pd.read_excel(file_path, dtype={REF_COL: str}) 
        df.columns = df.columns.str.strip() 
        
        required_cols = [REF_COL, 'Latitude', 'Longitude', COL_REGION, COL_DEPARTEMENT, COL_EMPLACEMENT, COL_TYPOLOGIE, COL_RESTAURATION, COL_SURFACE, COL_LOYER]
        for col in required_cols:
            # Si le nom de colonne de travail n'est pas trouvé, on le crée avec des NaNs
            if col not in df.columns:
                # Exception pour 'Typologie du bien' si l'utilisateur utilisait l'ancienne colonne
                if col == COL_TYPOLOGIE and 'Typologie du bien' in df.columns:
                    df[COL_TYPOLOGIE] = df['Typologie du bien']
                else:
                    df[col] = np.nan 

        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce') 
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce') 
        df[REF_COL] = df[REF_COL].astype(str).str.strip() 
        df[REF_COL] = df[REF_COL].apply(lambda x: x.split('.')[0] if isinstance(x, str) else str(x).split('.')[0]) 
        df[REF_COL] = df[REF_COL].str.zfill(5) 
        df.dropna(subset=['Latitude', 'Longitude'], inplace=True) 
        
        if COL_RESTAURATION in df.columns:
            df[COL_RESTAURATION] = df[COL_RESTAURATION].fillna('Non renseigné').astype(str)

        # Conversion numérique propre pour les filtres sliders
        if COL_SURFACE in df.columns:
            df[COL_SURFACE] = pd.to_numeric(df[COL_SURFACE], errors='coerce').fillna(0)
        if COL_LOYER in df.columns:
            df[COL_LOYER] = pd.to_numeric(df[COL_LOYER], errors='coerce').fillna(0)

        return df, None 
    except Exception as e: 
        return pd.DataFrame(), f"❌ Erreur critique lors du chargement: {e}" 

# --- Chargement des données --- 
data_df, error_message = load_data(EXCEL_FILE_PATH) 

# --- 1. Préparation des variables de mise en page et de filtrage (inchangée) --- 

selected_ref_clean = st.session_state['selected_ref'].strip() if st.session_state['selected_ref'] else None 
if selected_ref_clean == 'None': 
    selected_ref_clean = None 
    st.session_state['selected_ref'] = None 

show_details = selected_ref_clean and not data_df[data_df[REF_COL].str.strip() == selected_ref_clean].empty 
panel_class = "details-panel-open" if show_details else "details-panel-closed" 

filtered_df = data_df.copy()

# --- 2. Panneau de Contrôle Gauche (Dans le st.sidebar) --- 

with st.sidebar: 
    # 🎨 Logo avec div pour supprimer le bouton agrandir
    st.markdown('<div class="sidebar-logo-container">', unsafe_allow_html=True)
    st.image(LOGO_FILE_PATH_URL, use_column_width=True) 
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.info(f"Annonces chargées : **{len(data_df)}**") 
    
    # ➕ Bouton de réinitialisation des filtres (Style forcé par CSS)
    if st.button("Réinitialiser tous les filtres", use_container_width=True, type="secondary"):
        reset_all_filters()
        st.rerun()

    st.markdown("---") 

    # --- 2.1. FILTRE 1: RÉGION / DÉPARTEMENT (Logique d'union) ---
    
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
            
            # Si la région est cochée, on l'ajoute à la liste des régions sélectionnées
            if is_region_selected:
                selected_regions.append(region)
            
            # Affichage des départements si la région est cochée OU si au moins un département est déjà coché dans cette région
            departements = data_df[data_df[COL_REGION] == region][COL_DEPARTEMENT].dropna().unique()
            
            show_dept_list = is_region_selected or any(st.session_state.get(f"dept_{dept}", False) for dept in departements)
            
            if show_dept_list:
                for dept in sorted(departements):
                    dept_key = f"dept_{dept}"
                    
                    if dept_key not in st.session_state:
                         st.session_state[dept_key] = False
                    
                    # On affiche la checkbox du département
                    col_indent, col_dept = st.columns([0.1, 0.9])
                    with col_dept:
                        # Le checkbox est affiché et son état est géré par la session_state
                        st.checkbox(label=f"{dept}", key=dept_key) 
                        
                        # Si le checkbox est coché (dans l'état de session), on l'ajoute à la liste de filtrage
                        if st.session_state[dept_key]:
                             selected_depts.append(dept)

        # LOGIQUE DE FILTRAGE GÉOGRAPHIQUE (Union des Régions/Départements) :
        if selected_regions or selected_depts:
            # Filtre par région ET/OU département
            region_indices = data_df[data_df[COL_REGION].isin(selected_regions)].index
            dept_indices = data_df[data_df[COL_DEPARTEMENT].isin(selected_depts)].index
            
            # Union (OR) : On prend tous les lots dans les régions sélectionnées ET tous les lots dans les départements sélectionnés
            combined_geo_indices = region_indices.union(dept_indices)
            
            # Application du filtre à filtered_df
            # Note : On filtre `data_df` puis on croise avec `filtered_df.index` pour respecter les autres filtres
            # Correction : filtered_df doit être filtré directement si des régions/départements sont sélectionnés.
            # On assure que le filtre s'applique à l'état actuel de filtered_df
            filtered_df = filtered_df.loc[filtered_df.index.intersection(combined_geo_indices)].copy()
            
    
    st.markdown("---")

    # --- 2.2. FILTRES 2: CASES À COCHER INDIVIDUELLES (Emplacement, Typologie, Restauration) ---
    st.subheader("Caractéristiques du Lot")
    
    selected_charac_map = {
        COL_EMPLACEMENT: [],
        COL_TYPOLOGIE: [], # <- Utilise 'Typologie'
        COL_RESTAURATION: []
    }
    
    # 2.2.1. Emplacement
    if COL_EMPLACEMENT in data_df.columns:
        st.markdown(f'**{COL_EMPLACEMENT} :**')
        options_emp = data_df[COL_EMPLACEMENT].dropna().unique()
        for option in sorted(options_emp):
            key_emp = f'emp_{option}'
            if key_emp not in st.session_state:
                st.session_state[key_emp] = False
            
            if st.checkbox(f'{option}', key=key_emp):
                selected_charac_map[COL_EMPLACEMENT].append(option)
    
    # 2.2.2. Typologie du bien
    if COL_TYPOLOGIE in data_df.columns: # <- Utilise 'Typologie'
        st.markdown(f'**{COL_TYPOLOGIE} :**')
        options_type = data_df[COL_TYPOLOGIE].dropna().unique()
        for option in sorted(options_type):
            key_type = f'type_{option}'
            if key_type not in st.session_state:
                st.session_state[key_type] = False
                
            if st.checkbox(f'{option}', key=key_type):
                selected_charac_map[COL_TYPOLOGIE].append(option)

    # 2.2.3. Restauration
    if COL_RESTAURATION in data_df.columns:
        st.markdown(f'**{COL_RESTAURATION} :**')
        options_restauration = data_df[COL_RESTAURATION].dropna().unique()
        for option in sorted(options_restauration):
            key_rest = f'rest_{option}'
            if key_rest not in st.session_state:
                st.session_state[key_rest] = False
                
            if st.checkbox(f'{option}', key=key_rest):
                selected_charac_map[COL_RESTAURATION].append(option)
                
    # LOGIQUE DE FILTRAGE CASES À COCHER (AND entre catégories) :
    for col, selected_options in selected_charac_map.items():
        if selected_options and not filtered_df.empty:
            filtered_df = filtered_df[filtered_df[col].isin(selected_options)]

    st.markdown("---")

    # --- 2.3. FILTRES 3: SLIDERS (Surface GLA et Loyer) ---
    st.subheader("Valeurs Numériques")
    
    # 2.3.1. Surface GLA 
    if COL_SURFACE in data_df.columns and pd.api.types.is_numeric_dtype(data_df[COL_SURFACE]):
        df_surface = data_df[data_df[COL_SURFACE] > 0]
        
        if not df_surface.empty:
            min_s_total = float(df_surface[COL_SURFACE].min())
            max_s_total = float(df_surface[COL_SURFACE].max())
            
            if 'surface_range' not in st.session_state or st.session_state['surface_range'] == (0.0, 0.0):
                 st.session_state['surface_range'] = (min_s_total, max_s_total)

            if min_s_total < max_s_total:
                surface_range = st.slider(
                    f'{COL_SURFACE} (m²)',
                    min_value=min_s_total,
                    max_value=max_s_total,
                    value=st.session_state['surface_range'],
                    step=10.0,
                    format="%.0f m²",
                    key='surface_range'
                )
                filtered_df = filtered_df[
                    (filtered_df[COL_SURFACE] >= surface_range[0]) & 
                    (filtered_df[COL_SURFACE] <= surface_range[1])
                ]

    # 2.3.2. Loyer Annuel 
    if COL_LOYER in data_df.columns and pd.api.types.is_numeric_dtype(data_df[COL_LOYER]):
        df_loyer = data_df[data_df[COL_LOYER] > 0]
        
        if not df_loyer.empty:
            min_l_total = float(df_loyer[COL_LOYER].min())
            max_l_total = float(df_loyer[COL_LOYER].max())

            if 'loyer_range' not in st.session_state or st.session_state['loyer_range'] == (0.0, 0.0):
                 st.session_state['loyer_range'] = (min_l_total, max_l_total)

            if min_l_total < max_l_total:
                loyer_range = st.slider(
                    f'{COL_LOYER} (€)',
                    min_value=min_l_total,
                    max_value=max_l_total,
                    value=st.session_state['loyer_range'],
                    step=100.0,
                    format="%.0f €",
                    key='loyer_range'
                )
                filtered_df = filtered_df[
                    (filtered_df[COL_LOYER] >= loyer_range[0]) & 
                    (filtered_df[COL_LOYER] <= loyer_range[1])
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
        
        folium.CircleMarker( 
            location=[lat, lon], 
            radius=10, 
            color=COLOR_SMBG_BLUE, 
            fill=True, 
            fill_color=COLOR_SMBG_BLUE, 
            fill_opacity=0.8, 
        ).add_to(m) 

    map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=['last_clicked'], key="main_map") 

    # --- Logique de détection de clic (inchangée) --- 
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


# --- 4. Panneau de Détails Droit (Injection HTML Flottant via st.markdown) --- 

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
        
        html_content += '<h5 style="color: white; margin-top: 20px; margin-bottom: 10px;">📋 Annonce du Lot Sélectionné</h5>'
        
        # COLONNES À EXCLURE : on ajoute l'ancienne colonne Typologie du bien pour éviter la redondance
        cols_to_exclude = [
            REF_COL, 'Latitude', 'Longitude', 'Lien Google Maps', 'Adresse', 
            'Code Postal', 'Ville', 'distance_sq', 'Photos annonce', 'Actif', 
            'Valeur BP', 'Contact', 'Page Web', 
            'Typologie du bien' # <- EXCLUSION de l'ancienne colonne pour éviter la redondance
        ]
        all_cols = data_df.columns.tolist()
        
        temp_cols = [c for c in all_cols if c not in cols_to_exclude]
        
        html_content += """
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
        """
        
        for champ in temp_cols:
            valeur = selected_data.get(champ, 'N/A')
            unit = ''
            if any(k in champ for k in ['Loyer', 'Charges', 'garantie', 'foncière', 'Taxe', 'Marketing', 'Gestion', 'BP', 'annuel', 'Mensuel']) and '€' not in champ: 
                unit = '€' 
            elif any(k in champ for k in ['Surface', 'GLA', 'utile']) and 'm²' not in champ: 
                unit = 'm²' 
            formatted_value = format_value(valeur, unit=unit)
            
            html_content += f"""
            <tr style="border-bottom: 1px solid #304f65;">
                <td style="font-weight: bold; color: {COLOR_SMBG_COPPER}; padding: 5px 0; max-width: 50%; overflow-wrap: break-word;">{champ}</td>
                <td style="text-align: right; padding: 5px 0; max-width: 50%; overflow-wrap: break-word; color: white;">{formatted_value}</td>
            </tr>
            """
            
        html_content += "</table>"
        
    else: 
        html_content += "<p style='color: white;'>❌ Erreur: Référence non trouvée.</p>" 
        
else: 
    # Le panneau est vide par défaut (plus de logo)
    pass 

html_content += '</div>' 
st.markdown(html_content, unsafe_allow_html=True) 


# --- 5. Affichage de l'Annonce Sélectionnée (Sous la carte, inchangé) --- 
st.markdown("---") 
st.header("📋 Annonce du Lot Sélectionné (Tableau complet)") 

dataframe_container = st.container() 

with dataframe_container: 
    if show_details: 
        selected_row_df = data_df[data_df[REF_COL].str.strip() == selected_ref_clean].copy() 
        
        if not selected_row_df.empty: 
            lien_maps = selected_row_df.iloc[0].get('Lien Google Maps', None) 

            if lien_maps and pd.notna(lien_maps) and str(lien_maps).lower().strip() not in ('nan', 'n/a', 'none', ''): 
                col1, col2, col3 = st.columns([1, 6, 1]) 
                with col2: 
                    st.markdown("<hr style='margin-top: 5px; margin-bottom: 10px;'>", unsafe_allow_html=True) 
                    st.link_button( 
                        label="🌍 Voir sur Google Maps", 
                        url=lien_maps, 
                        type="secondary", 
                        use_container_width=True 
                    ) 
                    st.markdown("<hr style='margin-top: 10px; margin-bottom: 5px;'>", unsafe_allow_html=True) 

            if 'distance_sq' in selected_row_df.columns: 
                display_df = selected_row_df.drop(columns=['distance_sq']) 
            else: 
                display_df = selected_row_df 
                
            all_cols = display_df.columns.tolist() 
            
            # Exclusion de l'ancienne colonne 'Typologie du bien' pour le tableau du bas aussi
            if 'Typologie du bien' in all_cols:
                all_cols.remove('Typologie du bien')
                display_df = display_df[all_cols]
            
            try: 
                adresse_index = all_cols.index('Adresse') 
                commentaires_index = all_cols.index('Commentaires') 
                cols_to_keep = all_cols[adresse_index : commentaires_index + 1] 
                display_df = display_df[cols_to_keep] 
            except ValueError: 
                pass 

            transposed_df = display_df.T.reset_index() 
            transposed_df.columns = ['Champ', 'Valeur'] 
            transposed_df = transposed_df[transposed_df['Champ'] != 'Lien Google Maps'] 
            
            transposed_df['Valeur'] = transposed_df.apply(format_monetary_value, axis=1) 
            
            st.dataframe(transposed_df, hide_index=True, use_container_width=True) 
            
        else: 
            st.warning(f"Référence **{selected_ref_clean}** introuvable dans les données.") 
    else: 
        st.info("Cliquez sur un marqueur sur la carte pour afficher l'annonce complète ici.")

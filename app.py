import pandas as pd 
import streamlit as st 
import folium 
from streamlit_folium import st_folium 
import numpy as np 
from folium.features import DivIcon

# --- COULEURS SMBG ---
COLOR_SMBG_BLUE = "#05263D" 
COLOR_SMBG_COPPER = "#C67B42" 
# --------------------

# --- 0. Configuration et Initialisation --- 
st.set_page_config(layout="wide", page_title="Carte Interactive") 

# Initialisation de la session state 
if 'selected_ref' not in st.session_state: 
    st.session_state['selected_ref'] = None 
if 'last_clicked_coords' not in st.session_state: 
    st.session_state['last_clicked_coords'] = (0, 0) 

# --- Chemin d'accès du fichier et Colonnes Essentielles --- 
EXCEL_FILE_PATH = 'data/Liste des lots.xlsx' 
REF_COL = 'Référence annonce' 
COL_REGION = 'Région'
COL_DEPARTEMENT = 'Département'

# --- CSS / HTML pour le volet flottant --- 
CUSTOM_CSS = f""" 
<style> 
/* Styles du Panneau de Détails */
.details-panel {{ 
    position: fixed; 
    top: 0; 
    right: 0; 
    width: 300px; 
    height: 100vh; 
    background-color: white; 
    z-index: 1000; 
    padding: 15px; 
    box-shadow: -5px 0 15px rgba(0,0,0,0.2); 
    overflow-y: auto; 
    transition: transform 0.4s ease-in-out; 
}} 

.details-panel-closed {{ 
    transform: translateX(100%); 
}} 

.details-panel-open {{ 
    transform: translateX(0); 
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
    border-bottom: 1px solid #eee;
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

# --- Fonctions utilitaires de formatage --- 

def format_value(value, unit=""): 
    """ Formate la valeur pour le panneau de droite. """ 
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
    """Applique le formatage monétaire/surface pour le st.dataframe.""" 
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
    try: 
        df = pd.read_excel(file_path, dtype={REF_COL: str}) 
        df.columns = df.columns.str.strip() 
        
        if REF_COL not in df.columns or 'Latitude' not in df.columns or 'Longitude' not in df.columns: 
             return pd.DataFrame(), f"Colonnes essentielles manquantes. Colonnes trouvées : {list(df.columns)}" 
            
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce') 
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce') 
        
        df[REF_COL] = df[REF_COL].astype(str).str.strip() 
        df[REF_COL] = df[REF_COL].apply(lambda x: x.split('.')[0] if isinstance(x, str) else str(x).split('.')[0]) 
        df[REF_COL] = df[REF_COL].str.zfill(5) 
        
        df.dropna(subset=['Latitude', 'Longitude'], inplace=True) 
        
        return df, None 
    except Exception as e: 
        return pd.DataFrame(), f"❌ Erreur critique lors du chargement: {e}" 

# --- Chargement des données --- 
data_df, error_message = load_data(EXCEL_FILE_PATH) 

# --- 1. Préparation des variables de mise en page et de filtrage --- 

selected_ref_clean = st.session_state['selected_ref'].strip() if st.session_state['selected_ref'] else None 
if selected_ref_clean == 'None': 
    selected_ref_clean = None 
    st.session_state['selected_ref'] = None 

show_details = selected_ref_clean and not data_df[data_df[REF_COL].str.strip() == selected_ref_clean].empty 
panel_class = "details-panel-open" if show_details else "details-panel-closed" 

# Déclaration du DataFrame qui sera utilisé pour la carte
filtered_df = data_df.copy()

# --- 2. Panneau de Contrôle Gauche (Dans le st.sidebar) --- 

with st.sidebar: 
    st.header("⚙️ Contrôles et Filtres") 
    
    st.info(f"Lots chargés : **{len(data_df)}**") 
    st.markdown("---") 

    # --- 2.1. FILTRE UNIQUE: RÉGION / DÉPARTEMENT ---
    
    selected_depts = []
    
    if COL_REGION in data_df.columns and COL_DEPARTEMENT in data_df.columns:
        st.subheader("Région et Départements")
        
        regions = data_df[COL_REGION].dropna().unique()
        
        for region in sorted(regions):
            region_key = f"reg_{region}"
            
            # Checkbox Région: AUCUNE cochée par défaut (value=False)
            is_region_selected = st.checkbox(label=f"**{region}**", key=region_key, value=False)
            
            # Affichage des Départements UNIQUEMENT si la région est sélectionnée
            if is_region_selected:
                departements = data_df[data_df[COL_REGION] == region][COL_DEPARTEMENT].dropna().unique()
                
                for dept in sorted(departements):
                    dept_key = f"dept_{dept}"
                    
                    # Utilisation de st.columns pour l'indentation visuelle
                    col_indent, col_dept = st.columns([0.1, 0.9])
                    with col_dept:
                        # Checkbox Département: AUCUNE cochée par défaut (value=False)
                        if st.checkbox(label=f"{dept}", key=dept_key, value=False):
                            selected_depts.append(dept)

        # Application du filtre
        if selected_depts:
            # On filtre le DataFrame sur les départements sélectionnés
            filtered_df = data_df[data_df[COL_DEPARTEMENT].isin(selected_depts)].copy()
        else:
            # Si selected_depts est vide, le DataFrame filtré doit être vide par défaut
            filtered_df = data_df.iloc[0:0]
            
    # --- FIN FILTRES ---

    st.markdown("---")
    # Affichage du nombre de lots après filtrage
    st.info(f"Lots filtrés : **{len(filtered_df)}**")
    
    # Bouton Masquer/Afficher les détails
    if show_details: 
        if st.button("Masquer les détails", key="hide_left", use_container_width=True): 
            st.session_state['selected_ref'] = None 
            st.rerun() 
    
    if error_message: 
        st.error(error_message) 
    elif data_df.empty: 
        st.warning("Le DataFrame est vide.") 
# --- FIN st.sidebar ---

# --- 3. Zone de la Carte (Corps Principal) --- 

MAP_HEIGHT = 800 
st.header("Carte des Lots Immobiliers") 

df_to_map = filtered_df

if not df_to_map.empty: 
    # Recalculer le centre uniquement sur les données filtrées
    centre_lat = df_to_map['Latitude'].mean() 
    centre_lon = df_to_map['Longitude'].mean() 
    
    m = folium.Map(location=[centre_lat, centre_lon], zoom_start=6, control_scale=True) 

    # --- Création des marqueurs --- 
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

    # Affichage et capture des événements de clic 
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
    st.info("⚠️ Aucun lot ne correspond aux critères de filtre. Veuillez sélectionner au moins une Région et un Département.") 


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
            <h3 style="color:#303030; margin-top: 0;">🔍 Détails du Lot</h3> 
            <hr style="border: 1px solid #ccc; margin: 5px 0;"> 
            <h4 style="color: {COLOR_SMBG_BLUE};">Réf. : {display_title_ref}</h4> 
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
        
        html_content += f'<p style="font-weight: bold; color: #555; margin: 10px 0 5px;">📍 Adresse complète</p>' 
        adresse_str = str(adresse).strip() 
        code_ville_str = f"{code_postal} - {ville}".strip() 
        
        html_content += f'<p style="margin: 0; font-size: 14px;">' 
        if adresse_str not in ('N/A', 'nan', ''): 
             html_content += f'{adresse_str}<br>' 
        
        if code_ville_str not in ('N/A - N/A', 'nan - nan', '-'): 
             html_content += f'{code_ville_str}' 
        
        html_content += '</p>' 


        html_content += '<hr style="border: 1px solid #eee; margin: 15px 0;">' 
        
        html_content += '<h5 style="color: #303030; margin-top: 20px; margin-bottom: 10px;">📋 Annonce du Lot Sélectionné</h5>'
        
        # Préparation des données pour le tableau HTML
        # Suppression des colonnes non pertinentes pour l'affichage des détails
        cols_to_exclude = [REF_COL, 'Latitude', 'Longitude', 'Lien Google Maps', 'Adresse', 'Code Postal', 'Ville', 'distance_sq', 'Photos annonce', 'Actif', 'Valeur BP', 'Contact', 'Page Web']
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
            <tr style="border-bottom: 1px solid #eee;">
                <td style="font-weight: bold; color: {COLOR_SMBG_BLUE}; padding: 5px 0; max-width: 50%; overflow-wrap: break-word;">{champ}</td>
                <td style="text-align: right; padding: 5px 0; max-width: 50%; overflow-wrap: break-word;">{formatted_value}</td>
            </tr>
            """
            
        html_content += "</table>"
        
    else: 
        html_content += "<p>❌ Erreur: Référence non trouvée.</p>" 
        
else: 
    html_content += f""" 
    <p style="font-weight: bold; margin-top: 10px; color: {COLOR_SMBG_BLUE};"> 
        Cliquez sur un marqueur (cercle) sur la carte pour afficher ses détails ici. 
    </p> 
    """ 

html_content += '</div>' 
st.markdown(html_content, unsafe_allow_html=True) 


# --- 5. Affichage de l'Annonce Sélectionnée (Sous la carte - pour l'exhaustivité) --- 
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

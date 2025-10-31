import pandas as pd 
import streamlit as st 
import folium 
from streamlit_folium import st_folium 
import numpy as np 
# --- NOUVEAU: Import pour les pins numérotés ---
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

# --- Chemin d'accès du fichier --- 
EXCEL_FILE_PATH = 'data/Liste des lots.xlsx' 
REF_COL = 'Référence annonce' 

# --- CSS / HTML pour le volet flottant --- 
CUSTOM_CSS = f""" 
<style> 
/* 1. La classe de base : définit l'apparence, la position FIXE et la TRANSITION */ 
.details-panel { 
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
} 

/* 2. Classe pour l'état FERMÉ (caché) */ 
.details-panel-closed { 
    transform: translateX(100%); 
} 

/* 3. Classe pour l'état OUVERT (visible) */ 
.details-panel-open { 
    transform: translateX(0); 
} 

/* Ajustement pour que le st.sidebar (Contrôles Gauche) soit bien visible */ 
.css-hxt7xp {{ 
    z-index: 1000 !important; 
}} 

/* Assure que la section principale gère correctement le débordement horizontal */ 
section.main {{ 
    overflow-x: auto; 
}} 

/* Style du bouton Google Maps ré-implémenté en HTML (Couleur Cuivre) */ 
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

</style> 
""" 
# On injecte le CSS dès le début 
st.markdown(CUSTOM_CSS, unsafe_allow_html=True) 
# --- FIN CSS / HTML --- 

# --- Fonctions utilitaires de formatage --- 

def format_value(value, unit=""): 
    """ 
    Formate la valeur en utilisant un ESPACE comme séparateur de milliers 
    et une VIRGULE comme séparateur décimal (norme FR). 
    """ 
    val_str = str(value).strip() 
    
    if val_str in ('N/A', 'nan', '', 'None', 'None €', 'None m²', '/'): 
        return "Non renseigné" 
        
    if any(c.isalpha() for c in val_str) and not any(c.isdigit() for c in val_str): 
        return val_str 
    
    try: 
        num_value = float(value) 
        
        # Formatage avec espace milliers / virgule décimale 
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

def format_table_value(value, champ): 
    """Applique le formatage monétaire/surface/coordonnées pour le tableau.""" 
    money_keywords = ['Loyer', 'Charges', 'garantie', 'foncière', 'Taxe', 'Marketing', 'Gestion', 'BP', 'annuel', 'Mensuel', 'Prix'] 
    
    val_str = str(value).strip()
    if val_str in ('N/A', 'nan', '', 'None', 'None €', 'None m²', '/'): 
        return "Non renseigné" 
        
    is_numeric = pd.api.types.is_numeric_dtype(pd.Series(value))
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
    
    return format_value(value)

# --- Fonction de Chargement des Données (Cache Réactivé) --- 
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

# --- 1. Préparation des variables de mise en page --- 

selected_ref_clean = st.session_state['selected_ref'].strip() if st.session_state['selected_ref'] else None 
if selected_ref_clean == 'None': 
    selected_ref_clean = None 
    st.session_state['selected_ref'] = None 

show_details = selected_ref_clean and not data_df[data_df[REF_COL].str.strip() == selected_ref_clean].empty 

panel_class = "details-panel-open" if show_details else "details-panel-closed" 


# --- 2. Panneau de Contrôle Gauche (Dans le st.sidebar) --- 
with st.sidebar: 
    st.header("⚙️ Contrôles") 
    st.markdown("---") 
    
    st.info(f"Lots chargés: **{len(data_df)}**") 
    
    if show_details: 
        if st.button("Masquer les détails", key="hide_left", use_container_width=True): 
            st.session_state['selected_ref'] = None 
            st.rerun() 
    
    st.markdown("---") 
    
    if error_message: 
        st.error(error_message) 
    elif data_df.empty: 
        st.warning("Le DataFrame est vide.") 

# --- 3. Zone de la Carte (Corps Principal) --- 

MAP_HEIGHT = 800 
st.header("Carte des Lots Immobiliers") 

if not data_df.empty: 
    centre_lat = data_df['Latitude'].mean() 
    centre_lon = data_df['Longitude'].mean() 
    
    m = folium.Map(location=[centre_lat, centre_lon], zoom_start=6, control_scale=True) 

    # --- Création des marqueurs --- 
    for index, row in data_df.iterrows(): 
        lat = row['Latitude'] 
        lon = row['Longitude'] 
        
        # Référence sans zéros de tête pour l'affichage
        ref = row[REF_COL].lstrip('0') 
        
        # 1. CircleMarker (pour la zone de clic - Couleur SMBG)
        folium.CircleMarker( 
            location=[lat, lon], 
            radius=10, 
            color=COLOR_SMBG_BLUE, 
            fill=True, 
            fill_color=COLOR_SMBG_BLUE, 
            fill_opacity=0.8, 
        ).add_to(m) 
        
        # 2. DivIcon (pour le numéro - Couleur Cuivre SMBG)
        # 🎯 ATTENTION: pointer-events: none est essentiel pour laisser passer le clic
        icon_style = f"font-size: 10px; font-weight: bold; color: {COLOR_SMBG_COPPER}; text-align: center; line-height: 20px; width: 20px; height: 20px; pointer-events: none;"

        folium.Marker( 
            location=[lat, lon], 
            icon=DivIcon( 
                icon_size=(20, 20), 
                icon_anchor=(10, 10), 
                html=f'<div style="{icon_style}">{ref}</div>', 
            ) 
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
        
        # Seuil de clic élargi 
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
    st.info("⚠️ Le DataFrame est vide ou les coordonnées sont manquantes. Aucune carte ne peut être affichée.") 


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
            
        # --- Entête (Réf. : en Bleu SMBG) --- 
        html_content += f""" 
            <h3 style="color:#303030; margin-top: 0;">🔍 Détails du Lot</h3> 
            <hr style="border: 1px solid #ccc; margin: 5px 0;"> 
            <h4 style="color: {COLOR_SMBG_BLUE};">Réf. : {display_title_ref}</h4> 
        """ 
        
        # --- Bouton Google Maps (Réimplémenté en HTML avec la couleur Cuivre) --- 
        lien_maps = selected_data.get('Lien Google Maps', None) 
        
        if lien_maps and pd.notna(lien_maps) and str(lien_maps).lower().strip() not in ('nan', 'n/a', 'none', ''): 
            html_content += f"""
                <a href="{lien_maps}" target="_blank" style="text-decoration: none;">
                    <button class="maps-button">
                        🌍 Voir sur Google Maps
                    </button>
                </a>
            """
            
        # --- Affichage de l'adresse --- 
        adresse = selected_data.get('Adresse', 'N/A') 
        code_postal = selected_data.get('Code Postal', '') 
        ville = selected_data.get('Ville', '') 
        
        html_content += f'<p style="font-weight: bold; color: #555; margin: 10px 0 5px;">📍 Adresse complète</p>' 
        adresse_str = str(adresse).strip() 
        code_ville_str = f"{code_postal} - {ville}".strip() 
        
        html_content += f'<p style="margin: 0 0 15px 0; font-size: 14px;">' 
        if adresse_str not in ('N/A', 'nan', ''): 
             html_content += f'{adresse_str}<br>'
        
        if code_ville_str not in ('N/A - N/A', 'nan - nan', '-'): 
             html_content += f'{code_ville_str}' 
        
        html_content += '</p>'
        
        # ---------------------------------------------------------------------------------
        # --- TABLEAU DÉTAILLÉ (Déplacé de la section 5) ---
        # ---------------------------------------------------------------------------------
        
        html_content += '<h5 style="color: #303030; margin-top: 20px; margin-bottom: 10px;">📋 Annonce du Lot Sélectionné</h5>'
        
        # Préparation du DataFrame pour l'affichage (Filtrage et Transposition) 
        temp_df = selected_data_series.copy()
        
        if 'distance_sq' in temp_df.columns: 
            temp_df = temp_df.drop(columns=['distance_sq']) 
            
        all_cols = temp_df.columns.tolist() 
        
        # Filtrage pour ne garder que les colonnes de 'Adresse' jusqu'à 'Commentaires'
        try: 
            adresse_index = all_cols.index('Adresse') 
            commentaires_index = all_cols.index('Commentaires') 
            cols_to_keep = all_cols[adresse_index : commentaires_index + 1] 
            display_df = temp_df[cols_to_keep] 
        except ValueError: 
            # Fallback
            try:
                adresse_index = all_cols.index('Adresse')
                cols_to_keep = all_cols[adresse_index:]
                display_df = temp_df[cols_to_keep]
            except ValueError:
                display_df = temp_df

        # Transposition et nettoyage
        transposed_df = display_df.T.reset_index() 
        transposed_df.columns = ['Champ', 'Valeur'] 
        transposed_df = transposed_df[transposed_df['Champ'] != 'Lien Google Maps'] 
        # On exclut les champs d'adresse déjà affichés en haut
        transposed_df = transposed_df[~transposed_df['Champ'].isin(['Adresse', 'Code Postal', 'Ville'])] 
        
        # Début de la table HTML
        html_content += """
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
        """
        
        # Ajout des lignes formatées
        for index, row in transposed_df.iterrows():
            champ = row['Champ']
            valeur = row['Valeur']
            formatted_value = format_table_value(valeur, champ)
            
            html_content += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="font-weight: bold; color: {COLOR_SMBG_BLUE}; padding: 5px 0; max-width: 50%; overflow-wrap: break-word;">{champ}</td>
                <td style="text-align: right; padding: 5px 0; max-width: 50%; overflow-wrap: break-word;">{formatted_value}</td>
            </tr>
            """
            
        # Fin de la table HTML
        html_content += "</table>"
        
    else: 
        html_content += "<p>❌ Erreur: Référence non trouvée.</p>" 
        
else: 
    # Message par défaut 
    html_content += f""" 
    <p style="font-weight: bold; margin-top: 10px; color: {COLOR_SMBG_BLUE};"> 
        Cliquez sur un marqueur (cercle) sur la carte pour afficher ses détails ici. 
    </p> 
    """ 

# Fermeture de la div flottante (FIN du panneau) 
html_content += '</div>' 
st.markdown(html_content, unsafe_allow_html=True) 

# --- 5. L'ancienne section d'affichage du tableau sous la carte est maintenant vide ---
# st.markdown("---") 
# st.header("📋 Annonce du Lot Sélectionné") 
# ... (SUPPRIMÉE)

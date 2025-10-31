import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
import streamlit.components.v1 as components # NOUVEAU: Importation pour l'injection HTML

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

# --- CSS / HTML pour le volet flottant avec transition ---
# Note : Le CSS est maintenant injecté directement dans le composant HTML
# pour une meilleure isolation, mais nous gardons cette section pour la clarté.
# L'injection finale se fera via components.html
CUSTOM_CSS_AND_PANEL_STRUCTURE = """
<style>
/* Style global pour la transition du panneau de détails */
.details-panel {
    position: fixed;
    top: 0;
    right: 0; 
    width: 300px; 
    height: 100vh;
    background-color: white; 
    z-index: 999; 
    padding: 15px;
    box-shadow: -5px 0 15px rgba(0,0,0,0.2); 
    overflow-y: auto; 
    transition: transform 0.4s ease-in-out; 
    /* Point important: Le panneau doit être complètement hors-écran par défaut si fermé */
}
.details-panel-closed {
    transform: translateX(100%);
}
.details-panel-open {
    transform: translateX(0);
}
/* Empêcher l'injection de code HTML du panneau dans le corps principal de Streamlit */
body {
    overflow: hidden; 
}
</style>
"""

# Injection du CSS global (pour le panneau principal)
st.markdown(CUSTOM_CSS_AND_PANEL_STRUCTURE, unsafe_allow_html=True) 
# --- FIN CSS / HTML ---

# --- Fonction utilitaire de formatage ---
def format_value(value, unit=""):
    """
    Formate la valeur: 
    - Supprime les unités si la valeur est un texte descriptif.
    - Ajoute les unités si la valeur est numérique et les arrondit si nécessaire.
    """
    val_str = str(value).strip()
    
    # 1. Gestion des valeurs vides ou non pertinentes
    if val_str in ('N/A', 'nan', '', 'None', 'None €', 'None m²', '/'):
        return "Non renseigné"
        
    # 2. Gestion des valeurs textuelles (sans chiffres)
    if any(c.isalpha() for c in val_str) and not any(c.isdigit() for c in val_str):
        return val_str
    
    # 3. Gestion des valeurs numériques
    try:
        num_value = float(value)
        
        # Arrondit à 2 décimales si nécessaire
        if num_value != round(num_value, 2):
            val_str = f"{num_value:.2f}"
            
        # Ajoute l'unité si elle n'est pas déjà présente
        if unit and not val_str.lower().endswith(unit.lower().strip()):
            return f"{val_str} {unit}"
            
    except (ValueError, TypeError):
        # La valeur n'est pas un simple nombre (ex: "300 €/m² = 73 500 €", "36 à 265 m²")
        pass
        
    return val_str


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
        
        folium.CircleMarker(
            location=[lat, lon],
            radius=10,
            color="#0072B2",
            fill=True,
            fill_color="#0072B2",
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
        
        DISTANCE_THRESHOLD = 0.0005 

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
    st.info("⚠️ Le DataFrame est vide ou les coordonnées sont manquantes.")


# --- 4. Panneau de Détails Droit (Injection via components.html) ---

# Construction du contenu HTML interne
html_content_inner = ""

if show_details:
    selected_data_series = data_df[data_df[REF_COL].str.strip() == selected_ref_clean]
    
    if len(selected_data_series) > 0:
        selected_data = selected_data_series.iloc[0].copy()
        
        try:
            display_title_ref = str(int(selected_ref_clean))
        except ValueError:
            display_title_ref = selected_ref_clean
            
        # --- Entête ---
        html_content_inner += f"""
            <h3 style="color:#303030; margin-top: 0;">🔍 Détails du Lot</h3>
            <hr style="border: 1px solid #ccc; margin: 5px 0;">
            <h4 style="color: #0072B2;">Réf. : {display_title_ref}</h4>
        """
        
        # --- Affichage de l'adresse ---
        adresse = selected_data.get('Adresse', 'N/A')
        code_postal = selected_data.get('Code Postal', '')
        ville = selected_data.get('Ville', '')
        
        html_content_inner += f'<p style="font-weight: bold; color: #555; margin: 10px 0 5px;">📍 Adresse complète</p>'
        adresse_str = str(adresse).strip()
        code_ville_str = f"{code_postal} - {ville}".strip()
        
        html_content_inner += f'<p style="margin: 0; font-size: 14px;">'
        if adresse_str not in ('N/A', 'nan', ''):
             html_content_inner += f'{adresse_str}<br>'
        
        if code_ville_str not in ('N/A - N/A', 'nan - nan', '-'):
             html_content_inner += f'{code_ville_str}'
        
        html_content_inner += '</p>'


        html_content_inner += '<hr style="border: 1px solid #eee; margin: 15px 0;">'
        
        # --- LOGIQUE D'AFFICHAGE DES INFORMATIONS DÉTAILLÉES (G à AH) ---
        html_content_inner += '<p style="font-weight: bold; margin-bottom: 10px;">Informations Détaillées:</p>'
        
        # Colonnes à exclure (déjà traitées ou non pertinentes pour l'affichage général)
        cols_to_exclude = [
            REF_COL, 
            'Latitude', 'Longitude', 
            'Lien Google Maps' ,
            'Adresse', 'Code Postal', 'Ville',
            'distance_sq' 
        ]
        
        # Toutes les colonnes à partir de l'indice 6 (colonne G)
        all_cols = data_df.columns.tolist()
        detail_cols = all_cols[6:] 

        for col_name in detail_cols:
            if col_name not in cols_to_exclude:
                value = selected_data.get(col_name, 'N/A')
                
                # Détermination de l'unité basée sur le nom de la colonne
                unit = ''
                if any(k in col_name for k in ['Loyer', 'Charges', 'garantie', 'foncière', 'Taxe', 'Marketing', 'Gestion', 'BP', 'annuel', 'Mensuel']) and '€' not in col_name:
                    unit = '€'
                elif any(k in col_name for k in ['Surface', 'GLA', 'utile']) and 'm²' not in col_name:
                    unit = 'm²'
                
                # Utilisation de la fonction de formatage
                formatted_value = format_value(value, unit=unit)
                
                # Affichage des paires Nom : Valeur
                html_content_inner += f'''
                <div style="margin-bottom: 8px;">
                    <span style="font-weight: bold; color: #555; font-size: 14px;">{col_name} :</span> 
                    <span style="font-size: 14px;">{formatted_value}</span>
                </div>
                '''

        # --- Lien Google Maps (en bas du volet) ---
        lien_maps = selected_data.get('Lien Google Maps', None)
        if lien_maps and pd.notna(lien_maps) and str(lien_maps).lower().strip() not in ('nan', 'n/a', 'none', ''):
             html_content_inner += f'''
             <hr style="border: 1px solid #eee; margin: 20px 0;">
             <a href="{lien_maps}" target="_blank" style="text-decoration: none;">
                <button style="background-color: #4CAF50; color: white; border: none; padding: 10px 0px; text-align: center; text-decoration: none; display: block; font-size: 14px; margin-top: 10px; cursor: pointer; border-radius: 4px; width: 100%;">
                    Voir sur Google Maps
                </button>
            </a>
             '''
        
    else:
        html_content_inner += "<p>❌ Erreur: Référence non trouvée.</p>"

# --- Injection Finale du Composant HTML ---

# On injecte le tout dans un composant HTML Streamlit
# Note: Nous définissons une hauteur de 0 et une clé, car nous voulons uniquement que 
# le CSS et le HTML flottant soient exécutés, le contenu étant positionné en dehors
# du flux normal de l'application.

# Pour éviter l'affichage dans le corps principal, nous utilisons un espace réservé.
# Le CSS global (au début du script) gère le positionnement fixe.
components.html(
    f"""
    {html_content_inner}
    """,
    height=0, # Hauteur minimale car le panneau est positionné en 'fixed'
    width=0,
    scrolling=False 
)

# Message dans le corps principal si aucun détail n'est affiché
if not show_details and not data_df.empty:
    st.info("Cliquez sur un marqueur sur la carte pour afficher ses détails dans le volet de droite.")

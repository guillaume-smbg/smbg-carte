import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np

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

# --- CSS / HTML pour le volet flottant à droite ---
CUSTOM_CSS = """
<style>
/* Cette règle fixe le panneau de détails à droite, au-dessus de la carte. */
.details-panel {
    position: fixed;
    top: 0; /* Aligné en haut */
    right: 0; /* Aligné à droite */
    width: 300px; /* Largeur du panneau de détails */
    height: 100vh;
    background-color: white; 
    z-index: 999; /* Très haut pour être au-dessus de tous les éléments */
    padding: 15px;
    box-shadow: -5px 0 15px rgba(0,0,0,0.2); 
    overflow-y: auto; 
}

/* Ajustement pour que le st.sidebar (Contrôles Gauche) soit bien visible */
.css-hxt7xp { /* Cible le st.sidebar de Streamlit */
    z-index: 1000 !important; 
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# --- FIN CSS / HTML ---


# --- Fonction de Chargement des Données (Cache Réactivé) ---
@st.cache_data
def load_data(file_path):
    # ... (fonction load_data inchangée) ...
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

# Nettoyage de la référence pour la vérification
selected_ref_clean = st.session_state['selected_ref'].strip() if st.session_state['selected_ref'] else None
if selected_ref_clean == 'None':
    selected_ref_clean = None
    st.session_state['selected_ref'] = None 

show_details = selected_ref_clean and not data_df[data_df[REF_COL].str.strip() == selected_ref_clean].empty


# --- 2. Panneau de Contrôle Gauche (Dans le st.sidebar) ---
with st.sidebar:
    st.header("⚙️ Contrôles")
    st.markdown("---")
    
    st.info(f"Lots chargés: **{len(data_df)}**")
    
    if show_details:
        # st.rerun() est utilisé ici
        if st.button("Masquer les détails", key="hide_left", use_container_width=True):
            st.session_state['selected_ref'] = None
            st.rerun() 
    
    st.markdown("---")
    
    if error_message:
        st.error(error_message)
    elif data_df.empty:
        st.warning("Le DataFrame est vide.")

# --- 3. Zone de la Carte (Corps Principal) ---
# La carte prendra maintenant toute la place restante du corps principal (colonne de gauche non incluse)

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
        
        if current_coords != st.session_state['last_clicked_coords']:
            st.session_state['last_clicked_coords'] = current_coords
            
            # Recherche du lot le plus proche 
            data_df['distance_sq'] = (data_df['Latitude'] - current_coords[0])**2 + (data_df['Longitude'] - current_coords[1])**2
            closest_row = data_df.loc[data_df['distance_sq'].idxmin()]
            
            new_ref = closest_row[REF_COL]
            
            if new_ref != st.session_state['selected_ref']:
                st.session_state['selected_ref'] = new_ref
                # On ne rafraîchit que si la référence change pour afficher/masquer le panneau
                st.rerun() 
             
else:
    st.info("⚠️ Le DataFrame est vide ou les coordonnées sont manquantes.")


# --- 4. Panneau de Détails Droit (Injection HTML Flottant) ---

if show_details:
    # Récupération des données sélectionnées
    selected_data_series = data_df[data_df[REF_COL].str.strip() == selected_ref_clean]
    
    if len(selected_data_series) > 0:
        selected_data = selected_data_series.iloc[0].copy()
        
        try:
            display_title_ref = str(int(selected_ref_clean))
        except ValueError:
            display_title_ref = selected_ref_clean
            
        # Début de la construction du contenu HTML/CSS
        html_content = f"""
        <div class="details-panel">
            <h3 style="color:#303030; margin-top: 0;">🔍 Détails du Lot</h3>
            <hr style="border: 1px solid #ccc; margin: 5px 0;">
            <h4 style="color: #0072B2;">Réf. : {display_title_ref}</h4>
        """
        
        # --- Contenu des informations clés ---
        html_content += '<div style="background-color: #f7f7f7; padding: 10px; border-radius: 5px; margin-bottom: 10px;">'
        html_content += '<p style="font-weight: bold; margin: 5px 0;">Informations clés:</p>'
        
        colonnes_a_afficher = [
            ('Emplacement', selected_data.get('Emplacement', 'N/A')),
            ('Typologie', selected_data.get('Typologie', 'N/A')),
            ('Surface GLA', f"{selected_data.get('Surface GLA', 'N/A')} m²"),
            ('Loyer annuel', f"{selected_data.get('Loyer annuel', 'N/A')} €"),
        ]
        
        for nom, valeur in colonnes_a_afficher:
            valeur_str = str(valeur).strip()
            if valeur_str not in ('N/A', 'nan', '', '€', 'm²', 'None', 'None €', 'None m²'):
                 html_content += f'<div style="margin-bottom: 5px;"><span style="font-weight: bold; color: #555;">{nom} :</span> {valeur}</div>'
                 
        html_content += '</div>' # Fin div informations clés
        
        # --- Adresse ---
        adresse = selected_data.get('Adresse', 'N/A')
        code_postal = selected_data.get('Code Postal', '')
        ville = selected_data.get('Ville', '')
        
        html_content += f'<p style="font-weight: bold; color: #555; margin: 10px 0 0px;">📍 Adresse</p>'
        if str(adresse).strip() not in ('N/A', 'nan', ''):
             html_content += f'<p style="margin: 0;">{adresse}<br>{code_postal} - {ville}</p>'
        else:
             html_content += f'<p style="margin: 0;">Adresse non renseignée.</p>'
             
        # --- Lien Google Maps ---
        lien_maps = selected_data.get('Lien Google Maps', None)
        if lien_maps and pd.notna(lien_maps) and str(lien_maps).lower().strip() not in ('nan', 'n/a', 'none', ''):
             html_content += f'''
             <a href="{lien_maps}" target="_blank" style="text-decoration: none;">
                <button style="background-color: #4CAF50; color: white; border: none; padding: 10px 0px; text-align: center; text-decoration: none; display: block; font-size: 14px; margin-top: 20px; cursor: pointer; border-radius: 4px; width: 100%;">
                    Voir sur Google Maps
                </button>
            </a>
             '''
        
        # Fermeture de la div flottante
        html_content += '</div>' 
        
        # Injection du panneau de détails flottant
        st.markdown(html_content, unsafe_allow_html=True)

else:
    # Message dans le corps principal si aucun détail n'est affiché
    if not show_details and not data_df.empty:
        st.info("Cliquez sur un marqueur sur la carte pour afficher ses détails dans le volet de droite.")

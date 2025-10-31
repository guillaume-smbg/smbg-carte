import pandas as pd
import streamlit as st
import folium
from folium.features import DivIcon
from streamlit_folium import st_folium
import numpy as np

# --- 0. Configuration et Initialisation ---
st.set_page_config(layout="wide", page_title="Carte Interactive (Panneaux Fixes)") 

# Initialisation de la session state
if 'selected_ref' not in st.session_state:
    st.session_state['selected_ref'] = None
if 'last_clicked_coords' not in st.session_state:
    st.session_state['last_clicked_coords'] = (0, 0)

# --- Chemin d'accès du fichier ---
EXCEL_FILE_PATH = 'data/Liste des lots.xlsx' 

# --- Fonction de Chargement des Données ---
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_excel(file_path)
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df['Référence annonce'] = df['Référence annonce'].astype(str)
        df.dropna(subset=['Latitude', 'Longitude'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Erreur de chargement du fichier : {e}")
        return pd.DataFrame()

# --- Chargement des données ---
data_df = load_data(EXCEL_FILE_PATH)

# --- 1. Définition de la Mise en Page (3 Colonnes Fixes) ---

# Largeur de la barre latérale et du panneau (ratios Streamlit pour simuler 275px)
SIDEBAR_WIDTH = 2
DETAILS_PANEL_WIDTH = 2

# Création des trois colonnes
# Le ratio central est ce qui reste : 10 - 2 (gauche) - 2 (droite) = 6
col_left, col_map, col_right = st.columns([SIDEBAR_WIDTH, 6, DETAILS_PANEL_WIDTH]) 


# --- 2. Panneau de Contrôle Gauche (275px) ---
with col_left:
    st.header("⚙️ Contrôles")
    st.info("Espace de 275px à gauche pour les filtres.")
    st.markdown("---")
    st.write(f"Lots chargés: **{len(data_df)}**")


# --- 3. Zone de la Carte ---
with col_map:
    MAP_HEIGHT = 800 
    st.header("Carte des Lots Immobiliers")
    
    if not data_df.empty:
        centre_lat = data_df['Latitude'].mean()
        centre_lon = data_df['Longitude'].mean()
        
        m = folium.Map(location=[centre_lat, centre_lon], zoom_start=6, control_scale=True)

        # --- Création des marqueurs circulaires personnalisés (Pas de popup ni de tooltip) ---
        for index, row in data_df.iterrows():
            lat = row['Latitude']
            lon = row['Longitude']
            reference = str(row.get('Référence annonce', 'N/A'))
            
            display_ref = reference[-4:] if len(reference) > 4 and reference != 'nan' else reference
            
            html = f"""
                <div id='lot-{reference}' style='
                    background-color: #0072B2; 
                    color: white; 
                    border-radius: 50%; 
                    width: 30px; 
                    height: 30px; 
                    text-align: center; 
                    line-height: 30px; 
                    font-size: 10px;
                    font-weight: bold;
                    cursor: pointer;
                    border: 2px solid white;'>
                    {display_ref}
                </div>
                """
            
            icon = DivIcon(html=html)
            
            # Pas de popup, pas de tooltip, pas de max_width.
            folium.Marker(
                location=[lat, lon],
                icon=icon,
            ).add_to(m)

        # Affichage et capture des événements de clic
        # L'utilisation de 'st_folium' avec 'returned_objects' est la clé.
        map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=['last_clicked'], key="main_map")

        # --- Logique de détection de clic ---
        if map_output and map_output.get("last_clicked"):
            clicked_coords = map_output["last_clicked"]
            current_coords = (clicked_coords['lat'], clicked_coords['lng'])
            
            # Se déclenche seulement si un nouveau clic a eu lieu
            if current_coords != st.session_state['last_clicked_coords']:
                st.session_state['last_clicked_coords'] = current_coords
                
                # Recherche du lot le plus proche
                data_df['distance'] = np.sqrt((data_df['Latitude'] - current_coords[0])**2 + (data_df['Longitude'] - current_coords[1])**2)
                closest_row = data_df.loc[data_df['distance'].idxmin()]
                
                # Seuil de tolérance (doit être proche d'un marqueur)
                if closest_row['distance'] < 0.0001: 
                    new_ref = closest_row['Référence annonce']
                    
                    # Mise à jour de l'état (le panneau se mettra à jour à la fin du script)
                    if st.session_state['selected_ref'] != new_ref:
                        st.session_state['selected_ref'] = new_ref
                        # Pas besoin de rerun car la structure des colonnes est fixe !
                 
    else:
        st.info("Le DataFrame est vide ou les coordonnées sont manquantes.")


# --- 4. Panneau de Détails Droit (Toujours affiché - 275px) ---
with col_right:
    st.header("🔍 Détails du Lot")
    st.markdown("---")
    
    selected_ref = st.session_state['selected_ref']
    
    # Affichage du contenu en fonction du lot sélectionné
    if selected_ref:
        # Tente de récupérer les données du lot sélectionné
        selected_data = data_df[data_df['Référence annonce'] == selected_ref].iloc[0]
        
        st.subheader(f"Réf. : {selected_ref}")
        
        # Affichage des informations clés
        st.write(f"**Adresse :** {selected_data.get('Adresse', 'N/A')}")
        st.write(f"**Ville :** {selected_data.get('Ville', 'N/A')}")
        st.write(f"**Surface GLA :** {selected_data.get('Surface GLA', 'N/A')} m²")
        st.write(f"**Loyer Annuel :** {selected_data.get('Loyer annuel', 'N/A')} €")
        st.write(f"**Typologie :** {selected_data.get('Typologie', 'N/A')}")
        
        st.caption("Commentaires:")
        st.text(selected_data.get('Commentaires', 'Aucun commentaire disponible.'))
        
        # Affichage de l'image (Cloudflare)
        photo_url = selected_data.get('Photos annonce', '')
        if photo_url and pd.notna(photo_url) and photo_url != 'nan':
             st.image(photo_url, caption="Photo de l'annonce", use_column_width=True)
        
        # Bouton pour désélectionner
        if st.button("Masquer les détails", key="deselect_right"):
             st.session_state['selected_ref'] = None
             # La structure des colonnes est fixe, mais ce 'rerun' est nécessaire
             # pour effacer le contenu du panneau et revenir à l'état initial.
             st.experimental_rerun() 
             
    else:
        st.info("Cliquez sur un marqueur (cercle) sur la carte pour afficher ses détails ici.")

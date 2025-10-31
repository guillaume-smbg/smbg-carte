import pandas as pd
import streamlit as st
import folium
from folium.features import DivIcon
from streamlit_folium import st_folium
import numpy as np

# --- 0. Configuration et Initialisation ---
st.set_page_config(layout="wide", page_title="Carte Interactive Avancée") 

# Initialisation de la session state pour gérer le lot sélectionné
if 'selected_ref' not in st.session_state:
    st.session_state['selected_ref'] = None
# Ajout d'une variable pour forcer le redessinage si l'état change
if 'last_clicked_coords' not in st.session_state:
    st.session_state['last_clicked_coords'] = (0, 0)

# --- Chemin d'accès du fichier ---
EXCEL_FILE_PATH = 'data/Liste des lots.xlsx' 

# --- Fonction de Chargement des Données ---
# Le code load_data reste inchangé
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

# --- 1. Gestion de la Mise en Page Dynamique (Colonnes) ---

SIDEBAR_WIDTH = 2
DETAILS_PANEL_WIDTH = 2 # Simulation des 275px

if st.session_state['selected_ref']:
    # Sélection active : Trois colonnes
    col_left, col_map, col_right = st.columns([SIDEBAR_WIDTH, 10 - DETAILS_PANEL_WIDTH, DETAILS_PANEL_WIDTH])
else:
    # Pas de sélection : Deux colonnes
    col_left, col_map = st.columns([SIDEBAR_WIDTH, 10]) 
    col_right = None 


# --- 2. Panneau de Contrôle Gauche (275px) ---
with col_left:
    st.header("⚙️ Contrôles")
    st.info("Espace réservé (275px) pour les filtres et options.")
    st.markdown("---")
    st.write(f"Lots affichés: **{len(data_df)}**")

    if st.session_state['selected_ref']:
        if st.button("Masquer les détails", key="hide_left"):
            st.session_state['selected_ref'] = None
            st.experimental_rerun()


# --- 3. Zone de la Carte ---
with col_map:
    MAP_HEIGHT = 800 
    st.header("Carte des Lots Immobiliers")
    
    if not data_df.empty:
        centre_lat = data_df['Latitude'].mean()
        centre_lon = data_df['Longitude'].mean()
        
        m = folium.Map(location=[centre_lat, centre_lon], zoom_start=6, control_scale=True)

        # --- Création des marqueurs circulaires personnalisés (Pas de tooltip ni de popup) ---
        for index, row in data_df.iterrows():
            lat = row['Latitude']
            lon = row['Longitude']
            reference = str(row.get('Référence annonce', 'N/A'))
            
            # Préparer la référence à afficher
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
            
            # Pas de popup, pas de tooltip
            folium.Marker(
                location=[lat, lon],
                icon=icon,
            ).add_to(m)

        # Affichage et capture des événements de clic
        map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=['last_clicked'], key="main_map")

        # --- Logique de détection de clic (AMÉLIORÉE) ---
        if map_output and map_output.get("last_clicked"):
            clicked_coords = map_output["last_clicked"]
            current_coords = (clicked_coords['lat'], clicked_coords['lng'])
            
            # Vérifier si les coordonnées ont changé
            if current_coords != st.session_state['last_clicked_coords']:
                st.session_state['last_clicked_coords'] = current_coords
                
                # Recherche du lot le plus proche
                data_df['distance'] = np.sqrt((data_df['Latitude'] - current_coords[0])**2 + (data_df['Longitude'] - current_coords[1])**2)
                closest_row = data_df.loc[data_df['distance'].idxmin()]
                
                # Le seuil de tolérance (assurez-vous d'être très près du marqueur)
                if closest_row['distance'] < 0.0001: 
                    new_ref = closest_row['Référence annonce']
                    
                    # Mise à jour et FORCAGE du redessinage
                    if st.session_state['selected_ref'] != new_ref:
                        st.session_state['selected_ref'] = new_ref
                        # Relancer l'application pour que la nouvelle disposition (3 colonnes) s'applique
                        st.experimental_rerun() 
                 
    else:
        st.info("Le DataFrame est vide ou les coordonnées sont manquantes.")


# --- 4. Panneau Rétractable de Détails Droit (275px) ---
if col_right:
    # Le panneau apparaît ici si st.session_state['selected_ref'] n'est pas None (grâce au rerun)
    with col_right:
        selected_ref = st.session_state['selected_ref']
        
        st.header("Détails du Lot")
        st.markdown("---")
        
        if selected_ref:
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
            
            if st.button("Masquer les détails", key="close_right"):
                 st.session_state['selected_ref'] = None
                 st.experimental_rerun()

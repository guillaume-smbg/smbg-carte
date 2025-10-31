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
    st.session_state['last_clicked_coords'] = None

# --- Chemin d'accès du fichier ---
EXCEL_FILE_PATH = 'data/Liste des lots.xlsx' 

# --- Fonction de Chargement des Données ---
@st.cache_data
def load_data(file_path):
    # (Même code de chargement et de nettoyage des coordonnées)
    try:
        df = pd.read_excel(file_path)
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        # S'assurer que la colonne de référence est bien une chaîne de caractères
        df['Référence annonce'] = df['Référence annonce'].astype(str)
        df.dropna(subset=['Latitude', 'Longitude'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Erreur de chargement du fichier : {e}")
        return pd.DataFrame()

# --- Chargement des données ---
data_df = load_data(EXCEL_FILE_PATH)

# --- 1. Gestion de la Mise en Page Dynamique (Colonnes) ---

# Définition des largeurs en fonction de la sélection
# Largeur de la barre latérale gauche (275px simulés)
SIDEBAR_WIDTH = 2
# Largeur du panneau de détails droit (275px simulés)
DETAILS_PANEL_WIDTH = 2

if st.session_state['selected_ref']:
    # Sélection active : Créer les trois colonnes
    col_left, col_map, col_right = st.columns([SIDEBAR_WIDTH, 10 - DETAILS_PANEL_WIDTH, DETAILS_PANEL_WIDTH])
else:
    # Pas de sélection : Seulement deux colonnes, la carte prend l'espace restant
    col_left, col_map = st.columns([SIDEBAR_WIDTH, 10]) 
    col_right = None 


# --- 2. Panneau de Contrôle Gauche (Statique 275px) ---
with col_left:
    st.header("⚙️ Contrôles")
    st.info("Espace réservé (275px) pour les filtres et options.")
    st.markdown("---")
    st.write(f"Lots affichés: **{len(data_df)}**")

    # Bouton pour effacer la sélection (si elle existe)
    if st.session_state['selected_ref']:
        # Utilisez une clé unique pour le bouton
        if st.button("Masquer les détails", key="hide_left"):
            st.session_state['selected_ref'] = None
            st.experimental_rerun()


# --- 3. Zone de la Carte ---
with col_map:
    # Ajuster la hauteur de la carte à une valeur élevée pour simuler le "non scrollable"
    MAP_HEIGHT = 800 
    
    st.header("Carte des Lots Immobiliers")
    
    if not data_df.empty:
        centre_lat = data_df['Latitude'].mean()
        centre_lon = data_df['Longitude'].mean()
        
        m = folium.Map(location=[centre_lat, centre_lon], zoom_start=6, control_scale=True)

        # --- Création des marqueurs circulaires personnalisés ---
        for index, row in data_df.iterrows():
            lat = row['Latitude']
            lon = row['Longitude']
            reference = str(row.get('Référence annonce', 'N/A'))
            
            # Préparer la référence à afficher (ex: prendre les 4 derniers caractères)
            # Utilisation de .get() pour gérer les colonnes qui pourraient être absentes ou NaN
            display_ref = reference[-4:] if len(reference) > 4 and reference != 'nan' else reference
            
            # HTML pour le cercle avec le numéro à l'intérieur
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
            
            # ATTENTION : Suppression de 'popup=popup' et 'tooltip=reference' pour éviter tout affichage de pop-up ou tooltip au survol/clic
            folium.Marker(
                location=[lat, lon],
                icon=icon,
            ).add_to(m)

        # Affichage et capture des événements de clic
        # Nous utilisons 'last_clicked' pour obtenir les coordonnées du clic sur la carte.
        # Il est important d'utiliser une clé unique pour la carte si vous avez d'autres widgets Folium.
        map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=['last_clicked'], key="main_map")

        # --- Logique de détection de clic ---
        if map_output and map_output.get("last_clicked"):
            clicked_coords = map_output["last_clicked"]
            clicked_lat = clicked_coords['lat']
            clicked_lon = clicked_coords['lng']
            
            # Vérifier si les coordonnées ont changé (pour éviter une boucle de rafraîchissement)
            current_coords = (clicked_lat, clicked_lon)
            if current_coords != st.session_state['last_clicked_coords']:
                st.session_state['last_clicked_coords'] = current_coords
                
                # Recherche du lot le plus proche du clic
                data_df['distance'] = np.sqrt((data_df['Latitude'] - clicked_lat)**2 + (data_df['Longitude'] - clicked_lon)**2)
                closest_row = data_df.loc[data_df['distance'].idxmin()]
                
                # Seuil de tolérance (vérifie que le clic est proche d'un marqueur)
                if closest_row['distance'] < 0.0001: 
                    new_ref = closest_row['Référence annonce']
                    
                    # Mise à jour de la référence sélectionnée et relance l'application
                    if st.session_state['selected_ref'] != new_ref:
                        st.session_state['selected_ref'] = new_ref
                        # Relancer l'application pour dessiner la troisième colonne
                        st.experimental_rerun() 
                 
    else:
        st.info("Le DataFrame est vide ou les coordonnées sont manquantes.")


# --- 4. Panneau Rétractable de Détails Droit (275px simulés) ---
if col_right:
    with col_right:
        selected_ref = st.session_state['selected_ref']
        
        st.header("Détails")
        st.markdown("---")
        
        if selected_ref:
            # Récupérer les données du lot sélectionné
            selected_data = data_df[data_df['Référence annonce'] == selected_ref].iloc[0]
            
            st.subheader(f"Lot Référence : {selected_ref}")
            
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
            if photo_url and pd.notna(photo_url):
                 st.image(photo_url, caption="Photo de l'annonce", use_column_width=True)
            
            # Bouton pour fermer le panneau 
            if st.button("Masquer les détails", key="close_right"):
                 st.session_state['selected_ref'] = None
                 st.experimental_rerun()

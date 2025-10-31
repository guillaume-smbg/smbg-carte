import pandas as pd
import streamlit as st
import folium
from streamlit_folium import folium_static

# --- 1. Configuration de la Page (Full Width et non scrollable) ---
# Le layout="wide" utilise toute la largeur disponible.
# Pour la rendre "non scrollable", nous utiliserons un container de hauteur fixe (si nécessaire)
# et st.set_page_config doit être la PREMIÈRE commande Streamlit.
st.set_page_config(layout="wide", page_title="Carte Interactive") 

# --- Chemin d'accès du fichier dans le dépôt GitHub ---
EXCEL_FILE_PATH = 'data/Liste des lots.xlsx' 

# --- Fonction de Chargement des Données (Identique) ---
@st.cache_data
def load_data(file_path):
    # (Votre code de chargement de données reste ici)
    try:
        df = pd.read_excel(file_path)
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        df.dropna(subset=['Latitude', 'Longitude'], inplace=True)
        return df
    except FileNotFoundError:
        st.error(f"Erreur : Le fichier '{file_path}' est introuvable. Vérifiez le chemin et le nom.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Une erreur s'est produite lors du traitement du fichier : {e}")
        return pd.DataFrame()

# --- Chargement et Traitement ---
data_df = load_data(EXCEL_FILE_PATH)

# --- 2. Création des deux colonnes (Barre latérale et Carte) ---
# Pour simuler une largeur de 275px, nous devons utiliser les ratios de colonnes. 
# La colonne de la barre latérale doit être *relativement* petite.
# Exemple : un ratio de 2:8 (2 pour la barre latérale, 8 pour la carte) pourrait être un bon point de départ.
# Streamlit ne permet pas de spécifier directement la largeur en pixels, nous utilisons donc les ratios.
col_sidebar, col_map = st.columns([2, 8]) # Ajustez les ratios (e.g., [2, 8], [1, 5], etc.) si 275px est critique.


# --- 3. Barre Latérale (275px simulés) ---
with col_sidebar:
    st.header("⚙️ Espace de Contrôle")
    st.info("Cet espace fera office de barre latérale (environ 275px de largeur) et sera utilisé pour les filtres et options.")
    
    # Utilisez une hauteur fixe pour simuler l'affichage non scrollable sur cet élément
    # Note : Le défilement global de la page dépend de la hauteur totale du contenu par rapport à la fenêtre.
    # st.write(f"Nombre total de lots : {len(data_df)}")
    
    # Vous ajouterez ici les sélecteurs de filtre (sliders, boutons) plus tard.


# --- 4. Affichage de la Carte (Zone Principale) ---
with col_map:
    st.header("Carte des Lots Immobiliers")
    
    if not data_df.empty:
        
        # Le code de création de la carte Folium (le même qu'avant)
        
        centre_lat = data_df['Latitude'].mean()
        centre_lon = data_df['Longitude'].mean()

        # Hauteur de la carte : Nous allons la fixer pour qu'elle prenne la majorité de l'écran (ex: 80% de la hauteur)
        map_height = 800 # Hauteur en pixels à ajuster selon votre écran cible
        
        m = folium.Map(location=[centre_lat, centre_lon], zoom_start=6, control_scale=True)
        
        # Ajout des marqueurs... (omission du code pour la clarté, il reste le même que dans la réponse précédente)
        # ------------------------------------------------------------------------------------------------------
        for index, row in data_df.iterrows():
            # Création du contenu de la pop-up (HTML)
            photo_url = row.get('Photos annonce', '')
            adresse = row.get('Adresse', 'Non spécifiée')
            loyer = row.get('Loyer annuel', 'N/A')
            commentaires = row.get('Commentaires', 'Pas de commentaires.')
            reference = row.get('Référence annonce', 'N/A')
            
            html = f"""
            <h4>Référence : {reference}</h4>
            <p><strong>Adresse :</strong> {adresse}</p>
            <p><strong>Loyer annuel :</strong> {loyer} €</p>
            <p>{commentaires}</p>
            """
            if photo_url and pd.notna(photo_url):
                 html += f"<img src='{photo_url}' alt='Photo de l'annonce' style='width:150px; height:auto;'>"

            iframe = folium.IFrame(html, width=200, height=250)
            popup = folium.Popup(iframe, max_width=2650)
            
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=popup,
                tooltip=reference,
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
        # ------------------------------------------------------------------------------------------------------

        # Affichage de la carte dans Streamlit avec la hauteur fixée
        st.subheader(f"Affichage de {len(data_df)} points")
        folium_static(m, width=None, height=map_height) # width=None utilise la largeur de la colonne
        
    else:
        st.info("Le DataFrame est vide ou les coordonnées sont manquantes.")

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import folium_static

# --- Configuration Streamlit ---
st.set_page_config(layout="wide")
st.title("🗺️ Carte Interactive de Vos Annonces Immobilières")
st.markdown("---")

# --- Chemin d'accès du fichier dans le dépôt GitHub ---
EXCEL_FILE_PATH = 'data/Liste des lots.xlsx' 

# --- Fonction de Chargement des Données ---
@st.cache_data # Mise en cache pour une exécution rapide avec Streamlit
def load_data(file_path):
    try:
        # Lecture du fichier Excel
        df = pd.read_excel(file_path)
        
        # Nettoyage des coordonnées (crucial pour la carte)
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        
        # Filtrer pour ne garder que les lignes avec des coordonnées valides
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

if not data_df.empty:
    
    # --- Code de la Carte Folium ---
    
    # 1. Calcul du centre initial (moyenne des coordonnées)
    centre_lat = data_df['Latitude'].mean()
    centre_lon = data_df['Longitude'].mean()

    # 2. Création de la carte Folium de base
    m = folium.Map(location=[centre_lat, centre_lon], zoom_start=6, control_scale=True)
    
    # 3. Ajout des marqueurs
    for index, row in data_df.iterrows():
        
        # Récupération des données pour la pop-up
        photo_url = row.get('Photos annonce', '')
        adresse = row.get('Adresse', 'Non spécifiée')
        loyer = row.get('Loyer annuel', 'N/A')
        commentaires = row.get('Commentaires', 'Pas de commentaires.')
        reference = row.get('Référence annonce', 'N/A')
        
        # Création du contenu HTML pour la pop-up
        html = f"""
        <h4>Référence : {reference}</h4>
        <p><strong>Adresse :</strong> {adresse}</p>
        <p><strong>Loyer annuel :</strong> {loyer} €</p>
        <p>{commentaires}</p>
        """
        # Intégration de l'image Cloudflare (s'assurer que l'URL est publique)
        if photo_url and pd.notna(photo_url):
             html += f"<img src='{photo_url}' alt='Photo de l'annonce' style='width:150px; height:auto;'>"

        iframe = folium.IFrame(html, width=200, height=250)
        popup = folium.Popup(iframe, max_width=2650)
        
        # Ajouter le marqueur à la carte
        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=popup,
            tooltip=reference,
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)

    # 4. Affichage de la carte dans Streamlit
    st.subheader(f"Affichage de {len(data_df)} points sur la carte.")
    folium_static(m, width=800, height=600)
    
else:
    st.info("Le DataFrame est vide. Veuillez vous assurer que le fichier Excel contient des données valides pour 'Latitude' et 'Longitude'.")

import pandas as pd
import streamlit as st
import folium
from folium.features import DivIcon
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
        
        # SÉCURISATION MAXIMALE DE LA COLONNE DE RÉFÉRENCE:
        df[REF_COL] = df[REF_COL].astype(str).str.strip()
        df[REF_COL] = df[REF_COL].apply(lambda x: x.split('.')[0] if isinstance(x, str) else str(x).split('.')[0])
        df[REF_COL] = df[REF_COL].str.zfill(5) 
        
        df.dropna(subset=['Latitude', 'Longitude'], inplace=True)
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"❌ Erreur critique lors du chargement: {e}"

# --- Chargement des données ---
data_df, error_message = load_data(EXCEL_FILE_PATH)

# --- 1. Définition de la Mise en Page (3 Colonnes) ---
SIDEBAR_WIDTH = 2
DETAILS_PANEL_WIDTH = 2
col_left, col_map, col_right = st.columns([SIDEBAR_WIDTH, 6, DETAILS_PANEL_WIDTH]) 


# --- 2. Panneau de Contrôle Gauche ---
with col_left:
    st.header("⚙️ Contrôles")
    st.markdown("---")
    st.write(f"Lots chargés: **{len(data_df)}**")
    
    # --- PANNEAU DE DIAGNOSTIC ---
    st.header("⚠️ Diagnostic Données")
    if error_message:
        st.error(error_message)
    elif not data_df.empty:
        st.caption("5 premières références :")
        st.dataframe(data_df[[REF_COL]].head(), use_container_width=True)
    
    st.markdown("---")
    
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

        # --- Création des marqueurs (CircleMarker standard SANS POPUP NI TOOLTIP) ---
        for index, row in data_df.iterrows():
            lat = row['Latitude']
            lon = row['Longitude']
            
            # Création d'un CircleMarker simple pour assurer la transmission du clic
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
            
            # Seulement si un nouveau point a été cliqué
            if current_coords != st.session_state['last_clicked_coords']:
                st.session_state['last_clicked_coords'] = current_coords
                
                # Recherche du lot le plus proche 
                data_df['distance_sq'] = (data_df['Latitude'] - current_coords[0])**2 + (data_df['Longitude'] - current_coords[1])**2
                closest_row = data_df.loc[data_df['distance_sq'].idxmin()]
                
                new_ref = closest_row[REF_COL]
                st.session_state['selected_ref'] = new_ref
                 
    else:
        st.info("⚠️ Le DataFrame est vide ou les coordonnées sont manquantes. Vérifiez si le fichier s'est chargé correctement.")


# --- 4. Panneau de Détails Droit (Volet rétractable) ---
with col_right:
    st.header("🔍 Détails du Lot")
    st.markdown("---") 

    selected_ref = st.session_state['selected_ref']

    if selected_ref and selected_ref != 'None':
        selected_ref_clean = selected_ref.strip()
        
        # Filtre sécurisé sur la colonne de référence nettoyée
        selected_data_series = data_df[data_df[REF_COL].str.strip() == selected_ref_clean]
        
        if len(selected_data_series) > 0:
            # --- SUCCÈS : Affichage des données ---
            selected_data = selected_data_series.iloc[0].copy()
            
            try:
                display_title_ref = str(int(selected_ref))
            except ValueError:
                display_title_ref = selected_ref

            st.subheader(f"Réf. : {display_title_ref}")
            
            # Affichage en utilisant des st.metric ou st.write pour les champs
            
            colonnes_a_afficher = [
                ('Emplacement', selected_data.get('Emplacement', 'N/A')),
                ('Typologie', selected_data.get('Typologie', 'N/A')),
                ('Surface GLA', f"{selected_data.get('Surface GLA', 'N/A')} m²"),
                ('Surface utile', f"{selected_data.get('Surface utile', 'N/A')} m²"),
                ('Loyer annuel', f"{selected_data.get('Loyer annuel', 'N/A')} €"),
                ('Charges anuelles', f"{selected_data.get('Charges anuelles', 'N/A')} €"),
                ('Taxe foncière', f"{selected_data.get('Taxe foncière', 'N/A')} €"),
                ('Etat de livraison', selected_data.get('Etat de livraison', 'N/A')),
            ]
            
            # Utilisation d'un conteneur rétractable
            with st.expander("Informations clés", expanded=True):
                for nom, valeur in colonnes_a_afficher:
                    valeur_str = str(valeur).strip()
                    if valeur_str not in ('N/A', 'nan', '', '€', 'm²', 'None', 'None €', 'None m²'):
                        st.write(f"**{nom} :** {valeur}")

            # Affichage de l'adresse et du lien Google Maps
            adresse = selected_data.get('Adresse', 'N/A')
            code_postal = selected_data.get('Code Postal', '')
            ville = selected_data.get('Ville', '')
            
            st.caption("📍 Adresse")
            if str(adresse).strip() not in ('N/A', 'nan', ''):
                st.write(f"{adresse} \n{code_postal} - {ville}")
            else:
                st.write("Adresse non renseignée.")
            
            # Lien Google Maps
            lien_maps = selected_data.get('Lien Google Maps', None)
            if lien_maps and pd.notna(lien_maps) and str(lien_maps).lower().strip() not in ('nan', 'n/a', 'none', ''):
                st.markdown(
                    f'<a href="{lien_maps}" target="_blank">'
                    f'<button style="background-color: #0072B2; color: white; border: none; padding: 10px 0px; text-align: center; text-decoration: none; display: inline-block; font-size: 14px; margin-top: 10px; cursor: pointer; border-radius: 4px; width: 100%;">'
                    f'Voir sur Google Maps'
                    f'</button></a>',
                    unsafe_allow_html=True
                )

            # --- Détails supplémentaires dans un autre expander ---
            with st.expander("Détails supplémentaires"):
                commentaires = selected_data.get('Commentaires', 'N/A')
                if str(commentaires).strip() not in ('N/A', 'nan', ''):
                    st.caption("Commentaires:")
                    st.text(commentaires)
                else:
                    st.caption("Pas de commentaires.")
                
                st.markdown("---")
                st.write(f"**Latitude :** {selected_data.get('Latitude', 'N/A')}")
                st.write(f"**Longitude :** {selected_data.get('Longitude', 'N/A')}")


        else:
            st.error("❌ Erreur : La référence capturée n'a pas été trouvée dans le DataFrame.")
            
    else:
        st.info("Cliquez sur un marqueur sur la carte pour afficher ses détails ici.")

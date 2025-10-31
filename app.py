import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np

# --- 0. Configuration et Initialisation ---
# On supprime le layout="wide" dans la sidebar pour ne pas interférer avec le corps principal
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

# --- 1. Préparation des variables de mise en page ---

# Nettoyage de la référence pour la vérification
selected_ref_clean = st.session_state['selected_ref'].strip() if st.session_state['selected_ref'] else None
if selected_ref_clean == 'None':
    selected_ref_clean = None
    st.session_state['selected_ref'] = None 

show_details = selected_ref_clean and not data_df[data_df[REF_COL].str.strip() == selected_ref_clean].empty


# --- 2. Panneau de Contrôle Gauche (avec Sidebar) ---
# Le st.sidebar est utilisé ici pour le panneau de contrôle, mais il est par défaut rétractable.
# Pour le volet de droite (détails), nous allons utiliser la colonne principale.

# NOTE : La meilleure façon d'avoir un panneau *fixe* à gauche et un panneau *superposé* à droite
# n'est pas possible directement sans CSS. Cependant, si vous utilisez le st.sidebar
# standard pour les contrôles, et la colonne principale pour la carte, la carte sera
# toujours de la même largeur par rapport au corps de l'application.

# Si vous voulez un panneau de contrôle *non-rétractable* à gauche (comme précédemment),
# nous devons le coder en dur. Rétablissons les colonnes, mais cette fois la carte sera dans
# un conteneur qui simule la pleine largeur, en espérant que Streamlit ne la réduise pas.

# --- REVENONS À LA LOGIQUE À 3 COLONNES EN FORÇANT LA TAILLE (APPROCHE 2) ---
# Définition de la mise en page : Contrôles (1), Carte (6), Détails (1)
COL_CONTROLS_WIDTH = 1
COL_DETAILS_WIDTH = 1 # Sera caché lorsque non sélectionné

# On utilise un conteneur pour la carte afin d'essayer de forcer sa taille
container_map = st.container()

# La logique de colonnes conditionnelles est la seule façon de le faire sans CSS personnalisé,
# mais elle cause le redimensionnement que vous voulez éviter.
# Nous allons donc utiliser la colonne de gauche (contrôles) et le corps principal (carte + détails).

# --- 1. Mise en place du panneau de contrôle de gauche ---
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

# --- 2. Définition de la Mise en Page (Carte + Détails dans le corps principal) ---
# Le corps principal contient la carte et, conditionnellement, le panneau de détails.

if show_details:
    # 2 colonnes dans le corps principal : Carte (8) et Détails (4)
    # NOTE : C'est ici que la carte sera réduite par défaut.
    col_map, col_right = st.columns([4, 1])
else:
    # 1 colonne : Carte (qui prend toute la place restante)
    col_map = st.container() 
    col_right = None 


# --- 3. Zone de la Carte (dans la colonne Map ou le conteneur Map) ---
with col_map:
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
                    st.rerun()
                 
    else:
        st.info("⚠️ Le DataFrame est vide ou les coordonnées sont manquantes.")


# --- 4. Panneau de Détails Droit (Conditionnel) ---
if col_right: # Exécuté uniquement si show_details est True (donc mise en page à 2 colonnes du corps principal)
    with col_right:
        st.header("🔍 Détails du Lot")
        st.markdown("---") 

        selected_data_series = data_df[data_df[REF_COL].str.strip() == selected_ref_clean]
        
        if len(selected_data_series) > 0:
            selected_data = selected_data_series.iloc[0].copy()
            
            try:
                display_title_ref = str(int(selected_ref_clean))
            except ValueError:
                display_title_ref = selected_ref_clean

            st.subheader(f"Réf. : {display_title_ref}")
            
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

            # --- Détails supplémentaires ---
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
            st.error("❌ Erreur : La référence capturée n'a pas été trouvée.")
            
else:
    # Message si aucun détail n'est affiché
    with col_map: # Col_map est le conteneur principal si show_details est False
        if not show_details and not data_df.empty:
            st.info("Cliquez sur un marqueur sur la carte pour afficher ses détails dans le volet de droite.")

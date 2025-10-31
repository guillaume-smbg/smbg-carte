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

# --- 1. Définition de la Mise en Page (2 Colonnes : Contrôles + Carte) ---
SIDEBAR_WIDTH = 2
MAP_WIDTH = 8
col_left, col_map = st.columns([SIDEBAR_WIDTH, MAP_WIDTH]) 


# --- 2. Panneau de Contrôle Gauche (Filtres/Diagnostic) ---
with col_left:
    st.header("⚙️ Contrôles")
    st.info("Espace à gauche pour les filtres.")
    st.markdown("---")
    st.write(f"Lots chargés: **{len(data_df)}**")
    
    # --- PANNEAU DE DIAGNOSTIC ---
    st.header("⚠️ Diagnostic Données")
    if error_message:
        st.error(error_message)
    elif not data_df.empty:
        st.caption("5 premières lignes lues par Pandas :")
        st.dataframe(data_df.head(), use_container_width=True)
        st.info("Le chargement des données est vérifié et semble correct.")
    
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

        # --- Création des marqueurs ---
        for index, row in data_df.iterrows():
            lat = row['Latitude']
            lon = row['Longitude']
            reference = row.get(REF_COL, 'N/A')
            
            display_ref = reference
            if reference != 'N/A' and reference.isdigit():
                try:
                    display_ref = str(int(reference)) 
                except ValueError:
                    pass 
            
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
            
            folium.Marker(
                location=[lat, lon],
                icon=icon,
            ).add_to(m)

        # Affichage et capture des événements de clic
        map_output = st_folium(m, height=MAP_HEIGHT, width="100%", returned_objects=['last_clicked'], key="main_map")

        # --- DIAGNOSTIC DU CLIC EN TEMPS RÉEL (CRITIQUE) ---
        st.markdown("---")
        if map_output and map_output.get("last_clicked"):
            st.info(f"✅ **Clic Détecté** : Coordonnées {map_output['last_clicked']['lat']:.4f}, {map_output['last_clicked']['lng']:.4f}")
        else:
            st.warning("❌ **Clic non détecté** ou la carte n'a pas renvoyé de coordonnées. (Le signal n'arrive pas.)")
        st.markdown("---")
        # ----------------------------------------
        
        # --- Logique de détection de clic (Mise à jour de la session state) ---
        if map_output and map_output.get("last_clicked"):
            clicked_coords = map_output["last_clicked"]
            current_coords = (clicked_coords['lat'], clicked_coords['lng'])
            
            if current_coords != st.session_state['last_clicked_coords']:
                st.session_state['last_clicked_coords'] = current_coords
                
                # Recherche du lot le plus proche 
                data_df['distance_sq'] = (data_df['Latitude'] - current_coords[0])**2 + (data_df['Longitude'] - current_coords[1])**2
                closest_row = data_df.loc[data_df['distance_sq'].idxmin()]
                
                new_ref = closest_row[REF_COL]
                st.session_state['selected_ref'] = new_ref
                 
    else:
        st.info("⚠️ Le DataFrame est vide ou les coordonnées sont manquantes. Vérifiez si le fichier s'est chargé correctement.")


# --- 4. Panneau de Détails (Plein Écran sous la Carte) ---
st.markdown("---") 

selected_ref = st.session_state['selected_ref']
st.header("🔍 Détails du Lot Sélectionné")
# DIAGNOSTIC CRITIQUE : Cette valeur doit changer après le clic
st.text(f"DEBUG REF: {selected_ref if selected_ref else 'NOT SET'}") 
st.markdown("---")

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

        st.subheader(f"Référence : {display_title_ref}")
        
        # --- Adresse & Lien Google Maps ---
        
        lien_maps = selected_data.get('Lien Google Maps', None)
        if lien_maps and pd.notna(lien_maps) and str(lien_maps).lower().strip() not in ('nan', 'n/a', 'none', ''):
            st.markdown(
                f'<a href="{lien_maps}" target="_blank">'
                f'<button style="background-color: #4CAF50; color: white; border: none; padding: 10px 20px; text-align: center; text-decoration: none; display: inline-block; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 8px; width: 100%;">'
                f'Voir sur Google Maps'
                f'</button></a>',
                unsafe_allow_html=True
            )
        else:
            st.caption("Lien Google Maps indisponible.")

        adresse = selected_data.get('Adresse', 'N/A')
        code_postal = selected_data.get('Code Postal', '')
        ville = selected_data.get('Ville', '')
        
        st.markdown("##### 📍 Adresse")
        if str(adresse).strip() not in ('N/A', 'nan', ''):
            st.write(f"**{adresse}** \n{code_postal} - {ville}")
        else:
            st.write("Adresse non renseignée.")
        
        st.markdown("---")
        st.markdown("##### Informations Détaillées (Filtrées)")
        
        colonnes_a_afficher = [
            ('Emplacement', selected_data.get('Emplacement', 'N/A')),
            ('Typologie', selected_data.get('Typologie', 'N/A')),
            ('Type', selected_data.get('Type', 'N/A')),
            ('Cession / Droit au bail', selected_data.get('Cession / Droit au bail', 'N/A')),
            ('Nombre de lots', selected_data.get('Nombre de lots', 'N/A')),
            ('Surface GLA', f"{selected_data.get('Surface GLA', 'N/A')} m²"),
            ('Répartition surface GLA', selected_data.get('Répartition surface GLA', 'N/A')),
            ('Surface utile', f"{selected_data.get('Surface utile', 'N/A')} m²"),
            ('Répartition surface utile', selected_data.get('Répartition surface utile', 'N/A')),
            ('Loyer annuel', f"{selected_data.get('Loyer annuel', 'N/A')} €"),
            ('Loyer Mensuel', f"{selected_data.get('Loyer Mensuel', 'N/A')} €"),
            ('Loyer €/m²', f"{selected_data.get('Loyer €/m²', 'N/A')} €/m²"),
            ('Loyer variable', selected_data.get('Loyer variable', 'N/A')),
            ('Charges anuelles', f"{selected_data.get('Charges anuelles', 'N/A')} €"),
            ('Charges Mensuelles', f"{selected_data.get('Charges Mensuelles', 'N/A')} €"),
            ('Charges €/m²', f"{selected_data.get('Charges €/m²', 'N/A')} €/m²"),
            ('Dépôt de garantie', selected_data.get('Dépôt de garantie', 'N/A')),
            ('GAPD', selected_data.get('GAPD', 'N/A')),
            ('Taxe foncière', f"{selected_data.get('Taxe foncière', 'N/A')} €"),
            ('Marketing', selected_data.get('Marketing', 'N/A')),
            ('Gestion', selected_data.get('Gestion', 'N/A')),
            ('Etat de livraison', selected_data.get('Etat de livraison', 'N/A')),
            ('Extraction', selected_data.get('Extraction', 'N/A')),
            ('Restauration', selected_data.get('Restauration', 'N/A')),
            ('Environnement Commercial', selected_data.get('Environnement Commercial', 'N/A')),
            ('Commentaires', selected_data.get('Commentaires', 'N/A')),
            ('Actif', selected_data.get('Actif', 'N/A')),
            ('Valeur BP', selected_data.get('Valeur BP', 'N/A')),
            ('Contact', selected_data.get('Contact', 'N/A')),
        ]
        
        cols_info = st.columns(3)
        col_index = 0
        
        for nom, valeur in colonnes_a_afficher:
            valeur_str = str(valeur).strip()
            if valeur_str not in ('N/A', 'nan', '', '€', 'm²', 'None', 'None €', 'None m²'):
                with cols_info[col_index % 3]:
                    if nom == 'Commentaires':
                        st.caption("Commentaires:")
                        st.text(valeur)
                    else:
                        st.metric(label=nom, value=valeur)
                col_index += 1
        
        st.markdown("---")
            
    else:
        st.error("❌ ÉCHEC : La référence a été capturée, mais la recherche dans le DataFrame a échoué (Problème de correspondance de chaîne).")
        st.text(f"Référence cherchée : '{selected_ref}' (Long: {len(selected_ref)})")
        
else:
    st.info("Cliquez sur un marqueur (cercle) sur la carte pour afficher ses détails ci-dessous.")

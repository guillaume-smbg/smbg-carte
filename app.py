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

# --- CSS / HTML pour le volet flottant avec transition ---
CUSTOM_CSS = """
<style>
/* 1. La classe de base : définit l'apparence, la position FIXE et la TRANSITION */
.details-panel {
    position: fixed;
    top: 0;
    right: 0; /* Position par défaut (ouverte), sera ajustée par transform */
    width: 300px; /* Largeur du panneau de détails */
    height: 100vh;
    background-color: white; 
    z-index: 999; 
    padding: 15px;
    box-shadow: -5px 0 15px rgba(0,0,0,0.2); 
    overflow-y: auto; 
    
    /* PROPRIÉTÉ CLÉ : Ajoute la transition au mouvement (transform) */
    transition: transform 0.4s ease-in-out; 
}

/* 2. Classe pour l'état FERMÉ (caché) */
/* Translate le panneau de 100% de sa largeur (300px) vers la droite, hors écran */
.details-panel-closed {
    transform: translateX(100%);
}

/* 3. Classe pour l'état OUVERT (visible) */
/* Le panneau est à sa position normale (translateX(0)) */
.details-panel-open {
    transform: translateX(0);
}

/* Ajustement pour que le st.sidebar (Contrôles Gauche) soit bien visible */
.css-hxt7xp { 
    z-index: 1000 !important; 
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# --- FIN CSS / HTML ---

# --- Fonction utilitaire de formatage (NOUVELLE) ---
def format_value(value, unit=""):
    """Formate la valeur: supprime les unités si la valeur est un texte."""
    val_str = str(value).strip()
    
    # Vérifie si la valeur ressemble à un NaN ou à une chaîne vide/non pertinente
    if val_str in ('N/A', 'nan', '', 'None'):
        return "Non renseigné"
        
    # Vérifie si la valeur est une chaîne contenant des lettres (ex: "Selon surface")
    if any(c.isalpha() for c in val_str):
        # Si c'est un texte, on retourne le texte seul
        return val_str
    
    # Si c'est un nombre (ou une plage comme "36 à 265 m²" déjà formatée dans l'Excel)
    # on n'ajoute l'unité que si elle n'est pas déjà présente pour éviter les doublons.
    if unit and not val_str.lower().endswith(unit.lower().strip()):
        return f"{val_str} {unit}"
        
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
        
        # Vérifie si le clic est éloigné des pins (logique approximative pour "clic sur la carte")
        data_df['distance_sq'] = (data_df['Latitude'] - current_coords[0])**2 + (data_df['Longitude'] - current_coords[1])**2
        closest_row = data_df.loc[data_df['distance_sq'].idxmin()]
        min_distance_sq = data_df['distance_sq'].min()
        
        DISTANCE_THRESHOLD = 0.0005 

        if current_coords != st.session_state['last_clicked_coords']:
            st.session_state['last_clicked_coords'] = current_coords
            
            if min_distance_sq > DISTANCE_THRESHOLD:
                # Clic loin du pin le plus proche -> Masquer le volet
                if st.session_state['selected_ref'] is not None:
                     st.session_state['selected_ref'] = None
                     st.rerun()
            else:
                # Clic proche d'un pin -> Afficher les détails
                new_ref = closest_row[REF_COL]
                if new_ref != st.session_state['selected_ref']:
                    st.session_state['selected_ref'] = new_ref
                    st.rerun() 
             
else:
    st.info("⚠️ Le DataFrame est vide ou les coordonnées sont manquantes.")


# --- 4. Panneau de Détails Droit (Injection HTML Flottant) ---

html_content = f"""
<div class="details-panel {panel_class}">
"""

if show_details:
    selected_data_series = data_df[data_df[REF_COL].str.strip() == selected_ref_clean]
    
    if len(selected_data_series) > 0:
        selected_data = selected_data_series.iloc[0].copy()
        
        try:
            display_title_ref = str(int(selected_ref_clean))
        except ValueError:
            display_title_ref = selected_ref_clean
            
        
        html_content += f"""
            <h3 style="color:#303030; margin-top: 0;">🔍 Détails du Lot</h3>
            <hr style="border: 1px solid #ccc; margin: 5px 0;">
            <h4 style="color: #0072B2;">Réf. : {display_title_ref}</h4>
        """
        
        html_content += '<div style="background-color: #f7f7f7; padding: 10px; border-radius: 5px; margin-bottom: 10px;">'
        html_content += '<p style="font-weight: bold; margin: 5px 0;">Informations clés:</p>'
        
        # --- Utilisation de la fonction format_value() ---
        
        # 1. Empêche la double unité "m² m²"
        val_gla = format_value(selected_data.get('Surface GLA', 'N/A'), unit="m²")
        
        # 2. Empêche le doublon "Selon surface €"
        val_loyer = format_value(selected_data.get('Loyer annuel', 'N/A'), unit="€")
        
        # 3. Traite les autres valeurs
        val_emplacement = format_value(selected_data.get('Emplacement', 'N/A'))
        val_typologie = format_value(selected_data.get('Typologie', 'N/A'))
        
        colonnes_a_afficher = [
            ('Emplacement', val_emplacement),
            ('Typologie', val_typologie),
            ('Surface GLA', val_gla),
            ('Loyer annuel', val_loyer),
        ]
        
        for nom, valeur in colonnes_a_afficher:
             html_content += f'<div style="margin-bottom: 5px;"><span style="font-weight: bold; color: #555;">{nom} :</span> {valeur}</div>'
                 
        html_content += '</div>' 
        
        # --- Correction de l'affichage de l'adresse ---
        adresse = selected_data.get('Adresse', 'N/A')
        code_postal = selected_data.get('Code Postal', '')
        ville = selected_data.get('Ville', '')
        
        st.write(f"valeur adresse: {adresse}")
        st.write(f"valeur code postal: {code_postal}")
        st.write(f"valeur ville: {ville}")
        
        html_content += f'<p style="font-weight: bold; color: #555; margin: 10px 0 0px;">📍 Adresse</p>'
        
        # On affiche uniquement la ligne Code Postal - Ville s'ils sont renseignés
        adresse_str = str(adresse).strip()
        code_ville_str = f"{code_postal} - {ville}".strip()
        
        if adresse_str not in ('N/A', 'nan', ''):
             html_content += f'<p style="margin: 0;">{adresse_str}<br>'
             if code_ville_str not in ('N/A - N/A', 'nan - nan', '-'):
                 html_content += f'{code_ville_str}'
             html_content += '</p>'
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
        
    else:
        html_content += "<p>❌ Erreur: Référence non trouvée.</p>"

# Fermeture de la div flottante (ouvert ou fermé)
html_content += '</div>' 

# Injection du panneau de détails flottant
st.markdown(html_content, unsafe_allow_html=True)

# Message dans le corps principal si aucun détail n'est affiché (pour la visibilité initiale)
if not show_details and not data_df.empty:
    st.info("Cliquez sur un marqueur sur la carte pour afficher ses détails dans le volet de droite.")

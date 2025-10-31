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
    right: 0; 
    width: 300px; 
    height: 100vh;
    background-color: white; 
    z-index: 1000; /* Z-INDEX ÉLEVÉ POUR S'ASSURER QU'IL EST AU DESSUS DE TOUT */
    padding: 15px;
    box-shadow: -5px 0 15px rgba(0,0,0,0.2); 
    overflow-y: auto; 
    transition: transform 0.4s ease-in-out; 
}

/* 2. Classe pour l'état FERMÉ (caché) */
.details-panel-closed {
    transform: translateX(100%);
}

/* 3. Classe pour l'état OUVERT (visible) */
.details-panel-open {
    transform: translateX(0);
}

/* Ajustement pour que le st.sidebar (Contrôles Gauche) soit bien visible */
.css-hxt7xp { 
    z-index: 1000 !important; 
}
</style>
"""
# On injecte le CSS dès le début
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
# --- FIN CSS / HTML ---

# --- Fonction utilitaire de formatage (utilisée uniquement par le panneau de droite) ---
def format_value(value, unit=""):
    """
    Formate la valeur en utilisant un ESPACE comme séparateur de milliers
    et une VIRGULE comme séparateur décimal (norme FR).
    """
    val_str = str(value).strip()
    
    # 1. Gestion des valeurs vides ou non pertinentes
    if val_str in ('N/A', 'nan', '', 'None', 'None €', 'None m²', '/'):
        return "Non renseigné"
        
    # 2. Gestion des valeurs textuelles (sans chiffres)
    if any(c.isalpha() for c in val_str) and not any(c.isdigit() for c in val_str):
        return val_str
    
    # 3. Gestion des valeurs numériques
    try:
        num_value = float(value)
        
        # --- FORMATAGE FRANÇAIS (espace milliers, virgule décimale) ---
        if num_value != round(num_value, 2):
            # Format avec décimales (Ex: 12,345.67 avec f-string standard)
            val_str = f"{num_value:,.2f}"
            
            # 1. Remplacer la virgule de milliers par un espace
            val_str = val_str.replace(',', ' ') 
            # 2. Remplacer le point décimal par une virgule
            val_str = val_str.replace('.', ',')
        else:
            # Format sans décimales (Ex: 12,345 avec f-string standard)
            val_str = f"{num_value:,.0f}"
            
            # Remplacer la virgule de milliers par un espace
            val_str = val_str.replace(',', ' ') 
            
        # Ajoute l'unité si elle n'est pas déjà présente
        if unit and not val_str.lower().endswith(unit.lower().strip()):
            return f"{val_str} {unit}"
            
    except (ValueError, TypeError):
        # La valeur n'est pas un simple nombre 
        pass
        
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
        
        data_df['distance_sq'] = (data_df['Latitude'] - current_coords[0])**2 + (data_df['Longitude'] - current_coords[1])**2
        closest_row = data_df.loc[data_df['distance_sq'].idxmin()]
        min_distance_sq = data_df['distance_sq'].min()
        
        DISTANCE_THRESHOLD = 0.0005 

        if current_coords != st.session_state['last_clicked_coords']:
            st.session_state['last_clicked_coords'] = current_coords
            
            if min_distance_sq > DISTANCE_THRESHOLD:
                if st.session_state['selected_ref'] is not None:
                     st.session_state['selected_ref'] = None
                     st.rerun()
            else:
                new_ref = closest_row[REF_COL]
                if new_ref != st.session_state['selected_ref']:
                    st.session_state['selected_ref'] = new_ref
                    st.rerun() 
             
else:
    st.info("⚠️ Le DataFrame est vide ou les coordonnées sont manquantes. Aucune carte ne peut être affichée.")


# --- 4. Panneau de Détails Droit (Injection HTML Flottant via st.markdown) ---
# Le code du panneau de droite est laissé tel quel.

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
            
        # --- Entête ---
        html_content += f"""
            <h3 style="color:#303030; margin-top: 0;">🔍 Détails du Lot</h3>
            <hr style="border: 1px solid #ccc; margin: 5px 0;">
            <h4 style="color: #0072B2;">Réf. : {display_title_ref}</h4>
        """
        
        # --- Affichage de l'adresse ---
        adresse = selected_data.get('Adresse', 'N/A')
        code_postal = selected_data.get('Code Postal', '')
        ville = selected_data.get('Ville', '')
        
        html_content += f'<p style="font-weight: bold; color: #555; margin: 10px 0 5px;">📍 Adresse complète</p>'
        adresse_str = str(adresse).strip()
        code_ville_str = f"{code_postal} - {ville}".strip()
        
        html_content += f'<p style="margin: 0; font-size: 14px;">'
        if adresse_str not in ('N/A', 'nan', ''):
             html_content += f'{adresse_str}<br>'
        
        if code_ville_str not in ('N/A - N/A', 'nan - nan', '-'):
             html_content += f'{code_ville_str}'
        
        html_content += '</p>'


        html_content += '<hr style="border: 1px solid #eee; margin: 15px 0;">'
        
        # --- LOGIQUE D'AFFICHAGE DES INFORMATIONS DÉTAILLÉES (G à AH) ---
        html_content += '<p style="font-weight: bold; margin-bottom: 10px;">Informations Détaillées:</p>'
        
        # Colonnes à exclure 
        cols_to_exclude = [
            REF_COL, 
            'Latitude', 'Longitude', 
            'Lien Google Maps' ,
            'Adresse', 'Code Postal', 'Ville',
            'distance_sq' 
        ]
        
        # Toutes les colonnes à partir de l'indice 6 (colonne G)
        all_cols = data_df.columns.tolist()
        detail_cols = all_cols[6:] 

        for col_name in detail_cols:
            if col_name not in cols_to_exclude:
                value = selected_data.get(col_name, 'N/A')
                
                # Détermination de l'unité basée sur le nom de la colonne
                unit = ''
                if any(k in col_name for k in ['Loyer', 'Charges', 'garantie', 'foncière', 'Taxe', 'Marketing', 'Gestion', 'BP', 'annuel', 'Mensuel']) and '€' not in col_name:
                    unit = '€'
                elif any(k in col_name for k in ['Surface', 'GLA', 'utile']) and 'm²' not in col_name:
                    unit = 'm²'
                
                # Utilisation de la fonction de formatage
                formatted_value = format_value(value, unit=unit)
                
                # Affichage des paires Nom : Valeur
                html_content += f'''
                <div style="margin-bottom: 8px;">
                    <span style="font-weight: bold; color: #555; font-size: 14px;">{col_name} :</span> 
                    <span style="font-size: 14px;">{formatted_value}</span>
                </div>
                '''

        # --- Lien Google Maps (en bas du volet) ---
        lien_maps = selected_data.get('Lien Google Maps', None)
        if lien_maps and pd.notna(lien_maps) and str(lien_maps).lower().strip() not in ('nan', 'n/a', 'none', ''):
             html_content += f'''
             <hr style="border: 1px solid #eee; margin: 20px 0;">
             <a href="{lien_maps}" target="_blank" style="text-decoration: none;">
                <button style="background-color: #4CAF50; color: white; border: none; padding: 10px 0px; text-align: center; text-decoration: none; display: block; font-size: 14px; margin-top: 10px; cursor: pointer; border-radius: 4px; width: 100%;">
                    Voir sur Google Maps
                </button>
            </a>
             '''
        
    else:
        html_content += "<p>❌ Erreur: Référence non trouvée.</p>"
        
else:
    # Message par défaut quand aucun lot n'est sélectionné
    html_content += """
    <p style="font-weight: bold; margin-top: 10px; color: #0072B2;">
        Cliquez sur un marqueur (cercle) sur la carte pour afficher ses détails ici.
    </p>
    """


# Fermeture de la div flottante (FIN du panneau)
html_content += '</div>' 

# Injection du panneau de détails flottant
st.markdown(html_content, unsafe_allow_html=True)


# --- 5. Affichage de l'Annonce Sélectionnée (Sous la carte) ---
st.markdown("---")
st.header("📋 Annonce du Lot Sélectionné")

if show_details:
    # Filtre sur la référence sélectionnée
    selected_row_df = data_df[data_df[REF_COL].str.strip() == selected_ref_clean].copy()
    
    if not selected_row_df.empty:
        # Suppression des colonnes temporaires pour l'affichage
        if 'distance_sq' in selected_row_df.columns:
            display_df = selected_row_df.drop(columns=['distance_sq'])
        else:
            display_df = selected_row_df
            
        # --- NOUVELLE LOGIQUE: Limiter les colonnes de 'Adresse' jusqu'à 'Commentaires' inclus ---
        all_cols = display_df.columns.tolist()
        
        try:
            # 1. Trouver l'index de 'Adresse'
            adresse_index = all_cols.index('Adresse')
            
            # 2. Trouver l'index de 'Commentaires'
            commentaires_index = all_cols.index('Commentaires')
            
            # 3. Conserver les colonnes de 'Adresse' à 'Commentaires' inclus
            cols_to_keep = all_cols[adresse_index : commentaires_index + 1]
            display_df = display_df[cols_to_keep]
        
        except ValueError as e:
            if 'Adresse' in str(e):
                st.warning("La colonne 'Adresse' est introuvable. Affichage de toutes les colonnes disponibles.")
            elif 'Commentaires' in str(e):
                 # Si 'Commentaires' n'existe pas, on commence à 'Adresse' et va jusqu'à la fin
                 try:
                     adresse_index = all_cols.index('Adresse')
                     cols_to_keep = all_cols[adresse_index:]
                     display_df = display_df[cols_to_keep]
                     st.warning("La colonne 'Commentaires' est introuvable. Affichage des colonnes à partir de 'Adresse' jusqu'à la fin.")
                 except ValueError:
                    st.warning("Erreur de filtrage des colonnes. Affichage de toutes les colonnes disponibles.")

        # Transposition du DataFrame
        transposed_df = display_df.T.reset_index()
        transposed_df.columns = ['Champ', 'Valeur']
        
        # --- LOGIQUE D'ARRONDI ET DE FORMATAGE MONÉTAIRE (AVEC ESPACE) ---
        
        money_keywords = ['Loyer', 'Charges', 'garantie', 'foncière', 'Taxe', 'Marketing', 'Gestion', 'BP', 'annuel', 'Mensuel', 'Prix']
        
        def format_monetary_value(row):
            """Applique le formatage en utilisant un ESPACE comme séparateur de milliers."""
            champ = row['Champ']
            value = row['Valeur']
            
            # Vérifie si la valeur est un nombre
            is_numeric = pd.api.types.is_numeric_dtype(pd.Series(value))
            
            # Colonne monétaire
            is_money_col = any(keyword.lower() in champ.lower() for keyword in money_keywords)
            
            if is_money_col and is_numeric:
                try:
                    float_value = float(value)
                    
                    # 1. Formatage standard US sans décimales (ex: 85,723)
                    formatted_value = f"{float_value:,.0f}" 
                    
                    # 2. Remplacer la virgule de milliers par un espace
                    formatted_value = formatted_value.replace(",", " ")
                    
                    return f"€{formatted_value}"
                    
                except (ValueError, TypeError):
                    return value 
            
            # Colonne surface
            is_surface_col = any(keyword.lower() in champ.lower() for keyword in ['Surface', 'GLA', 'utile'])
            if is_surface_col and is_numeric:
                 try:
                    float_value = float(value)
                    formatted_value = f"{float_value:,.0f}" # 12,345
                    formatted_value = formatted_value.replace(",", " ") # 12 345
                    
                    return f"{formatted_value} m²"
                 except (ValueError, TypeError):
                    return value
                    
            # Coordonnées (à ne plus afficher dans ce tableau, mais la logique est là si on les réintroduit)
            if champ in ['Latitude', 'Longitude'] and is_numeric:
                 try:
                    return f"{float(value):.4f}"
                 except (ValueError, TypeError):
                    return value

            return value
        
        # Appliquer la fonction de formatage à la colonne 'Valeur'
        transposed_df['Valeur'] = transposed_df.apply(format_monetary_value, axis=1)
        
        # Affichage du tableau formaté
        st.dataframe(transposed_df, hide_index=True, use_container_width=True)
        
    else:
        st.warning(f"Référence **{selected_ref_clean}** introuvable dans les données.")
else:
    st.info("Cliquez sur un marqueur sur la carte pour afficher l'annonce complète ici.")

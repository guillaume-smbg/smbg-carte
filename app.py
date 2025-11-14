import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import math
import os

# --- 1. CONFIGURATION ET CONSTANTES ---

# Constantes SMBG
SMBG_BLUE = "#05263d"
SMBG_COPPER = "#C67B42"
FONT_FALLBACK = 'Futura, "Futura PT", "Century Gothic", Arial, sans-serif'
APP_ID = "smbg_carte_app" # ID pour les sélecteurs CSS personnalisés

# Colonnes de l'Excel (simulées)
COLUMNS = [
    'Référence annonce', 'Région', 'Département', 'Ville', 'Adresse', 'Surface GLA',
    'Loyer annuel', 'Charges', 'Taxe foncière', 'Honoraires', 'Emplacement',
    'Typologie', 'Extraction', 'Restauration', 'Latitude', 'Longitude', 'Actif'
]
# Colonnes à afficher dans le panneau de détails (G à AL, sans H)
# J'ajoute des colonnes génériques pour simuler les colonnes AL
DETAIL_COLUMNS_KEYS = [
    'Surface GLA', 'Loyer annuel', 'Charges', 'Taxe foncière', 'Honoraires',
    'Emplacement', 'Typologie', 'Extraction', 'Restauration',
    'Autre Détail 1', 'Autre Détail 2', 'Autre Détail 3', 'Autre Détail 4',
    'Autre Détail 5', 'Autre Détail 6', 'Autre Détail 7', 'Autre Détail 8',
    'Autre Détail 9', 'Autre Détail 10', 'Autre Détail 11', 'Autre Détail 12',
    'Autre Détail 13', 'Autre Détail 14', 'Autre Détail 15', 'Autre Détail 16',
    'Autre Détail 17', 'Autre Détail 18', 'Autre Détail 19', 'Autre Détail 20',
    'Autre Détail 21', 'Autre Détail 22', 'Autre Détail 23', 'Autre Détail 24',
]
# Colonne spéciale Google Maps (colonne H)
MAPS_URL_COLUMN = 'Lien Google Maps'

# --- 2. FONCTIONS UTILITAIRES DE DONNÉES ---

def format_reference(ref):
    """Formate la référence (ex: 0005.1 -> 5.1)."""
    if isinstance(ref, (int, float)):
        # Si c'est un nombre (float ou int)
        s = str(ref)
        if '.' in s:
            parts = s.split('.')
            integer_part = parts[0].lstrip('0')
            if not integer_part:
                integer_part = '0'
            return f"{integer_part}.{parts[1].rstrip('0').rstrip('.')}"
        else:
            return s.lstrip('0') if s.lstrip('0') else '0'
    elif isinstance(ref, str):
        # Si c'est une chaîne (ex: '0005.1')
        if '.' in ref:
            parts = ref.split('.')
            integer_part = parts[0].lstrip('0')
            if not integer_part:
                integer_part = '0'
            return f"{integer_part}.{parts[1].rstrip('0').rstrip('.')}"
        else:
            return ref.lstrip('0') if ref.lstrip('0') else '0'
    return str(ref)

def format_value(key, value):
    """Formate les valeurs pour le panneau de détails (Euro, Surface, Texte)."""
    if pd.isna(value) or value is None:
        return None # Sera masqué par la règle

    # Règle de masquage
    str_value = str(value).strip().lower()
    if str_value in ["néant", "-", "/", "0"] or value == 0:
        return None

    if 'loyer' in key.lower() or 'charge' in key.lower() or 'honoraire' in key.lower() or 'taxe' in key.lower():
        try:
            # Formatage en Euros
            return f"{int(value):,.0f} €".replace(",", " ").replace(".", ",")
        except:
            return str(value)

    if 'surface' in key.lower() or 'gla' in key.lower():
        try:
            # Formatage en m²
            return f"{int(value):,.0f} m²".replace(",", " ").replace(".", ",")
        except:
            return str(value)

    return str(value)

def load_and_prepare_data():
    """Charge le fichier Excel (simulé) et prépare le DataFrame."""
    try:
        # Tente de charger le vrai fichier si possible
        df = pd.read_excel('data/Liste des lots.xlsx')
    except (FileNotFoundError, ValueError):
        # Simulation des données si le fichier n'est pas trouvé
        data = {
            'Référence annonce': ['0003', '0005.1', '0012', '0020.5', '0025'],
            'Région': ['Île-de-France', 'Île-de-France', 'Auvergne-Rhône-Alpes', 'Nouvelle-Aquitaine', 'Île-de-France'],
            'Département': ['Paris', 'Hauts-de-Seine', 'Rhône', 'Gironde', 'Paris'],
            'Ville': ['Paris', 'Neuilly-sur-Seine', 'Lyon', 'Bordeaux', 'Paris 16'],
            'Adresse': ['Rue de Rivoli', 'Av. Charles de Gaulle', 'Place Bellecour', 'Cours de l\'Intendance', 'Av. Victor Hugo'],
            'Surface GLA': [240, 1500, 320, 50, 600],
            'Loyer annuel': [120000, 450000, 95000, 15000, 300000],
            MAPS_URL_COLUMN: ['https://maps.google.com/?q=Paris+Rivoli', 'https://maps.google.com/?q=Neuilly', None, 'https://maps.google.com/?q=Bordeaux', 'https://maps.google.com/?q=Paris+Hugo'],
            'Charges': [5000, 15000, 'néant', 0, 12000],
            'Taxe foncière': [10000, 30000, 2000, 500, '-'],
            'Honoraires': [24000, 90000, 19000, 3000, 60000],
            'Emplacement': ['Centre-Ville', 'Périphérie', 'Centre-Ville', 'Centre-Ville', 'Centre-Ville'],
            'Typologie': ['Bureaux', 'Commerce', 'Commerce', 'Bureaux', 'Commerce'],
            'Extraction': ['Oui', 'Non', 'Non', 'Oui', 'Non'],
            'Restauration': ['Non', 'Oui', 'Non', 'Non', 'Oui'],
            'Latitude': [48.857, 48.883, 45.759, 44.84, 48.868],
            'Longitude': [2.35, 2.25, 4.83, -0.57, 2.28],
            'Actif': ['oui', 'oui', 'oui', 'oui', 'non'],
        }
        # Ajout des colonnes de détail AL
        for i in range(1, 25):
             data[f'Autre Détail {i}'] = ['Valeur ' + str(i)] * 5
        
        df = pd.DataFrame(data)
        st.warning("⚠️ **Mode de démonstration :** Le fichier Excel `data/Liste des lots.xlsx` n'a pas été trouvé. Les données sont simulées.")

    # Assurer que les colonnes critiques existent et sont du bon type
    required_map_cols = ['Latitude', 'Longitude', 'Référence annonce']
    for col in required_map_cols:
        if col not in df.columns:
            st.error(f"La colonne essentielle '{col}' est manquante dans les données.")
            return pd.DataFrame()

    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    
    # Filtrer les lots non actifs et les coordonnées invalides
    df = df[df['Actif'].astype(str).str.lower() == 'oui']
    df = df.dropna(subset=['Latitude', 'Longitude'])
    df = df[(df['Latitude'] >= -90) & (df['Latitude'] <= 90)]
    df = df[(df['Longitude'] >= -180) & (df['Longitude'] <= 180)]

    # Appliquer le formatage de la référence
    df['Ref Formatée'] = df['Référence annonce'].apply(format_reference)
    
    # Créer une clé unique pour le GeoJson
    df['lot_key'] = 'Lot_' + df['Ref Formatée'].astype(str)
    
    # Stocker les min/max pour les sliders
    if 'Surface GLA' in df.columns and 'Loyer annuel' in df.columns:
        st.session_state.gla_min_max = (df['Surface GLA'].min(), df['Surface GLA'].max())
        st.session_state.loyer_min_max = (df['Loyer annuel'].min(), df['Loyer annuel'].max())

    return df

# --- 3. GESTION DES ÉTATS ET INITIALISATION ---

if 'data' not in st.session_state:
    st.session_state.data = load_and_prepare_data()

if 'filtered_data' not in st.session_state:
    st.session_state.filtered_data = st.session_state.data.copy()

if 'selected_lot_key' not in st.session_state:
    st.session_state.selected_lot_key = None

if 'gla_range' not in st.session_state and 'gla_min_max' in st.session_state:
    st.session_state.gla_range = st.session_state.gla_min_max

if 'loyer_range' not in st.session_state and 'loyer_min_max' in st.session_state:
    st.session_state.loyer_range = st.session_state.loyer_min_max

# --- 4. CSS D'INJECTION (Layout et Style CRITIQUE) ---

# Fonction pour injecter le CSS critique
def inject_custom_css():
    css = f"""
    <style>
        /* 3. Identité Visuelle: Font Futura (Simulation basée sur chemin assets) */
        @font-face {{
            font-family: 'Futura';
            src: url('assets/Futura Book.ttf') format('truetype'); /* Chemin à ajuster */
            font-weight: 400;
        }}
        @font-face {{
            font-family: 'Futura';
            src: url('assets/Futura Bold.ttf') format('truetype'); /* Chemin à ajuster */
            font-weight: 700;
        }}
        
        /* Appliquer la police à toute l'application */
        html, body, .stApp {{
            font-family: Futura, {FONT_FALLBACK};
            overflow: hidden !important; /* 11. Comportement général: Pas de scroll vertical/horizontal */
        }}

        /* 4. Layout Général (CRITIQUE) */

        /* A. Volet gauche (sidebar) */
        [data-testid="stSidebar"] {{
            width: 275px !important; /* Largeur fixe: 275 px */
            min-width: 275px !important;
            max-width: 275px !important;
            background-color: {SMBG_BLUE} !important; /* Fond: bleu SMBG */
            transition: none; /* Empêche le slide-in/out */
        }}
        
        /* 12. Ce que je ne veux JAMAIS: Jamais rétractable (cacher le bouton collapse) */
        [data-testid="stSidebarToggleButton"] {{
            display: none !important;
        }}

        /* Masquer le bouton d'agrandissement du logo (3. Logo) */
        .st-emotion-cache-1mnn9i2 {{ /* Sélecteur Streamlit pour le bouton d'agrandissement d'image */
            display: none !important;
        }}

        /* B. Zone centrale (Map) */
        /* La Map occupe tout l'espace restant */
        [data-testid="stVerticalBlock"] {{
            height: 100vh;
        }}
        
        /* S'assurer que le bloc principal est bien plein écran */
        [data-testid="stAppViewBlockContainer"] {{
            height: 100vh;
            max-height: 100vh;
        }}
        
        /* S'assurer que le conteneur de la carte prend toute la hauteur */
        #map_container {{
            height: 100vh; /* 4. La carte doit remplir 100 % de la hauteur de l'écran (100vh) */
            margin: 0 !important;
            padding: 0 !important;
        }}
        
        /* Retirer la bande blanche sous le footer Streamlit */
        footer {{ visibility: hidden; }}
        
        /* Styling des checkboxes (pour l'indentation) */
        .department-checkbox > div > label {{
            margin-left: 15px; /* Indentation de 15px pour les départements */
        }}
        
        /* --- C. Volet droit (Panneau de détails) --- */
        #detail-panel {{
            position: fixed;
            top: 0;
            right: var(--panel-offset, -275px); /* Contrôlé par JS/State: par défaut replié */
            width: 275px; /* Largeur fixe: 275 px */
            height: 100vh;
            background-color: {SMBG_BLUE};
            color: white;
            padding: 20px;
            box-shadow: -5px 0 15px rgba(0, 0, 0, 0.5);
            z-index: 1000;
            transition: right 0.3s ease-in-out; /* Animation d'ouverture/fermeture */
            overflow-y: auto; /* Scroll interne si nécessaire */
        }}

        #detail-panel h3, #detail-panel h4 {{
            color: white;
            font-weight: bold;
            margin-top: 0;
            margin-bottom: 15px;
        }}
        
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .detail-label {{
            color: {SMBG_COPPER}; /* Couleur cuivre SMBG pour les labels */
            font-weight: bold;
            flex-shrink: 0;
            padding-right: 10px;
        }}
        
        .detail-value {{
            text-align: right;
            font-weight: 300;
            word-break: break-word;
        }}
        
        /* Marge haute du logo (3. Logo) */
        .sidebar-logo {{
            padding-top: 25px; /* Marge haute: environ 25 px */
            padding-bottom: 25px;
            text-align: center;
        }}
        
        /* Style des sliders pour harmonisation avec le thème */
        .stSlider > div > div > div {{
            background-color: {SMBG_COPPER};
        }}
        
        /* Style des boutons (Réinitialiser, Google Maps) */
        .stButton button {{
            background-color: {SMBG_COPPER};
            color: {SMBG_BLUE};
            border: none;
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
            width: 100%;
            transition: background-color 0.2s;
        }}
        .stButton button:hover {{
            background-color: #d18d5b;
        }}
        
    </style>
    """
    # JS pour contrôler la position du panneau droit via la variable CSS
    js = f"""
    <script>
        function updatePanel() {{
            const panel = document.getElementById('detail-panel');
            if (panel) {{
                const show = window.stPanelState === 'visible';
                panel.style.right = show ? '0px' : '-275px';
            }}
        }}
        
        // Initialiser l'état Streamlit/Python dans l'environnement JS
        window.stPanelState = '{'visible' if st.session_state.selected_lot_key else 'hidden'}';
        updatePanel();
    </script>
    """
    
    st.html(css)
    st.html(js)

# --- 5. LOGIQUE DES FILTRES ET MISE À JOUR ---

def filter_data():
    """Applique tous les filtres actifs à la session state."""
    df = st.session_state.data.copy()
    
    # --- 1. Filtre Région / Département ---
    selected_regions = [r for r, checked in st.session_state.region_checks.items() if checked]
    region_mask = pd.Series(False, index=df.index)

    if selected_regions:
        for region in selected_regions:
            # Départements cochés pour cette région
            dept_checks = st.session_state.dept_checks.get(region, {})
            selected_departments = [d for d, checked in dept_checks.items() if checked]

            if selected_departments:
                # 9. Logique de filtrage: Région cochée + certains départements cochés
                mask = (df['Région'] == region) & (df['Département'].isin(selected_departments))
            else:
                # 9. Logique de filtrage: Région cochée + aucun département cochée -> toute la région
                mask = (df['Région'] == region)

            region_mask = region_mask | mask

        df = df[region_mask]
    
    if df.empty and not st.session_state.data.empty:
        st.session_state.filtered_data = pd.DataFrame()
        return

    # --- 2. Filtre Sliders (Surface GLA) ---
    min_gla, max_gla = st.session_state.gla_range
    if 'Surface GLA' in df.columns:
        df = df[(df['Surface GLA'] >= min_gla) & (df['Surface GLA'] <= max_gla)]
        
    # --- 3. Filtre Sliders (Loyer annuel) ---
    min_loyer, max_loyer = st.session_state.loyer_range
    if 'Loyer annuel' in df.columns:
        df = df[(df['Loyer annuel'] >= min_loyer) & (df['Loyer annuel'] <= max_loyer)]

    # --- 4. Autres cases à cocher (Emplacement, Typologie, Extraction, Restauration) ---
    for col_name in ['Emplacement', 'Typologie', 'Extraction', 'Restauration']:
        if col_name in df.columns:
            selected_values = [v for v, checked in st.session_state.other_checks.get(col_name, {}).items() if checked]
            if selected_values:
                df = df[df[col_name].isin(selected_values)]

    st.session_state.filtered_data = df

def reset_filters():
    """Réinitialise tous les filtres et ferme le panneau droit."""
    
    # 8. Réinitialiser: décocher toutes les cases
    for region in st.session_state.data['Région'].unique():
        st.session_state.region_checks[region] = False
        if region in st.session_state.dept_checks:
            for dept in st.session_state.dept_checks[region].keys():
                st.session_state.dept_checks[region][dept] = False
                
    for col_name in ['Emplacement', 'Typologie', 'Extraction', 'Restauration']:
        if col_name in st.session_state.data.columns:
            for value in st.session_state.data[col_name].unique():
                st.session_state.other_checks.get(col_name, {})[value] = False

    # 8. Réinitialiser: réinitialiser les sliders
    if 'gla_min_max' in st.session_state:
        st.session_state.gla_range = st.session_state.gla_min_max
    if 'loyer_min_max' in st.session_state:
        st.session_state.loyer_range = st.session_state.loyer_min_max
    
    # 8. Réinitialiser: refermer le panneau droit
    st.session_state.selected_lot_key = None
    
    # 8. Réinitialiser: afficher tous les pins
    st.session_state.filtered_data = st.session_state.data.copy()
    
    st.rerun() # Relancer pour mettre à jour l'UI

# --- 6. RENDU DE LA SIDEBAR (VOLET GAUCHE) ---

def render_sidebar():
    """Affiche le logo et tous les filtres dans la sidebar."""
    
    # 3. Logo
    st.markdown(f'<div class="sidebar-logo"><img src="assets/Logo bleu crop.png" alt="Logo SMBG" style="width: 200px; height: auto;"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 8. Bouton Réinitialiser
    st.button("Réinitialiser les filtres", on_click=reset_filters)

    st.markdown("---")
    
    # --- 8.1 Filtres Région / Département imbriqués ---
    st.markdown("#### Région / Département")

    unique_regions = st.session_state.data['Région'].unique()
    
    # Initialisation des states si nécessaire
    if 'region_checks' not in st.session_state:
        st.session_state.region_checks = {r: False for r in unique_regions}
    if 'dept_checks' not in st.session_state:
        st.session_state.dept_checks = {}

    for region in unique_regions:
        # Checkbox Région
        st.session_state.region_checks[region] = st.checkbox(
            region, 
            value=st.session_state.region_checks.get(region, False), 
            key=f"region_check_{region}"
        )

        # Affichage des Départements si la Région est cochée
        if st.session_state.region_checks[region]:
            region_df = st.session_state.data[st.session_state.data['Région'] == region]
            unique_departments = region_df['Département'].unique()

            if region not in st.session_state.dept_checks:
                st.session_state.dept_checks[region] = {d: False for d in unique_departments}
            
            for dept in unique_departments:
                # Checkbox Département (avec indentation via CSS)
                st.session_state.dept_checks[region][dept] = st.checkbox(
                    dept, 
                    value=st.session_state.dept_checks[region].get(dept, False), 
                    key=f"dept_check_{region}_{dept}",
                    # Utilisation d'un sélecteur CSS spécifique pour l'indentation
                    help=f'<div class="department-checkbox"></div>'
                )
    
    st.markdown("---")
    
    # --- 8.2 Filtres Sliders ---
    
    # Surface GLA
    st.markdown("#### Surface GLA (m²)")
    if 'gla_min_max' in st.session_state:
        min_gla_all, max_gla_all = st.session_state.gla_min_max
        st.session_state.gla_range = st.slider(
            "Sélectionnez la plage",
            min_value=float(min_gla_all),
            max_value=float(max_gla_all),
            value=st.session_state.gla_range,
            key='gla_range_slider',
            label_visibility="collapsed"
        )
    
    # Loyer annuel
    st.markdown("#### Loyer annuel (€)")
    if 'loyer_min_max' in st.session_state:
        min_loyer_all, max_loyer_all = st.session_state.loyer_min_max
        st.session_state.loyer_range = st.slider(
            "Sélectionnez la plage",
            min_value=float(min_loyer_all),
            max_value=float(max_loyer_all),
            value=st.session_state.loyer_range,
            key='loyer_range_slider',
            label_visibility="collapsed"
        )
        
    st.markdown("---")

    # --- 8.3 Autres cases à cocher ---
    
    st.markdown("#### Autres Critères")
    
    if 'other_checks' not in st.session_state:
        st.session_state.other_checks = {}

    for col_name in ['Emplacement', 'Typologie', 'Extraction', 'Restauration']:
        if col_name in st.session_state.data.columns:
            st.markdown(f"**{col_name}**")
            unique_values = st.session_state.data[col_name].unique()
            
            if col_name not in st.session_state.other_checks:
                st.session_state.other_checks[col_name] = {v: False for v in unique_values}
                
            for value in unique_values:
                st.session_state.other_checks[col_name][value] = st.checkbox(
                    str(value),
                    value=st.session_state.other_checks[col_name].get(value, False),
                    key=f"other_check_{col_name}_{value}"
                )

    # Déclencher le filtrage après toutes les interactions
    filter_data()


# --- 7. RENDU DE LA CARTE (ZONE CENTRALE) ---

def create_folium_map():
    """Crée la carte Folium avec les pins personnalisés et la logique de clic."""
    df_map = st.session_state.filtered_data
    
    if df_map.empty:
        # Centre par défaut si aucune donnée filtrée
        m = folium.Map(location=[46.603354, 1.888334], zoom_start=6, control_scale=True)
    else:
        # Calculer le centre de la carte en fonction des lots filtrés
        center_lat = df_map['Latitude'].mean()
        center_lon = df_map['Longitude'].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=10, control_scale=True)
        # Ajuster le zoom pour contenir tous les points si trop peu de points
        if len(df_map) > 0:
             m.fit_bounds([[df_map['Latitude'].min(), df_map['Longitude'].min()], 
                           [df_map['Latitude'].max(), df_map['Longitude'].max()]])

    # 7. Pins sur la carte: ABSOLUMENT AUCUN POPUP, style personnalisé
    
    # Création du GeoJson pour gérer le clic sans popup
    geojson_data = {
        "type": "FeatureCollection",
        "features": []
    }

    for index, row in df_map.iterrows():
        lat, lon = row['Latitude'], row['Longitude']
        ref = row['Ref Formatée']
        lot_key = row['lot_key']

        # Utilisation d'un cercle (CircleMarker) pour le pin
        # J'ajoute le lot_key dans les propriétés pour le récupérer via st_folium
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat] 
            },
            "properties": {
                "lot_key": lot_key,
                "ref": ref
            }
        }
        geojson_data["features"].append(feature)

    # Style pour le CircleMarker (le cercle)
    def style_function(feature):
        return {
            'fillColor': SMBG_BLUE,
            'color': '#333333',  # Contour fin sombre
            'weight': 1,
            'fillOpacity': 0.8,
            'radius': 10  # Taille du cercle
        }

    # Style pour le hover (curseur main)
    highlight_function = lambda x: {'fillOpacity': 1, 'weight': 2, 'color': SMBG_COPPER}

    # GeoJson pour le marquage (le point cliquable)
    geojson_layer = folium.GeoJson(
        geojson_data,
        name="Lots",
        style_function=style_function,
        highlight_function=highlight_function,
        tooltip=False, # Désactiver le tooltip
        popup=False # Désactiver le popup
    ).add_to(m)

    # Ajout des marqueurs Textes (pour afficher la référence)
    for index, row in df_map.iterrows():
        lat, lon = row['Latitude'], row['Longitude']
        ref = row['Ref Formatée']

        # Utilisation d'un DivIcon pour afficher le texte au centre du cercle
        html = f"""
        <div style="
            font-family: Futura, {FONT_FALLBACK};
            color: white; 
            font-size: 10px; 
            font-weight: bold;
            line-height: 20px;
            text-align: center;
            width: 20px;
            height: 20px;
            pointer-events: none; /* Important pour laisser le clic passer au GeoJson */
        ">{ref}</div>
        """
        icon = folium.DivIcon(html=html, icon_size=(20, 20), icon_anchor=(10, 10))
        
        folium.Marker(
            location=[lat, lon],
            icon=icon,
            tooltip=False,
            popup=False
        ).add_to(m)

    return m, geojson_layer


# --- 8. RENDU DU PANNEAU DE DÉTAILS (VOLET DROIT) ---

def render_detail_panel():
    """Affiche le panneau de détails rétractable."""
    
    lot_key = st.session_state.selected_lot_key
    
    # Rendre le JS pour contrôler l'ouverture/fermeture du panneau
    if lot_key:
        js_update = f"<script>window.stPanelState = 'visible'; updatePanel();</script>"
        st.html(js_update)
        
        # Trouver le lot sélectionné
        selected_lot = st.session_state.data[st.session_state.data['lot_key'] == lot_key].iloc[0]
        
        # Début du conteneur HTML fixe (Volet C)
        st.markdown('<div id="detail-panel">', unsafe_allow_html=True)
        
        st.markdown("### Détails de l'annonce") # Titre
        st.markdown(f"#### Référence : {selected_lot['Ref Formatée']}")
        
        st.markdown("---")
        
        # --- 10. Contenu: Tableau des colonnes G à AL (simulées par DETAIL_COLUMNS_KEYS) ---
        for col_key in DETAIL_COLUMNS_KEYS:
            value = selected_lot.get(col_key)
            formatted_val = format_value(col_key, value)
            
            # 10. Règles d’affichage: Cacher complètement la ligne si la valeur est vide/néant/0...
            if formatted_val is not None:
                st.markdown(
                    f"""
                    <div class="detail-row">
                        <span class="detail-label">{col_key}</span>
                        <span class="detail-value">{formatted_val}</span>
                    </div>
                    """, unsafe_allow_html=True
                )
        
        st.markdown("---")
        
        # --- 10. Colonne H (Lien Google Maps) ---
        maps_url = selected_lot.get(MAPS_URL_COLUMN)
        
        if maps_url and format_value(MAPS_URL_COLUMN, maps_url) is not None:
            # Devient un bouton “Cliquer ici”, ouvre dans un nouvel onglet
            st.link_button(
                "Cliquer ici pour Google Maps", 
                url=maps_url, 
                help="Ouvre le lien Google Maps dans un nouvel onglet",
                type="primary", # Style par défaut, ajusté par le CSS
                key="google_maps_button"
            )
        else:
             st.markdown('<p style="font-style: italic; color: #aaa;">Lien Google Maps non disponible.</p>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
        
    else:
        # Fermer le panneau droit
        js_update = f"<script>window.stPanelState = 'hidden'; updatePanel();</script>"
        st.html(js_update)


# --- 9. LOGIQUE DE CLIC SUR LA CARTE ---

def handle_map_click(map_result):
    """Gère le clic sur la carte ou sur un pin."""
    
    if map_result and map_result.get('last_object_clicked'):
        # Clic sur un GeoJson Feature (Pin)
        clicked_data = map_result['last_object_clicked']
        
        # 7. Interaction: Clic sur pin → ouverture du panneau droit
        if 'properties' in clicked_data and 'lot_key' in clicked_data['properties']:
            lot_key = clicked_data['properties']['lot_key']
            st.session_state.selected_lot_key = lot_key
            st.rerun()
            return
            
    # 7. Interaction: Clic sur carte hors pin → fermeture du panneau droit
    # Cela est géré par la logique du clic sur la carte elle-même.
    # st_folium renvoie aussi les coordonnées du clic sur la carte.
    # Si on arrive ici et qu'un lot était sélectionné, on le ferme.
    if st.session_state.selected_lot_key:
        st.session_state.selected_lot_key = None
        st.rerun()


# --- 10. FONCTION PRINCIPALE DE L'APPLICATION ---

def main():
    # Configuration de la page (Streamlit configuration)
    st.set_page_config(
        page_title="SMBG Carte - Immobilier Commercial",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # --- 1. Injection du CSS critique pour le layout et le style ---
    inject_custom_css()

    # Le conteneur de la sidebar est géré par `st.sidebar`
    with st.sidebar:
        render_sidebar()
        
    # Le conteneur principal gère la carte
    # Je force la carte à prendre la place avec un div 100vh
    st.markdown('<div id="map_container">', unsafe_allow_html=True)
    
    # --- 7. Rendu de la Carte (Zone B) ---
    m, geojson_layer = create_folium_map()
    
    # Rendre la carte et récupérer l'état du clic
    map_result = st_folium(
        m, 
        width='100%', 
        height='100%', 
        key="smbg_map", 
        # Propriétés importantes pour le clic (éviter les popups)
        returned_objects=["last_object_clicked", "last_click"], 
        # Déclencher le JS pour gérer la fermeture du panneau au clic sur la carte
        # sans affecter la carte elle-même.
        js_callback="""
            function(e) { 
                if (e.last_click && !e.last_object_clicked) {
                    // Clic sur la carte (hors pin)
                    if (window.stPanelState === 'visible') {
                        // Simuler la fermeture du panneau via Streamlit
                        Streamlit.set
                        Streamlit.setComponentValue({
                            'action': 'close_panel' 
                        });
                        return 'close_panel_event';
                    }
                }
                return e; 
            }
        """
    )
    
    st.markdown('</div>', unsafe_allow_html=True)

    # --- 8. Rendu du Panneau de Détails (Zone C) ---
    # Le panneau est un élément en position fixe géré par HTML/CSS
    render_detail_panel()
    
    # --- 9. Post-traitement du clic sur la carte ---
    
    # 1. Traiter le clic sur un pin via 'last_object_clicked'
    if map_result and map_result.get('last_object_clicked'):
        # handle_map_click s'occupe de l'ouverture
        handle_map_click(map_result) 
        
    # 2. Traiter le clic de fermeture (clic sur la carte hors pin) via 'last_click' ou le callback JS
    # Si le callback JS a été déclenché, il envoie un objet spécial
    if map_result and map_result.get('action') == 'close_panel' and st.session_state.selected_lot_key:
        st.session_state.selected_lot_key = None
        st.rerun()


if __name__ == "__main__":
    main()

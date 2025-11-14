import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import numpy as np
import os
import base64
import re
import io

# --- 1. CONFIGURATION ET CONSTANTES ---

# Couleurs SMBG
BLUE_SMBG = "#05263d"
COPPER_SMBG = "#C67B42"
BG_COLOR = BLUE_SMBG # Couleur de fond pour les sidebars

# Chemins des assets (Simulés pour le déploiement sur Streamlit Cloud)
# En production réelle, ces fichiers doivent exister dans les dossiers spécifiés.
LOGO_PATH = "assets/Logo bleu crop.png"
DATA_FILE = "Liste des lots.xlsx - Tableau recherche.csv" # Utilisation du fichier uploade

# Configuration de la page Streamlit
st.set_page_config(
    page_title="SMBG Carte - Immobilier Commercial",
    layout="wide",
    initial_sidebar_state="expanded" # La sidebar gauche est toujours visible
)

# --- 2. FONCTIONS UTILITAIRES ---

# Fonction pour formater la référence annonce
def format_reference(ref):
    """Supprime les zéros non significatifs, conserve la partie décimale."""
    if pd.isna(ref) or ref == '':
        return ''
    
    # Assurez-vous que c'est une chaîne pour l'opération de recherche/remplacement
    ref_str = str(ref)

    # Si c'est un nombre décimal (ex: 0005.1)
    if '.' in ref_str:
        try:
            # Sépare partie entière et décimale
            parts = ref_str.split('.')
            entier = parts[0].lstrip('0') or '0'
            decimal = parts[1].rstrip('0') # Supprime les zéros non significatifs de la partie décimale
            if decimal:
                return f"{entier}.{decimal}"
            else:
                return entier
        except:
            return ref_str.lstrip('0') # Fallback
            
    # Si c'est un nombre entier (ex: 0003)
    else:
        return ref_str.lstrip('0') or '0' # Retourne '0' si la chaîne est vide après lstrip

# Fonction pour formater les valeurs monétaires
def format_currency(value):
    """Formate les nombres en € avec séparateur de milliers et arrondi."""
    if pd.isna(value) or value == 0 or str(value).strip() in ["néant", "-", "/", "0", ""]:
        return None
    try:
        # Convertir en float et arrondir si nécessaire (ou laisser en int si c'est un entier)
        if isinstance(value, str):
            value = float(re.sub(r'[^\d\.\,]', '', value.replace(',', '.')))
        
        # Arrondir à l'entier le plus proche
        rounded_value = int(round(value))
        
        # Utiliser la locale française pour le séparateur de milliers (espace insécable)
        return f"{rounded_value:,.0f} €".replace(",", " ")
    except:
        return str(value) # Retourne la valeur originale si le formatage échoue

# Fonction pour formater les surfaces
def format_surface(value):
    """Formate les surfaces en m²."""
    if pd.isna(value) or value == 0 or str(value).strip() in ["néant", "-", "/", "0", ""]:
        return None
    try:
        # Convertir en float et arrondir à l'entier le plus proche
        if isinstance(value, str):
            value = float(re.sub(r'[^\d\.\,]', '', value.replace(',', '.')))
        
        rounded_value = int(round(value))
        
        # Utiliser la locale française pour le séparateur de milliers (espace insécable)
        return f"{rounded_value:,.0f} m²".replace(",", " ")
    except:
        return str(value) # Retourne la valeur originale si le formatage échoue

# Fonction pour vérifier si une ligne doit être affichée dans le panneau de détails
def is_value_displayable(value):
    """Vérifie si la valeur est vide, 'néant', '-', '/', '0' (texte ou nombre)"""
    if pd.isna(value):
        return False
    value_str = str(value).strip().lower()
    if value_str in ["", "néant", "-", "/", "0"]:
        return False
    try:
        # Vérifie si c'est un zéro numérique
        if float(value) == 0.0:
            return False
    except ValueError:
        pass # Pas un nombre, on continue
    return True

# --- 3. CHARGEMENT ET PRÉPARATION DES DONNÉES ---

@st.cache_data
def load_data():
    # Le fichier CSV est chargé via l'API, nous le lisons directement
    try:
        # Assurez-vous d'utiliser le nom du fichier correct
        df = pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        st.error(f"Erreur : Le fichier de données '{DATA_FILE}' n'a pas été trouvé. Assurez-vous qu'il se trouve dans le dossier 'data/'.")
        # Création d'un DataFrame vide de secours
        df = pd.DataFrame(columns=[
            'Référence annonce', 'Région', 'Département', 'Ville', 'Adresse', 'Surface GLA',
            'Loyer annuel', 'Charges', 'Taxe foncière', 'Honoraires', 'Emplacement',
            'Typologie', 'Extraction', 'Restauration', 'Latitude', 'Longitude', 'Actif', 'Lien Google Maps'
        ])
        return df

    # Nettoyage des noms de colonnes : supprime les espaces, les accents, met en minuscules
    df.columns = df.columns.str.strip()
    
    # Renommage des colonnes pour la manipulation interne, en conservant les noms affichables
    column_mapping = {
        'Référence annonce': 'Ref_Annonce',
        'Lien Google Maps': 'Lien_GMaps',
        'Surface GLA': 'Surface_GLA',
        'Loyer annuel': 'Loyer_Annuel',
        'Charges annuelles': 'Charges_Annuelles', # C'est le nom dans le CSV
        'Taxe foncière': 'Taxe_Fonciere',
        'Emplacement': 'Emplacement',
        'Typologie': 'Typologie',
        'Extraction': 'Extraction',
        'Restauration': 'Restauration',
        'Latitude': 'Latitude',
        'Longitude': 'Longitude',
        'Actif': 'Actif',
        'Région': 'Region',
        'Département': 'Departement',
        # On va aussi utiliser les Honoraires (colonne AL dans la description, 'Honoraires' dans le CSV)
        'Honoraires': 'Honoraires',
    }

    # Inverse mapping pour l'affichage des détails (colonnes G à AL, sauf H)
    # Les colonnes à afficher dans le panneau droit (selon le CSV fourni)
    detail_columns = {
        'Region': 'Région',
        'Departement': 'Département',
        'Adresse': 'Adresse Complète',
        'Surface_GLA': 'Surface GLA',
        'Répartition surface GLA': 'Répartition Surface GLA',
        'Surface utile': 'Surface Utile',
        'Répartition surface utile': 'Répartition Surface Utile',
        'Loyer_Annuel': 'Loyer Annuel',
        'Loyer Mensuel': 'Loyer Mensuel',
        'Loyer €/m²': 'Loyer €/m²',
        'Loyer variable': 'Loyer Variable',
        'Charges_Annuelles': 'Charges Annuelles',
        'Charges Mensuelles': 'Charges Mensuelles',
        'Charges €/m²': 'Charges €/m²',
        'Taxe_Fonciere': 'Taxe Foncière',
        'Taxe foncière €/m²': 'Taxe Foncière €/m²',
        'Marketing': 'Marketing Annuel',
        'Marketing €/m²': 'Marketing €/m²',
        'Total (L+C+M)': 'Total (Loyer + Charges + Marketing)',
        'Dépôt de garantie': 'Dépôt de Garantie',
        'GAPD': 'GAPD',
        'Gestion': 'Gestion',
        'Etat de livraison': 'État de Livraison',
        'Extraction': 'Extraction',
        'Restauration': 'Restauration',
        'Environnement Commercial': 'Environnement Commercial',
        'Commentaires': 'Commentaires',
        'Honoraires': 'Honoraires',
        # La colonne H 'Lien Google Maps' est spéciale (Lien_GMaps)
    }

    df = df.rename(columns=column_mapping)
    df = df.rename(columns={'Lien Google Maps': 'Lien_GMaps'}) # On s'assure que le lien est bien nommé
    
    # Filtrer uniquement les lots 'Actif'
    df = df[df['Actif'].astype(str).str.lower().str.strip() == 'oui'].copy()
    
    # S'assurer que les colonnes clés sont présentes et nettoyer les NaNs
    df = df.dropna(subset=['Latitude', 'Longitude', 'Ref_Annonce'])
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    
    # Appliquer le formatage de référence une fois
    df['Ref_Format'] = df['Ref_Annonce'].apply(format_reference)

    # Convertir les colonnes de filtrage en chaînes pour éviter les erreurs de type
    for col in ['Region', 'Departement', 'Emplacement', 'Typologie', 'Extraction', 'Restauration']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df, detail_columns

# Charger les données
df_data, DETAIL_COLUMNS_MAPPING = load_data()

# Définir l'état initial des filtres pour le bouton Réinitialiser
if 'filters' not in st.session_state:
    st.session_state.filters = {
        'selected_regions': set(df_data['Region'].unique()),
        'selected_departments': set(df_data['Departement'].unique()),
        'surface_range': (df_data['Surface_GLA'].min(), df_data['Surface_GLA'].max()),
        'loyer_range': (df_data['Loyer_Annuel'].min(), df_data['Loyer_Annuel'].max()),
        'emplacement': set(df_data['Emplacement'].unique()),
        'typologie': set(df_data['Typologie'].unique()),
        'extraction': set(df_data['Extraction'].unique()),
        'restauration': set(df_data['Restauration'].unique()),
        'selected_lot_ref': None, # Réf. du lot sélectionné pour le panneau droit
        'show_detail_panel': False # État du panneau droit
    }

# Fonction de réinitialisation complète
def reset_filters():
    """Réinitialise tous les filtres à l'état initial (tout sélectionné/min-max) et ferme le panneau."""
    st.session_state.filters = {
        'selected_regions': set(df_data['Region'].unique()),
        'selected_departments': set(df_data['Departement'].unique()),
        'surface_range': (df_data['Surface_GLA'].min(), df_data['Surface_GLA'].max()),
        'loyer_range': (df_data['Loyer_Annuel'].min(), df_data['Loyer_Annuel'].max()),
        'emplacement': set(df_data['Emplacement'].unique()),
        'typologie': set(df_data['Typologie'].unique()),
        'extraction': set(df_data['Extraction'].unique()),
        'restauration': set(df_data['Restauration'].unique()),
        'selected_lot_ref': None,
        'show_detail_panel': False
    }

# --- 4. CSS PERSONNALISÉ ET IDENTITÉ VISUELLE ---

# Fonction pour charger les assets en base64 (nécessaire pour CSS)
def get_base64_of_bin_file(bin_file):
    if not os.path.exists(bin_file):
        return None
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Simuler l'intégration des polices Futura (remplacez par vos fichiers .ttf réels)
# Pour une démo fonctionnelle sans les fichiers, j'utilise une font-family de secours,
# mais le code montre la méthode correcte (@font-face)
# NOTE: Streamlit Cloud peut avoir des difficultés avec les font-face custom.
# J'utilise des noms de fichiers génériques comme demandé dans le cahier des charges.

futura_light_b64 = get_base64_of_bin_file("assets/futura_light.ttf")
futura_medium_b64 = get_base64_of_bin_file("assets/futura_medium.ttf")
futura_bold_b64 = get_base64_of_bin_file("assets/futura_bold.ttf")

if futura_light_b64:
    font_face_css = f"""
    @font-face {{
        font-family: 'Futura';
        src: url(data:font/ttf;charset=utf-8;base64,{futura_light_b64}) format('truetype');
        font-weight: 300;
        font-style: normal;
    }}
    @font-face {{
        font-family: 'Futura';
        src: url(data:font/ttf;charset=utf-8;base64,{futura_medium_b64}) format('truetype');
        font-weight: 500;
        font-style: normal;
    }}
    @font-face {{
        font-family: 'Futura';
        src: url(data:font/ttf;charset=utf-8;base64,{futura_bold_b64}) format('truetype');
        font-weight: 700;
        font-style: normal;
    }}
    """
else:
    # Fallback pour la démo si les fichiers .ttf ne sont pas présents
    font_face_css = ""

# CSS CRITIQUE pour le layout et le style
critical_css = f"""
{font_face_css}

/* 3. Identité visuelle et 4. Layout Général (CRITIQUE) */
:root {{
    --smbg-blue: {BLUE_SMBG};
    --smbg-copper: {COPPER_SMBG};
}}

/* Appliquer la police Futura à toute l'application */
html, body, [class*="st-"] {{
    font-family: Futura, "Futura PT", "Century Gothic", Arial, sans-serif !important;
}}

/* 11. Comportement général: Supprimer le scroll global et définir la hauteur à 100vh */
html, body, .main, .block-container, #root, [data-testid="stAppViewContainer"] {{
    height: 100vh !important;
    overflow: hidden !important;
    padding: 0 !important;
    margin: 0 !important;
}}

/* A. Volet gauche (sidebar) */
[data-testid="stSidebar"] {{
    width: 275px !important;
    min-width: 275px !important;
    max-width: 275px !important;
    background-color: var(--smbg-blue) !important;
    transition: none !important; /* Aucun bouton de collapse, toujours visible */
}}

/* Cacher le bouton de collapse de la sidebar gauche (même si elle est 'expanded') */
[data-testid="stSidebarContent"] > button {{
    display: none !important;
}}

/* B. Zone centrale : la carte (Contenu principal) */
[data-testid="stVerticalBlock"] {{
    height: 100%;
}}

.st-emotion-cache-1cypcdp {{ /* Le conteneur qui contient la carte */
    height: 100% !important;
    min-height: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}}

/* Ajuster le container de la carte (folium_static) pour qu'il prenne 100% de l'espace disponible */
.streamlit-container {{
    height: 100vh !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
}}

.folium-map {{
    height: 100vh !important;
    width: 100% !important;
    border: none !important;
    margin: 0 !important;
}}

/* 4. Layout général: C. Volet droit (panneau de détails) */
/* Création du panneau de détails rétractable */
.detail-panel {{
    position: fixed;
    top: 0;
    right: 0;
    width: 275px;
    height: 100vh;
    background-color: var(--smbg-blue);
    color: white;
    box-shadow: -5px 0 15px rgba(0,0,0,0.5);
    transition: transform 0.3s ease-in-out;
    padding: 20px;
    overflow-y: auto; /* Scroll possible dans ce volet si besoin */
    z-index: 9999;
}}
.detail-panel.collapsed {{
    transform: translateX(275px); /* Masqué par défaut */
}}
.detail-panel.expanded {{
    transform: translateX(0); /* Visible */
}}

/* Style du logo dans la sidebar */
.logo-container {{
    padding-top: 25px; /* Marge haute: environ 25 px */
    padding-bottom: 25px;
    display: flex;
    justify-content: center;
    align-items: center;
}}
.logo-container img {{
    max-width: 90%;
    height: auto;
    /* 12. Ce que je ne veux JAMAIS: Aucun bouton d’agrandissement du logo */
    pointer-events: none; 
    user-select: none;
}}

/* Style des titres et labels de la sidebar (bleu SMBG, texte blanc) */
[data-testid="stSidebarContent"] label,
[data-testid="stSidebarContent"] .st-b5,
[data-testid="stSidebarContent"] h2 {{
    color: white !important;
}}

/* Style des labels dans le panneau de détails (Cuivre SMBG) */
.detail-panel .detail-label {{
    color: var(--smbg-copper);
    font-weight: 500;
    margin-right: 5px;
}}

.detail-panel h3 {{
    color: white;
    font-weight: 700;
    margin-bottom: 20px;
    text-align: center;
}}

/* Style du bouton "Cliquer ici" */
.gmaps-button button {{
    background-color: var(--smbg-copper) !important;
    color: var(--smbg-blue) !important;
    border: none !important;
    border-radius: 5px !important;
    padding: 8px 15px !important;
    font-weight: bold !important;
    margin-top: 10px;
    width: 100%;
}}

/* Indentation des départements (9. Logique de filtrage) */
.department-checkbox {{
    padding-left: 15px; /* Décalage de 15 px (indentation) */
}}

/* Style pour le bouton Réinitialiser */
#reset-button button {{
    background-color: #f4f4f4;
    color: var(--smbg-blue);
    border: 1px solid var(--smbg-blue);
}}

/* Masquer les radio/dropdown/selectbox (12. Ce que je ne veux JAMAIS) */
.stRadio, .stSelectbox, .stMultiselect {{
    display: none !important;
}}

"""
st.markdown(f"<style>{critical_css}</style>", unsafe_allow_html=True)

# --- 5. LOGIQUE DE FILTRAGE ---

def apply_filters(df):
    """Applique tous les filtres actifs à la DataFrame."""
    filtered_df = df.copy()

    # 1. Filtres Région / Département
    # Logique : Région cochée + aucun département cochée -> tous les lots de cette région
    # Région cochée + certains départements cochés -> uniquement ces départements
    
    selected_regions_filter = st.session_state.filters['selected_regions']
    selected_deps_filter = st.session_state.filters['selected_departments']
    
    # 9. Logique de filtrage Région / Département:
    # Crée l'ensemble des départements dont la région parente est sélectionnée
    # Si AUCUN département n'est coché DANS la région, TOUS les départements de cette région sont inclus.
    
    # Étape 1: Identifier les régions cochées
    regions_df = filtered_df[['Region', 'Departement']].drop_duplicates()
    
    # Étape 2: Identifier les régions où AUCUN département spécifique n'est coché
    regions_with_no_specific_dep_selection = []
    
    for region in selected_regions_filter:
        # Départements de cette région
        deps_in_region = set(regions_df[regions_df['Region'] == region]['Departement'].unique())
        
        # Intersection entre les départements cochés et les départements de cette région
        # Si l'intersection est vide, cela signifie qu'aucun département de cette région n'a été spécifiquement coché.
        if not (deps_in_region.intersection(selected_deps_filter)):
            regions_with_no_specific_dep_selection.append(region)

    
    # Étape 3: Créer la liste finale des départements autorisés
    final_allowed_deps = set()
    
    # Inclure tous les départements spécifiquement cochés (dans toutes les régions)
    final_allowed_deps.update(selected_deps_filter)
    
    # Pour les régions où aucun département spécifique n'est coché, inclure TOUS leurs départements
    for region in regions_with_no_specific_dep_selection:
        deps_to_add = set(regions_df[regions_df['Region'] == region]['Departement'].unique())
        final_allowed_deps.update(deps_to_add)

    # Appliquer le filtre Région/Département: le lot doit être dans la liste des départements autorisés
    filtered_df = filtered_df[filtered_df['Departement'].isin(final_allowed_deps)]

    # 2. Filtres Sliders (Surface GLA et Loyer annuel)
    min_surface, max_surface = st.session_state.filters['surface_range']
    min_loyer, max_loyer = st.session_state.filters['loyer_range']

    filtered_df = filtered_df[
        (filtered_df['Surface_GLA'] >= min_surface) & (filtered_df['Surface_GLA'] <= max_surface)
    ]
    
    filtered_df = filtered_df[
        (filtered_df['Loyer_Annuel'] >= min_loyer) & (filtered_df['Loyer_Annuel'] <= max_loyer)
    ]

    # 3. Autres filtres cases à cocher (Emplacement, Typologie, Extraction, Restauration)
    for filter_col in ['Emplacement', 'Typologie', 'Extraction', 'Restauration']:
        if filter_col in filtered_df.columns:
            selected_options = st.session_state.filters[filter_col.lower()]
            # Le lot doit avoir une valeur de la colonne qui est dans les options sélectionnées
            filtered_df = filtered_df[filtered_df[filter_col].isin(selected_options)]
            
    return filtered_df

# --- 6. GESTION DES CLICS SUR LA CARTE (Panneau de Détails) ---

# Callback pour ouvrir le panneau de détails
def open_detail_panel(lot_ref):
    st.session_state.filters['selected_lot_ref'] = lot_ref
    st.session_state.filters['show_detail_panel'] = True

# Callback pour fermer le panneau de détails
def close_detail_panel():
    st.session_state.filters['selected_lot_ref'] = None
    st.session_state.filters['show_detail_panel'] = False

# --- 7. VOLET GAUCHE (SIDEBAR) ---

with st.sidebar:
    # 3. Identité visuelle: Logo
    if os.path.exists(LOGO_PATH):
        st.markdown(f"""
            <div class="logo-container">
                <img src="data:image/png;base64,{get_base64_of_bin_file(LOGO_PATH)}" alt="Logo SMBG" />
            </div>
        """, unsafe_allow_html=True)
    else:
        # Fallback si le logo n'est pas disponible localement
        st.markdown(f"<div class='logo-container' style='color: white; font-size: 24px; font-weight: bold;'>SMBG Carte</div>", unsafe_allow_html=True)

    # Bouton Réinitialiser (9. Logique de filtrage)
    st.markdown('<div id="reset-button">', unsafe_allow_html=True)
    st.button("Réinitialiser les filtres", on_click=reset_filters)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---", unsafe_allow_html=True)

    # 8. Filtres
    
    # 1. Région / Département imbriqués
    st.markdown("<h2>Filtres Géographiques</h2>", unsafe_allow_html=True)

    unique_regions = sorted(df_data['Region'].unique().tolist())
    
    # Initialisation de l'état des régions
    initial_regions = st.session_state.filters['selected_regions']
    
    # Dictionnaire pour stocker l'état des régions cochées
    region_check_states = {}

    for region in unique_regions:
        is_checked = region in initial_regions
        
        # Utilisation de st.checkbox avec une clé pour lier l'état à la session
        checkbox_key = f"region_{region}"
        region_check_states[region] = st.checkbox(
            label=region,
            value=is_checked,
            key=checkbox_key
        )
        
        # Mettre à jour l'état de la région
        if region_check_states[region]:
            st.session_state.filters['selected_regions'].add(region)
        elif region in st.session_state.filters['selected_regions']:
            st.session_state.filters['selected_regions'].remove(region)

        # Si la région est cochée, afficher les départements (indentation)
        if region_check_states[region]:
            departments_in_region = sorted(df_data[df_data['Region'] == region]['Departement'].unique().tolist())
            
            # Initialisation de l'état des départements (tous les départements sont sélectionnés par défaut)
            initial_deps = st.session_state.filters['selected_departments']
            
            for dep in departments_in_region:
                is_dep_checked = dep in initial_deps
                
                # Le label du département est affiché avec l'indentation
                st.markdown(f'<div class="department-checkbox">', unsafe_allow_html=True)
                
                dep_checkbox_key = f"dep_{dep}"
                dep_checked = st.checkbox(
                    label=dep,
                    value=is_dep_checked,
                    key=dep_checkbox_key
                )
                
                # Mettre à jour l'état du département
                if dep_checked:
                    st.session_state.filters['selected_departments'].add(dep)
                elif dep in st.session_state.filters['selected_departments']:
                    st.session_state.filters['selected_departments'].remove(dep)
                
                st.markdown('</div>', unsafe_allow_html=True)

    # Mise à jour des régions/départements cochés avant l'application des autres filtres
    # La logique de st.session_state permet de gérer cela correctement après chaque interaction.

    # --- 2. Sliders ---
    st.markdown("<h2>Filtres Numériques</h2>", unsafe_allow_html=True)
    
    # Surface GLA
    gla_min = df_data['Surface_GLA'].min()
    gla_max = df_data['Surface_GLA'].max()
    
    # Utiliser les valeurs de session pour l'état initial/actuel du slider
    initial_gla_range = st.session_state.filters['surface_range']
    
    new_gla_range = st.slider(
        "Surface GLA (m²)",
        min_value=float(gla_min),
        max_value=float(gla_max),
        value=initial_gla_range,
        step=1.0,
        key="surface_slider"
    )
    if new_gla_range != st.session_state.filters['surface_range']:
        st.session_state.filters['surface_range'] = new_gla_range

    # Loyer annuel
    loyer_min = df_data['Loyer_Annuel'].min()
    loyer_max = df_data['Loyer_Annuel'].max()
    
    # Utiliser les valeurs de session pour l'état initial/actuel du slider
    initial_loyer_range = st.session_state.filters['loyer_range']

    new_loyer_range = st.slider(
        "Loyer annuel (€)",
        min_value=float(loyer_min),
        max_value=float(loyer_max),
        value=initial_loyer_range,
        step=1000.0,
        key="loyer_slider",
        format="%i €"
    )
    if new_loyer_range != st.session_state.filters['loyer_range']:
        st.session_state.filters['loyer_range'] = new_loyer_range

    # --- 3. Autres cases à cocher ---
    st.markdown("<h2>Filtres Thématiques</h2>", unsafe_allow_html=True)
    
    checkbox_filters = ['Emplacement', 'Typologie', 'Extraction', 'Restauration']
    
    for filter_col in checkbox_filters:
        unique_options = sorted(df_data[filter_col].unique().tolist())
        st.markdown(f"**{filter_col}**", unsafe_allow_html=True)
        
        initial_options = st.session_state.filters[filter_col.lower()]
        
        for option in unique_options:
            checkbox_key = f"{filter_col.lower()}_{option.replace(' ', '_')}"
            is_checked = option in initial_options
            
            checked = st.checkbox(
                label=option,
                value=is_checked,
                key=checkbox_key
            )
            
            # Mise à jour de l'état
            if checked:
                if option not in st.session_state.filters[filter_col.lower()]:
                    st.session_state.filters[filter_col.lower()].add(option)
            else:
                if option in st.session_state.filters[filter_col.lower()]:
                    st.session_state.filters[filter_col.lower()].remove(option)

# --- 8. APPLICATION DES FILTRES ET PRÉPARATION DE LA CARTE ---

filtered_data = apply_filters(df_data)

# Calculer le centre de la carte
if not filtered_data.empty:
    center_lat = filtered_data['Latitude'].mean()
    center_lon = filtered_data['Longitude'].mean()
    zoom_start = 6
else:
    # Position par défaut si aucun lot n'est affiché (France)
    center_lat = 46.603354
    center_lon = 1.888334
    zoom_start = 5

# --- 9. ZONE CENTRALE : LA CARTE ---

# Création de la carte Folium (fond OpenStreetMap Mapnik par défaut)
m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=zoom_start,
    control_scale=True,
    # S'assurer que la carte prend bien toute la hauteur restante
    height="100%",
    width="100%",
    tiles='OpenStreetMap' # OpenStreetMap Mapnik est le fond par défaut
)

# Style du pin (Marker personnalisé avec Leaflet DivIcon pour le texte et le style)
for index, row in filtered_data.iterrows():
    ref = row['Ref_Format']
    lat = row['Latitude']
    lon = row['Longitude']
    lot_ref_annonce = row['Ref_Annonce']

    # 7. Pins sur la carte: Style du pin
    html = f"""
    <div style="
        background-color: {BLUE_SMBG};
        color: white;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        border: 2px solid black; /* Contour fin sombre */
        text-align: center;
        line-height: 26px; /* Ajusté pour centrer le texte */
        font-weight: bold;
        font-size: 10px;
        cursor: pointer; /* Curseur devient une main (pointer) au survol */
        box-shadow: 0 0 5px rgba(0,0,0,0.5);
    " onclick="
        // 7. Pins sur la carte: Interaction
        // Au clic, envoie un message à Streamlit pour déclencher le callback
        var event = new CustomEvent('lot_clicked', {{ detail: '{lot_ref_annonce}' }});
        window.parent.document.dispatchEvent(event);
    ">{ref}</div>
    """
    
    # Création de l'icône Leaflet DivIcon
    icon = folium.features.DivIcon(
        icon_size=(30, 30),
        icon_anchor=(15, 15), # Centre le pin
        html=html
    )

    # Ajout du marqueur sans popup ni tooltip
    folium.Marker(
        [lat, lon],
        icon=icon,
        tooltip=None, # ABSOLUMENT AUCUN POPUP : pas de tooltip
        popup=None    # ABSOLUMENT AUCUN POPUP : pas de popup Leaflet
    ).add_to(m)

# Ajouter une couche de clic invisible pour fermer le panneau de détails
# On utilise le plugin MousePosition pour intercepter un clic sur la carte elle-même
# Puis on utilise JS pour envoyer un message à Streamlit
# NOTE: Cette implémentation nécessite l'utilisation d'une extension JS dans Streamlit/Folium,
# ce qui n'est pas directement supporté par st.button(). On utilisera un hack JS pour cela.

# HTML/JS pour gérer le clic sur la carte et le clic sur le pin
# Le code JS est injecté dans l'application pour gérer les événements de clic.
js_injection = f"""
<script>
    // Événement pour gérer le clic sur un pin (déclenché depuis le DivIcon)
    window.parent.document.addEventListener('lot_clicked', function(e) {{
        // Envoie un message de retour à Streamlit avec la référence du lot
        var msg = {{
            type: 'streamlit:setComponentValue',
            componentName: 'lot_click_handler',
            value: e.detail
        }};
        window.parent.postMessage(msg, '*');
    }});

    // Événement pour gérer le clic sur la carte (hors pin)
    // On doit cibler le conteneur principal de la carte
    window.onload = function() {{
        var mapContainer = window.parent.document.querySelector('.folium-map');
        if (mapContainer) {{
            mapContainer.addEventListener('click', function(e) {{
                // Vérifie si l'élément cliqué n'est pas un pin (DivIcon)
                // Si l'élément cliqué ou un de ses parents n'a pas la classe 'leaflet-marker-icon'
                let isPinClick = false;
                let target = e.target;
                while (target) {{
                    if (target.classList && target.classList.contains('leaflet-marker-icon')) {{
                        isPinClick = true;
                        break;
                    }}
                    target = target.parentNode;
                }}

                if (!isPinClick) {{
                    // Envoie un message de retour à Streamlit pour fermer le panneau
                    var msg = {{
                        type: 'streamlit:setComponentValue',
                        componentName: 'map_click_handler',
                        value: 'map_clicked'
                    }};
                    window.parent.postMessage(msg, '*');
                }}
            }});
        }}
    }}
</script>
"""
st.markdown(js_injection, unsafe_allow_html=True)

# Affichage de la carte
folium_static(m, width=9999, height=9999) # Largeurs exagérées pour forcer le plein écran

# --- 10. GESTION DES ÉVÉNEMENTS FOLIUM/JS ---

# Placeholder pour le gestionnaire de clic de pin
# Simuler l'interaction avec un composant personnalisé (même si c'est un hack)
lot_clicked_ref = st.empty().text_input("lot_click_handler", key="lot_click_handler_key", label="hidden_lot_click", max_chars=0)
map_clicked_state = st.empty().text_input("map_click_handler", key="map_click_handler_key", label="hidden_map_click", max_chars=0)

# Masquer les inputs de gestion des clics
st.markdown("""
<style>
[data-testid="stTextInput"] { display: none; }
</style>
""", unsafe_allow_html=True)


# Logique de gestion de clic
if lot_clicked_ref and lot_clicked_ref != st.session_state.get('last_clicked_ref'):
    # Clic sur un Pin
    open_detail_panel(lot_clicked_ref)
    st.session_state['last_clicked_ref'] = lot_clicked_ref
    # Réinitialise la valeur de l'input pour permettre le clic suivant sur le même lot
    st.session_state.lot_click_handler_key = ""

if map_clicked_state and map_clicked_state != st.session_state.get('last_map_clicked'):
    # Clic sur la Carte (hors pin)
    close_detail_panel()
    st.session_state['last_map_clicked'] = map_clicked_state
    # Réinitialise la valeur de l'input
    st.session_state.map_click_handler_key = ""

# --- 11. VOLET DROIT (PANNEAU DE DÉTAILS) ---

# Déterminer la classe CSS (collapsed ou expanded)
panel_class = "expanded" if st.session_state.filters['show_detail_panel'] else "collapsed"

# Contenu du panneau
panel_content = ""

if st.session_state.filters['selected_lot_ref']:
    ref = st.session_state.filters['selected_lot_ref']
    lot_data = df_data[df_data['Ref_Annonce'] == ref].iloc[0]
    
    panel_content += f"<h3>Détails de l'annonce</h3>"
    
    # Référence annonce (formatée)
    panel_content += f"<p style='text-align: center; font-size: 1.2em; font-weight: bold; color: {COPPER_SMBG}; margin-bottom: 25px;'>Réf. {lot_data['Ref_Format']}</p>"

    # Tableau des détails
    table_html = "<table style='width: 100%; border-collapse: collapse; font-size: 0.9em;'>"
    
    # Les colonnes à afficher (selon DETAIL_COLUMNS_MAPPING)
    for col_internal, col_display in DETAIL_COLUMNS_MAPPING.items():
        value = lot_data.get(col_internal)
        
        # 10. Règles d’affichage: Cacher complètement la ligne si la valeur est non affichable
        if not is_value_displayable(value):
            continue

        # Formatage
        formatted_value = value
        
        if 'Loyer' in col_display or 'Charges' in col_display or 'Taxe' in col_display or 'Total' in col_display or 'Dépôt' in col_display or 'GAPD' in col_display or 'Gestion' in col_display or 'Honoraires' in col_display:
            # Valeurs en €
            formatted_value = format_currency(value)
        elif 'Surface' in col_display and 'Répartition' not in col_display:
            # Surfaces (sauf répartition)
            formatted_value = format_surface(value)

        # Si le formatage retourne None, cela signifie que la valeur n'est pas affichable (0, néant, etc.)
        if formatted_value is None:
            continue

        table_html += f"""
        <tr>
            <td class='detail-label' style='padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.1);'>{col_display}:</td>
            <td style='padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: right;'>{formatted_value}</td>
        </tr>
        """
    
    table_html += "</table>"
    panel_content += table_html

    # Colonne H (Lien Google Maps)
    gmaps_link = lot_data.get('Lien_GMaps')
    if is_value_displayable(gmaps_link):
        panel_content += f"""
        <div class="gmaps-button">
            <a href="{gmaps_link}" target="_blank" style="text-decoration: none;">
                <button>Cliquer ici pour Google Maps</button>
            </a>
        </div>
        """
    
    panel_content = f"<div class='detail-panel {panel_class}'>{panel_content}</div>"
else:
    # Panneau replié sans contenu
    panel_content = f"<div class='detail-panel {panel_class}'></div>"

# Affichage du panneau de détails via markdown (position fixed)
st.markdown(panel_content, unsafe_allow_html=True)

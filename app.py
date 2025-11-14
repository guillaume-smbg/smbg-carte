import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import numpy as np
import os
import base64
import re
import io
import unicodedata

# --- 1. CONFIGURATION ET CONSTANTES ---

# Couleurs SMBG
BLUE_SMBG = "#05263d"
COPPER_SMBG = "#C67B42"
BG_COLOR = BLUE_SMBG # Couleur de fond pour les sidebars

# Chemins des assets (Simulés pour le déploiement sur Streamlit Cloud)
LOGO_PATH = "assets/Logo bleu crop.png"
# CORRECTION: Utilisation du chemin conforme au cahier des charges /data/
DATA_FILE_PATH = "data/Liste des lots.xlsx - Tableau recherche.csv" 

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
            # Conserver toute la partie décimale, sans rstrip pour la cohérence
            decimal = parts[1] 
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
    if pd.isna(value) or value == 0 or str(value).strip().lower() in ["néant", "-", "/", "0", "0.0", ""]:
        return None
    try:
        # Tenter de convertir en nombre (gestion des strings avec virgule)
        if isinstance(value, str):
            # Nettoyage des caractères non numériques avant de tenter la conversion
            clean_value = re.sub(r'[^\d\.\,]', '', value).replace(',', '.')
            value = float(clean_value)
        
        # Arrondir à l'entier le plus proche
        rounded_value = int(round(value))
        
        # Utiliser la locale française pour le séparateur de milliers (espace)
        return f"{rounded_value:,.0f} €".replace(",", " ")
    except:
        return str(value) # Retourne la valeur originale si le formatage échoue

# Fonction pour formater les surfaces
def format_surface(value):
    """Formate les surfaces en m²."""
    if pd.isna(value) or value == 0 or str(value).strip().lower() in ["néant", "-", "/", "0", "0.0", ""]:
        return None
    try:
        # Tenter de convertir en nombre
        if isinstance(value, str):
            clean_value = re.sub(r'[^\d\.\,]', '', value).replace(',', '.')
            value = float(clean_value)
        
        rounded_value = int(round(value))
        
        # Utiliser la locale française pour le séparateur de milliers (espace)
        return f"{rounded_value:,.0f} m²".replace(",", " ")
    except:
        return str(value) # Retourne la valeur originale si le formatage échoue

# Fonction pour vérifier si une ligne doit être affichée dans le panneau de détails
def is_value_displayable(value):
    """Vérifie si la valeur est vide, 'néant', '-', '/', '0' (texte ou nombre)"""
    if pd.isna(value):
        return False
    value_str = str(value).strip().lower()
    if value_str in ["", "néant", "-", "/", "0", "0.0"]:
        return False
    try:
        # Vérifie si c'est un zéro numérique après conversion
        if float(re.sub(r'[^\d\.\,]', '', value_str).replace(',', '.')) == 0.0:
             return False
    except ValueError:
        pass # Pas un nombre, on continue
    return True

# Fonction pour normaliser les noms de colonnes
def normalize_column_name(col_name):
    """
    Normalise les noms de colonnes: supprime les accents, les espaces, 
    met en minuscule.
    Ex: "Référence annonce" -> "reference_annonce"
    """
    col_name = str(col_name).strip().lower()
    # Supprimer les accents
    col_name = unicodedata.normalize('NFKD', col_name).encode('ascii', 'ignore').decode('utf-8')
    # Remplacer les espaces et autres caractères non alphanumériques par '_'
    col_name = re.sub(r'[^a-z0-9]+', '_', col_name)
    return col_name.strip('_')


# --- 3. CHARGEMENT ET PRÉPARATION DES DONNÉES ---

@st.cache_data
def load_data():
    
    df = pd.DataFrame()
    
    # 1. Tenter de lire le fichier
    try:
        # Essayer avec le séparateur standard (virgule)
        df = pd.read_csv(DATA_FILE_PATH, sep=',', encoding='utf-8')
    except Exception:
        try:
            # Essayer avec le séparateur point-virgule (courant en France)
            df = pd.read_csv(DATA_FILE_PATH, sep=';', encoding='utf-8')
        except FileNotFoundError:
            st.error(f"Erreur : Le fichier de données '{DATA_FILE_PATH}' n'a pas été trouvé. Veuillez vérifier le chemin et le nom du fichier.")
            # Création d'un DataFrame vide de secours
            return pd.DataFrame(), {}
        except Exception as e:
            st.error(f"Erreur lors de la lecture du fichier de données CSV: {e}")
            return pd.DataFrame(), {}

    if df.empty:
        return pd.DataFrame(), {}
    
    # 2. Normalisation des noms de colonnes (CRITIQUE pour le KeyError)
    original_cols = {col: normalize_column_name(col) for col in df.columns}
    df.columns = original_cols.values()
    
    # 3. Définition des mappings internes et d'affichage
    
    # Mapping des noms normalisés aux noms d'affichage désirés
    # Ces noms internes DOIVENT correspondre aux noms normalisés dans le DF
    INTERNAL_COLUMNS_MAP = {
        'reference_annonce': 'Ref_Annonce',
        'lien_google_maps': 'Lien_GMaps',
        'surface_gla': 'Surface_GLA',
        'loyer_annuel': 'Loyer_Annuel',
        'charges_annuelles': 'Charges_Annuelles',
        'taxe_fonciere': 'Taxe_Fonciere',
        'emplacement': 'Emplacement',
        'typologie': 'Typologie',
        'extraction': 'Extraction',
        'restauration': 'Restauration',
        'latitude': 'Latitude',
        'longitude': 'Longitude',
        'actif': 'Actif',
        'region': 'Region',
        'departement': 'Departement',
        'honoraires': 'Honoraires',
        # Ajouter d'autres colonnes utilisées pour les détails ici
        'ville': 'Ville',
        'adresse': 'Adresse',
        'repartition_surface_gla': 'Répartition surface GLA',
        'surface_utile': 'Surface utile',
        'repartition_surface_utile': 'Répartition surface utile',
        'loyer_mensuel': 'Loyer Mensuel',
        'loyer_m2': 'Loyer €/m²',
        'loyer_variable': 'Loyer Variable',
        'charges_mensuelles': 'Charges Mensuelles',
        'charges_m2': 'Charges €/m²',
        'taxe_fonciere_m2': 'Taxe Foncière €/m²',
        'marketing': 'Marketing',
        'marketing_m2': 'Marketing €/m²',
        'total_l_c_m': 'Total (L+C+M)',
        'depot_de_garantie': 'Dépôt de garantie',
        'gapd': 'GAPD',
        'gestion': 'Gestion',
        'etat_de_livraison': 'Etat de livraison',
        'environnement_commercial': 'Environnement Commercial',
        'commentaires': 'Commentaires',
    }

    # Création du Dictionnaire de mapping pour l'affichage des détails
    DETAIL_COLUMNS_MAPPING = {}
    for internal_key, display_name in INTERNAL_COLUMNS_MAP.items():
        if internal_key in df.columns:
            # On utilise le nom interne (Ref_Annonce, Region...) comme clé dans le DF final
            # et le nom d'affichage comme valeur
            DETAIL_COLUMNS_MAPPING[INTERNAL_COLUMNS_MAP.get(internal_key, internal_key)] = display_name
    
    # Renommage des colonnes du DF pour utiliser les clés internes simplifiées (Ref_Annonce, Region...)
    df = df.rename(columns={
        normalized_name: simplified_name 
        for normalized_name, simplified_name in INTERNAL_COLUMNS_MAP.items() 
        if normalized_name in df.columns
    })
    
    # Liste des colonnes critiques attendues (simplifiées)
    REQUIRED_COLS = ['Region', 'Departement', 'Latitude', 'Longitude', 'Ref_Annonce', 'Actif']
    
    # 4. Vérification des colonnes critiques
    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
    if missing_cols:
        st.error(f"Erreur de données: Colonnes manquantes après normalisation: {', '.join(missing_cols)}. (Colonnes trouvées: {', '.join(df.columns)})")
        return pd.DataFrame(), {}


    # 5. Filtrer uniquement les lots 'Actif'
    if 'Actif' in df.columns:
        df = df[df['Actif'].astype(str).str.lower().str.strip() == 'oui'].copy()
    
    # 6. S'assurer que les colonnes clés sont présentes et nettoyer les NaNs
    df = df.dropna(subset=['Latitude', 'Longitude'])
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    
    # Supprimer les lignes avec des coordonnées non valides
    df = df.dropna(subset=['Latitude', 'Longitude', 'Ref_Annonce'])
    
    # Appliquer le formatage de référence une fois
    df['Ref_Format'] = df['Ref_Annonce'].apply(format_reference)

    # Convertir les colonnes de filtrage en chaînes pour éviter les erreurs de type
    for col in ['Region', 'Departement', 'Emplacement', 'Typologie', 'Extraction', 'Restauration']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            # Remplacer les valeurs vides/non significatives dans les colonnes de filtre par 'N/A'
            df[col] = df[col].apply(lambda x: 'N/A' if str(x).strip().lower() in ["", "nan", "néant", "-", "/", "0"] else x)
        else:
             # Ajouter une colonne par défaut si elle est manquante pour éviter KeyError dans les filtres
             df[col] = 'N/A' 
             
    # Mise à jour du DETAIL_COLUMNS_MAPPING pour garantir l'ordre des détails
    # Ne garder que les colonnes existantes
    final_detail_mapping = {
        key: value for key, value in DETAIL_COLUMNS_MAPPING.items() if key in df.columns
    }

    return df, final_detail_mapping

# Charger les données
df_data, DETAIL_COLUMNS_MAPPING = load_data()

# Définir les valeurs min/max initiales
MIN_SURFACE = df_data['Surface_GLA'].min() if not df_data.empty and 'Surface_GLA' in df_data.columns else 0
MAX_SURFACE = df_data['Surface_GLA'].max() if not df_data.empty and 'Surface_GLA' in df_data.columns else 100
MIN_LOYER = df_data['Loyer_Annuel'].min() if not df_data.empty and 'Loyer_Annuel' in df_data.columns else 0
MAX_LOYER = df_data['Loyer_Annuel'].max() if not df_data.empty and 'Loyer_Annuel' in df_data.columns else 100000

# Définir l'état initial des filtres pour le bouton Réinitialiser
if 'filters' not in st.session_state:
    st.session_state.filters = {
        'selected_regions': set(df_data['Region'].unique()) if not df_data.empty else set(),
        'selected_departments': set(df_data['Departement'].unique()) if not df_data.empty else set(),
        'surface_range': (MIN_SURFACE, MAX_SURFACE),
        'loyer_range': (MIN_LOYER, MAX_LOYER),
        'emplacement': set(df_data['Emplacement'].unique()) if not df_data.empty else set(),
        'typologie': set(df_data['Typologie'].unique()) if not df_data.empty else set(),
        'extraction': set(df_data['Extraction'].unique()) if not df_data.empty else set(),
        'restauration': set(df_data['Restauration'].unique()) if not df_data.empty else set(),
        'selected_lot_ref': None, # Réf. du lot sélectionné pour le panneau droit
        'show_detail_panel': False # État du panneau droit
    }
    
    # Pour le cas où le DataFrame est vide
    if df_data.empty:
        st.session_state.filters['surface_range'] = (0, 1)
        st.session_state.filters['loyer_range'] = (0, 1)


# Fonction de réinitialisation complète
def reset_filters():
    """Réinitialise tous les filtres à l'état initial (tout sélectionné/min-max) et ferme le panneau."""
    st.session_state.filters = {
        'selected_regions': set(df_data['Region'].unique()) if not df_data.empty else set(),
        'selected_departments': set(df_data['Departement'].unique()) if not df_data.empty else set(),
        'surface_range': (MIN_SURFACE, MAX_SURFACE),
        'loyer_range': (MIN_LOYER, MAX_LOYER),
        'emplacement': set(df_data['Emplacement'].unique()) if not df_data.empty else set(),
        'typologie': set(df_data['Typologie'].unique()) if not df_data.empty else set(),
        'extraction': set(df_data['Extraction'].unique()) if not df_data.empty else set(),
        'restauration': set(df_data['Restauration'].unique()) if not df_data.empty else set(),
        'selected_lot_ref': None,
        'show_detail_panel': False
    }
    if df_data.empty:
        st.session_state.filters['surface_range'] = (0, 1)
        st.session_state.filters['loyer_range'] = (0, 1)
    # Rétablir les inputs de clic pour permettre le nouveau clic après réinitialisation
    st.session_state.lot_click_handler_key = ""
    st.session_state.map_click_handler_key = ""


# --- 4. CSS PERSONNALISÉ ET IDENTITÉ VISUELLE ---

# Fonction pour charger les assets en base64
def get_base64_of_bin_file(bin_file):
    try:
        if not os.path.exists(bin_file):
            return None
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None

# Simulation de l'intégration des polices Futura (remplacez par vos fichiers .ttf réels)
# J'utilise une police de secours si les TTF ne sont pas disponibles
futura_light_b64 = get_base64_of_bin_file("assets/futura_light.ttf")
futura_medium_b64 = get_base64_of_bin_file("assets/futura_medium.ttf")
futura_bold_b64 = get_base64_of_bin_file("assets/futura_bold.ttf")

font_face_css = ""
if futura_light_b64:
    # Intégrer les polices uniquement si les fichiers sont trouvés
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
    FONT_FAMILY_FALLBACK = "Futura, 'Futura PT', 'Century Gothic', Arial, sans-serif"
else:
    FONT_FAMILY_FALLBACK = "'Century Gothic', Arial, sans-serif"


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
    font-family: {FONT_FAMILY_FALLBACK} !important;
}}

/* 11. Comportement général: Supprimer le scroll global et définir la hauteur à 100vh */
html, body, .main, [data-testid="stAppViewContainer"], [data-testid="stVerticalBlock"] {{
    height: 100vh !important;
    overflow: hidden !important;
    padding: 0 !important;
    margin: 0 !important;
}}

/* Correction de la zone principale pour qu'elle prenne 100% de la hauteur restante */
[data-testid="stAppViewContainer"] > .main {{
    padding: 0;
    margin: 0;
}}

.block-container {{
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
    height: 100vh !important;
}}

/* A. Volet gauche (sidebar) */
[data-testid="stSidebar"] {{
    width: 275px !important;
    min-width: 275px !important;
    max-width: 275px !important;
    background-color: var(--smbg-blue) !important;
    transition: none !important; /* Aucun bouton de collapse, toujours visible */
}}

/* Cacher le bouton de collapse de la sidebar gauche */
[data-testid="stSidebarUserContent"] > button {{
    display: none !important;
}}

/* B. Zone centrale : la carte (Contenu principal) */
.st-emotion-cache-1cypcdp {{ /* Conteneur de la carte (colonne principale) */
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
    pointer-events: none; /* Supprimer le bouton d’agrandissement de Streamlit */
    user-select: none;
}}

/* Style des titres et labels de la sidebar (bleu SMBG, texte blanc) */
[data-testid="stSidebarContent"] label,
[data-testid="stSidebarContent"] .st-b5,
[data-testid="stSidebarContent"] h2 {{
    color: white !important;
}}
[data-testid="stSidebarContent"] .st-bp {{ /* Slider value */
    color: var(--smbg-copper) !important;
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
.gmaps-button a button {{
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

/* Masquer les inputs de gestion des clics (hack) */
[data-testid="stTextInput"] {{ display: none !important; }}

"""
st.markdown(f"<style>{critical_css}</style>", unsafe_allow_html=True)

# --- 5. LOGIQUE DE FILTRAGE ---

def apply_filters(df):
    """Applique tous les filtres actifs à la DataFrame."""
    filtered_df = df.copy()

    # Colonnes de filtres textuels
    filter_cols_text = ['Region', 'Departement', 'Emplacement', 'Typologie', 'Extraction', 'Restauration']
    
    # 1. Filtres Région / Département
    selected_regions_filter = st.session_state.filters['selected_regions']
    selected_deps_filter = st.session_state.filters['selected_departments']
    
    # S'assurer que les colonnes de filtre textuel existent
    for col in filter_cols_text:
        if col not in filtered_df.columns:
            # Si une colonne de filtre est manquante (normalement traitée dans load_data)
            # on crée une colonne par défaut pour éviter un KeyError
            filtered_df[col] = 'N/A' 
    
    # 9. Logique de filtrage Région / Département:
    regions_df_unique = filtered_df[['Region', 'Departement']].drop_duplicates()
    
    final_allowed_deps = set()
    
    for region in df_data['Region'].unique():
        # S'assurer que 'Region' existe dans regions_df_unique avant d'appeler .unique()
        deps_in_region = set(regions_df_unique[regions_df_unique['Region'] == region]['Departement'].unique())
        
        # Intersection entre les départements de cette région et ceux cochés globalement
        cochage_specifique_dans_region = deps_in_region.intersection(selected_deps_filter)
        
        is_region_selected = region in selected_regions_filter

        if is_region_selected:
            if cochage_specifique_dans_region:
                # Région cochée + certains départements cochés -> uniquement ces départements
                final_allowed_deps.update(cochage_specifique_dans_region)
            else:
                # Région cochée + aucun département cochée spécifiquement -> tous les lots de cette région
                final_allowed_deps.update(deps_in_region)

    # Si la liste finale est vide, on ne filtre rien sur la géographie
    if final_allowed_deps:
        filtered_df = filtered_df[filtered_df['Departement'].isin(final_allowed_deps)]
    else:
        # Si aucune région n'est cochée MAIS des régions existent dans le DF, on ne filtre rien.
        # Si le DF est vide, ça passe.
        pass
    
    # 2. Filtres Sliders (Surface GLA et Loyer annuel)
    min_surface, max_surface = st.session_state.filters['surface_range']
    min_loyer, max_loyer = st.session_state.filters['loyer_range']

    if 'Surface_GLA' in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Surface_GLA'] >= min_surface) & (filtered_df['Surface_GLA'] <= max_surface)
        ]
    
    if 'Loyer_Annuel' in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Loyer_Annuel'] >= min_loyer) & (filtered_df['Loyer_Annuel'] <= max_loyer)
        ]

    # 3. Autres filtres cases à cocher
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
    logo_b64 = get_base64_of_bin_file(LOGO_PATH)
    if logo_b64:
        st.markdown(f"""
            <div class="logo-container">
                <img src="data:image/png;base64,{logo_b64}" alt="Logo SMBG" />
            </div>
        """, unsafe_allow_html=True)
    else:
        # Fallback si le logo n'est pas disponible localement
        st.markdown(f"<div class='logo-container' style='color: white; font-size: 24px; font-weight: bold;'>SMBG Carte</div>", unsafe_allow_html=True)

    # Bouton Réinitialiser
    st.markdown('<div id="reset-button">', unsafe_allow_html=True)
    # Vérifiez si df_data n'est pas vide avant de tenter d'accéder à l'état
    disabled_reset = df_data.empty
    st.button("Réinitialiser les filtres", on_click=reset_filters, use_container_width=True, disabled=disabled_reset)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<hr style='border-top: 1px solid rgba(255,255,255,0.2);'>", unsafe_allow_html=True)

    # 8. Filtres
    
    # 1. Région / Département imbriqués
    st.markdown("<h2>Filtres Géographiques</h2>", unsafe_allow_html=True)

    # Utiliser les données chargées pour les options (gère le cas où le DF est vide)
    unique_regions = sorted(df_data['Region'].unique().tolist()) if 'Region' in df_data.columns else []
    
    if df_data.empty or not unique_regions:
        st.info("Aucune donnée géographique à filtrer.")
    else:
        # Copie des états pour la manipulation des checkbox
        temp_regions = st.session_state.filters['selected_regions'].copy()
        temp_departments = st.session_state.filters['selected_departments'].copy()

        for region in unique_regions:
            # Checkbox Région
            checkbox_key_reg = f"region_{region}"
            is_region_checked = region in temp_regions
            
            if st.checkbox(label=region, value=is_region_checked, key=checkbox_key_reg):
                temp_regions.add(region)
            else:
                temp_regions.discard(region)

            # Affichage des départements si la région est cochée
            if region in temp_regions:
                # S'assurer que le filtre fonctionne même si la colonne est 'N/A'
                departments_in_region = sorted(df_data[df_data['Region'] == region]['Departement'].unique().tolist())
                
                for dep in departments_in_region:
                    # Checkbox Département avec indentation
                    st.markdown(f'<div class="department-checkbox">', unsafe_allow_html=True)
                    
                    checkbox_key_dep = f"dep_{dep}"
                    is_dep_checked = dep in temp_departments
                    
                    if st.checkbox(label=dep, value=is_dep_checked, key=checkbox_key_dep):
                        temp_departments.add(dep)
                    else:
                        temp_departments.discard(dep)
                    
                    st.markdown('</div>', unsafe_allow_html=True)

        # Mise à jour de l'état global après le rendu de toutes les checkboxes
        st.session_state.filters['selected_regions'] = temp_regions
        st.session_state.filters['selected_departments'] = temp_departments

    st.markdown("<hr style='border-top: 1px solid rgba(255,255,255,0.2);'>", unsafe_allow_html=True)

    # --- 2. Sliders ---
    st.markdown("<h2>Filtres Numériques</h2>", unsafe_allow_html=True)
    
    # Surface GLA
    if 'Surface_GLA' in df_data.columns:
        initial_gla_range = st.session_state.filters['surface_range']
        
        new_gla_range = st.slider(
            "Surface GLA (m²)",
            min_value=float(MIN_SURFACE),
            max_value=float(MAX_SURFACE),
            value=initial_gla_range,
            step=1.0,
            key="surface_slider",
            disabled=disabled_reset
        )
        st.session_state.filters['surface_range'] = new_gla_range
    else:
         st.markdown("<p style='color: rgba(255,255,255,0.5);'>Surface GLA non disponible</p>", unsafe_allow_html=True)


    # Loyer annuel
    if 'Loyer_Annuel' in df_data.columns:
        initial_loyer_range = st.session_state.filters['loyer_range']

        new_loyer_range = st.slider(
            "Loyer annuel (€)",
            min_value=float(MIN_LOYER),
            max_value=float(MAX_LOYER),
            value=initial_loyer_range,
            step=1000.0,
            key="loyer_slider",
            format="%i €",
            disabled=disabled_reset
        )
        st.session_state.filters['loyer_range'] = new_loyer_range
    else:
         st.markdown("<p style='color: rgba(255,255,255,0.5);'>Loyer annuel non disponible</p>", unsafe_allow_html=True)


    st.markdown("<hr style='border-top: 1px solid rgba(255,255,255,0.2);'>", unsafe_allow_html=True)
    
    # --- 3. Autres cases à cocher ---
    st.markdown("<h2>Filtres Thématiques</h2>", unsafe_allow_html=True)
    
    checkbox_filters = ['Emplacement', 'Typologie', 'Extraction', 'Restauration']
    
    for filter_col in checkbox_filters:
        if filter_col in df_data.columns:
            unique_options = sorted(df_data[filter_col].unique().tolist())
            st.markdown(f"**{filter_col}**", unsafe_allow_html=True)
            
            temp_options = st.session_state.filters[filter_col.lower()].copy()

            for option in unique_options:
                checkbox_key = f"{filter_col.lower()}_{option.replace(' ', '_')}"
                is_checked = option in temp_options
                
                checked = st.checkbox(
                    label=option,
                    value=is_checked,
                    key=checkbox_key,
                    disabled=disabled_reset
                )
                
                # Mise à jour de l'état temporaire
                if checked:
                    temp_options.add(option)
                else:
                    temp_options.discard(option)

            st.session_state.filters[filter_col.lower()] = temp_options
        else:
             st.markdown(f"<p style='color: rgba(255,255,255,0.5);'>Filtre {filter_col} non disponible</p>", unsafe_allow_html=True)


# --- 8. APPLICATION DES FILTRES ET PRÉPARATION DE LA CARTE ---

# Vérifier si le DataFrame est vide
if df_data.empty:
    filtered_data = pd.DataFrame()
    st.info("Aucune donnée disponible pour l'affichage.")
else:
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
    height="100%",
    width="100%",
    tiles='OpenStreetMap'
)

# Style du pin (Marker personnalisé avec Leaflet DivIcon pour le texte et le style)
for index, row in filtered_data.iterrows():
    if 'Ref_Format' not in row or 'Latitude' not in row or 'Longitude' not in row or 'Ref_Annonce' not in row:
        continue # Ignorer les lignes sans données critiques après filtrage
        
    ref = row['Ref_Format']
    lat = row['Latitude']
    lon = row['Longitude']
    lot_ref_annonce = row['Ref_Annonce'] # Clé unique pour l'identification

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
    " onmousedown="
        // Au clic, envoie un message à Streamlit pour déclencher le callback
        var event = new CustomEvent('lot_clicked', {{ detail: '{lot_ref_annonce}' }});
        window.parent.document.dispatchEvent(event);
        event.stopPropagation(); // Empêche l'événement de se propager à la carte (fermeture du panneau)
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
        tooltip=None,
        popup=None
    ).add_to(m)

# HTML/JS pour gérer le clic sur la carte et le clic sur le pin
js_injection = f"""
<script>
    // Ajout d'une variable globale pour suivre l'état du clic (pour éviter le double déclenchement)
    window.clickedLotRef = null;
    window.clickedMapRef = null;
    
    // Événement pour gérer le clic sur un pin (déclenché depuis le DivIcon)
    window.parent.document.addEventListener('lot_clicked', function(e) {{
        // Si la référence est la même, ignorer (déjà en cours de traitement)
        if (window.clickedLotRef === e.detail) return;
        
        window.clickedLotRef = e.detail;
        
        // Envoie un message de retour à Streamlit avec la référence du lot
        var msg = {{
            type: 'streamlit:setComponentValue',
            componentName: 'lot_click_handler',
            value: e.detail
        }};
        window.parent.postMessage(msg, '*');
        
        // Nettoyer la référence après un court délai
        setTimeout(() => {{ window.clickedLotRef = null; }}, 500);
    }});

    // Événement pour gérer le clic sur la carte (hors pin)
    window.onload = function() {{
        var mapContainer = window.parent.document.querySelector('.folium-map');
        if (mapContainer) {{
            mapContainer.addEventListener('mousedown', function(e) {{
                // Vérifie si l'élément cliqué n'est pas un pin (DivIcon)
                let target = e.target;
                let isPinClick = false;
                
                // Vérifie si le clic provient du DivIcon Leaflet ou d'un de ses parents
                while (target) {{
                    if (target.classList && target.classList.contains('leaflet-marker-icon')) {{
                        isPinClick = true;
                        break;
                    }}
                    // S'assurer que le clic vient bien de la carte et non d'un autre composant streamlit
                    if (target === mapContainer) break; 
                    target = target.parentNode;
                }}

                if (!isPinClick) {{
                    // Si le clic n'est pas un pin, envoyer le signal de fermeture
                    var msg = {{
                        type: 'streamlit:setComponentValue',
                        componentName: 'map_click_handler',
                        value: 'map_clicked_' + Date.now()
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
folium_static(m, width=9999, height=9999)

# --- 10. GESTION DES ÉVÉNEMENTS FOLIUM/JS ---

# Inputs cachés pour recevoir les messages du JS (hack)
# IMPORTANT: L'initialisation se fait en dehors du bloc if/else
lot_clicked_ref = st.text_input("lot_click_handler", key="lot_click_handler_key", label="hidden_lot_click")
map_clicked_state = st.text_input("map_click_handler", key="map_click_handler_key", label="hidden_map_click")

# Logique de gestion de clic
if lot_clicked_ref:
    # Clic sur un Pin : Ouvrir le panneau
    open_detail_panel(lot_clicked_ref)
    # CORRECTION CRITIQUE: Réinitialiser l'input pour permettre un nouveau clic
    st.session_state.lot_click_handler_key = "" 

if map_clicked_state and st.session_state.filters['show_detail_panel']:
    # Clic sur la Carte (hors pin) ET le panneau est ouvert : Fermer le panneau
    close_detail_panel()
    # CORRECTION CRITIQUE: Réinitialiser l'input pour permettre un nouveau clic
    st.session_state.map_click_handler_key = ""

# --- 11. VOLET DROIT (PANNEAU DE DÉTAILS) ---

# Déterminer la classe CSS (collapsed ou expanded)
panel_class = "expanded" if st.session_state.filters['show_detail_panel'] else "collapsed"

# Contenu du panneau
panel_content = ""

if st.session_state.filters['selected_lot_ref'] and not df_data.empty:
    ref = st.session_state.filters['selected_lot_ref']
    
    # S'assurer que le lot est toujours dans le DF filtré (sinon le panneau doit se fermer)
    lot_data_series = df_data[df_data['Ref_Annonce'] == ref]
    
    if not lot_data_series.empty:
        lot_data = lot_data_series.iloc[0]
        
        panel_content += f"<h3>Détails de l'annonce</h3>"
        
        # Référence annonce (formatée)
        panel_content += f"<p style='text-align: center; font-size: 1.2em; font-weight: bold; color: {COPPER_SMBG}; margin-bottom: 25px;'>Réf. {lot_data['Ref_Format']}</p>"

        # Tableau des détails
        table_html = "<table style='width: 100%; border-collapse: collapse; font-size: 0.9em;'>"
        
        # Les colonnes à afficher (selon DETAIL_COLUMNS_MAPPING)
        for col_internal, col_display in DETAIL_COLUMNS_MAPPING.items():
            if col_internal == 'Lien_GMaps': # La colonne H est traitée séparément
                continue
            
            # S'assurer que la colonne existe dans la ligne de données
            if col_internal not in lot_data:
                continue

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
            
            # Pour d'autres valeurs numériques non monétaires/surfaces, forcer à str si ce n'est pas déjà formaté
            if formatted_value is None:
                continue
            
            # Remplacement de N/A par tiret si la valeur était présente mais n'a pas été formatée
            if formatted_value == 'N/A': formatted_value = '-'

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
        # Lot non trouvé (par exemple, filtré depuis la dernière sélection) -> Fermer le panneau
        close_detail_panel()
        panel_content = f"<div class='detail-panel collapsed'></div>"
else:
    # Panneau replié sans contenu
    panel_content = f"<div class='detail-panel collapsed'></div>"

# Affichage du panneau de détails via markdown (position fixed)
st.markdown(panel_content, unsafe_allow_html=True)

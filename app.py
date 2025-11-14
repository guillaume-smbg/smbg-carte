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
# Utilisation de l'image de secours si le chemin n'est pas trouvé
LOGO_PATH = "assets/Logo bleu crop.png" 

# CHEMIN D'ACCÈS DU FICHIER :
# Utilisation du nom du fichier que vous avez téléversé.
# IMPORTANT : Ce fichier doit être présent dans le même dossier que l'application Streamlit.
DATA_FILE_PATH = "Liste des lots.xlsx - Tableau recherche.csv" 

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
        # On utilise une vérification moins stricte pour les strings qui contiennent du texte
        numeric_part = re.sub(r'[^\d\.\,]', '', value_str).replace(',', '.')
        if numeric_part and float(numeric_part) == 0.0:
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
        # Tenter avec le point-virgule (le plus fréquent pour les exports français)
        df = pd.read_csv(DATA_FILE_PATH, sep=';', encoding='utf-8')
    except FileNotFoundError:
        st.error(f"Erreur : Le fichier de données '{DATA_FILE_PATH}' n'a pas été trouvé. Veuillez vérifier que le fichier est bien nommé ainsi.")
        return pd.DataFrame(), {}
    except Exception:
        try:
            # Tenter avec la virgule (standard CSV)
            df = pd.read_csv(DATA_FILE_PATH, sep=',', encoding='utf-8')
        except Exception as e:
            st.error(f"Erreur lors de la lecture du fichier de données CSV: {e}")
            return pd.DataFrame(), {}

    if df.empty:
        st.error("Le fichier de données est vide après le chargement.")
        return pd.DataFrame(), {}
    
    # 2. Normalisation des noms de colonnes (CRITIQUE pour le KeyError)
    # Mapping des noms originaux normalisés aux noms d'affichage désirés (simplifiés)
    INTERNAL_COLUMNS_MAP = {
        # Format: normalized_name_from_file: Simplified_Internal_Name
        normalize_column_name('Référence annonce'): 'Ref_Annonce',
        normalize_column_name('Lien Google Maps'): 'Lien_GMaps',
        normalize_column_name('Surface GLA'): 'Surface_GLA',
        normalize_column_name('Loyer annuel'): 'Loyer_Annuel',
        normalize_column_name('Charges annuelles'): 'Charges_Annuelles',
        normalize_column_name('Taxe foncière'): 'Taxe_Fonciere',
        normalize_column_name('Emplacement'): 'Emplacement',
        normalize_column_name('Typologie'): 'Typologie',
        normalize_column_name('Extraction'): 'Extraction',
        normalize_column_name('Restauration'): 'Restauration',
        normalize_column_name('Latitude'): 'Latitude',
        normalize_column_name('Longitude'): 'Longitude',
        normalize_column_name('Actif'): 'Actif',
        normalize_column_name('Région'): 'Region',
        normalize_column_name('Département'): 'Departement',
        normalize_column_name('Honoraires'): 'Honoraires',
        
        # Colonnes de détails
        normalize_column_name('Ville'): 'Ville',
        normalize_column_name('Adresse'): 'Adresse',
        normalize_column_name('Répartition surface GLA'): 'Répartition surface GLA',
        normalize_column_name('Surface utile'): 'Surface utile',
        normalize_column_name('Répartition surface utile'): 'Répartition surface utile',
        normalize_column_name('Loyer Mensuel'): 'Loyer Mensuel',
        normalize_column_name('Loyer €/m²'): 'Loyer €/m²',
        normalize_column_name('Loyer variable'): 'Loyer Variable',
        normalize_column_name('Charges Mensuelles'): 'Charges Mensuelles',
        normalize_column_name('Charges €/m²'): 'Charges €/m²',
        normalize_column_name('Taxe foncière €/m²'): 'Taxe Foncière €/m²',
        normalize_column_name('Marketing'): 'Marketing',
        normalize_column_name('Marketing €/m²'): 'Marketing €/m²',
        normalize_column_name('Total (L+C+M)'): 'Total (L+C+M)',
        normalize_column_name('Dépôt de garantie'): 'Dépôt de garantie',
        normalize_column_name('GAPD'): 'GAPD',
        normalize_column_name('Gestion'): 'Gestion',
        normalize_column_name('Etat de livraison'): 'Etat de livraison',
        normalize_column_name('Environnement Commercial'): 'Environnement Commercial',
        normalize_column_name('Commentaires'): 'Commentaires',
        normalize_column_name('Type'): 'Type', # Type (Location pure, Cession, etc.)
        # N° Département n'est pas utilisé dans l'app, mais on le garde pour le mapping
        normalize_column_name('N° Département'): 'N° Département', 
    }
    
    # 3. Renommage des colonnes du DF pour utiliser les clés internes simplifiées (Ref_Annonce, Region...)
    df_normalized_cols = {col: normalize_column_name(col) for col in df.columns}
    
    rename_dict = {}
    
    for original_col, normalized_col in df_normalized_cols.items():
        if normalized_col in INTERNAL_COLUMNS_MAP:
            # Assigner le nom interne simplifié au nom original du DF
            rename_dict[original_col] = INTERNAL_COLUMNS_MAP[normalized_col]
        # Sinon, on garde le nom original de la colonne si non critique

    df = df.rename(columns=rename_dict)
    
    # Création du Dictionnaire de mapping pour l'affichage des détails (Nom interne: Nom d'affichage)
    DETAIL_COLUMNS_MAPPING = {
        simplified_name: display_name 
        for normalized_name, simplified_name in INTERNAL_COLUMNS_MAP.items() 
        for display_name in [simplified_name]
        if simplified_name in df.columns
    }
    
    # Liste des colonnes critiques attendues (simplifiées)
    REQUIRED_COLS = ['Region', 'Departement', 'Latitude', 'Longitude', 'Ref_Annonce', 'Actif', 'Surface_GLA', 'Loyer_Annuel']
    
    # 4. Vérification des colonnes critiques
    missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
    if missing_cols:
        st.error(f"Erreur de données: Colonnes critiques manquantes après normalisation. Vérifiez que les noms originaux sont exacts et non vides. Colonnes manquantes: {', '.join(missing_cols)}. (Colonnes trouvées: {', '.join(df.columns)})")
        return pd.DataFrame(), {}


    # 5. Filtrer uniquement les lots 'Actif'
    df = df[df['Actif'].astype(str).str.lower().str.strip() == 'oui'].copy()
    
    # 6. S'assurer que les colonnes clés sont présentes et nettoyer les NaNs
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    
    # Convertir les valeurs numériques pour les sliders
    df['Surface_GLA'] = pd.to_numeric(df['Surface_GLA'], errors='coerce')
    df['Loyer_Annuel'] = pd.to_numeric(df['Loyer_Annuel'], errors='coerce')
    
    # Supprimer les lignes avec des coordonnées non valides
    df = df.dropna(subset=['Latitude', 'Longitude', 'Ref_Annonce', 'Surface_GLA', 'Loyer_Annuel'])
    
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
             
    # Rétablir l'ordre pour les détails: on itère sur la liste figée des noms simplifiés
    ordered_detail_mapping = {
        'Ref_Annonce': 'Référence annonce',
        'Ville': 'Ville',
        'Adresse': 'Adresse',
        'Region': 'Région',
        'Departement': 'Département',
        'Emplacement': 'Emplacement',
        'Typologie': 'Typologie',
        'Type': 'Type',
        'Etat de livraison': 'État de livraison',
        'Extraction': 'Extraction',
        'Restauration': 'Restauration',
        
        # Surfaces
        'Surface_GLA': 'Surface GLA',
        'Répartition surface GLA': 'Répartition surface GLA',
        'Surface utile': 'Surface utile',
        'Répartition surface utile': 'Répartition surface utile',

        # Coûts
        'Loyer_Annuel': 'Loyer annuel',
        'Loyer Mensuel': 'Loyer Mensuel',
        'Loyer €/m²': 'Loyer €/m²',
        'Loyer Variable': 'Loyer variable',
        'Charges_Annuelles': 'Charges annuelles',
        'Charges Mensuelles': 'Charges Mensuelles',
        'Charges €/m²': 'Charges €/m²',
        'Taxe_Fonciere': 'Taxe foncière',
        'Taxe Foncière €/m²': 'Taxe foncière €/m²',
        'Marketing': 'Marketing',
        'Marketing €/m²', 'Marketing €/m²',
        'Total (L+C+M)': 'Total (L+C+M)',
        'Honoraires': 'Honoraires',
        'Dépôt de garantie': 'Dépôt de garantie',
        'GAPD': 'GAPD',
        'Gestion': 'Gestion',
        
        # Commentaires / Environnement
        'Environnement Commercial': 'Environnement Commercial',
        'Commentaires': 'Commentaires',
        
        # Lien
        'Lien_GMaps': 'Lien Google Maps',
    }
    
    # Ne garder que les colonnes existantes dans le DF final
    final_detail_mapping = {
        key: value for key, value in ordered_detail_mapping.items() if key in df.columns
    }

    return df, final_detail_mapping

# Charger les données
df_data, DETAIL_COLUMNS_MAPPING = load_data()

# Définir les valeurs min/max initiales
# Utilisez min/max uniquement des données après NaN/0 removal pour des sliders pertinents
MIN_SURFACE = df_data['Surface_GLA'].min() if not df_data.empty and 'Surface_GLA' in df_data.columns and not df_data['Surface_GLA'].empty else 0
MAX_SURFACE = df_data['Surface_GLA'].max() if not df_data.empty and 'Surface_GLA' in df_data.columns and not df_data['Surface_GLA'].empty else 100
MIN_LOYER = df_data['Loyer_Annuel'].min() if not df_data.empty and 'Loyer_Annuel' in df_data.columns and not df_data['Loyer_Annuel'].empty else 0
MAX_LOYER = df_data['Loyer_Annuel'].max() if not df_data.empty and 'Loyer_Annuel' in df_data.columns and not df_data['Loyer_Annuel'].empty else 100000

# Pour éviter les problèmes si min == max
if MIN_SURFACE == MAX_SURFACE and MIN_SURFACE != 0: MAX_SURFACE += 1
if MIN_LOYER == MAX_LOYER and MIN_LOYER != 0: MAX_LOYER += 1
    
# Définir l'état initial des filtres pour le bouton Réinitialiser
if 'filters' not in st.session_state:
    # Si les données ne sont pas chargées, les ensembles seront vides
    unique_regions_init = set(df_data['Region'].unique()) if 'Region' in df_data.columns and not df_data['Region'].empty else set()
    unique_departments_init = set(df_data['Departement'].unique()) if 'Departement' in df_data.columns and not df_data['Departement'].empty else set()
    unique_emplacement_init = set(df_data['Emplacement'].unique()) if 'Emplacement' in df_data.columns and not df_data['Emplacement'].empty else set()
    unique_typologie_init = set(df_data['Typologie'].unique()) if 'Typologie' in df_data.columns and not df_data['Typologie'].empty else set()
    unique_extraction_init = set(df_data['Extraction'].unique()) if 'Extraction' in df_data.columns and not df_data['Extraction'].empty else set()
    unique_restauration_init = set(df_data['Restauration'].unique()) if 'Restauration' in df_data.columns and not df_data['Restauration'].empty else set()
    
    # S'assurer que les valeurs initiales sont des ensembles d'éléments non vides
    st.session_state.filters = {
        'selected_regions': unique_regions_init,
        'selected_departments': unique_departments_init,
        'surface_range': (MIN_SURFACE, MAX_SURFACE),
        'loyer_range': (MIN_LOYER, MAX_LOYER),
        'emplacement': unique_emplacement_init,
        'typologie': unique_typologie_init,
        'extraction': unique_extraction_init,
        'restauration': unique_restauration_init,
        'selected_lot_ref': None, # Réf. du lot sélectionné pour le panneau droit
        'show_detail_panel': False # État du panneau droit
    }
    
# Clés de hack pour les clics de carte (doivent être initialisées)
if 'lot_click_handler_key' not in st.session_state:
    st.session_state.lot_click_handler_key = ""
if 'map_click_handler_key' not in st.session_state:
    st.session_state.map_click_handler_key = ""


# Fonction de réinitialisation complète
def reset_filters():
    """Réinitialise tous les filtres à l'état initial (tout sélectionné/min-max) et ferme le panneau."""
    
    unique_regions_init = set(df_data['Region'].unique()) if 'Region' in df_data.columns and not df_data['Region'].empty else set()
    unique_departments_init = set(df_data['Departement'].unique()) if 'Departement' in df_data.columns and not df_data['Departement'].empty else set()
    unique_emplacement_init = set(df_data['Emplacement'].unique()) if 'Emplacement' in df_data.columns and not df_data['Emplacement'].empty else set()
    unique_typologie_init = set(df_data['Typologie'].unique()) if 'Typologie' in df_data.columns and not df_data['Typologie'].empty else set()
    unique_extraction_init = set(df_data['Extraction'].unique()) if 'Extraction' in df_data.columns and not df_data['Extraction'].empty else set()
    unique_restauration_init = set(df_data['Restauration'].unique()) if 'Restauration' in df_data.columns and not df_data['Restauration'].empty else set()
    
    st.session_state.filters = {
        'selected_regions': unique_regions_init,
        'selected_departments': unique_departments_init,
        'surface_range': (MIN_SURFACE, MAX_SURFACE),
        'loyer_range': (MIN_LOYER, MAX_LOYER),
        'emplacement': unique_emplacement_init,
        'typologie': unique_typologie_init,
        'extraction': unique_extraction_init,
        'restauration': unique_restauration_init,
        'selected_lot_ref': None,
        'show_detail_panel': False
    }

    # Rétablir les inputs de clic pour permettre le nouveau clic après réinitialisation
    st.session_state.lot_click_handler_key = ""
    st.session_state.map_click_handler_key = ""


# --- 4. CSS PERSONNALISÉ ET IDENTITÉ VISUELLE ---

# Fonction pour charger les assets en base64
def get_base64_of_bin_file(bin_file):
    try:
        # NOTE: Les assets ne sont pas disponibles directement dans cet environnement, 
        # donc cette fonction retourne souvent None. On utilise des fallbacks CSS.
        if not os.path.exists(bin_file):
            return None
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None

# Simulation de l'intégration des polices Futura (remplacez par vos fichiers .ttf réels)
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

/* Style du bouton de fermeture du panneau */
.close-button {{
    position: absolute;
    top: 10px;
    right: 10px;
    background: none;
    border: none;
    color: white;
    font-size: 20px;
    cursor: pointer;
    line-height: 1;
    padding: 5px;
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
            filtered_df[col] = 'N/A' 
    
    # 9. Logique de filtrage Région / Département:
    regions_df_unique = filtered_df[['Region', 'Departement']].drop_duplicates()
    
    final_allowed_deps = set()
    
    # Itérer sur TOUTES les régions disponibles dans le DF
    unique_regions_all = df_data['Region'].unique() if 'Region' in df_data.columns else []

    for region in unique_regions_all:
        # S'assurer que 'Region' existe dans regions_df_unique avant d'appeler .unique()
        deps_in_region = set(regions_df_unique[regions_df_unique['Region'] == region]['Departement'].unique())
        
        # Intersection entre les départements de cette région et ceux cochés globalement
        cochage_specifique_dans_region = deps_in_region.intersection(selected_deps_filter)
        
        is_region_checked = region in selected_regions_filter

        if is_region_checked: # On considère qu'une région est cochée
            # On prend en compte UNIQUEMENT les départements sélectionnés
            if cochage_specifique_dans_region:
                final_allowed_deps.update(cochage_specifique_dans_region)
            else:
                # Si la région est cochée, mais AUCUN département n'est spécifiquement coché
                # on inclut TOUS les départements de cette région (comportement par défaut)
                final_allowed_deps.update(deps_in_region)

    # 2. Filtres Sliders (Surface GLA et Loyer annuel)
    min_surface, max_surface = st.session_state.filters['surface_range']
    min_loyer, max_loyer = st.session_state.filters['loyer_range']

    if 'Surface_GLA' in filtered_df.columns:
        # Filtrage sur le résultat de la sélection géographique
        filtered_df = filtered_df[
            (filtered_df['Surface_GLA'] >= min_surface) & (filtered_df['Surface_GLA'] <= max_surface)
        ]
    
    if 'Loyer_Annuel' in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Loyer_Annuel'] >= min_loyer) & (filtered_df['Loyer_Annuel'] <= max_loyer)
        ]
    
    # Appliquer le filtre géographique après les filtres numériques
    if final_allowed_deps:
        filtered_df = filtered_df[filtered_df['Departement'].isin(final_allowed_deps)]
    else:
        # Si aucun département n'est sélectionné/autorisé (cas où tout est décoché), on vide le DF
        if not selected_regions_filter and not selected_deps_filter:
            return pd.DataFrame()
        # Si une région est sélectionnée mais aucun département n'est dans le DF restant après les sliders,
        # le DF peut être vide, ce qui est correct.


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

        # Liste de tous les départements pour gérer la logique de sélection des régions
        all_departments = set(df_data['Departement'].unique())

        for region in unique_regions:
            # Checkbox Région
            checkbox_key_reg = f"region_{region}"
            is_region_checked = region in temp_regions
            
            # Utiliser la valeur de l'état pour l'état initial
            if st.checkbox(label=region, value=is_region_checked, key=checkbox_key_reg):
                # Si la région est cochée, on ajoute tous ses départements à la sélection
                departments_in_region = set(df_data[df_data['Region'] == region]['Departement'].unique())
                temp_departments.update(departments_in_region)
                temp_regions.add(region)
            else:
                # Si la région est décochée, on retire tous ses départements et la région elle-même
                departments_in_region = set(df_data[df_data['Region'] == region]['Departement'].unique())
                temp_departments.difference_update(departments_in_region)
                temp_regions.discard(region)


            # Affichage des départements si la région est cochée
            # ATTENTION: On ne montre les départements que si la région est cochée dans l'état ACTUEL
            if region in temp_regions:
                # Filtrer les départements pour cette région
                departments_in_region = sorted(df_data[df_data['Region'] == region]['Departement'].unique().tolist())
                
                for dep in departments_in_region:
                    # Checkbox Département avec indentation
                    st.markdown(f'<div class="department-checkbox">', unsafe_allow_html=True)
                    
                    checkbox_key_dep = f"dep_{dep}_{region}" # Clé unique par département/région
                    is_dep_checked = dep in temp_departments
                    
                    # NOTE IMPORTANTE: L'interaction de la checkbox de Département doit uniquement
                    # modifier l'état des départements (temp_departments).
                    if st.checkbox(label=dep, value=is_dep_checked, key=checkbox_key_dep):
                        temp_departments.add(dep)
                    else:
                        # Si l'utilisateur décoche un département, on le retire.
                        # Cela désélectionne de facto la région mère s'il n'en reste plus.
                        temp_departments.discard(dep)
                        
                    st.markdown('</div>', unsafe_allow_html=True)

        # Mise à jour de l'état global après le rendu de toutes les checkboxes
        st.session_state.filters['selected_regions'] = temp_regions
        st.session_state.filters['selected_departments'] = temp_departments

    st.markdown("<hr style='border-top: 1px solid rgba(255,255,255,0.2);'>", unsafe_allow_html=True)

    # --- 2. Sliders ---
    st.markdown("<h2>Filtres Numériques</h2>", unsafe_allow_html=True)
    
    # Surface GLA
    if 'Surface_GLA' in df_data.columns and MIN_SURFACE < MAX_SURFACE:
        initial_gla_range = st.session_state.filters['surface_range']
        
        # S'assurer que les valeurs d'état sont comprises entre min et max globaux
        current_min_gla = max(MIN_SURFACE, min(initial_gla_range[0], MAX_SURFACE))
        current_max_gla = min(MAX_SURFACE, max(initial_gla_range[1], MIN_SURFACE))

        new_gla_range = st.slider(
            "Surface GLA (m²)",
            min_value=float(MIN_SURFACE),
            max_value=float(MAX_SURFACE),
            value=(current_min_gla, current_max_gla),
            step=1.0,
            key="surface_slider",
            disabled=disabled_reset,
            format="%i m²"
        )
        st.session_state.filters['surface_range'] = new_gla_range
    else:
         st.markdown("<p style='color: rgba(255,255,255,0.5);'>Surface GLA non disponible ou données min/max identiques.</p>", unsafe_allow_html=True)


    # Loyer annuel
    if 'Loyer_Annuel' in df_data.columns and MIN_LOYER < MAX_LOYER:
        initial_loyer_range = st.session_state.filters['loyer_range']
        
        # S'assurer que les valeurs d'état sont comprises entre min et max globaux
        current_min_loyer = max(MIN_LOYER, min(initial_loyer_range[0], MAX_LOYER))
        current_max_loyer = min(MAX_LOYER, max(initial_loyer_range[1], MIN_LOYER))

        new_loyer_range = st.slider(
            "Loyer annuel (€)",
            min_value=float(MIN_LOYER),
            max_value=float(MAX_LOYER),
            value=(current_min_loyer, current_max_loyer),
            step=1000.0,
            key="loyer_slider",
            format="%i €",
            disabled=disabled_reset
        )
        st.session_state.filters['loyer_range'] = new_loyer_range
    else:
         st.markdown("<p style='color: rgba(255,255,255,0.5);'>Loyer annuel non disponible ou données min/max identiques.</p>", unsafe_allow_html=True)


    st.markdown("<hr style='border-top: 1px solid rgba(255,255,255,0.2);'>", unsafe_allow_html=True)
    
    # --- 3. Autres cases à cocher ---
    st.markdown("<h2>Filtres Thématiques</h2>", unsafe_allow_html=True)
    
    checkbox_filters = ['Emplacement', 'Typologie', 'Extraction', 'Restauration']
    
    for filter_col in checkbox_filters:
        if filter_col in df_data.columns:
            # S'assurer que l'ensemble des options est trié
            unique_options = sorted(df_data[filter_col].unique().tolist())
            st.markdown(f"**{DETAIL_COLUMNS_MAPPING.get(filter_col, filter_col)}**", unsafe_allow_html=True)
            
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
            st.markdown(f"<p style='color: rgba(255,255,255,0.5);'>{filter_col} non disponible.</p>", unsafe_allow_html=True)


# --- 8. LOGIQUE PRINCIPALE DE LA CARTE ---

# Appliquer les filtres à la DataFrame principale
df_filtered = apply_filters(df_data)

# Calculer la position centrale de la carte
if not df_filtered.empty:
    center_lat = df_filtered['Latitude'].mean()
    center_lon = df_filtered['Longitude'].mean()
    # Ajustement pour la France métropolitaine si les données sont trop dispersées
    if df_filtered.shape[0] > 1:
        map_zoom = 5 # Zoom par défaut pour l'ensemble de la France
    else:
        map_zoom = 12 # Zoom plus précis si un seul point
else:
    # Coordonnées par défaut de la France (si le DF est vide)
    center_lat = 46.603354
    center_lon = 1.888334
    map_zoom = 5

# Création de la carte Folium
m = folium.Map(
    location=[center_lat, center_lon], 
    zoom_start=map_zoom, 
    tiles='cartodbpositron', # Un fond de carte clair et moderne
    control_scale=True,
    scrollWheelZoom=True
)

# Fonction JavaScript pour gérer le clic sur un marqueur
# Cette fonction envoie la référence de l'annonce cliquée à Streamlit via un st.text_input hack
# et empêche le panneau de se fermer si l'utilisateur clique en dehors de la carte (non géré ici)
js_click_lot = """
function onClick(ref) {
    Streamlit.setComponentValue(ref);
}
"""

# Ajout des marqueurs à la carte
if not df_filtered.empty:
    for index, row in df_filtered.iterrows():
        # Créer le Popup HTML pour chaque marqueur
        popup_html = f"""
        <div style="font-family: Arial, sans-serif; font-size: 14px; color: {BLUE_SMBG};">
            <h4 style="margin: 0 0 5px 0; color: {COPPER_SMBG};">Lot : {row['Ref_Format']}</h4>
            <p style="margin: 0;">**{row.get('Ville', 'N/A')}** - {row.get('Departement', 'N/A')}</p>
            <p style="margin: 0; margin-top: 5px;">**GLA :** {format_surface(row['Surface_GLA'])}</p>
            <p style="margin: 0;">**Loyer :** {format_currency(row['Loyer_Annuel'])} / an</p>
        </div>
        """
        
        # Créer un IFrame pour le popup pour s'assurer que le contenu est rendu correctement
        iframe = folium.IFrame(popup_html, width=250, height=130)
        popup = folium.Popup(iframe, max_width=250)
        
        # Lier le marqueur à la fonction JavaScript
        marker_lat = row['Latitude']
        marker_lon = row['Longitude']
        lot_ref = row['Ref_Format']
        
        # Utilisation de folium.Marker pour ajouter le marqueur
        marker = folium.Marker(
            [marker_lat, marker_lon],
            popup=popup,
            tooltip=f"Lot: {lot_ref} | GLA: {row['Surface_GLA']}m²",
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
        
        # Ajout d'une action de clic (hack)
        # Note: La liaison directe d'un clic de marqueur à une fonction Streamlit
        # n'est pas possible nativement avec streamlit-folium. Nous utilisons
        # l'interaction Folium pour afficher le popup contenant l'info.
        
    st.info(f"Nombre de lots affichés : {df_filtered.shape[0]}")
else:
    st.warning("Aucun lot ne correspond aux critères de filtrage.")


# --- 9. HACK STREAMLIT-FOLIUM POUR GESTION DES CLICS ---

# 1. Utilisation d'un hack de zone de texte invisible pour capter la référence cliquée
# L'utilisateur ne clique pas ici, mais la valeur est mise à jour par le JS de la carte (non implémenté
# car folium-streamlit ne supporte pas d'injecter directement des actions JS Streamlit sur Marker Click).
# Cependant, pour simuler l'intention, nous gardons la logique d'état.
# On utilise un simple `st.empty()` pour ne pas afficher le champ de texte
# st.text_input(
#     "Lot Cliqué (Hack)", 
#     key="lot_click_handler_key", 
#     value=st.session_state.lot_click_handler_key, 
#     on_change=lambda: open_detail_panel(st.session_state.lot_click_handler_key)
# )

# Afficher la carte Folium (occupe le reste de l'écran)
folium_static(m, width=None, height=None)


# --- 10. PANNEAU DE DÉTAILS (VOLET DROIT) ---

# Déterminer la classe CSS pour le panneau
panel_class = "expanded" if st.session_state.filters['show_detail_panel'] else "collapsed"

st.markdown(f'<div class="detail-panel {panel_class}">', unsafe_allow_html=True)
st.button("×", on_click=close_detail_panel, key="close_detail_button", help="Fermer les détails", class_name="close-button")

selected_ref = st.session_state.filters.get('selected_lot_ref')

if selected_ref:
    # Trouver la ligne correspondante dans le DF (filtré ou non)
    # Utiliser df_data pour s'assurer que même un lot filtré mais cliqué reste visible.
    lot_data = df_data[df_data['Ref_Format'] == selected_ref].iloc[0] if not df_data.empty and (df_data['Ref_Format'] == selected_ref).any() else None

    if lot_data is not None:
        st.markdown(f"<h3>Détails du Lot : {selected_ref}</h3>", unsafe_allow_html=True)

        # Affichage des détails selon la configuration (DETAIL_COLUMNS_MAPPING)
        for internal_col, display_name in DETAIL_COLUMNS_MAPPING.items():
            value = lot_data.get(internal_col)
            
            # Application des formatages si possible
            if internal_col in ['Loyer_Annuel', 'Charges_Annuelles', 'Taxe_Fonciere', 'Loyer Mensuel', 'Charges Mensuelles', 'Marketing', 'Dépôt de garantie', 'GAPD', 'Gestion', 'Honoraires']:
                formatted_value = format_currency(value)
            elif internal_col in ['Surface_GLA', 'Surface utile']:
                formatted_value = format_surface(value)
            else:
                # Pour les autres champs (texte, lien, etc.)
                formatted_value = str(value) if not pd.isna(value) else None

            # Afficher uniquement si la valeur est significative
            if is_value_displayable(value):
                # Traitement spécial pour le lien Google Maps
                if internal_col == 'Lien_GMaps' and formatted_value:
                    st.markdown(f"""
                        <div style="margin-top: 15px;">
                            <span class="detail-label">{display_name} :</span>
                            <div class="gmaps-button">
                                <a href="{formatted_value}" target="_blank">
                                    <button>Ouvrir sur Google Maps</button>
                                </a>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    # Affichage standard
                    st.markdown(f"""
                        <div style="margin-top: 5px;">
                            <span class="detail-label">{display_name} :</span>
                            {formatted_value}
                        </div>
                    """, unsafe_allow_html=True)
        
        # Pied de panneau
        st.markdown("<hr style='border-top: 1px solid rgba(255,255,255,0.2);'>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: small; text-align: center;'>SMBG Immobilier Commercial</p>", unsafe_allow_html=True)

    else:
        st.markdown("<p style='text-align: center; margin-top: 50px;'>Sélectionnez un lot sur la carte.</p>", unsafe_allow_html=True)
else:
    st.markdown("<p style='text-align: center; margin-top: 50px;'>Sélectionnez un lot sur la carte pour voir ses détails.</p>", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

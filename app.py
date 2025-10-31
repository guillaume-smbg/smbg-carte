import os
import io
import re
import math
import unicodedata
from typing import Optional, Dict, Tuple, List

import pandas as pd
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium


# -------------------------------------------------
# CONFIG DE BASE ET CONSTANTES
# -------------------------------------------------

# Configurer la page pour utiliser tout l'espace
st.set_page_config(
    page_title="SMBG Carte Immo",
    layout="wide",
    initial_sidebar_state="collapsed" # Le sidebar Streamlit est masqué pour laisser place au panneau de filtres
)

# Configuration des couleurs et dimensions
LOGO_BLUE = "#05263d"
COPPER = "#b87333"
# Largeurs fixes pour les panneaux
LEFT_PANEL_WIDTH_PX = 275 
RIGHT_PANEL_WIDTH_PX = 275 

# Le chemin du logo (qui est maintenant un chemin local)
LOGO_URL = "assets/Logo bleu crop.png" 

# Noms des colonnes pour les FILTRES et les COORDONNEES
COL_REGION = "Région"
COL_DEPARTEMENT = "Département"
COL_VILLE = "Ville"
COL_REF = "Référence annonce" 
COL_LAT = "Latitude"
COL_LON = "Longitude"
COL_ADDR_FULL = "Adresse"

# NOUVELLES COLONNES POUR LES FILTRES
COL_TYPOLOGIE = "Typologie"
COL_TYPE = "Type"
COL_CESSION = "Cession / Droit au bail"
COL_EXTRACTION = "Extraction"
COL_RESTAURATION = "Restauration"
COL_LOYER = "Loyer annuel" # Nouvelle colonne pour le slider
COL_SURFACE_GLA = "Surface GLA" # Nouvelle colonne pour le slider


# LISTE COMPLÈTE DES COLONNES À AFFICHER DE G À AH
DETAIL_COLUMNS = [
    "Emplacement", 
    "Lien Google Maps", 
    "Typologie", 
    "Type", 
    "Cession / Droit au bail", 
    "Nombre de lots", 
    COL_SURFACE_GLA, 
    "Répartition surface GLA", 
    "Surface utile", 
    "Répartition surface utile", 
    COL_LOYER, 
    "Loyer Mensuel", 
    "Loyer €/m²", 
    "Loyer variable", 
    "Charges anuelles", 
    "Charges Mensuelles", 
    "Charges €/m²", 
    "Dépôt de garantie", 
    "GAPD", 
    "Taxe foncière", 
    "Marketing", 
    "Gestion", 
    "Etat de livraison", 
    COL_EXTRACTION, 
    COL_RESTAURATION, 
    "Environnement Commercial", 
    "Commentaires" 
]
COL_GMAPS = "Lien Google Maps"

# Chemin du fichier de données (CORRIGÉ SELON VOTRE DEMANDE)
DATA_FILE_PATH = "data/Liste des lots.xlsx" 
DATA_SHEET_NAME = "Tableau recherche" # Nom de la feuille Excel à lire


# -------------------------------------------------
# CHARGEMENT ET PREPARATION DES DONNEES
# -------------------------------------------------

@st.cache_data
def load_data(file_path: str, sheet_name: str) -> pd.DataFrame:
    """
    Charge le DataFrame et effectue le nettoyage/formatage initial.
    """
    try:
        # UTILISATION DE pd.read_excel AVEC LE CHEMIN ET LE NOM DE FEUILLE CORRECTS
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        required_cols = [COL_LAT, COL_LON, COL_REF, COL_LOYER, COL_SURFACE_GLA]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"La colonne requise '{col}' est manquante dans la feuille '{sheet_name}'. Veuillez vérifier le fichier Excel.")
                return pd.DataFrame() 

    except FileNotFoundError:
        st.error(f"Fichier de données Excel non trouvé au chemin spécifié : '{file_path}'.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier Excel. Détails: {e}")
        return pd.DataFrame()


    df[COL_LAT] = pd.to_numeric(df[COL_LAT], errors='coerce')
    df[COL_LON] = pd.to_numeric(df[COL_LON], errors='coerce')
    
    # Nettoyage et conversion des colonnes numériques utilisées pour les sliders
    # Utiliser un regex pour nettoyer les chaînes (supprimer les espaces, convertir en string, puis remplacer les virgules par des points)
    # Remplacer les valeurs non numériques (ex: '/', '-') par NaN avant la conversion
    for col in [COL_LOYER, COL_SURFACE_GLA]:
         # Convertir en string, enlever les espaces, remplacer , par .
        df.loc[:, col] = df[col].astype(str).str.replace(' ', '').str.replace(',', '.', regex=False)
        # Convertir en numérique, forçant les erreurs (comme '/' ou 'Néant') à NaN
        df.loc[:, col] = pd.to_numeric(df[col], errors='coerce')

    df_clean = df.dropna(subset=[COL_LAT, COL_LON]).copy()
    
    df_clean.loc[:, COL_REF] = df_clean[COL_REF].astype(str).str.strip()

    df_clean.loc[:, "_lat_plot"] = df_clean[COL_LAT]
    df_clean.loc[:, "_lon_plot"] = df_clean[COL_LON]

    # Remplacer NaN dans les colonnes de filtre spécifiques
    for col in [COL_TYPOLOGIE, COL_TYPE, COL_CESSION]:
        if col in df_clean.columns:
            df_clean.loc[:, col] = df_clean[col].fillna('Non spécifié')
    
    # Normalisation des colonnes Extraction/Restauration
    if COL_EXTRACTION in df_clean.columns:
        df_clean.loc[:, COL_EXTRACTION] = df_clean[COL_EXTRACTION].astype(str).str.strip().str.lower().replace({'oui': 'Oui', 'non': 'Non', 'nan': 'Non spécifié', '': 'Non spécifié'})
    if COL_RESTAURATION in df_clean.columns:
        df_clean.loc[:, COL_RESTAURATION] = df_clean[COL_RESTAURATION].astype(str).str.strip().str.lower().replace({'oui': 'Oui', 'non': 'Non', 'nan': 'Non spécifié', '': 'Non spécifié'})

    for col in [COL_REGION, COL_DEPARTEMENT, COL_VILLE, COL_TYPOLOGIE, COL_TYPE, COL_CESSION]:
        if col in df_clean.columns:
            df_clean.loc[:, col] = df_clean[col].astype(str).str.strip().fillna('Non spécifié')
        else:
             # Si une colonne de filtre manque, la créer avec une valeur par défaut pour éviter les erreurs de filtre
             df_clean.loc[:, col] = 'Non spécifié'

    return df_clean

# -------------------------------------------------
# CSS GLOBAL (Injecté directement)
# -------------------------------------------------

GLOBAL_CSS = f"""
<style>
/* 1. Rendre l'application NON-SCROLLABLE et utiliser toute la hauteur de la fenêtre */
.stApp, div[data-testid="stAppViewContainer"] {{
    /* Définir la hauteur de l'application à 100% de la hauteur du viewport */
    height: 100vh;
    /* Empêcher le scroll sur le corps principal */
    overflow: hidden !important; 
}}

/* Le conteneur principal */
div[data-testid="stAppViewContainer"] > .main {{
    padding: 10px 10px 10px 20px !important; /* Ajuste le padding extérieur */
    max-width: none !important; /* Utiliser toute la largeur */
    height: 100vh;
    overflow: hidden;
}}

/* Conteneur du titre et des colonnes */
div[data-testid="stVerticalBlock"] {{
    gap: 15px; /* Espace entre le titre et les colonnes */
    height: 100%; /* Important: Assure que les colonnes utilisent tout l'espace restant */
    overflow: hidden;
}}

/* Le bloc contenant les colonnes (div[data-testid="stHorizontalBlock"]) */
/* Ceci garantit que les colonnes s'alignent sans overflow vertical */
div[data-testid="stHorizontalBlock"] {{
    height: calc(100vh - 80px); /* Hauteur calculée: 100vh moins la hauteur du titre/padding */
    overflow: hidden;
    gap: 15px; /* Espace entre les colonnes */
}}


/* ===== PANNEAUX LATÉRAUX et CARTE ===== */

/* Conteneur de la carte (col_map) doit être flexible */
[data-testid="stColumn"]:nth-child(2) {{
    height: 100%;
    padding: 0 5px; /* Petit padding horizontal */
}}

/* Panneau Gauche (Filtres) */
.left-panel {{
    background-color: {LOGO_BLUE};
    color: #fff !important;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    min-width: {LEFT_PANEL_WIDTH_PX}px;
    max-width: {LEFT_PANEL_WIDTH_PX}px;
    
    /* Hauteur fixe pour le panneau de filtres */
    height: 100%; 
    overflow-y: auto; /* Permet le scroll uniquement dans ce panneau si nécessaire */
}}

/* Panneau Droit (Détails) */
.right-panel {{
    padding: 20px;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    background-color: #f9f9f9;
    min-width: {RIGHT_PANEL_WIDTH_PX}px;
    max-width: {RIGHT_PANEL_WIDTH_PX}px;
    
    /* Hauteur fixe pour le panneau de détails */
    height: 100%;
    overflow-y: auto; /* Permet le scroll uniquement dans ce panneau si nécessaire */
}}

/* Carte Folium (centre) */
.map-wrapper {{
    height: 100%; /* Prend toute la hauteur du conteneur */
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}}

/* Le conteneur iframe de la carte */
.map-wrapper iframe {{
    height: 100% !important; /* Forcer l'iframe à prendre 100% de la hauteur */
}}

/* Le titre Streamlit doit être ajusté pour ne pas prendre trop de place */
h1 {{
    margin-top: 0;
    margin-bottom: 5px;
    font-size: 26px;
    color: {LOGO_BLUE};
}}


/* --- Styles spécifiques aux marqueurs --- */
.custom-marker {{
    /* Utilise une épingle/pin stylisée pour plus de visibilité */
    width: 20px;
    height: 20px;
    background-color: {COPPER};
    border-radius: 50%;
    border: 3px solid {LOGO_BLUE};
    box-shadow: 0 0 5px rgba(0, 0, 0, 0.5);
    position: relative;
    cursor: pointer;
    line-height: 14px;
    font-size: 10px;
    color: white;
    font-weight: bold;
    text-align: center;
    transform: translate(-50%, -50%); /* Centrage du pin */
}}

/* Petite étiquette de référence à côté du pin */
.ref-label {{
    position: absolute;
    top: 50%;
    left: 100%;
    padding: 2px 5px;
    background-color: rgba(255, 255, 255, 0.9);
    border: 1px solid {LOGO_BLUE};
    border-radius: 4px;
    transform: translateY(-50%);
    white-space: nowrap;
    font-size: 10px;
    color: {LOGO_BLUE};
    font-weight: normal;
}}


/* --- Autres Styles conservés --- */
:root {{
    --logo-blue: {LOGO_BLUE};
    --copper: {COPPER};
}}

.stButton > button {{
    background-color: var(--copper);
    color: white;
    font-weight: bold;
    border-radius: 8px;
    border: none;
    padding: 8px 16px;
    transition: background-color 0.3s;
    width: 100%;
}}
.stButton > button:hover {{
    background-color: #9e642d;
}}

.close-button {{
    background-color: #e0e0e0;
    color: #333;
    width: auto;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: normal;
    float: right;
    margin-top: 5px;
}}
.close-button:hover {{
    background-color: #ccc;
}}

.detail-line {{
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px dotted #ccc;
    font-size: 14px;
}}

.detail-label {{
    font-weight: bold;
    color: var(--logo-blue);
    flex-shrink: 0;
    margin-right: 15px;
}}

.detail-value {{
    text-align: right;
    word-break: break-word;
    color: #333;
}}

.no-selection-msg {{
    text-align: center;
    margin-top: 50px;
    padding: 20px;
    border: 1px dashed #ccc;
    border-radius: 8px;
    color: #888;
}}

/* Styles pour les Sliders dans le panneau bleu */
/* Les labels de slider par défaut sont noirs, on les force en blanc */
.stSlider label {{
    color: white !important;
}}
/* Les tooltips et valeurs affichées sur les sliders */
div[data-testid="stTickBarMinMax"] {{
    color: #fff !important;
    font-weight: bold;
}}
div[data-testid="stTooltipContent"] {{
    color: #333 !important; /* Couleur du texte dans le tooltip */
}}
</style>
"""


# -------------------------------------------------
# FONCTIONS DE RENDU
# -------------------------------------------------

def format_value(value):
    """
    Applique les règles de formatage pour l'affichage dans le panneau de détails.
    """
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    
    value_str = str(value).strip()
    
    if value_str in ["/", "-"]:
        return "Non spécifié"
    
    # Tentative de formatage pour les nombres/devise
    try:
        num_val = float(value_str.replace(' ', '').replace(',', '.'))
        # Si c'est un loyer ou une surface, on tente un formatage spécifique
        if num_val > 1000 and num_val == round(num_val): # C'est probablement un grand nombre entier
             return f"{int(num_val):,}".replace(',', ' ')
        elif num_val == round(num_val):
             return f"{int(num_val)}"
        else:
             return f"{num_val:,.2f}".replace(',', ' ').replace('.', ',')

    except ValueError:
        pass # La valeur n'est pas un nombre, on la laisse telle quelle
        
    return value_str


def render_right_panel(
    selected_ref: Optional[str],
    df: pd.DataFrame,
    detail_columns: List[str],
    col_ref: str,
    col_addr_full: str,
    col_gmaps: str,
    col_city: str,
):
    """Affiche le panneau de droite avec les détails du lot sélectionné."""
    
    with st.container():
        
        # Bouton pour masquer le panneau (utilise float:right dans le CSS)
        if st.button("X Masquer les détails", key="hide_details_button", help="Cliquez pour masquer ce panneau de détails.", classes="close-button"):
            st.session_state["show_right_panel"] = False
            st.session_state["selected_ref"] = "NO_SELECTION"
            st.rerun() # Rerun essentiel pour redessiner la mise en page des colonnes
            
        st.markdown('<div class="right-panel">', unsafe_allow_html=True)
        
        if selected_ref and selected_ref != "NO_SELECTION":
            
            # Assurer que la référence existe avant d'essayer de la chercher
            if selected_ref not in df[col_ref].values:
                st.markdown('<p class="no-selection-msg">Lot non trouvé dans les données filtrées.</p>', unsafe_allow_html=True)
            else:
                lot_data = df[df[col_ref] == selected_ref].iloc[0].fillna('') 

                # --- TITRE ET ADRESSE ---
                st.markdown(f"<h3>Lot Réf. : {selected_ref}</h3>", unsafe_allow_html=True)
                st.markdown(f'<p class="detail-address">{lot_data.get(col_addr_full, "Adresse non spécifiée")} ({lot_data.get(col_city, "Ville non spécifiée")})</p>', unsafe_allow_html=True)

                # --- BOUTON GOOGLE MAPS ---
                gmaps_link = format_value(lot_data.get(col_gmaps))
                if gmaps_link and gmaps_link != "Non spécifié":
                    st.link_button("Voir sur Google Maps 🗺️", gmaps_link, help="Ouvre le lien Google Maps dans un nouvel onglet", type="primary")
                    st.markdown("---")
                
                
                # --- AFFICHAGE DES AUTRES CHAMPS DE DÉTAILS ---
                data_columns_to_show = [col for col in detail_columns if col != col_gmaps and col != "Commentaires"]
                
                for col_name in data_columns_to_show:
                    value = lot_data.get(col_name)
                    formatted_value = format_value(value)
                    
                    if formatted_value is not None:
                        st.markdown(
                            f"""
                            <div class="detail-line">
                                <span class="detail-label">{col_name} :</span>
                                <span class="detail-value">{formatted_value}</span>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                
                # --- AFFICHAGE DES COMMENTAIRES ---
                comments = format_value(lot_data.get("Commentaires"))
                if comments is not None:
                    st.markdown('<br><span class="detail-label">Commentaires :</span>', unsafe_allow_html=True)
                    st.markdown(f'<p class="detail-comments">{comments}</p>', unsafe_allow_html=True)

        else:
            st.markdown('<p class="no-selection-msg">Cliquez sur un marqueur sur la carte pour voir les détails du lot.</p>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True) # fin .right-panel


# -------------------------------------------------
# FONCTION PRINCIPALE DE L'APPLICATION
# -------------------------------------------------

def main():
    # Injection du CSS global
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    # Initialisation de l'état de la sélection et de la visibilité
    if "selected_ref" not in st.session_state:
        st.session_state["selected_ref"] = "NO_SELECTION"
    if "show_right_panel" not in st.session_state:
        st.session_state["show_right_panel"] = False
    if "click_registry" not in st.session_state:
        st.session_state["click_registry"] = {}


    # Chargement des données
    df = load_data(DATA_FILE_PATH, DATA_SHEET_NAME) 
    if df.empty:
        return

    # Calcul des min/max pour les sliders (ignorer les NaN/valeurs non-numériques)
    df_valid_loyer = df[COL_LOYER].dropna()
    loyer_min_all = int(df_valid_loyer.min()) if not df_valid_loyer.empty else 0
    loyer_max_all = int(df_valid_loyer.max()) if not df_valid_loyer.empty else 1000000
    
    df_valid_surface = df[COL_SURFACE_GLA].dropna()
    surface_min_all = int(df_valid_surface.min()) if not df_valid_surface.empty else 0
    surface_max_all = int(df_valid_surface.max()) if not df_valid_surface.empty else 10000

    # Initialisation des états de filtre pour les sliders
    if "loyer_range" not in st.session_state:
        st.session_state["loyer_range"] = (loyer_min_all, loyer_max_all)
    if "surface_range" not in st.session_state:
        st.session_state["surface_range"] = (surface_min_all, surface_max_all)
        
    # Le titre est mieux placé au-dessus des colonnes
    st.title("Catalogue Immobilier : Visualisation Cartographique")

    # Détermination de la structure des colonnes
    if st.session_state["show_right_panel"]:
        # Panneau de droite visible: [275px, Flexible, 275px]
        # Le 0.1 ajouté aux largeurs fixes garantit que Streamlit les traite comme des colonnes de largeur fixe
        col_left, col_map, col_right = st.columns([LEFT_PANEL_WIDTH_PX/1000 + 0.1, 1, RIGHT_PANEL_WIDTH_PX/1000 + 0.1], gap="medium")
    else:
        # Panneau de droite masqué: [275px, Flexible]
        col_left, col_map = st.columns([LEFT_PANEL_WIDTH_PX/1000 + 0.1, 1], gap="medium")
        # On utilise None pour le placeholder de la colonne de droite masquée
        col_right = None 

    # Pré-filtrage pour les zones géographiques (à l'intérieur de la colonne gauche)
    df_filtered = df.copy()

    # ======== COLONNE GAUCHE (panneau de filtres) ========
    # Le panneau gauche contient le filtre et les contrôles
    with col_left:
        st.markdown('<div class="left-panel">', unsafe_allow_html=True)
        
        # 0. Affichage du LOGO
        st.markdown('<div class="logo-container">', unsafe_allow_html=True)
        try:
             # Assurez-vous que le chemin est correct si vous fournissez l'image
             st.image(os.path.join(os.path.dirname(__file__), "assets", "Logo bleu crop.png"), use_column_width=True)
        except Exception:
             st.markdown('<p style="color:white; font-size:20px; font-weight:bold;">LOGO SMBG</p>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("<h3>Filtres de Recherche</h3>", unsafe_allow_html=True)

        # 1. Filtre Région
        regions = ['Toutes'] + sorted(df[COL_REGION].unique().tolist())
        selected_region = st.selectbox("Région", regions, key="region_filter")

        if selected_region != 'Toutes':
            df_filtered = df_filtered[df_filtered[COL_REGION] == selected_region]

        # 2. Filtre Département
        departements = ['Tous'] + sorted(df_filtered[COL_DEPARTEMENT].unique().tolist())
        selected_departement = st.selectbox("Département", departements, key="departement_filter")

        if selected_departement != 'Tous':
            df_filtered = df_filtered[df_filtered[COL_DEPARTEMENT] == selected_departement]
            
        # 3. Filtre Ville
        villes = ['Toutes'] + sorted(df_filtered[COL_VILLE].unique().tolist())
        selected_ville = st.selectbox("Ville", villes, key="ville_filter")
        
        if selected_ville != 'Toutes':
            df_filtered = df_filtered[df_filtered[COL_VILLE] == selected_ville]
            
        st.markdown("<hr style='border-top: 1px solid var(--copper); margin: 15px 0;'>", unsafe_allow_html=True)
        
        # 4. Filtre Typologie
        typologies = ['Toutes'] + sorted(df_filtered[COL_TYPOLOGIE].unique().tolist())
        selected_typologie = st.selectbox("Typologie", typologies, key="typologie_filter")
        
        if selected_typologie != 'Toutes':
            df_filtered = df_filtered[df_filtered[COL_TYPOLOGIE] == selected_typologie]

        # 5. Filtre Type
        types = ['Tous'] + sorted(df_filtered[COL_TYPE].unique().tolist())
        selected_type = st.selectbox("Type d'Opération", types, key="type_filter")
        
        if selected_type != 'Tous':
            df_filtered = df_filtered[df_filtered[COL_TYPE] == selected_type]

        # 6. Filtre Cession / Droit au bail
        cessions = ['Toutes'] + sorted(df_filtered[COL_CESSION].unique().tolist())
        selected_cession = st.selectbox("Cession / Droit au bail", cessions, key="cession_filter")
        
        if selected_cession != 'Toutes':
            df_filtered = df_filtered[df_filtered[COL_CESSION] == selected_cession]
            
        st.markdown("<hr style='border-top: 1px solid var(--copper); margin: 15px 0;'>", unsafe_allow_html=True)
        
        # --- FILTRES SLIDERS NUMÉRIQUES ---
        st.markdown("<p style='font-weight: bold; color: white; margin-bottom: 5px;'>Filtres Numériques :</p>", unsafe_allow_html=True)

        # 7. Slider Loyer Annuel
        # Utiliser les valeurs min/max du DF PRÉ-FILTRÉ pour l'affichage de la borne réelle,
        # mais les valeurs TOUT DF pour le curseur initial
        current_loyer_min = int(df_filtered[COL_LOYER].min()) if not df_filtered[COL_LOYER].empty else loyer_min_all
        current_loyer_max = int(df_filtered[COL_LOYER].max()) if not df_filtered[COL_LOYER].empty else loyer_max_all
        
        if loyer_max_all > loyer_min_all:
            loyer_range_tuple = st.slider(
                "Loyer Annuel (€)", 
                min_value=loyer_min_all, 
                max_value=loyer_max_all,
                value=st.session_state["loyer_range"],
                step=1000,
                key="loyer_slider"
            )
            # Appliquer le filtre sur les valeurs non-NaN
            df_filtered = df_filtered[
                (df_filtered[COL_LOYER].isna()) | # Conserver les lots sans loyer spécifié
                ((df_filtered[COL_LOYER] >= loyer_range_tuple[0]) & (df_filtered[COL_LOYER] <= loyer_range_tuple[1]))
            ]
            st.session_state["loyer_range"] = loyer_range_tuple # Sauver le nouvel état

        # 8. Slider Surface GLA
        current_surface_min = int(df_filtered[COL_SURFACE_GLA].min()) if not df_filtered[COL_SURFACE_GLA].empty else surface_min_all
        current_surface_max = int(df_filtered[COL_SURFACE_GLA].max()) if not df_filtered[COL_SURFACE_GLA].empty else surface_max_all

        if surface_max_all > surface_min_all:
            surface_range_tuple = st.slider(
                "Surface GLA (m²)", 
                min_value=surface_min_all, 
                max_value=surface_max_all,
                value=st.session_state["surface_range"],
                step=10,
                key="surface_slider"
            )
            # Appliquer le filtre sur les valeurs non-NaN
            df_filtered = df_filtered[
                (df_filtered[COL_SURFACE_GLA].isna()) | # Conserver les lots sans surface spécifiée
                ((df_filtered[COL_SURFACE_GLA] >= surface_range_tuple[0]) & (df_filtered[COL_SURFACE_GLA] <= surface_range_tuple[1]))
            ]
            st.session_state["surface_range"] = surface_range_tuple # Sauver le nouvel état
            
        st.markdown("<hr style='border-top: 1px solid var(--copper); margin: 15px 0;'>", unsafe_allow_html=True)
        
        # 9. Filtre Extraction
        st.markdown("<p style='font-weight: bold; color: white; margin-bottom: 5px;'>Options Spécifiques:</p>", unsafe_allow_html=True)
        
        if COL_EXTRACTION in df_filtered.columns:
            filter_extraction = st.checkbox("Extraction existante", key="extraction_filter", value=st.session_state.get("extraction_filter", False))
            if filter_extraction:
                df_filtered = df_filtered[df_filtered[COL_EXTRACTION] == 'Oui']
            st.session_state["extraction_filter"] = filter_extraction
        else:
             st.markdown('<p style="color:#aaa; font-size:12px;">(Extraction non disponible)</p>', unsafe_allow_html=True)

        # 10. Filtre Restauration
        if COL_RESTAURATION in df_filtered.columns:
            filter_restauration = st.checkbox("Possibilité Restauration", key="restauration_filter", value=st.session_state.get("restauration_filter", False))
            if filter_restauration:
                df_filtered = df_filtered[df_filtered[COL_RESTAURATION] == 'Oui']
            st.session_state["restauration_filter"] = filter_restauration
        else:
            st.markdown('<p style="color:#aaa; font-size:12px;">(Restauration non disponible)</p>', unsafe_allow_html=True)


        # --- AFFICHAGE DU RÉSULTAT ET BOUTON ---
        st.markdown(f"<p style='margin-top: 20px; color: white;'>**{len(df_filtered)}** lots trouvés.</p>", unsafe_allow_html=True)

        if st.button("Réinitialiser les filtres", key="reset_button"):
            # Remise à zéro des états de session pour le clic et la visibilité
            st.session_state["selected_ref"] = "NO_SELECTION"
            st.session_state["show_right_panel"] = False
            
            # Remise à zéro des widgets de filtre
            st.session_state.region_filter = 'Toutes'
            st.session_state.departement_filter = 'Tous'
            st.session_state.ville_filter = 'Toutes'
            st.session_state.typologie_filter = 'Toutes'
            st.session_state.type_filter = 'Tous'
            st.session_state.cession_filter = 'Toutes'
            st.session_state.loyer_range = (loyer_min_all, loyer_max_all)
            st.session_state.surface_range = (surface_min_all, surface_max_all)
            
            try:
                st.session_state.extraction_filter = False
            except AttributeError:
                pass
            try:
                st.session_state.restauration_filter = False
            except AttributeError:
                pass
            
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True) # fin .left-panel

    # ======== COLONNE CENTRALE (carte) ========
    with col_map:
        st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)

        # Calcul du centre et du zoom
        center_lat, center_lon = 46.603354, 1.888334 # Centre de la France
        zoom_start = 6 

        if not df_filtered.empty:
            valid_lat = df_filtered["_lat_plot"].dropna()
            valid_lon = df_filtered["_lon_plot"].dropna()
            
            if not valid_lat.empty and not valid_lon.empty:
                # Recalculer le centre uniquement si des points sont affichés
                center_lat = valid_lat.mean()
                center_lon = valid_lon.mean()
                
                # Ajuster le zoom selon la sélection géographique
                if selected_region != 'Toutes': zoom_start = 8
                if selected_departement != 'Tous': zoom_start = 10
                if selected_ville != 'Toutes': zoom_start = 12

        # Création de la carte Folium
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom_start,
            control_scale=True,
            tiles='OpenStreetMap',
        )
        
        layer = folium.FeatureGroup(name="Lots Filtrés").add_to(m)
        click_registry = {} # Registre pour lier les coordonnées du clic à la référence

        
        # Ajout des marqueurs à la carte
        for index, r in df_filtered.iterrows():
            if pd.isna(r["_lat_plot"]) or pd.isna(r["_lon_plot"]):
                continue

            # Arrondir les coordonnées à 6 décimales pour la correspondance
            lat = round(float(r["_lat_plot"]), 6) 
            lon = round(float(r["_lon_plot"]), 6)
            raw_label = str(r[COL_REF]).strip()

            # Création de l'icône personnalisée avec un pin et l'étiquette de référence
            # Pin (rond cuivré) + Référence (label blanc à côté)
            icon_html = f"""
            <div class="custom-marker">
                <div class="ref-label">{raw_label}</div>
            </div>
            """
            icon = folium.DivIcon(html=icon_html)

            layer.add_child(
                folium.Marker(
                    location=[lat, lon],
                    icon=icon,
                )
            )

            # Enregistre la référence
            click_registry[(lat, lon)] = raw_label

        # Mettre à jour le registre dans la session state
        st.session_state["click_registry"] = click_registry

        # Affichage de la carte Streamlit
        map_key = f"folium_map_{len(df_filtered)}_{st.session_state['selected_ref']}"
        out = st_folium(m, height="100%", width="100%", key=map_key)

        
        last_clicked_location = None
        clicked_ref = None
        
        # 1. Détecter si Streamlit a renvoyé des informations de clic
        if isinstance(out, dict):
            loc_info = out.get("last_object_clicked")
            # Vérifie si un clic a eu lieu (peu importe où)
            if isinstance(loc_info, dict) and "lat" in loc_info and "lng" in loc_info:
                lat_clicked_raw = float(loc_info["lat"])
                lon_clicked_raw = float(loc_info["lng"])
                
                # Coordonnées arrondies pour la vérification du marqueur
                lat_clicked_rounded = round(lat_clicked_raw, 6)
                lon_clicked_rounded = round(lon_clicked_raw, 6)
                
                last_clicked_location = (lat_clicked_rounded, lon_clicked_rounded)

                # 2. Chercher si ce clic correspond à un marqueur enregistré
                clicked_ref = st.session_state["click_registry"].get(last_clicked_location)
        
        # 3. Gérer la réaction au clic
        is_rerun_needed = False
        
        # CAS A: Clic sur un NOUVEAU marqueur
        if clicked_ref and clicked_ref != st.session_state["selected_ref"]:
            st.session_state["selected_ref"] = clicked_ref
            st.session_state["show_right_panel"] = True
            is_rerun_needed = True # Nécessaire pour afficher le panneau de droite immédiatement
            
        # CAS B: Clic sur le FOND de carte (pas sur le marqueur)
        elif last_clicked_location and not clicked_ref and st.session_state["show_right_panel"]:
            # Rétracter le panneau si on clique en dehors d'un pins ET que le panneau était affiché
            st.session_state["selected_ref"] = "NO_SELECTION"
            st.session_state["show_right_panel"] = False
            is_rerun_needed = True # Nécessaire pour masquer le panneau de droite immédiatement

        # On fait un seul rerun à la fin si nécessaire
        if is_rerun_needed:
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)  # fin .map-wrapper

    # ======== COLONNE DROITE (panneau annonce) ========
    if st.session_state["show_right_panel"] and col_right is not None:
        with col_right:
            render_right_panel(
                st.session_state["selected_ref"],
                df,
                DETAIL_COLUMNS, 
                COL_REF,
                COL_ADDR_FULL,
                COL_GMAPS,
                COL_VILLE,
            )


# -------------------------------------------------
# LANCEMENT DE L'APPLICATION
# -------------------------------------------------

if __name__ == "__main__":
    main()

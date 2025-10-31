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


# LISTE COMPLÈTE DES COLONNES À AFFICHER DE G À AH
DETAIL_COLUMNS = [
    "Emplacement", 
    "Lien Google Maps", 
    "Typologie", 
    "Type", 
    "Cession / Droit au bail", 
    "Nombre de lots", 
    "Surface GLA", 
    "Répartition surface GLA", 
    "Surface utile", 
    "Répartition surface utile", 
    "Loyer annuel", 
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
    "Extraction", 
    "Restauration", 
    "Environnement Commercial", 
    "Commentaires" 
]
COL_GMAPS = "Lien Google Maps"

# Chemin du fichier de données
DATA_FILE_PATH = "data/Liste des lots.xlsx" 
DATA_SHEET_NAME = "Tableau recherche"


# -------------------------------------------------
# CHARGEMENT ET PREPARATION DES DONNEES
# -------------------------------------------------

@st.cache_data
def load_data(file_path: str, sheet_name: str) -> pd.DataFrame:
    """
    Charge le DataFrame et effectue le nettoyage/formatage initial.
    """
    try:
        # NOTE: Le fichier fourni par l'utilisateur était un CSV. 
        # On va tenter de le charger en CSV pour assurer la compatibilité,
        # mais la colonne COL_LAT et COL_LON doit être correctement identifiée.
        
        # Le fichier "Liste des lots Version 2.xlsx - Tableau recherche.csv" est disponible
        # On assume que les en-têtes sont à la première ligne.
        df = pd.read_csv("Liste des lots Version 2.xlsx - Tableau recherche.csv", encoding="utf-8")
        
        required_cols = [COL_LAT, COL_LON, COL_REF]
        for col in required_cols:
            if col not in df.columns:
                # Tentative de normaliser les noms de colonnes si le nom est proche
                st.error(f"La colonne requise '{col}' est manquante.")
                return pd.DataFrame() # Retourne un DataFrame vide en cas d'échec

    except FileNotFoundError:
        # En cas d'échec, on essaie de charger l'original du code, mais on garde le CSV pour la robustesse
        st.error(f"Fichier de données CSV non trouvé: Liste des lots Version 2.xlsx - Tableau recherche.csv.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier de données. Détails: {e}")
        return pd.DataFrame()


    df[COL_LAT] = pd.to_numeric(df[COL_LAT], errors='coerce')
    df[COL_LON] = pd.to_numeric(df[COL_LON], errors='coerce')
    
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

.custom-marker {{
    background-color: var(--logo-blue);
    color: white;
    border: 3px solid var(--copper);
    padding: 4px 8px;
    border-radius: 10px;
    font-weight: bold;
    font-size: 12px;
    text-align: center;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
    cursor: pointer;
    line-height: 1;
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
    
    # Correction: Le bouton doit forcer le rerun pour modifier la structure des colonnes dans main()
    # On utilise un conteneur pour garantir que le bouton est rendu avant le panneau
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

    # ======== COLONNE GAUCHE (panneau de filtres) ========
    # Le panneau gauche contient le filtre et les contrôles
    with col_left:
        st.markdown('<div class="left-panel">', unsafe_allow_html=True)
        
        # 0. Affichage du LOGO
        st.markdown('<div class="logo-container">', unsafe_allow_html=True)
        # On utilise la fonction 'image' de Streamlit avec le chemin d'accès local
        try:
             # Utiliser un chemin local simple. Si l'image n'est pas trouvable, l'utilisateur
             # devra la fournir dans un dossier 'assets'.
             st.image(os.path.join(os.path.dirname(__file__), "assets", "Logo bleu crop.png"), use_column_width=True)
        except Exception:
             # Afficher un placeholder si l'image n'est pas trouvée
             st.markdown('<p style="color:white; font-size:20px; font-weight:bold;">LOGO SMBG</p>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("<h3>Filtres de Recherche</h3>", unsafe_allow_html=True)

        # 1. Filtre Région
        # Utiliser uniquement les régions présentes dans le DF filtré pour les listes déroulantes suivantes
        regions = ['Toutes'] + sorted(df[COL_REGION].unique().tolist())
        selected_region = st.selectbox("Région", regions, key="region_filter")

        df_filtered = df.copy()
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

        # 7. Filtre Extraction
        st.markdown("<p style='font-weight: bold; color: white; margin-bottom: 5px;'>Options Spécifiques:</p>", unsafe_allow_html=True)
        
        # Vérifie si la colonne existe avant d'appliquer le filtre
        if COL_EXTRACTION in df_filtered.columns:
            filter_extraction = st.checkbox("Extraction existante", key="extraction_filter", value=False)
            if filter_extraction:
                df_filtered = df_filtered[df_filtered[COL_EXTRACTION] == 'Oui']
        else:
             st.markdown('<p style="color:#aaa; font-size:12px;">(Extraction non disponible)</p>', unsafe_allow_html=True)

        # 8. Filtre Restauration
        if COL_RESTAURATION in df_filtered.columns:
            filter_restauration = st.checkbox("Possibilité Restauration", key="restauration_filter", value=False)
            if filter_restauration:
                df_filtered = df_filtered[df_filtered[COL_RESTAURATION] == 'Oui']
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
            # Les checkboxes peuvent ne pas exister si les colonnes sont manquantes, on gère l'exception
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

            icon = folium.DivIcon(html=f'<div class="custom-marker" style="white-space:nowrap;">{raw_label}</div>')

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
        # La hauteur de 100% est gérée par le CSS .map-wrapper
        # On utilise une clé unique pour la carte à chaque exécution pour éviter des problèmes de cache
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
        # last_clicked_location est présent (il y a eu un clic)
        # MAIS clicked_ref n'est PAS dans le registre (le clic n'était PAS sur un marqueur)
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
    # N'afficher la colonne droite que si l'état le permet
    # NOTE: col_right est None si show_right_panel est False
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

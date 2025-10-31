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

st.set_page_config(
    page_title="SMBG Carte Immo",
    layout="wide",
)

# Configuration des couleurs et dimensions
LOGO_BLUE = "#05263d"
COPPER = "#b87333"
LEFT_PANEL_WIDTH_PX = 275
RIGHT_PANEL_WIDTH_PX = 275

# URL du logo (Utilisation du fichier uploadé par l'utilisateur)
# J'utilise le dernier logo que vous avez téléversé
LOGO_URL = "image_7f28be.png" 

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
# Les colonnes sont affichées dans l'ordre de cette liste
DETAIL_COLUMNS = [
    "Emplacement", 
    "Lien Google Maps", # H (sera traité comme bouton)
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
    "Commentaires" # AH (sera affiché avec un style spécial)
]
COL_GMAPS = "Lien Google Maps"

# Chemin du fichier (nom du CSV généré par la plateforme à partir de la feuille "Tableau recherche")
# CECI EST LE CHEMIN EXACT À UTILISER DANS CET ENVIRONNEMENT
DATA_SNIPPET_PATH = "Liste des lots Version 2.xlsx - Tableau recherche.csv"
DATA_EXCEL_NAME = "Liste des lots Version 2.xlsx" # Nom du fichier Excel original
DATA_SHEET_NAME = "Tableau recherche" # Nom de la feuille utilisée


# -------------------------------------------------
# CHARGEMENT ET PREPARATION DES DONNEES
# -------------------------------------------------

@st.cache_data
def load_data(file_path: str) -> pd.DataFrame:
    """
    Charge le DataFrame depuis le fichier de données en utilisant le chemin du snippet CSV.
    Utilisation de l'encodage UTF-8 pour gérer les caractères accentués.
    """
    try:
        # Lecture du fichier CSV snippet avec encodage UTF-8 pour garantir les accents
        df = pd.read_csv(file_path, encoding='utf-8')
        
        # Vérification minimale des colonnes critiques
        required_cols = [COL_LAT, COL_LON, COL_REF]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"La colonne requise '{col}' est manquante dans le fichier de données. Veuillez vérifier le contenu de la feuille '{DATA_SHEET_NAME}'.")
                return pd.DataFrame()

    except FileNotFoundError:
        st.error(f"Fichier de données non trouvé. Veuillez vous assurer que le fichier Excel '{DATA_EXCEL_NAME}' contenant la feuille '{DATA_SHEET_NAME}' a été correctement chargé.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier de données. Détails: {e}")
        return pd.DataFrame()


    # Nettoyage des coordonnées (Conversion en numériques et suppression des lignes invalides)
    df[COL_LAT] = pd.to_numeric(df[COL_LAT], errors='coerce')
    df[COL_LON] = pd.to_numeric(df[COL_LON], errors='coerce')
    
    # Suppression des lignes avec des coordonnées manquantes ou invalides pour la carte
    # Nous utilisons une copie pour les modifications pour éviter SettingWithCopyWarning
    df_clean = df.dropna(subset=[COL_LAT, COL_LON]).copy()
    
    # Assurer que la colonne de référence est une chaîne de caractères
    df_clean.loc[:, COL_REF] = df_clean[COL_REF].astype(str).str.strip()

    # Créer les colonnes de coordonnées utilisées pour le tracé (avec des noms uniques)
    df_clean.loc[:, "_lat_plot"] = df_clean[COL_LAT]
    df_clean.loc[:, "_lon_plot"] = df_clean[COL_LON]

    # Remplacer NaN dans les colonnes de filtre spécifiques pour le fonctionnement des selectbox
    df_clean.loc[:, COL_TYPOLOGIE] = df_clean[COL_TYPOLOGIE].fillna('Non spécifié')
    df_clean.loc[:, COL_TYPE] = df_clean[COL_TYPE].fillna('Non spécifié')
    df_clean.loc[:, COL_CESSION] = df_clean[COL_CESSION].fillna('Non spécifié')
    
    # Gestion des valeurs pour Extraction et Restauration
    # On normalise les valeurs binaires pour n'avoir que 'Oui', 'Non' ou 'Non spécifié'
    df_clean.loc[:, COL_EXTRACTION] = df_clean[COL_EXTRACTION].astype(str).str.strip().str.lower().replace({'oui': 'Oui', 'non': 'Non', 'nan': 'Non spécifié', '': 'Non spécifié'})
    df_clean.loc[:, COL_RESTAURATION] = df_clean[COL_RESTAURATION].astype(str).str.strip().str.lower().replace({'oui': 'Oui', 'non': 'Non', 'nan': 'Non spécifié', '': 'Non spécifié'})
    
    # Nettoyage des chaînes de caractères pour les filtres (éviter les espaces indésirables)
    for col in [COL_REGION, COL_DEPARTEMENT, COL_VILLE, COL_TYPOLOGIE, COL_TYPE, COL_CESSION]:
         df_clean.loc[:, col] = df_clean[col].astype(str).str.strip()

    return df_clean

# -------------------------------------------------
# CSS GLOBAL (Injecté directement)
# -------------------------------------------------

GLOBAL_CSS = f"""
<style>
/* Police et couleur globale */
.stApp, .stMarkdown, .stButton, .stDataFrame, div, span, p, td, th, label {{
    font-family: 'Futura', sans-serif !important;
    color: #000;
    font-size: 13px;
    line-height: 1.4;
}}

:root {{
    --logo-blue: {LOGO_BLUE};
    --copper: {COPPER};
}}

/* ===== GÉNÉRALITÉ STREAMLIT ===== */
/* Ajuster l'apparence des widgets pour correspondre au thème */
.stSelectbox > div > div, .stTextInput > div > div, .stCheckbox > label {{
    border-radius: 8px;
    border: 1px solid #ccc;
    padding: 4px 8px;
    background-color: #fff;
    color: var(--logo-blue);
}}

/* Boutons */
.stButton > button {{
    background-color: var(--copper);
    color: white;
    font-weight: bold;
    border-radius: 8px;
    border: none;
    padding: 8px 16px;
    transition: background-color 0.3s;
}}
.stButton > button:hover {{
    background-color: #9e642d; /* Copper plus foncé */
}}
/* Bouton Link (Google Maps) */
.stLinkButton > a {{
    background-color: var(--logo-blue);
    color: white;
    font-weight: bold;
    border-radius: 8px;
    padding: 8px 16px;
    text-decoration: none;
    transition: background-color 0.3s;
}}
.stLinkButton > a:hover {{
    background-color: #031a29; /* Bleu plus foncé */
}}


/* ===== TITRES ET PANNEAUX ===== */
h1, h2, h3 {{
    color: var(--logo-blue);
    font-weight: 700;
    margin-top: 0;
}}
h3 {{
    margin-bottom: 10px;
    font-size: 18px;
}}

/* Conteneur de l'application Streamlit */
.stApp {{
    padding: 0;
}}

/* Cadres des colonnes */
[data-testid="stColumn"] {{
    padding: 0 10px;
}}


/* ===== PANNEAU GAUCHE (filtres) ===== */
.left-panel {{
    background-color: var(--logo-blue);
    color: #fff !important;
    padding: 16px;
    border-radius: 12px;
}}

.left-panel h3, .left-panel label, .left-panel p, .left-panel .stCheckbox > label > div:first-child {{
    color: #fff !important;
}}
.left-panel .stSelectbox > label, .left-panel .stCheckbox > label {{
    font-weight: bold;
}}
/* Rendre le fond des selectbox blanc dans le panneau gauche pour la lisibilité */
.left-panel .stSelectbox > div > div {{
    background-color: #fff;
    color: var(--logo-blue);
}}
.left-panel .stSelectbox > label > div > p {{
    color: #fff !important;
}}
.left-panel .stSelectbox .st-ag {{
    color: var(--logo-blue) !important;
}}


/* ===== CARTE (centre) ===== */
.map-wrapper {{
    /* S'assurer que la carte utilise tout l'espace vertical disponible */
    height: 800px; 
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}}
/* Style du marqueur Folium (pour remplacer l'icône standard) */
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
}}

/* ===== PANNEAU DROIT (détails) ===== */
.right-panel {{
    padding: 16px;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    background-color: #f9f9f9;
    min-height: 800px; /* Alignement avec la carte */
}}

.detail-address {{
    font-weight: 500;
    color: #555;
    margin-bottom: 20px;
}}

.detail-line {{
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px dotted #ccc;
    font-size: 14px;
}}

.detail-label {{
    font-weight: bold;
    color: var(--logo-blue);
    flex-shrink: 0;
    margin-right: 10px;
}}

.detail-value {{
    text-align: right;
    word-break: break-word; /* Permet les longs textes dans le champ */
    color: #333;
}}

.detail-comments {{
    background-color: #fff;
    border: 1px solid #ddd;
    border-left: 4px solid var(--copper);
    padding: 10px;
    border-radius: 4px;
    margin-top: 5px;
    white-space: pre-wrap;
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
    - Retourne None si la valeur est vide/NaN.
    - Retourne "Non spécifié" si la valeur est '/' ou '-'.
    """
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None # Ne pas afficher le champ s'il est vide
    
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
    
    st.markdown('<div class="right-panel">', unsafe_allow_html=True)
    
    if selected_ref and selected_ref != "NO_SELECTION":
        
        # Récupérer les données du lot sélectionné
        # Utiliser .fillna('') pour remplacer les NaN par des chaînes vides
        lot_data = df[df[col_ref] == selected_ref].iloc[0].fillna('') 

        # --- TITRE ET ADRESSE ---
        st.markdown(f"<h3>Détails du Lot : {selected_ref}</h3>", unsafe_allow_html=True)
        st.markdown(f'<p class="detail-address">{lot_data.get(col_addr_full, "Adresse non spécifiée")} ({lot_data.get(col_city, "Ville non spécifiée")})</p>', unsafe_allow_html=True)

        # --- BOUTON GOOGLE MAPS (Traitement spécial pour Lien Google Maps) ---
        gmaps_link = format_value(lot_data.get(col_gmaps))
        if gmaps_link and gmaps_link != "Non spécifié":
             # st.link_button est le widget Streamlit le plus approprié
             st.link_button("Voir sur Google Maps 🗺️", gmaps_link, help="Ouvre le lien Google Maps dans un nouvel onglet", type="primary")
             st.markdown("---") # Séparateur après le bouton
        
        
        # --- AFFICHAGE DES AUTRES CHAMPS DE DÉTAILS ---
        
        # Filtrer la liste des colonnes pour exclure celles déjà traitées (Lien Google Maps et Commentaires)
        data_columns_to_show = [col for col in detail_columns if col != col_gmaps and col != "Commentaires"]
        
        for col_name in data_columns_to_show:
            value = lot_data.get(col_name)
            formatted_value = format_value(value)
            
            # Si format_value retourne None, on n'affiche pas cette ligne (valeur vide)
            if formatted_value is not None:
                # Utilise un format HTML pour un alignement précis Label/Valeur
                st.markdown(
                    f"""
                    <div class="detail-line">
                        <span class="detail-label">{col_name} :</span>
                        <span class="detail-value">{formatted_value}</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        
        # --- AFFICHAGE DES COMMENTAIRES (en bas avec un style dédié) ---
        comments = format_value(lot_data.get("Commentaires"))
        if comments is not None:
             st.markdown('<br><span class="detail-label">Commentaires :</span>', unsafe_allow_html=True)
             st.markdown(f'<p class="detail-comments">{comments}</p>', unsafe_allow_html=True)

    else:
        # Message si aucun lot n'est sélectionné
        st.markdown('<p class="no-selection-msg">Cliquez sur un marqueur sur la carte pour voir les détails du lot.</p>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True) # fin .right-panel


# -------------------------------------------------
# FONCTION PRINCIPALE DE L'APPLICATION
# -------------------------------------------------

def main():
    # Injection du CSS global
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    # Initialisation de l'état de la sélection
    if "selected_ref" not in st.session_state:
        st.session_state["selected_ref"] = "NO_SELECTION"

    # Chargement des données
    df = load_data(DATA_SNIPPET_PATH)
    if df.empty:
        return

    st.title("Catalogue Immobilier : Visualisation Cartographique")

    # Mise en place des colonnes pour la mise en page (GAUCHE - CENTRE - DROITE)
    # Les largeurs sont ajustées pour un meilleur rendu visuel
    col_left, col_map, col_right = st.columns([LEFT_PANEL_WIDTH_PX, 1000, RIGHT_PANEL_WIDTH_PX], gap="medium")


    # ======== COLONNE GAUCHE (panneau de filtres) ========
    with col_left:
        st.markdown('<div class="left-panel">', unsafe_allow_html=True)
        
        # 0. Affichage du LOGO (Utilisation du fichier uploadé)
        st.image(LOGO_URL, use_column_width=True)

        st.markdown("<h3>Filtres de Recherche</h3>", unsafe_allow_html=True)

        # --- FILTRES GÉOGRAPHIQUES (1, 2, 3) ---

        # 1. Filtre Région
        regions = ['Toutes'] + sorted(df[COL_REGION].dropna().unique().tolist())
        selected_region = st.selectbox("Région", regions, key="region_filter")

        # Filtrage par Région
        df_filtered = df.copy()
        if selected_region != 'Toutes':
            df_filtered = df_filtered[df_filtered[COL_REGION] == selected_region]

        # 2. Filtre Département (dépend de la région sélectionnée)
        # S'assurer que les valeurs ne sont pas vides avant de trier
        departements = ['Tous'] + sorted(df_filtered[COL_DEPARTEMENT].dropna().unique().tolist())
        selected_departement = st.selectbox("Département", departements, key="departement_filter")

        # Filtrage par Département
        if selected_departement != 'Tous':
            df_filtered = df_filtered[df_filtered[COL_DEPARTEMENT] == selected_departement]
            
        # 3. Filtre Ville (dépend de la région/département sélectionné)
        villes = ['Toutes'] + sorted(df_filtered[COL_VILLE].dropna().unique().tolist())
        selected_ville = st.selectbox("Ville", villes, key="ville_filter")
        
        # Filtrage par Ville
        if selected_ville != 'Toutes':
            df_filtered = df_filtered[df_filtered[COL_VILLE] == selected_ville]
            
        # --- SÉPARATEUR ---
        st.markdown("<hr style='border-top: 1px solid var(--copper); margin: 15px 0;'>", unsafe_allow_html=True)
        
        # --- NOUVEAUX FILTRES SPÉCIFIQUES (4, 5, 6) ---

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
            
        # --- SÉPARATEUR ---
        st.markdown("<hr style='border-top: 1px solid var(--copper); margin: 15px 0;'>", unsafe_allow_html=True)

        # --- FILTRES BINAIRES (7, 8) ---
        st.markdown("<p style='font-weight: bold; margin-bottom: 5px;'>Options Spécifiques:</p>", unsafe_allow_html=True)
        
        # 7. Filtre Extraction (CORRIGÉ : n'affiche que 'Oui' si la case est cochée)
        filter_extraction = st.checkbox("Extraction existante", key="extraction_filter", value=False)
        if filter_extraction:
            df_filtered = df_filtered[df_filtered[COL_EXTRACTION] == 'Oui']


        # 8. Filtre Restauration (CORRIGÉ : n'affiche que 'Oui' si la case est cochée)
        filter_restauration = st.checkbox("Possibilité Restauration", key="restauration_filter", value=False)
        if filter_restauration:
            df_filtered = df_filtered[df_filtered[COL_RESTAURATION] == 'Oui']


        # --- AFFICHAGE DU RÉSULTAT ET BOUTON ---
        st.markdown(f"<p style='margin-top: 20px;'>**{len(df_filtered)}** lots trouvés.</p>", unsafe_allow_html=True)

        # Bouton de Réinitialisation 
        if st.button("Réinitialiser les filtres", key="reset_button"):
            st.session_state["selected_ref"] = "NO_SELECTION"
            # Réinitialiser les selectbox
            st.session_state.region_filter = 'Toutes'
            st.session_state.departement_filter = 'Tous'
            st.session_state.ville_filter = 'Toutes'
            st.session_state.typologie_filter = 'Toutes'
            st.session_state.type_filter = 'Tous'
            st.session_state.cession_filter = 'Toutes'
            # Réinitialiser les checkbox
            st.session_state.extraction_filter = False
            st.session_state.restauration_filter = False
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True) # fin .left-panel

    # ======== COLONNE CENTRALE (carte) ========
    with col_map:
        st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)

        # Calculer le centre de la carte et le zoom
        if not df_filtered.empty:
            center_lat = df_filtered["_lat_plot"].mean()
            center_lon = df_filtered["_lon_plot"].mean()
        else:
            center_lat, center_lon = 46.603354, 1.888334 # Centre de la France (Par défaut)
        
        zoom_start = 6 
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
            # Conversion en float nécessaire pour folium
            lat = float(r["_lat_plot"]) 
            lon = float(r["_lon_plot"])
            raw_label = str(r[COL_REF]).strip()

            # Utilisation de la classe CSS .custom-marker pour le style
            icon = folium.DivIcon(html=f'<div class="custom-marker" style="white-space:nowrap;">{raw_label}</div>')

            layer.add_child(
                folium.Marker(
                    location=[lat, lon],
                    icon=icon,
                )
            )

            # Enregistre la référence pour la détection du clic
            # Arrondir les coordonnées permet de s'assurer que le clic Streamlit correspond au marqueur Folium
            click_registry[(round(lat, 6), round(lon, 6))] = raw_label

        # Affichage de la carte Streamlit
        out = st_folium(m, height=800, width=None) 

        clicked_ref = None
        if isinstance(out, dict):
            loc_info = out.get("last_object_clicked")
            # Vérifie si un marqueur a été cliqué
            if isinstance(loc_info, dict) and "lat" in loc_info and "lng" in loc_info:
                lat_clicked = round(float(loc_info["lat"]), 6)
                lon_clicked = round(float(loc_info["lng"]), 6)
                clicked_ref = click_registry.get((lat_clicked, lon_clicked))

        # Met à jour l'état de la session si une référence a été cliquée
        if clicked_ref:
            st.session_state["selected_ref"] = clicked_ref

        st.markdown('</div>', unsafe_allow_html=True)  # fin .map-wrapper

    # ======== COLONNE DROITE (panneau annonce) ========
    with col_right:
        render_right_panel(
            st.session_state["selected_ref"],
            df,
            DETAIL_COLUMNS, # Liste des colonnes de G à AH
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

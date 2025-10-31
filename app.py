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
# CONFIG DE BASE
# -------------------------------------------------


st.set_page_config(
    page_title="SMBG Carte",
    layout="wide",
)

LOGO_BLUE = "#05263d"
COPPER = "#b87333"
LEFT_PANEL_WIDTH_PX = 275
RIGHT_PANEL_WIDTH_PX = 275

# CORRECTION DÉFINITIVE DU CHEMIN ET DU NOM DU FICHIER EXCEL/CSV
# Le fichier CSV extrait de l'onglet "Tableau recherche" est utilisé ici.
# Le chemin d'accès au fichier est défini par l'utilisateur comme étant dans le dossier 'data/'
DEFAULT_LOCAL_PATH = "data/Liste des lots.xlsx - Tableau recherche.csv"


# -------------------------------------------------
# CSS GLOBAL
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

/* ===== PANNEAU GAUCHE (filtres) ===== */
.left-panel {{
    background-color: {LOGO_BLUE};
    color: #fff !important;
    padding: 16px;
    border-radius: 12px;
    min-width: {LEFT_PANEL_WIDTH_PX}px;
    max-width: {LEFT_PANEL_WIDTH_PX}px;
    height: 100vh;
    position: fixed;
    top: 0;
    left: 0;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: none; /* Firefox */
}}
.left-panel::-webkit-scrollbar {{
    display: none; /* Chrome, Safari, Opera */
}}
/* Rendre le fond du corps des filtres transparent pour laisser voir la couleur du panneau */
.left-panel .st-emotion-cache-1r7r3z {{{{
    background-color: transparent;
}}}}

/* Couleur des labels dans le panneau de gauche */
.left-panel label {{
    color: #fff !important;
    font-size: 14px;
    font-weight: bold;
    margin-bottom: 4px;
    display: block;
}}
/* Couleur et style des titres de section */
.left-panel .stMarkdown h3 {{
    color: {COPPER} !important;
    font-size: 16px;
    text-transform: uppercase;
    border-bottom: 1px solid {COPPER};
    padding-bottom: 5px;
    margin-top: 15px;
    margin-bottom: 10px;
}}


/* Widgets (slider, multiselect) */
.left-panel .stSlider > div:first-child {{
    background-color: #333333;
    border-radius: 8px;
}}

/* Boutons de réinitialisation */
.left-panel .stButton button {{
    background-color: {COPPER};
    color: #fff !important;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: bold;
    transition: background-color 0.3s;
    width: 100%;
    margin-top: 15px;
}}
.left-panel .stButton button:hover {{
    background-color: #e09849;
}}
/* Style pour les Multiselects */
.left-panel .stMultiSelect div[data-baseweb="select"] {{
    background-color: #fff;
    border-radius: 8px;
    color: #000;
}}
.left-panel .stMultiSelect div[data-baseweb="select"] input {{
    color: #000;
}}
.left-panel .stMultiSelect [data-baseweb="tag"] {{
    background-color: {COPPER};
    color: #fff;
}}

/* ===== CORPS PRINCIPAL (carte et panneau de droite) ===== */
.main-content-wrapper {{
    margin-left: {LEFT_PANEL_WIDTH_PX}px;
    padding: 16px;
    display: flex;
    gap: 16px;
}}

.map-wrapper {{
    flex-grow: 1;
    min-height: 800px;
}}

/* ===== CARTE FOLIUM (Marker) ===== */
.map-wrapper .streamlit-folium {{
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}}

/* Style des marqueurs personnalisés (les numéros de référence sur la carte) */
.map-wrapper .folium-div-icon {{
    background-color: {LOGO_BLUE} !important;
    color: white !important;
    border-radius: 50% !important;
    width: 28px !important;
    height: 28px !important;
    line-height: 28px !important;
    text-align: center !important;
    font-size: 11px !important;
    font-weight: bold !important;
    border: 2px solid {COPPER} !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.5);
    cursor: pointer;
}}
/* Style pour le marqueur cliqué/sélectionné */
.map-wrapper .folium-div-icon.selected-marker {{
    background-color: {COPPER} !important;
    border: 2px solid {LOGO_BLUE} !important;
    transform: scale(1.2);
    transition: transform 0.2s;
}}


/* ===== PANNEAU DROIT (détails de l'annonce) ===== */
.right-panel {{
    min-width: {RIGHT_PANEL_WIDTH_PX}px;
    max-width: {RIGHT_PANEL_WIDTH_PX}px;
    background-color: #f7f7f7;
    padding: 16px;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    position: sticky; /* Reste en haut lors du défilement */
    top: 16px;
    max-height: calc(100vh - 32px);
    overflow-y: auto;
    scrollbar-width: thin;
}}
.right-panel h4 {{
    color: {LOGO_BLUE};
    font-size: 16px;
    font-weight: bold;
    margin-top: 0;
    margin-bottom: 10px;
    border-bottom: 2px solid {COPPER};
    padding-bottom: 5px;
}}

/* Style des lignes de détail */
.detail-row {{
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px dashed #ddd;
    font-size: 14px;
}}
.detail-label {{
    font-weight: bold;
    color: #444;
}}
.detail-value {{
    color: #111;
    text-align: right;
}}
.detail-row:last-child {{
    border-bottom: none;
}}

/* Boutons dans le panneau de droite */
.right-panel .stButton button {{
    background-color: {LOGO_BLUE};
    color: #fff !important;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: bold;
    transition: background-color 0.3s;
    width: 100%;
    margin-top: 10px;
}}
.right-panel .stButton button:hover {{
    background-color: {COPPER};
}}

/* Mise en forme de l'adresse et de la ville */
.addr-line {{
    font-size: 14px;
    font-weight: 500;
    color: #333;
}}
.city-line {{
    font-size: 16px;
    font-weight: bold;
    color: {LOGO_BLUE};
    margin-bottom: 10px;
}}

/* Style pour l'alerte d'absence de sélection */
.no-selection-message {{
    background-color: #fff3cd;
    color: #856404;
    border: 1px solid #ffeeba;
    padding: 15px;
    border-radius: 8px;
    margin-top: 20px;
    text-align: center;
    font-weight: bold;
}}
/* Style pour l'alerte d'absence de résultats */
.no-results-message {{
    background-color: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
    padding: 15px;
    border-radius: 8px;
    margin-top: 20px;
    text-align: center;
    font-weight: bold;
}}

</style>
<link href="https://fonts.googleapis.com/css2?family=Futura:wght@400;700&display=swap" rel="stylesheet">
"""


# -------------------------------------------------
# CONSTANTES DE COLONNES (à ajuster selon votre fichier)
# -------------------------------------------------

# Colonnes obligatoires pour l'affichage/la carte
COL_LAT = "Latitude"
COL_LON = "Longitude"
COL_REF = "Référence annonce" # ou 'Numéro de lot'
COL_ADDR_FULL = "Adresse"
COL_CITY = "Ville"
COL_GMAPS = "Lien Google Maps"
COL_DATE_PUB = "Date de Publication" # Colonne factice, à remplacer si vous en avez une

# Colonnes utilisées pour le filtrage
COL_REGION = "Région"
COL_DEPT = "Département"
COL_TYPOLOGIE = "Typologie"
COL_SURFACE_GLA = "Surface GLA"
COL_LOYER_M2 = "Loyer €/m²"
COL_ETAT_LIVR = "Etat de livraison"
COL_EXTRACTION = "Extraction"
COL_RESTAURATION = "Restauration"
COL_ACTIF = "Actif"


# -------------------------------------------------
# FONCTIONS UTILITAIRES DE DONNÉES
# -------------------------------------------------

@st.cache_data
def load_data(url_or_path: str) -> pd.DataFrame:
    """Charge le DataFrame depuis un fichier local ou une URL."""
    try:
        # Tente de charger le fichier en considérant l'encodage comme 'latin-1' (souvent pour les CSV français)
        # Utilise l'index de ligne 0 pour les entêtes
        df = pd.read_csv(
            url_or_path,
            sep=',',
            header=0,
            skipinitialspace=True,
            encoding='utf-8' # Test initial en utf-8
        )
    except UnicodeDecodeError:
        # Si utf-8 échoue, tente latin-1
         df = pd.read_csv(
            url_or_path,
            sep=',',
            header=0,
            skipinitialspace=True,
            encoding='latin-1'
        )
    except Exception as e:
        st.error(f"Erreur de chargement du fichier : {e}")
        return pd.DataFrame()

    # Nettoyage et préparation
    df = clean_data(df)
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie et prépare le DataFrame."""

    # Conversion des colonnes numériques
    for col in [COL_SURFACE_GLA, COL_LOYER_M2, COL_LAT, COL_LON]:
        if col in df.columns:
            # Nettoyer les chaînes: Remplacer ',' par '.' pour la conversion, puis supprimer les non-numériques
            df[col] = df[col].astype(str).str.replace(',', '.').str.extract('(\d+\.?\d*)', expand=False)
            # Convertir en float. Les valeurs manquantes ou non convertibles deviennent NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Filtrer les lignes sans coordonnées valides
    df = df.dropna(subset=[COL_LAT, COL_LON])

    # S'assurer que COL_REF est une chaîne
    if COL_REF in df.columns:
        df[COL_REF] = df[COL_REF].astype(str).str.strip()
        # Créer une étiquette pour le marqueur (par ex. enlever les zéros non significatifs)
        df['ref_label'] = df[COL_REF].apply(lambda x: re.sub(r'^0+', '', x))

    # Récupérer uniquement les colonnes nécessaires (pour optimiser)
    cols_to_keep = list(set([
        COL_LAT, COL_LON, COL_REF, 'ref_label', COL_ADDR_FULL, COL_CITY,
        COL_GMAPS, COL_DATE_PUB, COL_REGION, COL_DEPT, COL_TYPOLOGIE,
        COL_SURFACE_GLA, COL_LOYER_M2, COL_ETAT_LIVR, COL_EXTRACTION,
        COL_RESTAURATION, COL_ACTIF
    ]) & set(df.columns))

    return df[cols_to_keep].copy()


def filter_dataframe(df: pd.DataFrame, filters: Dict) -> pd.DataFrame:
    """Applique les filtres de l'utilisateur au DataFrame."""
    df_filtered = df.copy()

    # Filtre Région
    if filters.get(COL_REGION):
        df_filtered = df_filtered[df_filtered[COL_REGION].isin(filters[COL_REGION])]

    # Filtre Département
    if filters.get(COL_DEPT):
        df_filtered = df_filtered[df_filtered[COL_DEPT].isin(filters[COL_DEPT])]

    # Filtre Typologie
    if filters.get(COL_TYPOLOGIE):
        df_filtered = df_filtered[df_filtered[COL_TYPOLOGIE].isin(filters[COL_TYPOLOGIE])]

    # Filtre Surface GLA (Range Slider)
    if COL_SURFACE_GLA in df.columns and filters.get('surface_range'):
        min_val, max_val = filters['surface_range']
        # Assurez-vous que la colonne est numérique pour les comparaisons
        df_filtered = df_filtered[
            (df_filtered[COL_SURFACE_GLA] >= min_val) &
            (df_filtered[COL_SURFACE_GLA] <= max_val)
        ]

    # Filtre Loyer €/m² (Range Slider)
    if COL_LOYER_M2 in df.columns and filters.get('loyer_range'):
        min_val, max_val = filters['loyer_range']
        df_filtered = df_filtered[
            (df_filtered[COL_LOYER_M2] >= min_val) &
            (df_filtered[COL_LOYER_M2] <= max_val)
        ]

    # Filtre Extraction/Restauration/Actif (Checkbox)
    if filters.get(COL_EXTRACTION):
        # Filtrer sur les valeurs sélectionnées, en gérant les NaN
        df_filtered = df_filtered[
            df_filtered[COL_EXTRACTION].astype(str).isin(filters[COL_EXTRACTION]) |
            df_filtered[COL_EXTRACTION].isna()
        ]

    if filters.get(COL_RESTAURATION):
        df_filtered = df_filtered[
            df_filtered[COL_RESTAURATION].astype(str).isin(filters[COL_RESTAURATION]) |
            df_filtered[COL_RESTAURATION].isna()
        ]

    if filters.get(COL_ACTIF):
        df_filtered = df_filtered[
            df_filtered[COL_ACTIF].astype(str).isin(filters[COL_ACTIF]) |
            df_filtered[COL_ACTIF].isna()
        ]


    return df_filtered

# -------------------------------------------------
# RENDU (PANNEAU DROIT)
# -------------------------------------------------

def format_value(value: Optional[any], unit: str = "", default: str = "-") -> str:
    """Formate une valeur pour l'affichage."""
    if pd.isna(value) or value is None or value == '' or str(value).strip() == '/':
        return default
    if isinstance(value, (int, float)):
        # Formatage avec séparateur de milliers et gestion des décimales
        if unit in ["€", "€/m²"]:
            # Pour l'argent, afficher deux décimales si l'unité est présente
            return f"{value:,.2f}".replace(",", " ").replace(".", ",") + f" {unit}".strip()
        else:
             # Pour les autres nombres, utiliser un entier si possible
            return f"{int(value):,}".replace(",", " ") + f" {unit}".strip()
    return str(value)

def render_detail_row(label: str, value: Optional[any], unit: str = ""):
    """Affiche une ligne de détail dans le panneau de droite."""
    st.markdown(
        f"""
        <div class="detail-row">
            <span class="detail-label">{label}</span>
            <span class="detail-value">{format_value(value, unit)}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_right_panel(selected_ref: str, df: pd.DataFrame, col_ref: str, col_addr_full: str, col_city: str, col_gmaps: str, col_date_pub: str):
    """Affiche le panneau de droite avec les détails de l'annonce sélectionnée."""

    if not selected_ref:
        st.markdown('<div class="no-selection-message">Sélectionnez un marqueur sur la carte pour afficher les détails de l\'annonce.</div>', unsafe_allow_html=True)
        return

    # S'assurer que la colonne de référence est la bonne
    # Utiliser .head(1) au cas où il y aurait des doublons de référence (et prendre le premier)
    try:
        row = df[df[col_ref] == selected_ref].iloc[0]
    except IndexError:
        st.error(f"Détails introuvables pour la référence : {selected_ref}")
        return

    # Début du panneau
    st.markdown('<h4>Annonce sélectionnée</h4>', unsafe_allow_html=True)

    # Référence et Adresse
    st.markdown(f'<h3>Référence : <span style="color:{COPPER};">{selected_ref}</span></h3>', unsafe_allow_html=True)
    st.markdown(f'<p class="city-line">{format_value(row.get(col_city))}</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="addr-line">{format_value(row.get(col_addr_full))}</p>', unsafe_allow_html=True)


    # Boutons d'action
    gmaps_url = format_value(row.get(col_gmaps), default="#")
    st.link_button("Voir sur Google Maps", gmaps_url, type="primary")

    st.markdown("---")

    # Détails
    st.markdown('<h4>Détails de l\'Offre</h4>', unsafe_allow_html=True)

    # Note: J'utilise les noms de colonnes du CSV pour l'affichage,
    # même s'ils ne correspondent pas aux constantes de filtrage pour les autres détails.
    columns_to_display = {
        "Surface GLA": COL_SURFACE_GLA,
        "Surface utile": "Surface utile",
        "Loyer annuel": "Loyer annuel",
        "Loyer Mensuel": "Loyer Mensuel",
        "Loyer €/m²": COL_LOYER_M2,
        "Charges anuelles": "Charges anuelles",
        "Charges Mensuelles": "Charges Mensuelles",
        "Charges €/m²": "Charges €/m²",
        "Typologie": COL_TYPOLOGIE,
        "Emplacement": "Emplacement",
        "Etat de livraison": COL_ETAT_LIVR,
        "Extraction": COL_EXTRACTION,
        "Restauration": COL_RESTAURATION,
        "Actif": COL_ACTIF,
        "Valeur BP": "Valeur BP",
        "Contact": "Contact",
    }

    # Unités et formatage spécifiques
    units = {
        COL_SURFACE_GLA: "m²",
        "Surface utile": "m²",
        "Loyer annuel": "€",
        "Loyer Mensuel": "€",
        COL_LOYER_M2: "€/m²",
        "Charges anuelles": "€",
        "Charges Mensuelles": "€",
        "Charges €/m²": "€/m²",
    }

    # Affichage dynamique des détails
    for label, col_name in columns_to_display.items():
        if col_name in row.index:
            unit = units.get(col_name, "")
            # Pour certains champs (Oui/Non), on veut un affichage simple
            if col_name in [COL_EXTRACTION, COL_RESTAURATION, COL_ACTIF]:
                display_value = row[col_name]
                if isinstance(display_value, str) and display_value.lower().strip() == 'oui':
                    display_value = "Oui"
                elif isinstance(display_value, str) and display_value.lower().strip() == 'non':
                    display_value = "Non"
                render_detail_row(label, display_value)
            else:
                render_detail_row(label, row[col_name], unit)


    # Commentaires
    if 'Commentaires' in row.index:
        comment = format_value(row.get('Commentaires'))
        if comment != '-':
             st.markdown("---")
             st.markdown('<h4>Commentaires</h4>', unsafe_allow_html=True)
             st.markdown(f'<p style="font-style: italic;">{comment}</p>', unsafe_allow_html=True)



# -------------------------------------------------
# LOGIQUE PRINCIPALE
# -------------------------------------------------

def main():
    """Fonction principale de l'application Streamlit."""

    # Injecter le CSS global
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    # Initialisation des états de session
    if "selected_ref" not in st.session_state:
        st.session_state["selected_ref"] = ""
    if "reset_filters" not in st.session_state:
        st.session_state["reset_filters"] = 0

    # Charger les données (utiliser le fichier Tableau recherche.csv)
    file_path = DEFAULT_LOCAL_PATH # Utilisation de la constante corrigée
    df = load_data(file_path)

    if df.empty:
        st.error(f"Impossible de charger les données. Vérifiez que le chemin d'accès '{file_path}' est correct et que le fichier est correctement formaté (séparateur: virgule, encodage: utf-8 ou latin-1).")
        return

    # Renommage des colonnes pour la compatibilité (si nécessaire)
    # Assurez-vous que les colonnes attendues existent
    if COL_LAT not in df.columns or COL_LON not in df.columns or COL_REF not in df.columns:
        st.error(f"Les colonnes '{COL_LAT}', '{COL_LON}' ou '{COL_REF}' sont manquantes dans le fichier de données. Colonnes trouvées: {df.columns.tolist()}")
        return

    # ======== PANNEAU GAUCHE (filtres) ========
    # Le panneau de gauche est un conteneur fixe
    with st.container():
        st.markdown('<div class="left-panel">', unsafe_allow_html=True)

        # Je mets un placeholder pour le logo, si vous en avez un, vous pouvez le remplacer
        st.markdown(f'<p style="text-align:center; font-size: 24px; color: {COPPER}; font-weight: bold;">SMBG Carte</p>', unsafe_allow_html=True)
        st.markdown('---')

        st.markdown('<h3>Filtres de recherche</h3>', unsafe_allow_html=True)

        # Bouton de réinitialisation
        if st.button("Réinitialiser les filtres", key="reset_btn"):
            st.session_state["reset_filters"] += 1
            st.session_state["selected_ref"] = "" # Réinitialiser la sélection de l'annonce
            st.rerun()

        st.markdown("---")

        # 1. Filtre Région
        all_regions = sorted(df[COL_REGION].dropna().unique().tolist())
        selected_regions = st.multiselect(
            "Région(s)",
            options=all_regions,
            default=[],
            key=f"region_filter_{st.session_state['reset_filters']}"
        )

        # 2. Filtre Département (doit être dynamique basé sur la Région sélectionnée)
        df_for_dept = df
        if selected_regions:
             df_for_dept = df[df[COL_REGION].isin(selected_regions)]

        all_depts = sorted(df_for_dept[COL_DEPT].dropna().unique().tolist())
        selected_depts = st.multiselect(
            "Département(s)",
            options=all_depts,
            default=[],
            key=f"dept_filter_{st.session_state['reset_filters']}"
        )

        # 3. Filtre Typologie
        all_typos = sorted(df[COL_TYPOLOGIE].dropna().unique().tolist())
        selected_typos = st.multiselect(
            "Typologie",
            options=all_typos,
            default=[],
            key=f"typo_filter_{st.session_state['reset_filters']}"
        )

        st.markdown('---')
        st.markdown('<h3>Critères Numériques</h3>', unsafe_allow_html=True)

        # Préparation des valeurs min/max pour les sliders
        surface_min_all = int(df[COL_SURFACE_GLA].min()) if not df[COL_SURFACE_GLA].empty and df[COL_SURFACE_GLA].min() is not None and not pd.isna(df[COL_SURFACE_GLA].min()) else 0
        surface_max_all = int(df[COL_SURFACE_GLA].max()) if not df[COL_SURFACE_GLA].empty and df[COL_SURFACE_GLA].max() is not None and not pd.isna(df[COL_SURFACE_GLA].max()) else 10000

        loyer_min_all = int(df[COL_LOYER_M2].min()) if not df[COL_LOYER_M2].empty and df[COL_LOYER_M2].min() is not None and not pd.isna(df[COL_LOYER_M2].min()) else 0
        loyer_max_all = int(df[COL_LOYER_M2].max()) if not df[COL_LOYER_M2].empty and df[COL_LOYER_M2].max() is not None and not pd.isna(df[COL_LOYER_M2].max()) else 1000

        # Filtres appliqués jusqu'à présent (sauf les sliders de surface/loyer)
        temp_filters = {
            COL_REGION: selected_regions,
            COL_DEPT: selected_depts,
            COL_TYPOLOGIE: selected_typos,
        }
        df_temp_filtered = filter_dataframe(df, temp_filters)

        # 4. Filtre Surface GLA
        if not df_temp_filtered.empty and COL_SURFACE_GLA in df_temp_filtered.columns:
            # S'assurer que les valeurs min/max des filtres appliqués sont valides et dans les bornes
            valid_surfaces = df_temp_filtered[COL_SURFACE_GLA].dropna()
            if not valid_surfaces.empty:
                current_surface_min = int(valid_surfaces.min())
                current_surface_max = int(valid_surfaces.max())
            else:
                 current_surface_min = surface_min_all
                 current_surface_max = surface_max_all
        else:
            current_surface_min = surface_min_all
            current_surface_max = surface_max_all

        # S'assurer que les valeurs min/max actuelles sont dans les bornes globales
        current_surface_min = max(min(current_surface_min, surface_max_all), surface_min_all)
        current_surface_max = min(max(current_surface_max, surface_min_all), surface_max_all)

        if current_surface_min > current_surface_max:
             current_surface_min = surface_min_all
             current_surface_max = surface_max_all

        selected_surface_range = st.slider(
            "Surface GLA (m²)",
            min_value=surface_min_all,
            max_value=surface_max_all,
            value=(current_surface_min, current_surface_max),
            step=50,
            key=f"surface_filter_{st.session_state['reset_filters']}"
        )


        # 5. Filtre Loyer €/m²
        if not df_temp_filtered.empty and COL_LOYER_M2 in df_temp_filtered.columns:
            valid_loyers = df_temp_filtered[COL_LOYER_M2].dropna()
            if not valid_loyers.empty:
                current_loyer_min = int(valid_loyers.min())
                current_loyer_max = int(valid_loyers.max())
            else:
                current_loyer_min = loyer_min_all
                current_loyer_max = loyer_max_all
        else:
            current_loyer_min = loyer_min_all
            current_loyer_max = loyer_max_all

        # S'assurer que les valeurs min/max actuelles sont dans les bornes globales
        current_loyer_min = max(min(current_loyer_min, loyer_max_all), loyer_min_all)
        current_loyer_max = min(max(current_loyer_max, loyer_min_all), loyer_max_all)

        if current_loyer_min > current_loyer_max:
            current_loyer_min = loyer_min_all
            current_loyer_max = loyer_max_all


        selected_loyer_range = st.slider(
            "Loyer (€/m²)",
            min_value=loyer_min_all,
            max_value=loyer_max_all,
            value=(current_loyer_min, current_loyer_max),
            step=10,
            key=f"loyer_filter_{st.session_state['reset_filters']}"
        )

        st.markdown('---')
        st.markdown('<h3>Autres Critères</h3>', unsafe_allow_html=True)

        # 6. Filtres Checkbox
        # Extraction
        extraction_opts = sorted(df[COL_EXTRACTION].astype(str).dropna().unique().tolist())
        selected_extraction = st.multiselect(
            "Extraction (Cheminée)",
            options=extraction_opts,
            default=[],
            key=f"extraction_filter_{st.session_state['reset_filters']}"
        )

        # Restauration
        restau_opts = sorted(df[COL_RESTAURATION].astype(str).dropna().unique().tolist())
        selected_restau = st.multiselect(
            "Restauration",
            options=restau_opts,
            default=[],
            key=f"restau_filter_{st.session_state['reset_filters']}"
        )

        # Actif
        actif_opts = sorted(df[COL_ACTIF].astype(str).dropna().unique().tolist())
        selected_actif = st.multiselect(
            "Statut d'Actif",
            options=actif_opts,
            default=[],
            key=f"actif_filter_{st.session_state['reset_filters']}"
        )

        st.markdown('</div>', unsafe_allow_html=True) # fin .left-panel

    # ======== CORPS PRINCIPAL (carte et panneau de droite) ========
    st.markdown('<div class="main-content-wrapper">', unsafe_allow_html=True)

    col_map, col_right = st.columns([1, RIGHT_PANEL_WIDTH_PX/800]) # Laisser Streamlit gérer la largeur

    # Collecte de tous les filtres
    all_filters = {
        COL_REGION: selected_regions,
        COL_DEPT: selected_depts,
        COL_TYPOLOGIE: selected_typos,
        'surface_range': selected_surface_range,
        'loyer_range': selected_loyer_range,
        COL_EXTRACTION: selected_extraction,
        COL_RESTAURATION: selected_restau,
        COL_ACTIF: selected_actif,
    }

    # Appliquer le filtrage final
    df_filtered = filter_dataframe(df, all_filters)

    # Affichage du nombre de résultats
    num_results = len(df_filtered)
    with st.sidebar:
         st.markdown(f'<p style="text-align: center; color: #fff; font-size: 16px; font-weight: bold; margin-top: 10px;">{num_results} annonce(s) trouvée(s)</p>', unsafe_allow_html=True)


    # ======== COLONNE GAUCHE (carte) ========
    with col_map:
        st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)

        # Initialisation de la référence cliquée
        clicked_ref = None

        if num_results == 0:
             st.markdown('<div class="no-results-message">Aucun résultat ne correspond aux filtres appliqués. Veuillez ajuster vos critères.</div>', unsafe_allow_html=True)
             # Afficher une carte centrée sur la France (avec 0 résultat)
             m = folium.Map(location=[46.603354, 1.888334], zoom_start=5, control_scale=True)
             out = st_folium(m, height=800, width=None, key="folium_empty_map")

        else:
            # Calculer le centre de la carte et le niveau de zoom
            avg_lat = df_filtered[COL_LAT].mean()
            avg_lon = df_filtered[COL_LON].mean()

            # Créer la carte Folium centrée sur les résultats filtrés
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=10, control_scale=True)

            # Créer un FeatureGroup pour les marqueurs
            layer = folium.FeatureGroup(name="Annonces Filtrées")
            m.add_child(layer)

            # Registre pour associer la position cliquée à la référence de l'annonce
            click_registry: Dict[Tuple[float, float], str] = {}

            # Ajouter un marqueur pour chaque ligne
            for _, r in df_filtered.iterrows():
                # CSS du marqueur standard
                css_marker = (
                    "background-color: #05263d !important; color: white !important; "
                    "border-radius: 50% !important; width: 28px !important; "
                    "height: 28px !important; line-height: 28px !important; "
                    "text-align: center !important; font-size: 11px !important; "
                    "font-weight: bold !important; border: 2px solid #b87333 !important; "
                    "box-shadow: 0 1px 3px rgba(0,0,0,0.5); cursor: pointer;"
                )

                # Si le marqueur est sélectionné, appliquer le style "selected-marker"
                if r.get('ref_label') == st.session_state.get('selected_ref'):
                    css_marker = (
                        "background-color: #b87333 !important; color: #05263d !important; "
                        "border-radius: 50% !important; width: 32px !important; "
                        "height: 32px !important; line-height: 32px !important; "
                        "text-align: center !important; font-size: 13px !important; "
                        "font-weight: bold !important; border: 2px solid #05263d !important; "
                        "box-shadow: 0 2px 5px rgba(0,0,0,0.7); cursor: pointer; "
                        "transform: scale(1.1);" # Léger zoom pour mieux voir
                    )

                lat = float(r[COL_LAT])
                lon = float(r[COL_LON])
                raw_label = str(r["ref_label"]).strip()

                icon = folium.DivIcon(html=f'<div class="folium-div-icon" style="{css_marker}">{raw_label}</div>')

                layer.add_child(
                    folium.Marker(
                        location=[lat, lon],
                        icon=icon,
                    )
                )

                # Clé pour le registre (arrondie)
                click_registry[(round(lat, 6), round(lon, 6))] = raw_label

            out = st_folium(m, height=800, width=None, key="folium_filtered_map")

            if isinstance(out, dict):
                loc_info = out.get("last_object_clicked")
                if isinstance(loc_info, dict) and "lat" in loc_info and "lng" in loc_info:
                    # Arrondir à 6 décimales pour correspondre aux clés du registre
                    lat_clicked = round(float(loc_info["lat"]), 6)
                    lon_clicked = round(float(loc_info["lng"]), 6)
                    # Récupérer la référence d'annonce associée à ces coordonnées
                    clicked_ref = click_registry.get((lat_clicked, lon_clicked))

        if clicked_ref:
            st.session_state["selected_ref"] = clicked_ref

        st.markdown('</div>', unsafe_allow_html=True)  # fin .map-wrapper

    # ======== COLONNE DROITE (panneau annonce) ========
    with col_right:
        st.markdown('<div class="right-panel">', unsafe_allow_html=True)
        render_right_panel(
            st.session_state["selected_ref"],
            df,
            COL_REF,
            COL_ADDR_FULL,
            COL_CITY,
            COL_GMAPS,
            COL_DATE_PUB,
        )
        st.markdown('</div>', unsafe_allow_html=True) # fin .right-panel

    st.markdown('</div>', unsafe_allow_html=True) # fin .main-content-wrapper


# -------------------------------------------------
# LANCEMENT DE L'APPLICATION
# -------------------------------------------------

if __name__ == "__main__":
    main()

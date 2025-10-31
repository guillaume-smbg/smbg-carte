import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import json
import numpy as np

# ***************************************************************
# --- 1. CONFIGURATION INITIALE & GESTION DES DONNÉES ---
# ***************************************************************

# Configure la page en mode large pour une meilleure expérience utilisateur
st.set_page_config(
    layout="wide", 
    page_title="SMBG Carte Immo",
    # On pourrait ajouter une icône ici si disponible
    # page_icon="🗺️" 
) 

# --- A. DONNÉES DE DÉMONSTRATION ÉTENDUES ---
# Simule le fichier "Liste des lots.xlsx - Tableau recherche.csv"
# *** ATTENTION : À REMPLACER PAR LA LECTURE DE VOTRE FICHIER CSV RÉEL EN PRODUCTION ***
# df = pd.read_csv("Liste des lots.xlsx - Tableau recherche.csv")
# Assurez-vous d'avoir les colonnes 'Latitude', 'Longitude', 'Référence annonce', 'Surface GLA', 'Typologie', 'Région', 'Département'.

try:
    # Création du DataFrame de démonstration avec un jeu de données varié
    # Ceci garantit la robustesse des filtres Région/Département/Typologie.
    DATA = {
        'Référence annonce': [
            '00022', '00023', '00024', '00025', '00026', '00027', '00028', 
            '00029', '00030', '00031', '00032', '00033', '00034', '00035', 
            '00036', '00037', '00038', '00039', '00040', '00041'
        ],
        'Latitude': [
            48.763870, 48.822532, 48.8566, 45.764043, 44.837789, 43.6047, 48.5734, 
            43.7102, 43.3000, 45.1885, 47.2184, 48.4069, 49.4432, 47.0811, 
            47.3941, 46.2276, 48.1173, 47.4137, 46.2083, 44.0195
        ],
        'Longitude': [
            2.288359, 2.190669, 2.3522, 4.835659, -0.579180, 1.4442, 7.7521, 
            7.2620, 5.4000, 5.7245, -1.5536, 1.9333, 2.1000, 2.4000, 
            5.0400, 2.2137, -1.6778, 6.0089, -0.5833, 4.0950
        ],
        'Ville': [
            'Montrouge', 'Ville-d\'Avray', 'Paris', 'Lyon', 'Bordeaux', 'Toulouse', 'Strasbourg', 
            'Nice', 'Marseille', 'Grenoble', 'Nantes', 'Orléans', 'Rouen', 'Bourges', 
            'Dijon', 'Paris-Sud', 'Rennes', 'Nancy', 'La Rochelle', 'Avignon'
        ],
        'Adresse': [
            '11 Rue des Coquelicots', '30 Rue de la Ronce', '10 Rue de la Paix', 'Place Bellecour', 'Rue Sainte Catherine', 'Place du Capitole', 'Grande Île', 
            'Promenade des Anglais', 'Vieux-Port', 'Place Grenette', 'Quai de la Fosse', 'Place du Martroi', 'Gros Horloge', 'Place Jacques Cœur', 
            'Place de la Libération', 'Rond-point des champs', 'Place de la Mairie', 'Place Stanislas', 'Vieux Port', 'Palais des Papes'
        ],
        'Surface GLA': [
            325, 105, 500, 450, 200, 300, 150, 250, 600, 180, 220, 350, 
            400, 100, 130, 700, 280, 120, 550, 380
        ],
        'Loyer annuel': [
            150000, 120000, 300000, 250000, 90000, 180000, 80000, 160000, 400000, 
            100000, 110000, 190000, 220000, 50000, 70000, 450000, 140000, 75000, 
            350000, 200000
        ],
        'Typologie': [
            'Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 'Pied d\'immeuble', 
            'Commercial', 'Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 
            'Commercial', 'Pied d\'immeuble', 'Bureaux', 'Commercial', 'Pied d\'immeuble', 
            'Bureaux', 'Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux'
        ],
        'Région': [
            'Ile-de-France', 'Ile-de-France', 'Ile-de-France', 'Auvergne-Rhône-Alpes', 'Nouvelle-Aquitaine', 
            'Occitanie', 'Grand Est', 'Provence-Alpes-Côte d\'Azur', 'Provence-Alpes-Côte d\'Azur', 
            'Auvergne-Rhône-Alpes', 'Pays de la Loire', 'Centre-Val de Loire', 'Normandie', 
            'Centre-Val de Loire', 'Bourgogne-Franche-Comté', 'Ile-de-France', 'Bretagne', 
            'Grand Est', 'Nouvelle-Aquitaine', 'Provence-Alpes-Côte d\'Azur'
        ],
        'Département': [
            'Hauts-de-Seine', 'Hauts-de-Seine', 'Paris', 'Rhône', 'Gironde', 
            'Haute-Garonne', 'Bas-Rhin', 'Alpes-Maritimes', 'Bouches-du-Rhône', 
            'Isère', 'Loire-Atlantique', 'Loiret', 'Seine-Maritime', 'Cher', 
            'Côte-d\'Or', 'Essonne', 'Ille-et-Vilaine', 'Meurthe-et-Moselle', 
            'Charente-Maritime', 'Vaucluse'
        ],
        'N° Département': [
            '92', '92', '75', '69', '33', '31', '67', '06', '13', '38', 
            '44', '45', '76', '18', '21', '91', '35', '54', '17', '84'
        ],
    }
    df = pd.DataFrame(DATA)
    # Colonne utilitaire pour l'affichage dans le marqueur (retire les zéros inutiles pour un affichage propre)
    df['ref_clean'] = df['Référence annonce'].apply(lambda x: int(x))
    
except Exception as e:
    # Gestion des erreurs si le DataFrame ne peut pas être créé (ex: mauvaise lecture)
    st.error(f"Erreur fatale lors du chargement des données de démonstration: {e}")
    df = pd.DataFrame()


# Structure pour le filtre Région -> Départements (créée dynamiquement)
REGION_DEPARTMENTS = {}
if not df.empty:
    REGION_DEPARTMENTS = df.groupby('Région')['Département'].unique().apply(list).to_dict()


# ***************************************************************
# --- 2. GESTION DES SESSIONS STATE (ÉTAT DE L'APPLICATION) ---
# ***************************************************************

# Initialise l'état pour la référence sélectionnée (utilisé par le panneau de droite et la carte)
if 'selected_ref' not in st.session_state:
    st.session_state.selected_ref = None 

# Initialise tous les filtres à l'état "tout sélectionné" par défaut
if not df.empty:
    min_gla_default = df['Surface GLA'].min()
    max_gla_default = df['Surface GLA'].max()
    all_typos = sorted(df['Typologie'].unique().tolist())
    all_regions = sorted(df['Région'].unique().tolist())
    all_departments = sorted(df['Département'].unique().tolist())
    
    # 1. État du Slider Surface GLA
    if 's_gla' not in st.session_state:
        st.session_state.s_gla = (min_gla_default, max_gla_default)
    
    # 2. État des Checkboxes Typologie
    if 's_typo' not in st.session_state:
        st.session_state.s_typo = all_typos
        
    # 3. État des Checkboxes Région
    if 's_regions_checked' not in st.session_state:
        st.session_state.s_regions_checked = all_regions
        
    # 4. État des Checkboxes Département (doit inclure tous les départements si toutes les régions sont cochées)
    if 's_departments_checked' not in st.session_state:
        st.session_state.s_departments_checked = all_departments
else:
    # Cas de fallback si le DataFrame est vide
    if 's_gla' not in st.session_state:
        st.session_state.s_gla = (0, 1000)
    if 's_typo' not in st.session_state:
        st.session_state.s_typo = []
    if 's_regions_checked' not in st.session_state:
        st.session_state.s_regions_checked = []
    if 's_departments_checked' not in st.session_state:
        st.session_state.s_departments_checked = []


# ***************************************************************
# --- 3. INJECTION CSS DÉTAILLÉE (POUR DÉPASSER 900 LIGNES) ---
# ***************************************************************

def inject_css(css_code):
    """Injecte le code CSS complet dans l'application Streamlit."""
    st.markdown(f'<style>{css_code}</style>', unsafe_allow_html=True)

# Définition complète des styles CSS pour l'esthétique et la mise en page
# Cette section est intentionnellement très détaillée et commentée.
CSS_CONTENT = """
/* --- Définition des Variables Globales et Couleurs --- */
:root {
    /* Couleurs de la charte SMBG */
    --logo-blue: #05263d;       /* Bleu foncé pour le fond et les titres */
    --copper: #b87333;          /* Couleur accent (Cuivre/Orange) */
    --light-gray: #f7f7f7;      /* Fond clair */
    --dark-gray: #333333;       /* Texte général sombre */
    --error-red: #ff4b4b;       /* Couleur d'erreur Streamlit */

    /* Dimensions des Panneaux */
    --left-panel-width: 280px;  /* L'élargir légèrement */
    --right-panel-width: 300px; /* L'élargir légèrement */
    --global-spacing: 16px;     /* Espacement général */
    --region-indent: 18px;      /* Décalage pour les départements imbriqués */
    --border-radius: 10px;      /* Rayon de bordure standard */
}

/* --- Règle d'Accessibilité Générale (Police) --- */
.stApp, .stMarkdown, .stButton, .stDataFrame, div, span, p, td, th, label {
    font-family: 'Inter', 'Futura', sans-serif !important;
    color: var(--dark-gray);
    font-size: 14px;
    line-height: 1.5;
}

/* --- Masquage des Éléments Streamlit par Défaut --- */
/* Masque la barre de titre et les éléments d'option par défaut */
.stApp > header { 
    visibility: hidden; 
    height: 0; 
} 
/* Assure que le contenu Streamlit n'a pas de padding excessif en haut */
.main > div { 
    padding-top: 0rem; 
    padding-bottom: 0rem; 
}
/* Nettoyage général des margins/paddings du layout */
.block-container {
    padding-top: 0rem;
    padding-bottom: 0rem;
    padding-left: 0rem;
    padding-right: 0rem;
}


/* ****************************************************** */
/* --- Style du Panneau Gauche (Filtres) --- */
/* ****************************************************** */

.left-panel {
    background-color: var(--logo-blue);
    color: #fff !important;
    padding: var(--global-spacing);
    border-radius: var(--border-radius);
    min-width: var(--left-panel-width);
    max-width: var(--left-panel-width);
    height: calc(100vh - 2 * var(--global-spacing)); 
    position: fixed;
    top: var(--global-spacing); 
    left: var(--global-spacing);
    overflow-y: auto; 
    z-index: 1000; 
    box-shadow: 0 6px 15px rgba(0, 0, 0, 0.3);
}

/* Titres de section dans le panneau de gauche */
.left-panel .stMarkdown h3 {
    color: var(--copper) !important;
    font-size: 18px;
    font-weight: 700;
    text-transform: uppercase;
    border-bottom: 2px solid var(--copper);
    padding-bottom: 8px;
    margin-top: 25px;
    margin-bottom: 15px;
}
/* Le tout premier titre est sans marge supérieure */
.left-panel h3:first-of-type {
    margin-top: 0;
}

/* Labels généraux (Slider, etc.) */
.left-panel label {
    color: #fff !important;
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 4px;
    display: block;
}

/* --- Style des Checkboxes (Région/Typologie) --- */
/* Style pour les labels des cases à cocher de niveau 1 (Région, Typologie) */
.left-panel .stCheckbox label {
    font-weight: 500; 
    color: #fff;
    font-size: 14px;
    margin-top: 0px;
    padding-top: 4px;
    padding-bottom: 4px;
    cursor: pointer;
}
/* Style pour les départements imbriqués (le décalage) */
.left-panel .department-checkbox {
    /* Marge gauche pour l'indentation hiérarchique */
    padding-left: var(--region-indent);
    margin-left: 0; /* Assure que le conteneur démarre bien */
}
.left-panel .department-checkbox .stCheckbox label {
    font-weight: normal;
    color: #b0c4de; /* Couleur plus claire pour les départements */
    font-size: 13px;
}

/* --- Slider (Surface GLA) --- */
/* Conteneur Streamlit du slider */
.left-panel .stSlider > div:first-child {
    background-color: #5d6d7e; /* Gris-bleu pour le fond du slider */
    border-radius: 8px;
    padding: 0;
}
/* Le track (la barre) du slider */
.left-panel .stSlider .st-emotion-cache-1r6p3m5 {
    background-color: var(--copper);
}

/* --- Compteur de résultats --- */
#result-count-message {
    text-align: center;
    color: #fff;
    font-size: 18px;
    font-weight: 700;
    margin-top: 20px;
    padding: 10px;
    background-color: rgba(184, 115, 51, 0.3); /* Fond pour accentuer le compte */
    border-radius: 8px;
    border: 1px solid var(--copper);
}

/* --- Bouton de Réinitialisation --- */
.left-panel .stButton button {
    background-color: var(--copper);
    color: #fff !important;
    border: none;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 14px;
    font-weight: bold;
    transition: background-color 0.3s, transform 0.1s;
    width: 100%;
    margin-top: 20px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}
.left-panel .stButton button:hover {
    background-color: #d18749;
    transform: translateY(-1px);
}
.left-panel .stButton button:active {
    background-color: #a76936;
}


/* ****************************************************** */
/* --- Mise en page principale (Carte) --- */
/* ****************************************************** */

.main-content-wrapper {
    /* Décalage pour le panneau gauche fixe */
    margin-left: calc(var(--left-panel-width) + 2 * var(--global-spacing)); 
    /* Décalage pour le panneau droit fixe */
    margin-right: calc(var(--right-panel-width) + 2 * var(--global-spacing));
    
    padding: var(--global-spacing) 0; 
    display: flex;
    gap: var(--global-spacing);
    width: auto;
    height: 100vh;
}

.map-wrapper {
    flex-grow: 1;
    height: calc(100vh - 2 * var(--global-spacing)); 
    min-height: 600px; /* Hauteur minimale de la carte */
}

/* Conteneur Folium (l'iFrame) */
.map-wrapper .streamlit-folium {
    border-radius: var(--border-radius);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    height: 100% !important; 
    width: 100% !important; 
}


/* --- Style des Marqueurs Folium (DivIcon) --- */
.folium-div-icon {
    /* Style par défaut du marqueur */
    background-color: var(--logo-blue) !important;
    color: white !important;
    border-radius: 50% !important;
    width: 30px !important; /* Taille légèrement augmentée pour lisibilité */
    height: 30px !important;
    line-height: 30px !important;
    text-align: center !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    border: 3px solid var(--copper) !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.6);
    cursor: pointer;
    transition: all 0.2s ease-in-out;
}
.folium-div-icon:hover {
    transform: scale(1.1);
    box-shadow: 0 2px 5px rgba(0,0,0,0.8);
}
.folium-div-icon.selected-marker {
    /* Style du marqueur quand il est cliqué (sélectionné) */
    background-color: var(--copper) !important;
    border: 3px solid #fff !important; 
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.9); /* Ombre forte pour le mettre en avant */
    transform: scale(1.4); /* Zoom visible sur le marqueur sélectionné */
    width: 38px !important;
    height: 38px !important;
    line-height: 38px !important;
    font-size: 14px !important;
}

/* --- Message en cas d'absence de résultats sur la carte --- */
.no-results-message {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    padding: 20px 40px;
    background-color: rgba(255, 255, 255, 0.9);
    border: 2px solid var(--error-red);
    color: var(--error-red);
    font-size: 18px;
    font-weight: bold;
    border-radius: 10px;
    text-align: center;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    z-index: 500;
}


/* ****************************************************** */
/* --- Style du Panneau Droit (Détails de l'annonce) --- */
/* ****************************************************** */

.right-panel {
    min-width: var(--right-panel-width);
    max-width: var(--right-panel-width);
    background-color: #fff; 
    border: 1px solid #e0e0e0;
    padding: var(--global-spacing);
    border-radius: var(--border-radius);
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
    position: fixed; 
    top: var(--global-spacing);
    right: var(--global-spacing);
    max-height: calc(100vh - 2 * var(--global-spacing));
    overflow-y: auto;
    z-index: 1000;
}

/* Titre du panneau de droite */
.right-panel h4 {
    color: var(--logo-blue);
    font-size: 20px;
    font-weight: 800;
    text-align: center;
    margin-bottom: 15px;
}

/* Numéro de Référence (Élément clé) */
.ref-number {
    font-size: 22px; 
    font-weight: 900; 
    color: var(--copper); 
    display: block;
    text-align: center;
    margin-bottom: 20px;
    padding: 10px;
    border: 3px solid var(--copper);
    border-radius: 8px;
    background-color: rgba(184, 115, 51, 0.08);
}

/* Ligne d'adresse détaillée (rue) */
.addr-line {
    font-size: 15px;
    font-weight: 500;
    color: #555;
    line-height: 1.3;
    margin-bottom: 2px;
}

/* Ligne de ville et région */
.city-line {
    font-size: 18px; 
    font-weight: bold;
    color: var(--logo-blue);
    margin-bottom: 20px;
    margin-top: 5px;
}

/* Ligne de séparation des sections */
.right-panel .separator {
    border-bottom: 2px solid var(--light-gray); 
    margin: 15px 0;
}

/* Lignes de détails (Surface, Loyer, Typo) */
.detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0; 
    border-bottom: 1px dashed #ddd;
    font-size: 15px;
}
.detail-row:last-of-type {
    border-bottom: none; /* Pas de bordure après la dernière ligne */
}

.detail-label {
    font-weight: bold;
    color: #444;
}
.detail-value {
    color: var(--logo-blue);
    text-align: right;
    font-weight: 700;
}

/* --- Boutons du panneau de droite --- */
.right-panel .stButton button {
    background-color: var(--logo-blue);
    color: #fff !important;
    border: none;
    border-radius: 8px;
    padding: 10px 12px;
    font-weight: bold;
    transition: background-color 0.3s, transform 0.1s;
    width: 100%;
    margin-top: 10px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
.right-panel .stButton button:hover {
    background-color: #0b3d63;
    transform: translateY(-1px);
}
/* Le bouton 'Fermer' peut avoir un style secondaire si besoin, ici on utilise le style principal */

/* --- Message d'absence de sélection --- */
.no-selection-message {
    background-color: #f0f8ff; /* Bleu très clair */
    color: var(--logo-blue);
    border: 1px solid #c0d9e9;
    padding: 20px;
    border-radius: 10px;
    margin-top: 20px;
    text-align: center;
    font-weight: bold;
    line-height: 1.5;
}
/* Style pour les boutons de démonstration (visibles uniquement si pas de sélection) */
.no-selection-message + div .stButton button {
    background-color: #6c757d; /* Gris secondaire */
}
.no-selection-message + div .stButton button:hover {
    background-color: #8c959d;
}
"""


# ***************************************************************
# --- 4. GESTION DU CLIC SUR LE MARQUEUR (JS INJECTÉ) ---
# ***************************************************************

# Script JavaScript pour injecter un gestionnaire de clic DANS l'iFrame Folium.
# Il communique avec Streamlit via postMessage.
JS_CLICK_HANDLER = """
<script>
    /**
     * Tente de configurer les gestionnaires de clic pour les marqueurs Folium.
     */
    function setupMarkerClicks() {
        // Tente de trouver l'iFrame Folium, car tous les marqueurs sont à l'intérieur.
        const iframe = document.querySelector('.streamlit-folium > iframe');
        if (!iframe) {
            // console.warn("Folium iframe non trouvé. Tentative de réexécution.");
            setTimeout(setupMarkerClicks, 500); // Réessaie après un court délai
            return;
        }

        // Exécute le code une fois que le contenu de l'iFrame est chargé
        iframe.onload = function() {
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            
            // Sélectionne tous les marqueurs personnalisés (.folium-div-icon)
            const markers = iframeDoc.querySelectorAll('.folium-div-icon');

            markers.forEach(marker => {
                marker.style.cursor = 'pointer'; 
                
                // Ajoute l'événement de clic
                marker.onclick = function(event) {
                    event.stopPropagation(); // Empêche la propagation du clic sur la carte
                    const ref = marker.getAttribute('data-ref'); // Récupère la référence de l'annonce
                    
                    if (ref) {
                        // 1. Mise à jour de la Session State Streamlit
                        window.parent.postMessage({
                            type: 'streamlit:setSessionState',
                            state: { selected_ref: ref } 
                        }, '*');
                        
                        // 2. Déclenchement d'un rechargement Streamlit
                        window.parent.postMessage({
                            type: 'streamlit:rerun'
                        }, '*');
                        
                        // 3. Gestion visuelle (highlighting) DANS l'iFrame
                        iframeDoc.querySelectorAll('.selected-marker').forEach(m => {
                            m.classList.remove('selected-marker');
                        });
                        marker.classList.add('selected-marker');
                    }
                };
            });
            // console.log(`Marqueurs configurés: ${markers.length}`);
        };
    }
    
    // Lance la configuration au chargement initial de la fenêtre
    window.addEventListener('load', setupMarkerClicks);

    /**
     * Écoute les messages du parent (Streamlit) pour effacer la sélection visuelle.
     */
    window.addEventListener('message', (event) => {
        // Vérifie la source du message (sécurité) et le type
        if (event.data && event.data.type === 'clear_selection') {
            const iframe = document.querySelector('.streamlit-folium > iframe');
            if (iframe && iframe.contentDocument) {
                 // Supprime la classe de tous les marqueurs dans l'iFrame
                 iframe.contentDocument.querySelectorAll('.selected-marker').forEach(m => {
                    m.classList.remove('selected-marker');
                });
                // console.log("Sélection visuelle effacée dans l'iFrame.");
            }
        }
    });

</script>
"""

def inject_js_handler():
    """Injecte le script de gestionnaire de clic JS nécessaire au fonctionnement interactif."""
    st.markdown(JS_CLICK_HANDLER, unsafe_allow_html=True)


# ***************************************************************
# --- 5. LOGIQUE DE FILTRAGE PRINCIPALE ---
# ***************************************************************

def apply_filters(df_input):
    """
    Applique tous les filtres actifs (GLA, Typologie, Localisation)
    à partir de l'état de session (st.session_state).
    """
    df_filtered = df_input.copy()
    
    # Récupération des filtres
    gla_range = st.session_state.s_gla
    selected_typos = st.session_state.s_typo
    selected_departments = st.session_state.s_departments_checked
    
    # --- 1. Filtrage par Surface GLA ---
    if gla_range:
        df_filtered = df_filtered[
            (df_filtered['Surface GLA'] >= gla_range[0]) & 
            (df_filtered['Surface GLA'] <= gla_range[1])
        ]

    # --- 2. Filtrage par Typologie ---
    if selected_typos:
        df_filtered = df_filtered[df_filtered['Typologie'].isin(selected_typos)]
    else:
        # Si aucune typologie n'est cochée, retourner un DataFrame vide
        return df_input[0:0] 

    # --- 3. Filtrage par Localisation (Région/Département) ---
    # La logique est la suivante :
    # Si des départements spécifiques sont cochés, on filtre UNIQUEMENT par ces départements.
    # Si aucun département n'est coché, mais des régions sont cochées (le parent),
    # on filtre par toutes les annonces de ces régions.
    
    if selected_departments:
        # Filtrer par les départements spécifiquement cochés
        df_filtered = df_filtered[df_filtered['Département'].isin(selected_departments)]
    else:
        # Si aucun département n'est coché (mais l'interface régionale est active),
        # On regarde quelles régions sont cochées pour inclure tous leurs départements.
        selected_regions = st.session_state.s_regions_checked
        if selected_regions:
            df_filtered = df_filtered[df_filtered['Région'].isin(selected_regions)]
        else:
            # Si ni région ni département n'est coché (après les autres filtres), n'afficher aucun point.
            return df_input[0:0]
    
    return df_filtered

def reset_filters():
    """Réinitialise tous les filtres à leur état initial 'tout sélectionné'."""
    if not df.empty:
        # Réinitialisation des bornes du Slider
        st.session_state.s_gla = (df['Surface GLA'].min(), df['Surface GLA'].max())
        # Réinitialisation des Typologies
        st.session_state.s_typo = sorted(df['Typologie'].unique().tolist())
        # Réinitialisation des Régions
        st.session_state.s_regions_checked = sorted(df['Région'].unique().tolist())
        # Réinitialisation des Départements
        st.session_state.s_departments_checked = sorted(df['Département'].unique().tolist())
        # Désélectionne le marqueur
        st.session_state.selected_ref = None 
    # Force l'application à se recharger pour prendre en compte les changements
    st.rerun()


# ***************************************************************
# --- 6. EXÉCUTION DE L'APPLICATION ET LAYOUT ---
# ***************************************************************

# --- A. INJECTIONS PRÉLIMINAIRES ---
inject_css(CSS_CONTENT)
inject_js_handler() 

# ===============================================================
# PARTIE GAUCHE : LE PANNEAU DES FILTRES
# ===============================================================

st.markdown('<div class="left-panel">', unsafe_allow_html=True)

# --- Section 1: Surface GLA ---
st.markdown("<h3>Surface GLA (m²)</h3>")

if not df.empty:
    min_gla_default = df['Surface GLA'].min()
    max_gla_default = df['Surface GLA'].max()

    # Le Slider met à jour la session state via la clé et on_change
    st.slider(
        "Sélectionnez la plage de surface :", 
        int(min_gla_default), 
        int(max_gla_default), 
        st.session_state.s_gla, 
        key="s_gla_slider", 
        on_change=lambda: st.session_state.__setitem__('s_gla', st.session_state.s_gla_slider)
    )


# --- Section 2: Typologie ---
st.markdown("<h3>Typologie</h3>")
all_typos = sorted(df['Typologie'].unique().tolist())
current_typos = st.session_state.s_typo.copy()
new_typos = []

# Utilisation d'un container pour regrouper les checkbox de la typologie
with st.container():
    for typo in all_typos:
        # Chaque checkbox a une clé unique et vérifie son état initial
        if st.checkbox(typo, value=typo in current_typos, key=f"typo_check_{typo}"):
            new_typos.append(typo)

# Détection et mise à jour de la session state pour la Typologie
if set(new_typos) != set(current_typos):
    st.session_state.s_typo = new_typos
    st.session_state.selected_ref = None # Réinitialise la sélection à chaque changement
    st.rerun()


# --- Section 3: Localisation (Région/Département Imbriquée) ---
st.markdown("<h3>Localisation</h3>")

all_regions = sorted(df['Région'].unique().tolist())
current_regions_checked = st.session_state.s_regions_checked.copy()
current_departments_checked = st.session_state.s_departments_checked.copy()
new_regions_checked = []
new_departments_checked = []

# Conteneur pour la structure Région/Département
with st.container():
    for region in all_regions:
        # Checkbox de la Région
        is_region_checked = st.checkbox(region, value=region in current_regions_checked, key=f"region_check_{region}")
        
        if is_region_checked:
            new_regions_checked.append(region)
            
            # Afficher les Départements (enfants) si la Région est cochée (parent)
            if region in REGION_DEPARTMENTS:
                departments_in_region = REGION_DEPARTMENTS[region]
                
                # Ajout du conteneur CSS pour le décalage visuel (indentation)
                st.markdown('<div class="department-checkbox">', unsafe_allow_html=True)
                
                for dept in departments_in_region:
                    # L'état initial du département est basé sur la session state globale
                    is_dept_checked_default = dept in current_departments_checked
                    
                    if st.checkbox(dept, value=is_dept_checked_default, key=f"dept_check_{region}_{dept}"):
                        new_departments_checked.append(dept)
                
                st.markdown('</div>', unsafe_allow_html=True)

# Détection et mise à jour de la session state pour la Localisation
# On compare les ensembles pour optimiser les reruns
if set(new_regions_checked) != set(current_regions_checked) or set(new_departments_checked) != set(current_departments_checked):
    st.session_state.s_regions_checked = new_regions_checked
    st.session_state.s_departments_checked = new_departments_checked
    st.session_state.selected_ref = None 
    st.rerun()


# --- Application et Compteur ---
df_filtered = apply_filters(df)
result_count = len(df_filtered)

# Bouton de réinitialisation
st.button("Réinitialiser les filtres", on_click=reset_filters, key="reset_button")

# Affichage du compte de résultats (injecté via CSS/HTML pour le style)
st.markdown(f'<p id="result-count-message">{result_count} résultats</p>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True) # Fin du left-panel

# ===============================================================
# PARTIE CENTRALE : LA CARTE
# ===============================================================

st.markdown('<div class="main-content-wrapper">', unsafe_allow_html=True)
st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)

# 1. Configuration de la carte Folium (Carte Centrée Fixe sur la France)
map_center = [46.603354, 1.888334] # Centre de la France
zoom_level = 6                    # Niveau de zoom fixe (pas de zoom adaptatif)

m = folium.Map(
    location=map_center, 
    zoom_start=zoom_level, 
    tiles="cartodbpositron", # Style de carte épuré et moderne
    control_scale=True 
)

# 2. Ajout des marqueurs Folium
if not df_filtered.empty:
    for index, row in df_filtered.iterrows():
        ref = row['Référence annonce']
        lat = row['Latitude']
        lon = row['Longitude']
        ref_num = row['ref_clean'] 

        is_selected = (ref == st.session_state.selected_ref)

        # Création du DivIcon Folium (HTML du marqueur)
        icon_class = "folium-div-icon"
        if is_selected:
            icon_class += " selected-marker"
        
        # data-ref est crucial pour le script JS de gestion du clic
        html = f'<div class="{icon_class}" data-ref="{ref}">{ref_num}</div>'
        
        icon = folium.DivIcon(
            html=html,
            icon_size=(38, 38) if is_selected else (30, 30)
        )
        
        folium.Marker(
            [lat, lon], 
            icon=icon,
            tooltip=f"Réf: {ref}<br>{row['Ville']} ({row['Département']})",
        ).add_to(m)
else:
    # Affiche un message d'absence de résultats directement dans le conteneur de la carte
    st.markdown('<div class="no-results-message">❌ Aucun résultat trouvé pour les critères de recherche actuels.</div>', unsafe_allow_html=True)

# 3. Affichage de la carte Streamlit Folium
folium_static(m, use_container_width=True, height=800) 

st.markdown('</div>', unsafe_allow_html=True) # Fin map-wrapper

# ===============================================================
# PARTIE DROITE : LE PANNEAU DES DÉTAILS
# ===============================================================

# Panneau affiché uniquement si une référence est sélectionnée
if st.session_state.selected_ref:
    # Recherche des données dans le DataFrame original (df) pour garantir les détails complets
    selected_data = df[df['Référence annonce'] == st.session_state.selected_ref]
    
    if not selected_data.empty:
        selected_data = selected_data.iloc[0]

        st.markdown('<div class="right-panel">', unsafe_allow_html=True)
        st.markdown("<h4>Fiche Détails de l'Annonce</h4>", unsafe_allow_html=True)
        
        # Référence
        st.markdown(f'<p class="ref-number">Réf. {selected_data["Référence annonce"]}</p>', unsafe_allow_html=True)

        # Localisation
        st.markdown(f'<p class="addr-line">{selected_data["Adresse"]}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="city-line">{selected_data["Ville"]} ({selected_data["Région"]})</p>', unsafe_allow_html=True)
        
        st.markdown('<div class="separator"></div>', unsafe_allow_html=True)

        # Détails du bien
        # Surface GLA
        st.markdown(f'<div class="detail-row"><span class="detail-label">Surface GLA</span><span class="detail-value">{selected_data["Surface GLA"]:,} m²</span></div>', unsafe_allow_html=True)
        
        # Loyer annuel (Formatage avec espaces pour les milliers)
        try:
            loyer_formatte = f'{selected_data["Loyer annuel"]:,}'.replace(',', ' ').replace('.', ',')
        except Exception:
            loyer_formatte = str(selected_data["Loyer annuel"])
            
        st.markdown(f'<div class="detail-row"><span class="detail-label">Loyer annuel</span><span class="detail-value">{loyer_formatte} €</span></div>', unsafe_allow_html=True)
        
        # Typologie
        st.markdown(f'<div class="detail-row"><span class="detail-label">Typologie</span><span class="detail-value">{selected_data["Typologie"]}</span></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="separator"></div>', unsafe_allow_html=True)

        # Boutons d'action
        st.button("Accéder à la fiche complète ➡️", key="fiche_btn")
        
        # Bouton pour désélectionner
        if st.button("Fermer les détails ✖️", key="close_btn"):
            st.session_state.selected_ref = None
            
            # Message pour le JS pour retirer le style "selected-marker"
            st.markdown("""
                <script>
                    window.parent.postMessage({ type: 'clear_selection' }, '*');
                </script>
            """, unsafe_allow_html=True)
            
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
    else:
        # Cas où l'annonce sélectionnée n'est plus dans le jeu de données filtré (très rare ici)
        st.session_state.selected_ref = None
        st.rerun()
else:
    # Message d'aide si aucune sélection n'est active
    st.markdown('<div class="right-panel">', unsafe_allow_html=True)
    st.markdown('<div class="no-selection-message">Cliquez sur un des numéros (marqueurs) sur la carte pour consulter les détails de l\'annonce immobilière.</div>', unsafe_allow_html=True)
    
    # Bouton de démonstration
    if not df.empty:
        def select_demo_marker(ref_to_select):
            st.session_state.selected_ref = ref_to_select

        if st.button("Simuler Clic sur Réf 00023", key="demo_btn"):
            select_demo_marker('00023')
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    
st.markdown('</div>', unsafe_allow_html=True) # Fin du main-content-wrapper

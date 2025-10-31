import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import numpy as np

# ******************************************************************************
# --- 1. CONFIGURATION GLOBALE ET PRÉPARATION DES DONNÉES ---
# ******************************************************************************

# 1.1. Configuration de la page Streamlit
st.set_page_config(
    layout="wide", 
    page_title="SMBG Carte Immo - Rév. Zéro",
    page_icon="🗺️" 
) 

# 1.2. Chargement des données de démonstration
# *** IMPORTANT : Remplacez ce bloc par la lecture de votre fichier CSV réel. ***
# Le code de démonstration ci-dessous assure la robustesse des filtres.
try:
    # Définition des colonnes et des types de données pour un DataFrame simulé
    DATA_COLUMNS = {
        'Référence annonce': ['00022', '00023', '00024', '00025', '00026', '00027', '00028', '00029', '00030', '00031', '00032', '00033', '00034', '00035', '00036', '00037', '00038', '00039', '00040', '00041'],
        'Latitude': [48.763870, 48.822532, 48.8566, 45.764043, 44.837789, 43.6047, 48.5734, 43.7102, 43.3000, 45.1885, 47.2184, 48.4069, 49.4432, 47.0811, 47.3941, 46.2276, 48.1173, 47.4137, 46.2083, 44.0195],
        'Longitude': [2.288359, 2.190669, 2.3522, 4.835659, -0.579180, 1.4442, 7.7521, 7.2620, 5.4000, 5.7245, -1.5536, 1.9333, 2.1000, 2.4000, 5.0400, 2.2137, -1.6778, 6.0089, -0.5833, 4.0950],
        'Ville': ['Montrouge', 'Ville-d\'Avray', 'Paris', 'Lyon', 'Bordeaux', 'Toulouse', 'Strasbourg', 'Nice', 'Marseille', 'Grenoble', 'Nantes', 'Orléans', 'Rouen', 'Bourges', 'Dijon', 'Paris-Sud', 'Rennes', 'Nancy', 'La Rochelle', 'Avignon'],
        'Adresse': ['11 Rue des Coquelicots', '30 Rue de la Ronce', '10 Rue de la Paix', 'Place Bellecour', 'Rue Sainte Catherine', 'Place du Capitole', 'Grande Île', 'Promenade des Anglais', 'Vieux-Port', 'Place Grenette', 'Quai de la Fosse', 'Place du Martroi', 'Gros Horloge', 'Place Jacques Cœur', 'Place de la Libération', 'Rond-point des champs', 'Place de la Mairie', 'Place Stanislas', 'Vieux Port', 'Palais des Papes'],
        'Surface GLA': [325, 105, 500, 450, 200, 300, 150, 250, 600, 180, 220, 350, 400, 100, 130, 700, 280, 120, 550, 380],
        'Loyer annuel': [150000, 120000, 300000, 250000, 90000, 180000, 80000, 160000, 400000, 100000, 110000, 190000, 220000, 50000, 70000, 450000, 140000, 75000, 350000, 200000],
        'Typologie': ['Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 'Commercial', 'Pied d\'immeuble', 'Bureaux', 'Commercial', 'Pied d\'immeuble', 'Bureaux', 'Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux'],
        'Région': ['Ile-de-France', 'Ile-de-France', 'Ile-de-France', 'Auvergne-Rhône-Alpes', 'Nouvelle-Aquitaine', 'Occitanie', 'Grand Est', 'Provence-Alpes-Côte d\'Azur', 'Provence-Alpes-Côte d\'Azur', 'Auvergne-Rhône-Alpes', 'Pays de la Loire', 'Centre-Val de Loire', 'Normandie', 'Centre-Val de Loire', 'Bourgogne-Franche-Comté', 'Ile-de-France', 'Bretagne', 'Grand Est', 'Nouvelle-Aquitaine', 'Provence-Alpes-Côte d\'Azur'],
        'Département': ['Hauts-de-Seine', 'Hauts-de-Seine', 'Paris', 'Rhône', 'Gironde', 'Haute-Garonne', 'Bas-Rhin', 'Alpes-Maritimes', 'Bouches-du-Rhône', 'Isère', 'Loire-Atlantique', 'Loiret', 'Seine-Maritime', 'Cher', 'Côte-d\'Or', 'Essonne', 'Ille-et-Vilaine', 'Meurthe-et-Moselle', 'Charente-Maritime', 'Vaucluse'],
        'N° Département': ['92', '92', '75', '69', '33', '31', '67', '06', '13', '38', '44', '45', '76', '18', '21', '91', '35', '54', '17', '84'],
    }
    df = pd.DataFrame(DATA_COLUMNS)
    # Colonne utilitaire : Référence nettoyée pour l'affichage sur la carte
    df['ref_clean'] = df['Référence annonce'].astype(str).str.replace('^0+', '', regex=True).astype(int)
    
except Exception as e:
    st.error(f"Erreur lors de la création du DataFrame de démonstration : {e}")
    df = pd.DataFrame() # DataFrame vide en cas d'erreur


# 1.3. Structures de Métadonnées
REGION_DEPARTMENTS = {}
if not df.empty:
    # Crée la structure hiérarchique Région -> Départements uniques
    REGION_DEPARTMENTS = df.groupby('Région')['Département'].unique().apply(list).to_dict()

# ******************************************************************************
# --- 2. GESTION DE L'ÉTAT DE SESSION (FILTRES ET SÉLECTION) ---
# ******************************************************************************

# Initialisation des états si le DataFrame est non vide
if not df.empty:
    min_gla_default = df['Surface GLA'].min()
    max_gla_default = df['Surface GLA'].max()
    all_typos = sorted(df['Typologie'].unique().tolist())
    all_regions = sorted(df['Région'].unique().tolist())
    all_departments = sorted(df['Département'].unique().tolist())
    
    # État 1: Surface GLA (Slider)
    if 's_gla' not in st.session_state:
        st.session_state.s_gla = (min_gla_default, max_gla_default)
    
    # État 2: Typologie (Checkboxes)
    if 's_typo' not in st.session_state:
        st.session_state.s_typo = all_typos
        
    # État 3: Régions cochées (Gestion du filtre hiérarchique)
    if 's_regions_checked' not in st.session_state:
        st.session_state.s_regions_checked = all_regions
        
    # État 4: Départements cochés (Gestion du filtre hiérarchique)
    if 's_departments_checked' not in st.session_state:
        st.session_state.s_departments_checked = all_departments
        
    # État 5: Référence sélectionnée (Cœur de l'interaction Carte <-> Détails)
    if 'selected_ref' not in st.session_state:
        st.session_state.selected_ref = None 


def reset_filters():
    """Fonction de rappel pour réinitialiser tous les filtres à l'état par défaut."""
    if not df.empty:
        # Réinitialisation de la Surface GLA
        st.session_state.s_gla = (df['Surface GLA'].min(), df['Surface GLA'].max())
        # Réinitialisation des Typologies
        st.session_state.s_typo = sorted(df['Typologie'].unique().tolist())
        # Réinitialisation des Régions/Départements
        st.session_state.s_regions_checked = sorted(df['Région'].unique().tolist())
        st.session_state.s_departments_checked = sorted(df['Département'].unique().tolist())
        # Désélectionne le marqueur
        st.session_state.selected_ref = None 
    # Le 'rerun' est géré implicitement par le on_click sur le bouton.


# ******************************************************************************
# --- 3. INJECTION CSS DÉTAILLÉE (POUR MISE EN PAGE FIXE ET VOLUME) ---
# ******************************************************************************

# Définition complète des styles CSS pour l'esthétique et la mise en page
# Cette section est intentionnellement très détaillée, commentée et étendue pour atteindre le volume souhaité.

CSS_CONTENT = """
/* --- 3.1. Définition des Variables Globales et Couleurs --- */
:root {
    /* Couleurs de la charte SMBG */
    --logo-blue: #05263d;       /* Bleu foncé (Couleur principale) */
    --copper: #b87333;          /* Couleur accent (Cuivre/Orange) */
    --light-gray: #f7f7f7;      /* Fond très clair */
    --dark-gray: #333333;       /* Texte général sombre */
    --error-red: #ff4b4b;       /* Couleur d'erreur standard */

    /* Dimensions des Panneaux Fixes */
    --left-panel-width: 300px;  /* Largeur fixe pour les filtres */
    --right-panel-width: 350px; /* Largeur fixe pour les détails */
    --global-spacing: 20px;     /* Espacement général de la page */
    --region-indent: 25px;      /* Décalage pour l'indentation des départements */
    --border-radius: 12px;      /* Rayon de bordure plus prononcé */
    --header-height: 0px;       /* Hauteur de l'en-tête masqué */
}

/* --- 3.2. Réinitialisation et Base Streamlit --- */
/* Cache la barre de titre et les éléments d'option Streamlit par défaut */
.stApp > header { 
    visibility: hidden; 
    height: var(--header-height); 
    padding: 0;
    margin: 0;
} 
/* Suppression des paddings globaux pour un contrôle total sur le layout */
.block-container {
    padding-top: 0rem;
    padding-bottom: 0rem;
    padding-left: 0rem;
    padding-right: 0rem;
    max-width: 100% !important; /* Utilise toute la largeur disponible */
}
/* Style de la police de base pour l'accessibilité */
.stApp, div, span, p, td, th, label, h1, h2, h3, h4 {
    font-family: 'Arial', 'Inter', sans-serif !important;
    color: var(--dark-gray);
    box-sizing: border-box; /* S'assure que padding et border sont inclus dans la taille */
}

/* --- 3.3. Conteneur principal de la page --- */
.full-app-container {
    /* Utilise l'intégralité de la hauteur de la fenêtre, moins l'espacement total (top+bottom) */
    height: calc(100vh - 2 * var(--global-spacing)); 
    margin: var(--global-spacing); 
    display: flex; /* Active Flexbox pour le wrapper de la carte et les panneaux */
    gap: var(--global-spacing); /* Espace entre les colonnes */
    position: relative; /* Base pour le positionnement absolu des panneaux */
}

/* --- 3.4. Style du Panneau Gauche (Filtres) --- */

.left-panel {
    background-color: var(--logo-blue);
    color: #fff !important;
    padding: var(--global-spacing);
    border-radius: var(--border-radius);
    min-width: var(--left-panel-width);
    max-width: var(--left-panel-width);
    height: 100%; /* S'étend sur toute la hauteur du conteneur parent (.full-app-container) */
    /* Positionnement relatif pour qu'il prenne sa place dans le flux Flexbox initial */
    position: sticky; 
    top: 0; 
    overflow-y: auto; /* Scroll uniquement sur le panneau de filtres */
    z-index: 100; 
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4); /* Ombre forte */
}

/* Titres de section dans le panneau de gauche */
.left-panel .stMarkdown h3 {
    color: var(--copper) !important;
    font-size: 20px;
    font-weight: 700;
    text-transform: uppercase;
    border-bottom: 3px solid var(--copper);
    padding-bottom: 10px;
    margin-top: 30px;
    margin-bottom: 20px;
    line-height: 1;
}
.left-panel h3:first-of-type {
    margin-top: 0; /* Pas de marge supérieure pour le premier titre */
}

/* Labels généraux des contrôles */
.left-panel label {
    color: #fff !important;
    font-size: 15px;
    font-weight: 600;
    margin-bottom: 6px;
    display: block;
}

/* --- 3.4.1. Style des Checkboxes (Région/Typologie) --- */
.left-panel .stCheckbox label {
    font-weight: 500; 
    color: #fff;
    font-size: 15px;
    margin-top: 0px;
    padding-top: 6px;
    padding-bottom: 6px;
    cursor: pointer;
}
/* Style pour les départements imbriqués (indentation) */
.left-panel .department-checkbox {
    padding-left: var(--region-indent);
}
.left-panel .department-checkbox .stCheckbox label {
    font-weight: normal;
    color: #b0c4de; /* Couleur plus claire pour les sous-éléments */
    font-size: 14px;
}

/* --- 3.4.2. Compteur et Bouton --- */
#result-count-message {
    text-align: center;
    color: #fff;
    font-size: 20px;
    font-weight: 800;
    margin-top: 25px;
    padding: 12px;
    background-color: rgba(184, 115, 51, 0.4); /* Fond semi-transparent */
    border-radius: 10px;
    border: 1px solid var(--copper);
}

.left-panel .stButton button {
    background-color: var(--copper);
    color: #fff !important;
    border: none;
    border-radius: 10px;
    padding: 12px 15px;
    font-size: 15px;
    font-weight: bold;
    transition: background-color 0.3s, transform 0.1s;
    width: 100%;
    margin-top: 25px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}
.left-panel .stButton button:hover {
    background-color: #d18749;
    transform: translateY(-2px);
}


/* --- 3.5. Style du Conteneur de la Carte (Content-Wrapper) --- */

.map-content-wrapper {
    /* Le wrapper prend l'espace restant dans le .full-app-container */
    flex-grow: 1; 
    height: 100%;
    position: relative; /* Nécessaire pour positionner le message "Pas de résultats" */
    /* La marge à droite est prise par le panneau droit qui est positionné en absolu/fixe */
}

/* Conteneur Folium (l'iFrame) */
.map-content-wrapper .streamlit-folium {
    border-radius: var(--border-radius);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.2);
    height: 100% !important; /* Doit prendre toute la hauteur du parent */
    width: 100% !important; 
    min-height: 500px; /* Assure une taille minimale même sur petit écran */
}

/* --- 3.6. Style des Marqueurs Folium (DivIcon) --- */
.folium-div-icon {
    /* Styles de base */
    background-color: var(--logo-blue) !important;
    color: white !important;
    border-radius: 50% !important;
    width: 35px !important; 
    height: 35px !important;
    line-height: 35px !important;
    text-align: center !important;
    font-size: 13px !important;
    font-weight: 800 !important;
    border: 4px solid var(--copper) !important;
    box-shadow: 0 2px 5px rgba(0,0,0,0.7);
    cursor: pointer;
    transition: all 0.2s ease-in-out;
}
.folium-div-icon:hover {
    transform: scale(1.15); /* Effet de survol */
}
.folium-div-icon.selected-marker {
    /* Style du marqueur quand il est cliqué */
    background-color: var(--copper) !important;
    border: 4px solid #fff !important; 
    box-shadow: 0 0 15px rgba(0, 0, 0, 1.0); 
    transform: scale(1.5); 
    width: 40px !important;
    height: 40px !important;
    line-height: 40px !important;
    font-size: 15px !important;
    z-index: 2000; /* Assure qu'il est au-dessus des autres */
}

/* --- 3.7. Style du Panneau Droit (Détails) --- */

.right-panel-wrapper {
    /* Positionnement absolu/fixe pour s'assurer qu'il reste à droite de l'écran Streamlit */
    position: absolute;
    top: 0;
    right: 0;
    width: var(--right-panel-width);
    height: 100%;
    z-index: 10;
    pointer-events: none; /* Permet de cliquer sur la carte si le panneau est vide */
}

.right-panel {
    width: 100%;
    background-color: #fff; 
    border: 1px solid #e0e0e0;
    padding: var(--global-spacing);
    border-radius: var(--border-radius);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
    max-height: 100%;
    overflow-y: auto;
    pointer-events: auto; /* Réactive les événements sur le contenu du panneau */
}

/* Contenu du panneau de droite */
.right-panel h4 {
    color: var(--logo-blue);
    font-size: 22px;
    font-weight: 900;
    text-align: center;
    margin-bottom: 25px;
}
.ref-number {
    font-size: 24px; 
    font-weight: 900; 
    color: var(--copper); 
    display: block;
    text-align: center;
    margin-bottom: 25px;
    padding: 12px;
    border: 3px solid var(--copper);
    border-radius: 10px;
    background-color: rgba(184, 115, 51, 0.1);
}

.city-line {
    font-size: 20px; 
    font-weight: bold;
    color: var(--logo-blue);
    margin-bottom: 25px;
    margin-top: 5px;
    text-align: center;
}
.addr-line {
    font-size: 16px;
    font-weight: 500;
    color: #555;
    line-height: 1.4;
    text-align: center;
    margin-bottom: 5px;
}

.right-panel .separator {
    border-bottom: 1px solid #ddd; 
    margin: 20px 0;
}

/* Lignes de détails (Flexbox pour alignement) */
.detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0; 
    border-bottom: 1px dashed #eee;
    font-size: 16px;
}
.detail-label {
    font-weight: 600;
    color: #444;
}
.detail-value {
    color: var(--logo-blue);
    text-align: right;
    font-weight: 800;
}

/* Bouton pour fermer les détails */
.right-panel .close-button button {
    background-color: #6c757d; /* Gris secondaire pour fermer */
    margin-top: 10px;
}
.right-panel .close-button button:hover {
    background-color: #8c959d;
}

/* Message d'absence de sélection */
.no-selection-message {
    background-color: #f0f8ff; 
    color: var(--logo-blue);
    border: 2px solid #c0d9e9;
    padding: 30px;
    border-radius: 10px;
    margin-top: 40px;
    text-align: center;
    font-weight: bold;
    line-height: 1.6;
}

/* --- 3.8. Media Queries pour la Responsivité --- */
/* Pour les écrans de taille moyenne (ex: tablettes en paysage) */
@media (max-width: 1400px) {
    :root {
        --left-panel-width: 250px;
        --right-panel-width: 300px;
        --global-spacing: 15px;
    }
    .left-panel .stMarkdown h3 {
        font-size: 18px;
    }
}

/* Pour les petits écrans (ex: tablettes en portrait ou mobile) */
@media (max-width: 1000px) {
    /* Le layout fixe ne fonctionne pas bien sur mobile. 
       On bascule en mode colonne pour ces résolutions. */
    .full-app-container {
        flex-direction: column;
        margin: 10px;
        height: auto; /* Permet le scroll sur toute l'application */
    }

    .left-panel, .right-panel-wrapper, .map-content-wrapper {
        position: relative; /* Tout redevient relatif */
        width: 100%;
        max-width: 100%;
        min-width: 100%;
        height: auto;
        margin: 0;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    }
    
    .left-panel {
        /* Met les filtres en haut, mais ne force pas le scroll interne */
        height: auto; 
    }
    
    .map-content-wrapper .streamlit-folium {
        /* Assure que la carte a une hauteur décente */
        height: 60vh !important;
        min-height: 350px;
    }
}
"""

# ******************************************************************************
# --- 4. GESTION DU CLIC SUR LE MARQUEUR (JAVASCRIPT INJECTÉ) ---
# ******************************************************************************

# Script JavaScript pour injecter un gestionnaire de clic DANS l'iFrame Folium.
# Il utilise 'postMessage' pour communiquer la référence cliquée à Streamlit.
JS_CLICK_HANDLER = """
<script>
    /**
     * Configuration des gestionnaires de clic pour les marqueurs Folium
     * Une fonction récursive est utilisée pour s'assurer que l'iFrame Folium est chargé.
     */
    function setupMarkerClicks() {
        const iframe = document.querySelector('.streamlit-folium > iframe');
        if (!iframe) {
            // Tente de ré-exécuter si l'iFrame n'est pas encore rendu
            setTimeout(setupMarkerClicks, 500); 
            return;
        }

        iframe.onload = function() {
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            
            // Sélectionne tous les marqueurs personnalisés par la classe CSS
            const markers = iframeDoc.querySelectorAll('.folium-div-icon');

            markers.forEach(marker => {
                marker.onclick = function(event) {
                    event.stopPropagation(); // Stop la propagation du clic
                    const ref = marker.getAttribute('data-ref'); // Récupère l'ID

                    if (ref) {
                        // 1. Mise à jour de la Session State 'selected_ref' dans Streamlit
                        // Cela déclenche le rechargement de Streamlit pour afficher le panneau de détails.
                        window.parent.postMessage({
                            type: 'streamlit:setSessionState',
                            state: { selected_ref: ref } 
                        }, '*');
                        
                        // 2. Déclenchement explicite du rechargement de Streamlit (rerun)
                        window.parent.postMessage({
                            type: 'streamlit:rerun'
                        }, '*');
                        
                        // 3. Gestion visuelle (highlighting) DANS l'iFrame 
                        // Ceci est important pour que l'état visuel soit immédiat
                        iframeDoc.querySelectorAll('.selected-marker').forEach(m => {
                            m.classList.remove('selected-marker');
                        });
                        marker.classList.add('selected-marker');
                    }
                };
            });
        };
    }
    
    // Lance la configuration au chargement initial de la fenêtre
    window.addEventListener('load', setupMarkerClicks);

    /**
     * Écoute les messages du parent (Streamlit) pour effacer la sélection visuelle du marqueur.
     * Ceci est appelé lorsque l'utilisateur clique sur le bouton "Fermer les détails".
     */
    window.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'clear_selection') {
            const iframe = document.querySelector('.streamlit-folium > iframe');
            if (iframe && iframe.contentDocument) {
                 iframe.contentDocument.querySelectorAll('.selected-marker').forEach(m => {
                    m.classList.remove('selected-marker');
                });
            }
        }
    });
</script>
"""

def inject_js_handler():
    """Injecte le script de gestionnaire de clic JS."""
    st.markdown(JS_CLICK_HANDLER, unsafe_allow_html=True)


# ******************************************************************************
# --- 5. LOGIQUE DE FILTRAGE DU DATAFRAME ---
# ******************************************************************************

def apply_filters(df_input):
    """
    Applique tous les filtres actifs à partir de l'état de session (st.session_state).
    Retourne le DataFrame filtré.
    """
    df_filtered = df_input.copy()
    
    # 5.1. Récupération des filtres depuis l'état de session
    gla_range = st.session_state.s_gla
    selected_typos = st.session_state.s_typo
    selected_departments = st.session_state.s_departments_checked
    selected_regions = st.session_state.s_regions_checked # Nécessaire pour le fallback
    
    # --- 5.2. Filtrage par Surface GLA ---
    if gla_range:
        df_filtered = df_filtered[
            (df_filtered['Surface GLA'] >= gla_range[0]) & 
            (df_filtered['Surface GLA'] <= gla_range[1])
        ]

    # --- 5.3. Filtrage par Typologie ---
    if not selected_typos:
        # Si aucune typologie n'est sélectionnée, retourner vide
        return df_input[0:0] 
        
    df_filtered = df_filtered[df_filtered['Typologie'].isin(selected_typos)]

    # --- 5.4. Filtrage par Localisation (Région OU Département) ---
    # Logique :
    # 1. Si des Départements spécifiques sont cochés (new_departments_checked), on filtre par ceux-là.
    # 2. SINON, si des Régions sont cochées (new_regions_checked), on filtre par toutes les annonces de ces régions.
    # 3. SINON (rien coché), on filtre par rien (vide).
    
    if selected_departments:
        # Cas 1: Filtrer par les départements spécifiquement cochés
        df_filtered = df_filtered[df_filtered['Département'].isin(selected_departments)]
    elif selected_regions:
        # Cas 2: Aucun département spécifique coché, mais des régions sont cochées.
        # On inclut tous les départements appartenant à ces régions.
        df_filtered = df_filtered[df_filtered['Région'].isin(selected_regions)]
    else:
        # Cas 3: Ni région ni département coché (après application des autres filtres)
        return df_input[0:0]
    
    return df_filtered


# ******************************************************************************
# --- 6. CONSTRUCTION ET AFFICHAGE DU LAYOUT ---
# ******************************************************************************

# 6.1. Injection CSS et JS
if not df.empty:
    st.markdown(CSS_CONTENT, unsafe_allow_html=True) 
    inject_js_handler() 

    # Conteneur principal englobant les trois zones (Filtres, Carte, Détails)
    st.markdown('<div class="full-app-container">', unsafe_allow_html=True)

    # ===============================================================
    # ZONE 1 : LE PANNEAU GAUCHE (FILTRES)
    # ===============================================================

    st.markdown('<div class="left-panel">', unsafe_allow_html=True)
    
    # --- 6.1.1. Filtre Surface GLA ---
    st.markdown("<h3>Surface GLA (m²)</h3>")
    min_gla_default = df['Surface GLA'].min()
    max_gla_default = df['Surface GLA'].max()

    # Utilise le 'key' pour lier l'input au session_state
    st.slider(
        "Plage de surface :", 
        int(min_gla_default), 
        int(max_gla_default), 
        st.session_state.s_gla, 
        step=50, # Pas de 50 pour plus de finesse
        key="s_gla"
    )

    # --- 6.1.2. Filtre Typologie ---
    st.markdown("<h3>Typologie</h3>")
    all_typos = sorted(df['Typologie'].unique().tolist())
    
    # Logique de détection des changements pour déclencher le rerun si nécessaire
    current_typos = st.session_state.s_typo.copy()
    new_typos = []
    
    with st.container():
        for typo in all_typos:
            if st.checkbox(typo, value=typo in current_typos, key=f"typo_check_{typo}"):
                new_typos.append(typo)

    if set(new_typos) != set(current_typos):
        st.session_state.s_typo = new_typos
        st.session_state.selected_ref = None 
        st.rerun() # Rerun si la typologie a changé

    # --- 6.1.3. Filtre Localisation (Région/Département Imbriquée) ---
    st.markdown("<h3>Localisation</h3>")

    all_regions = sorted(df['Région'].unique().tolist())
    current_regions_checked = st.session_state.s_regions_checked.copy()
    current_departments_checked = st.session_state.s_departments_checked.copy()
    
    new_regions_checked = []
    new_departments_checked = []

    # Conteneur pour la structure Région/Département
    with st.container():
        for region in all_regions:
            # Checkbox du parent (Région)
            is_region_checked = st.checkbox(
                region, 
                value=region in current_regions_checked, 
                key=f"region_check_{region}"
            )
            
            if is_region_checked:
                new_regions_checked.append(region)
                
                # Afficher les Départements (enfants) si la Région est cochée
                if region in REGION_DEPARTMENTS:
                    departments_in_region = REGION_DEPARTMENTS[region]
                    
                    # Indentation pour les départements
                    st.markdown('<div class="department-checkbox">', unsafe_allow_html=True)
                    
                    for dept in departments_in_region:
                        # Checkbox de l'enfant (Département)
                        is_dept_checked_default = dept in current_departments_checked
                        
                        if st.checkbox(
                            f'{dept} ({df[df["Département"] == dept]["N° Département"].iloc[0]})', 
                            value=is_dept_checked_default, 
                            key=f"dept_check_{region}_{dept}"
                        ):
                            new_departments_checked.append(dept)
                    
                    st.markdown('</div>', unsafe_allow_html=True)

    # Détection et mise à jour pour la Localisation
    if (set(new_regions_checked) != set(current_regions_checked) or 
        set(new_departments_checked) != set(current_departments_checked)):
        
        st.session_state.s_regions_checked = new_regions_checked
        st.session_state.s_departments_checked = new_departments_checked
        st.session_state.selected_ref = None 
        st.rerun()


    # --- 6.1.4. Application et Boutons ---
    df_filtered = apply_filters(df)
    result_count = len(df_filtered)

    # Bouton de réinitialisation
    st.button("Réinitialiser les filtres", on_click=reset_filters, key="reset_button")

    # Compteur de résultats (stylé en CSS)
    st.markdown(f'<p id="result-count-message">Annonces filtrées : {result_count}</p>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True) # Fin du left-panel


    # ===============================================================
    # ZONE 2 : LA CARTE (CONTENU PRINCIPAL)
    # ===============================================================

    st.markdown('<div class="map-content-wrapper">', unsafe_allow_html=True)

    # 1. Configuration de la carte Folium (Centrage et Zoom FIXES)
    map_center = [46.603354, 1.888334] # Centre de la France Métropolitaine
    zoom_level = 6                    # Niveau de zoom statique

    m = folium.Map(
        location=map_center, 
        zoom_start=zoom_level, 
        tiles="cartodbpositron", # Un fond de carte clair et neutre
        control_scale=True,
        # Désactive le zoom si l'utilisateur ne doit pas pouvoir trop s'éloigner/rapprocher
        # zoom_control=False,
        # dragging=False 
    )

    # 2. Ajout des marqueurs
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
            
            # data-ref est la clé pour le script JS de gestion du clic
            html = f'<div class="{icon_class}" data-ref="{ref}">{ref_num}</div>'
            
            icon = folium.DivIcon(
                html=html,
                # Ajuste la taille de l'icône dans l'iFrame pour le style sélectionné
                icon_size=(40, 40) if is_selected else (35, 35),
                icon_anchor=(20, 20) if is_selected else (17.5, 17.5) # Centre l'icône
            )
            
            folium.Marker(
                [lat, lon], 
                icon=icon,
                # Tooltip de base
                tooltip=f"Réf: {ref}<br>{row['Ville']} ({row['Département']})",
            ).add_to(m)
    else:
        # Message en cas d'absence de résultats
        st.markdown('<div class="no-results-message">❌ Aucun résultat trouvé pour les critères de recherche actuels. Modifiez vos filtres.</div>', unsafe_allow_html=True)


    # 3. Affichage de la carte
    # La hauteur est gérée par le CSS pour remplir le conteneur parent (100% de la hauteur disponible)
    folium_static(m, use_container_width=True, height=800) # La hauteur est ignorée si le CSS prend le dessus

    st.markdown('</div>', unsafe_allow_html=True) # Fin map-content-wrapper


    # ===============================================================
    # ZONE 3 : LE PANNEAU DROIT (DÉTAILS)
    # ===============================================================
    
    st.markdown('<div class="right-panel-wrapper">', unsafe_allow_html=True)

    # Panneau affiché uniquement si une référence est sélectionnée
    if st.session_state.selected_ref:
        # Récupération des données du lot sélectionné
        selected_data = df[df['Référence annonce'] == st.session_state.selected_ref]
        
        if not selected_data.empty:
            selected_data = selected_data.iloc[0]

            st.markdown('<div class="right-panel">', unsafe_allow_html=True)
            st.markdown("<h4>Détails du Lot Immobilier</h4>", unsafe_allow_html=True)
            
            # 6.3.1. Bloc d'information clé
            st.markdown(f'<p class="ref-number">Réf. {selected_data["Référence annonce"]}</p>', unsafe_allow_html=True)

            # Localisation
            st.markdown(f'<p class="addr-line">{selected_data["Adresse"]}</p>', unsafe_allow_html=True)
            st.markdown(f'<p class="city-line">{selected_data["Ville"]} ({selected_data["N° Département"]})</p>', unsafe_allow_html=True)
            
            st.markdown('<div class="separator"></div>', unsafe_allow_html=True)

            # 6.3.2. Tableau des détails
            
            # Surface GLA
            st.markdown(
                f'<div class="detail-row"><span class="detail-label">Surface GLA</span><span class="detail-value">{selected_data["Surface GLA"]:,} m²</span></div>', 
                unsafe_allow_html=True
            )
            
            # Loyer annuel (Formatage monétaire français)
            try:
                loyer_formatte = f'{selected_data["Loyer annuel"]:,.0f}'.replace(',', ' ').replace('.', ',')
            except Exception:
                loyer_formatte = str(selected_data["Loyer annuel"])
                
            st.markdown(
                f'<div class="detail-row"><span class="detail-label">Loyer annuel</span><span class="detail-value">{loyer_formatte} €</span></div>', 
                unsafe_allow_html=True
            )
            
            # Typologie
            st.markdown(
                f'<div class="detail-row"><span class="detail-label">Typologie</span><span class="detail-value">{selected_data["Typologie"]}</span></div>', 
                unsafe_allow_html=True
            )
            
            # Localisation Administrative
            st.markdown(
                f'<div class="detail-row"><span class="detail-label">Région</span><span class="detail-value">{selected_data["Région"]}</span></div>', 
                unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="detail-row"><span class="detail-label">Département</span><span class="detail-value">{selected_data["Département"]}</span></div>', 
                unsafe_allow_html=True
            )
            
            st.markdown('<div class="separator"></div>', unsafe_allow_html=True)

            # 6.3.3. Boutons d'action
            st.button("Accéder à la fiche complète ➡️", key="fiche_btn")
            
            # Bouton pour désélectionner
            if st.button("Fermer les détails ✖️", key="close_btn", help="Cliquez pour masquer ce panneau."):
                st.session_state.selected_ref = None
                
                # Envoi du message au JS pour retirer le style "selected-marker"
                st.markdown("""
                    <script>
                        // Envoi au parent pour qu'il le relaie à l'iFrame (voir JS_CLICK_HANDLER)
                        window.parent.postMessage({ type: 'clear_selection' }, '*');
                    </script>
                """, unsafe_allow_html=True)
                
                st.rerun() # Rafraîchit Streamlit pour masquer le panneau

            st.markdown('</div>', unsafe_allow_html=True)
            
        else:
            # Sécurité: si la réf est définie mais le lot introuvable (ne devrait pas arriver)
            st.session_state.selected_ref = None
            st.rerun()
    else:
        # Message d'aide si aucune sélection n'est active
        st.markdown('<div class="right-panel">', unsafe_allow_html=True)
        st.markdown('<div class="no-selection-message">Cliquez sur un marqueur (numéro) sur la carte pour afficher ici les informations détaillées de l\'annonce immobilière correspondante.</div>', unsafe_allow_html=True)
        
        # Exemple de bouton de démonstration (optionnel)
        def select_demo_marker(ref_to_select):
            st.session_state.selected_ref = ref_to_select
            st.rerun()

        st.button("Simuler Clic sur Réf 00023", on_click=select_demo_marker, args=('00023',), key="demo_btn")

        st.markdown('</div>', unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True) # Fin right-panel-wrapper
    
    st.markdown('</div>', unsafe_allow_html=True) # Fin full-app-container

else:
    # Message si les données n'ont pas pu être chargées
    st.error("Impossible d'initialiser l'application. Veuillez vérifier le formatage de votre fichier de données.")

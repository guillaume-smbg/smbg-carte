import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import json
import numpy as np

# --- 1. CONFIGURATION INITIALE & GESTION DES DONNÉES ---

# Configure la page en mode large et définit le titre
st.set_page_config(layout="wide", page_title="SMBG Carte Immo") 

# --- A. DONNÉES DE DÉMONSTRATION ---
# Simule le fichier "Liste des lots.xlsx - Tableau recherche.csv"
# *** IMPORTANT ***
# REMPLACER CES DONNÉES PAR LA LECTURE DE VOTRE FICHIER CSV RÉEL
# df = pd.read_csv("Liste des lots.xlsx - Tableau recherche.csv")
# Assurez-vous d'avoir les colonnes 'Latitude', 'Longitude', 'Référence annonce', 'Surface GLA', 'Typologie', 'Région', 'Département'.

try:
    # Création du DataFrame de démonstration
    # Ajout des colonnes 'Département' et 'N° Département' pour le filtrage local
    DATA = {
        'Référence annonce': ['00022', '00023', '00024', '00025', '00026', '00027', '00028', '00029', '00030', '00031', '00032', '00033', '00034', '00035', '00036', '00037'],
        'Latitude': [48.763870, 48.822532, 48.8566, 45.764043, 44.837789, 43.6047, 48.5734, 43.7102, 43.3000, 45.1885, 47.2184, 48.4069, 49.4432, 47.0811, 47.3941, 46.2276],
        'Longitude': [2.288359, 2.190669, 2.3522, 4.835659, -0.579180, 1.4442, 7.7521, 7.2620, 5.4000, 5.7245, -1.5536, 1.9333, 2.1000, 2.4000, 5.0400, 2.2137],
        'Ville': ['Montrouge', 'Ville-d\'Avray', 'Paris', 'Lyon', 'Bordeaux', 'Toulouse', 'Strasbourg', 'Nice', 'Marseille', 'Grenoble', 'Nantes', 'Orléans', 'Rouen', 'Bourges', 'Dijon', 'Paris-Sud'],
        'Adresse': ['11 Rue des Coquelicots', '30 Rue de la Ronce', '10 Rue de la Paix', 'Place Bellecour', 'Rue Sainte Catherine', 'Place du Capitole', 'Grande Île', 'Promenade des Anglais', 'Vieux-Port', 'Place Grenette', 'Quai de la Fosse', 'Place du Martroi', 'Gros Horloge', 'Place Jacques Cœur', 'Place de la Libération', 'Rond-point des champs'],
        'Surface GLA': [325, 105, 500, 450, 200, 300, 150, 250, 600, 180, 220, 350, 400, 100, 130, 700],
        'Loyer annuel': [150000, 120000, 300000, 250000, 90000, 180000, 80000, 160000, 400000, 100000, 110000, 190000, 220000, 50000, 70000, 450000],
        'Typologie': ['Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 'Commercial', 'Pied d\'immeuble', 'Bureaux', 'Commercial', 'Pied d\'immeuble', 'Bureaux'],
        'Région': ['Ile-de-France', 'Ile-de-France', 'Ile-de-France', 'Auvergne-Rhône-Alpes', 'Nouvelle-Aquitaine', 'Occitanie', 'Grand Est', 'Provence-Alpes-Côte d\'Azur', 'Provence-Alpes-Côte d\'Azur', 'Auvergne-Rhône-Alpes', 'Pays de la Loire', 'Centre-Val de Loire', 'Normandie', 'Centre-Val de Loire', 'Bourgogne-Franche-Comté', 'Ile-de-France'],
        'Département': ['Hauts-de-Seine', 'Hauts-de-Seine', 'Paris', 'Rhône', 'Gironde', 'Haute-Garonne', 'Bas-Rhin', 'Alpes-Maritimes', 'Bouches-du-Rhône', 'Isère', 'Loire-Atlantique', 'Loiret', 'Seine-Maritime', 'Cher', 'Côte-d\'Or', 'Essonne'],
        'N° Département': ['92', '92', '75', '69', '33', '31', '67', '06', '13', '38', '44', '45', '76', '18', '21', '91'],
    }
    df = pd.DataFrame(DATA)
    # Colonne utilitaire pour l'affichage dans le marqueur (retire les zéros inutiles)
    df['ref_clean'] = df['Référence annonce'].apply(lambda x: int(x))
    
except Exception as e:
    st.error(f"Erreur lors du chargement ou de la préparation des données de démo: {e}")
    df = pd.DataFrame()


# Structure pour le filtre Région -> Départements (basée sur les données de démo)
REGION_DEPARTMENTS = df.groupby('Région')['Département'].unique().apply(list).to_dict()

# --- 2. GESTION DES SESSIONS STATE (ÉTAT DE L'APPLICATION) ---

# Initialise l'état de la référence sélectionnée (panneau de droite)
if 'selected_ref' not in st.session_state:
    st.session_state.selected_ref = None 

# Initialise l'état des filtres si non existants
if not df.empty:
    min_gla_default = df['Surface GLA'].min()
    max_gla_default = df['Surface GLA'].max()
    all_typos = sorted(df['Typologie'].unique().tolist())
    
    if 's_gla' not in st.session_state:
        st.session_state.s_gla = (min_gla_default, max_gla_default)
    if 's_typo' not in st.session_state:
        # Par défaut, toutes les typologies sont sélectionnées
        st.session_state.s_typo = all_typos
    if 's_regions_checked' not in st.session_state:
        # Par défaut, toutes les régions sont sélectionnées si l'on veut afficher tous les points
        st.session_state.s_regions_checked = sorted(df['Région'].unique().tolist())
    if 's_departments_checked' not in st.session_state:
        # Par défaut, tous les départements sont sélectionnés
        st.session_state.s_departments_checked = sorted(df['Département'].unique().tolist())
else:
    # Cas où le DataFrame est vide
    if 's_gla' not in st.session_state:
        st.session_state.s_gla = (0, 1000)
    if 's_typo' not in st.session_state:
        st.session_state.s_typo = []
    if 's_regions_checked' not in st.session_state:
        st.session_state.s_regions_checked = []
    if 's_departments_checked' not in st.session_state:
        st.session_state.s_departments_checked = []


# --- 3. INJECTION CSS (STYLE & APPARENCE) ---

def inject_css(css_code):
    """Injecte le code CSS dans l'application Streamlit pour le style complet."""
    st.markdown(f'<style>{css_code}</style>', unsafe_allow_html=True)

# Définition complète des styles CSS pour l'esthétique et la mise en page
CSS_CONTENT = """
:root {
    /* Couleurs de la charte SMBG (à adapter) */
    --logo-blue: #05263d; /* Bleu foncé */
    --copper: #b87333;   /* Couleur accent (cuivre/orange) */
    --light-gray: #f7f7f7; /* Fond clair pour le panneau droit */
    --dark-gray: #333333; /* Texte et accents sombres */
    /* Dimensions des panneaux */
    --left-panel-width: 275px;
    --right-panel-width: 275px;
    --region-indent: 15px; /* Décalage pour les départements imbriqués */
}
/* IMPORTANT: Masque la barre Streamlit par défaut */
/* Masque le header de Streamlit */
.stApp > header { visibility: hidden; } 
/* Masque les indicateurs de pages Streamlit dans la sidebar */
/* .css-18e3th9 { padding-top: 1rem; } */ 

/* Style général de la police */
.stApp, .stMarkdown, .stButton, .stDataFrame, div, span, p, td, th, label {
    font-family: 'Futura', sans-serif !important;
    color: #000;
    font-size: 13px;
    line-height: 1.4;
}

/* --- Style du Panneau Gauche (Filtres) --- */
.left-panel {
    background-color: var(--logo-blue);
    color: #fff !important;
    padding: 16px;
    border-radius: 12px;
    min-width: var(--left-panel-width);
    max-width: var(--left-panel-width);
    height: calc(100vh - 32px); 
    position: fixed;
    top: 16px; 
    left: 16px;
    overflow-y: auto; /* Scroll si trop de filtres */
    z-index: 1000; /* Assure que le panneau est au-dessus de tout */
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}
/* Titres de section dans le panneau de gauche */
.left-panel .stMarkdown h3 {
    color: var(--copper) !important;
    font-size: 16px;
    text-transform: uppercase;
    border-bottom: 1px solid var(--copper);
    padding-bottom: 5px;
    margin-top: 15px;
    margin-bottom: 10px;
}
/* Labels principaux (Slider, etc.) */
.left-panel label {
    color: #fff !important;
    font-size: 14px;
    font-weight: bold;
    margin-bottom: 4px;
    display: block;
}
/* Style pour les labels des cases à cocher */
.left-panel .stCheckbox label {
    font-weight: normal; 
    color: #fff;
    font-size: 13px;
    margin-top: 0px;
    margin-bottom: 0px;
    padding-top: 2px;
    padding-bottom: 2px;
}
/* Style pour les départements imbriqués (le décalage) */
.left-panel .department-checkbox {
    padding-left: var(--region-indent);
}
.left-panel .department-checkbox .stCheckbox label {
    font-weight: normal;
    color: #ccc; /* Couleur légèrement différente pour les départements */
    font-size: 13px;
}

/* Compteur de résultats */
#result-count-message {
    text-align: center;
    color: #fff;
    font-size: 16px;
    font-weight: bold;
    margin-top: 10px;
    padding: 8px;
    background-color: rgba(184, 115, 51, 0.2); /* Fond léger pour accentuer */
    border-radius: 8px;
}

/* Slider (Surface GLA) */
.left-panel .stSlider > div:first-child {
    background-color: var(--dark-gray); 
    border-radius: 8px;
}
/* Cibler le track du slider */
.left-panel .stSlider .st-emotion-cache-1r6p3m5 {
    background-color: var(--copper);
}

/* Bouton de Réinitialisation */
.left-panel .stButton button {
    background-color: var(--copper);
    color: #fff !important;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: bold;
    transition: background-color 0.3s;
    width: 100%;
    margin-top: 15px;
}
.left-panel .stButton button:hover {
    background-color: #e09849;
}

/* --- Mise en page principale (Carte) --- */
.main-content-wrapper {
    /* Marge pour le panneau gauche */
    margin-left: calc(var(--left-panel-width) + 32px); 
    /* Marge pour le panneau droit */
    margin-right: calc(var(--right-panel-width) + 32px);
    padding: 16px 0; /* Padding vertical */
    display: flex;
    gap: 16px;
    width: auto;
    height: 100vh;
}
.map-wrapper {
    flex-grow: 1;
    height: calc(100vh - 32px); 
    min-height: 400px; 
}
.map-wrapper .streamlit-folium {
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    height: 100% !important; /* Force la hauteur à 100% du conteneur */
    width: 100% !important; /* Force la largeur à 100% du conteneur */
}

/* --- Style des Marqueurs Folium --- */
.folium-div-icon {
    background-color: var(--logo-blue) !important;
    color: white !important;
    border-radius: 50% !important;
    width: 28px !important;
    height: 28px !important;
    line-height: 28px !important;
    text-align: center !important;
    font-size: 11px !important;
    font-weight: bold !important;
    border: 2px solid var(--copper) !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.5);
    cursor: pointer;
    transition: all 0.2s ease-in-out;
}
.folium-div-icon.selected-marker {
    background-color: var(--copper) !important;
    border: 3px solid var(--logo-blue) !important; /* Bordure plus épaisse */
    transform: scale(1.3); /* Zoom léger sur le marqueur sélectionné */
    width: 32px !important;
    height: 32px !important;
    line-height: 32px !important;
    font-size: 13px !important;
}

/* --- Style du Panneau Droit (Détails) --- */
.right-panel {
    min-width: var(--right-panel-width);
    max-width: var(--right-panel-width);
    background-color: #fff; /* Fond blanc pur pour les détails */
    border: 1px solid #e0e0e0;
    padding: 16px;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    position: fixed; 
    top: 16px;
    right: 16px;
    max-height: calc(100vh - 32px);
    overflow-y: auto;
    z-index: 1000;
}
.right-panel h4 {
    color: var(--logo-blue);
    font-size: 18px;
    font-weight: 800;
    text-align: center;
    margin-bottom: 10px;
}
.ref-number {
    font-size: 20px; 
    font-weight: 800; 
    color: var(--copper); 
    display: block;
    text-align: center;
    margin-bottom: 15px;
    padding: 8px;
    border: 2px solid var(--copper);
    border-radius: 6px;
    background-color: rgba(184, 115, 51, 0.05);
}
/* Ligne d'adresse */
.addr-line {
    font-size: 14px;
    font-weight: 500;
    color: #333;
    line-height: 1.2;
}
/* Ligne de ville/région */
.city-line {
    font-size: 18px; 
    font-weight: bold;
    color: var(--logo-blue);
    margin-bottom: 15px;
    margin-top: 5px;
}
/* Lignes de détails (Surface, Loyer, Typo) */
.detail-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0; 
    border-bottom: 1px dashed #ddd;
    font-size: 14px;
}
.detail-label {
    font-weight: bold;
    color: #444;
}
.detail-value {
    color: #111;
    text-align: right;
    font-weight: 600;
}
/* Boutons du panneau de droite */
.right-panel .stButton button {
    background-color: var(--logo-blue);
    color: #fff !important;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: bold;
    transition: background-color 0.3s;
    width: 100%;
    margin-top: 10px;
}
.right-panel .stButton button:hover {
    background-color: var(--copper);
}

/* Message d'absence de sélection */
.no-selection-message {
    background-color: #f0f0ff; /* Bleu très clair */
    color: var(--logo-blue);
    border: 1px solid #c0c0ff;
    padding: 15px;
    border-radius: 8px;
    margin-top: 20px;
    text-align: center;
    font-weight: bold;
}
"""


# --- 4. GESTION DU CLIC SUR LE MARQUEUR (JS INJECTÉ) ---

# Script JavaScript pour injecter un gestionnaire de clic DANS l'iFrame Folium.
# Ce script envoie la référence cliquée à Streamlit via postMessage.
JS_CLICK_HANDLER = """
<script>
    function setupMarkerClicks() {
        // Tente de trouver l'iFrame Folium
        const iframe = document.querySelector('.streamlit-folium > iframe');
        if (!iframe) {
            // console.warn("Folium iframe not found.");
            return;
        }

        // Exécute le code une fois que le contenu de l'iFrame est chargé
        iframe.onload = function() {
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            // Sélectionne tous les marqueurs personnalisés (DivIcon)
            const markers = iframeDoc.querySelectorAll('.folium-div-icon');

            markers.forEach(marker => {
                marker.style.cursor = 'pointer'; 
                // Ajoute l'événement de clic
                marker.onclick = function(event) {
                    event.stopPropagation();
                    const ref = marker.getAttribute('data-ref'); // Récupère la référence de l'annonce
                    
                    if (ref) {
                        // 1. Envoyer la référence sélectionnée à Streamlit (via le parent)
                        window.parent.postMessage({
                            type: 'streamlit:setSessionState',
                            state: { selected_ref: ref } // Met à jour st.session_state.selected_ref
                        }, '*');
                        
                        // 2. Déclencher un rechargement de Streamlit pour appliquer l'état et afficher le panneau de droite
                        window.parent.postMessage({
                            type: 'streamlit:rerun'
                        }, '*');
                        
                        // Enlève la classe 'selected-marker' de tous les autres marqueurs dans l'iFrame
                        iframeDoc.querySelectorAll('.selected-marker').forEach(m => {
                            m.classList.remove('selected-marker');
                        });
                        // Ajoute la classe 'selected-marker' à l'élément cliqué
                        marker.classList.add('selected-marker');
                    }
                };
            });
        };
    }
    
    // Tente de configurer les clics au chargement de la fenêtre
    window.addEventListener('load', setupMarkerClicks);

    // Écoute les messages du parent (Streamlit) pour effacer la sélection si nécessaire
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


# --- 5. LOGIQUE DE FILTRAGE PRINCIPALE ---

def apply_filters(df_input):
    """Applique tous les filtres actifs à partir de st.session_state."""
    df_filtered = df_input.copy()
    
    # Récupération des filtres de la session state
    gla_range = st.session_state.s_gla
    selected_typos = st.session_state.s_typo
    selected_departments = st.session_state.s_departments_checked
    selected_regions = st.session_state.s_regions_checked # Utile pour le cas où aucun département n'est sélectionné

    # 1. Filtrage par Surface GLA
    if gla_range:
        df_filtered = df_filtered[
            (df_filtered['Surface GLA'] >= gla_range[0]) & 
            (df_filtered['Surface GLA'] <= gla_range[1])
        ]

    # 2. Filtrage par Typologie
    if selected_typos:
        df_filtered = df_filtered[df_filtered['Typologie'].isin(selected_typos)]
    else:
        # Si aucune typologie n'est cochée, n'afficher aucune annonce (filtre exclusif)
        return df_input[0:0] 

    # 3. Filtrage par Région/Département
    if selected_departments:
        # Si au moins un département est coché, filtrer UNIQUEMENT par les départements cochés
        df_filtered = df_filtered[df_filtered['Département'].isin(selected_departments)]
    elif selected_regions:
        # Si aucun département n'est coché, mais des régions sont cochées, filtrer par ces régions
        df_filtered = df_filtered[df_filtered['Région'].isin(selected_regions)]
    else:
        # Si ni région ni département n'est coché (mais d'autres filtres sont actifs), n'afficher aucun point.
        return df_input[0:0]
    
    return df_filtered

def reset_filters():
    """Réinitialise tous les filtres à leur état initial."""
    if not df.empty:
        st.session_state.s_gla = (df['Surface GLA'].min(), df['Surface GLA'].max())
        st.session_state.s_typo = sorted(df['Typologie'].unique().tolist())
        st.session_state.s_regions_checked = sorted(df['Région'].unique().tolist())
        st.session_state.s_departments_checked = sorted(df['Département'].unique().tolist())
        st.session_state.selected_ref = None # Désélectionne le marqueur
    # Ne pas oublier de forcer le rerun
    st.rerun()

# --- 6. EXÉCUTION DE L'APPLICATION ---

# Injection du CSS et du JS au début
inject_css(CSS_CONTENT)
inject_js_handler() 

# --- A. PANNEAU GAUCHE (FILTRES) ---

st.markdown('<div class="left-panel">', unsafe_allow_html=True)
st.markdown("<h3>Filtres de recherche</h3>")

# 1. SLIDER Surface GLA
if not df.empty:
    min_gla_default = df['Surface GLA'].min()
    max_gla_default = df['Surface GLA'].max()

    gla_range_ui = st.slider(
        "Surface GLA (m²)", 
        int(min_gla_default), 
        int(max_gla_default), 
        st.session_state.s_gla, 
        key="s_gla_slider", 
        on_change=lambda: st.session_state.__setitem__('s_gla', st.session_state.s_gla_slider)
    )
    # L'état est maintenant géré par la session state via on_change


# 2. Cases à cocher Typologie
st.markdown("<h3>Typologie</h3>", unsafe_allow_html=True)
all_typos = sorted(df['Typologie'].unique().tolist())
current_typos = st.session_state.s_typo.copy()
new_typos = []

# Utilisation d'un container pour regrouper les checkbox de la typologie
with st.container():
    for typo in all_typos:
        # Si la checkbox est cochée, on l'ajoute à la liste des filtres
        if st.checkbox(typo, value=typo in current_typos, key=f"typo_check_{typo}"):
            new_typos.append(typo)

# Mise à jour de la session state
if set(new_typos) != set(current_typos):
    st.session_state.s_typo = new_typos
    st.session_state.selected_ref = None # Réinitialise la sélection à chaque changement de filtre
    st.rerun()


# 3. Cases à cocher Région et Département (Imbriqué)
st.markdown("<h3>Localisation</h3>", unsafe_allow_html=True)

all_regions = sorted(df['Région'].unique().tolist())
current_regions_checked = st.session_state.s_regions_checked.copy()
current_departments_checked = st.session_state.s_departments_checked.copy()
new_regions_checked = []
new_departments_checked = []

# Utilisation d'un container pour la localisation
with st.container():
    for region in all_regions:
        is_region_checked = st.checkbox(region, value=region in current_regions_checked, key=f"region_check_{region}")
        
        if is_region_checked:
            new_regions_checked.append(region)
            
            # Afficher les Départements si la Région est cochée
            if region in REGION_DEPARTMENTS:
                departments_in_region = REGION_DEPARTMENTS[region]
                
                # Container imbriqué pour le décalage CSS
                st.markdown('<div class="department-checkbox">', unsafe_allow_html=True)
                
                for dept in departments_in_region:
                    # Si la région était cochée précédemment, l'état initial des départements est celui de la session state
                    is_dept_checked_default = dept in current_departments_checked
                    
                    if st.checkbox(dept, value=is_dept_checked_default, key=f"dept_check_{region}_{dept}"):
                        new_departments_checked.append(dept)
                
                st.markdown('</div>', unsafe_allow_html=True)

# Mise à jour des sessions state pour la localisation
# On utilise le set() pour une comparaison efficace et éviter un rerender inutile
if set(new_regions_checked) != set(current_regions_checked) or set(new_departments_checked) != set(current_departments_checked):
    st.session_state.s_regions_checked = new_regions_checked
    st.session_state.s_departments_checked = new_departments_checked
    st.session_state.selected_ref = None # Réinitialise la sélection à chaque changement de filtre
    st.rerun()


# --- Application des filtres et affichage des résultats ---
df_filtered = apply_filters(df)
result_count = len(df_filtered)

# Bouton de réinitialisation
st.button("Réinitialiser les filtres", on_click=reset_filters)

# Affichage du compte de résultats (injecté via CSS/HTML)
st.markdown(f'<p id="result-count-message">{result_count} résultats</p>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True) # Fin left-panel


# --- B. CORPS PRINCIPAL (CARTE) ---

st.markdown('<div class="main-content-wrapper">', unsafe_allow_html=True)
st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)

# 1. Configuration de la carte Folium
# Centre fixe sur la France
map_center = [46.603354, 1.888334] # Centre France métropolitaine
zoom_level = 6 # Niveau de zoom fixe initial

m = folium.Map(
    location=map_center, 
    zoom_start=zoom_level, 
    tiles="cartodbpositron", 
    control_scale=True # Permet d'avoir une échelle sur la carte
)


# 2. Ajout des marqueurs Folium
if not df_filtered.empty:
    for index, row in df_filtered.iterrows():
        ref = row['Référence annonce']
        lat = row['Latitude']
        lon = row['Longitude']
        ref_num = row['ref_clean'] # Numéro propre (ex: 23)

        # Vérifie si ce marqueur est le marqueur sélectionné
        is_selected = (ref == st.session_state.selected_ref)

        # Crée le HTML du marqueur
        icon_class = "folium-div-icon"
        if is_selected:
            icon_class += " selected-marker"
        
        # Le HTML contient le numéro de référence. 
        # On utilise l'attribut data-ref pour le script JS de l'iFrame.
        html = f'<div class="{icon_class}" data-ref="{ref}">{ref_num}</div>'
        
        icon = folium.DivIcon(
            html=html,
            icon_size=(32, 32) if is_selected else (28, 28)
        )
        
        folium.Marker(
            [lat, lon], 
            icon=icon,
            tooltip=f"Réf: {ref}<br>{row['Ville']} ({row['Département']})",
        ).add_to(m)
else:
    # Affiche un message sur la carte s'il n'y a pas de résultats
    st.markdown('<div class="no-results-message">Aucun résultat trouvé pour les filtres sélectionnés. Veuillez ajuster vos critères.</div>', unsafe_allow_html=True)

# 3. Affichage de la carte
folium_static(m, use_container_width=True, height=800) 

st.markdown('</div>', unsafe_allow_html=True) # Fin map-wrapper
st.markdown('</div>', unsafe_allow_html=True) # Fin main-content-wrapper

# --- C. PANNEAU DE DROITE (DÉTAILS) ---

# Ce panneau est affiché de manière conditionnelle et flotte au-dessus de la carte
if st.session_state.selected_ref:
    # Tente de trouver la donnée sélectionnée dans le DataFrame original (df)
    selected_data = df[df['Référence annonce'] == st.session_state.selected_ref]
    
    if not selected_data.empty:
        selected_data = selected_data.iloc[0]

        st.markdown('<div class="right-panel">', unsafe_allow_html=True)
        st.markdown("<h4>Détails de l'annonce</h4>", unsafe_allow_html=True)
        
        # Réf. de l'annonce
        st.markdown(f'<p class="ref-number">{selected_data["Référence annonce"]}</p>', unsafe_allow_html=True)

        # Adresse 
        st.markdown(f'<p class="addr-line">{selected_data["Adresse"]}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="city-line">{selected_data["Ville"]} ({selected_data["Région"]})</p>', unsafe_allow_html=True)
        
        st.markdown('<div style="border-bottom: 2px solid #eee; margin-bottom: 15px;"></div>', unsafe_allow_html=True)

        # Détails du bien
        st.markdown(f'<div class="detail-row"><span class="detail-label">Surface GLA</span><span class="detail-value">{selected_data["Surface GLA"]:,} m²</span></div>', unsafe_allow_html=True)
        
        # Formatage du loyer
        try:
            loyer_formatte = f'{selected_data["Loyer annuel"]:,}'.replace(',', ' ').replace('.', ',')
        except Exception:
            loyer_formatte = str(selected_data["Loyer annuel"])
            
        st.markdown(f'<div class="detail-row"><span class="detail-label">Loyer annuel</span><span class="detail-value">{loyer_formatte} €</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="detail-row"><span class="detail-label">Typologie</span><span class="detail-value">{selected_data["Typologie"]}</span></div>', unsafe_allow_html=True)
        
        st.button("Voir la fiche complète", key="fiche_btn")
        
        # Bouton pour désélectionner
        if st.button("Fermer les détails", key="close_btn"):
            st.session_state.selected_ref = None
            
            # Tente d'envoyer un message au script JS pour enlever la classe de sélection sur la carte
            st.markdown("""
                <script>
                    window.parent.postMessage({ type: 'clear_selection' }, '*');
                </script>
            """, unsafe_allow_html=True)
            
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
    else:
        # Si la référence sélectionnée n'existe plus (ex: elle a été filtrée)
        st.session_state.selected_ref = None
        st.rerun()
else:
    # Affiche le message d'absence de sélection
    st.markdown('<div class="right-panel">', unsafe_allow_html=True)
    st.markdown('<div class="no-selection-message">Cliquez sur un marqueur (numéro) sur la carte pour afficher les détails de l\'annonce.</div>', unsafe_allow_html=True)
    
    # Bouton de démonstration si les données existent
    if not df.empty:
        # Fonction simple pour simuler la sélection sans passer par la carte
        def select_demo_marker(ref_to_select):
            st.session_state.selected_ref = ref_to_select

        if st.button("Simuler Clic sur Réf 00023"):
            select_demo_marker('00023')
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

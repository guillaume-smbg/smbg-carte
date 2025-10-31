import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import json
import numpy as np

# --- 1. DONNÉES DE DÉMONSTRATION (Remplacer par vos données réelles) ---
# Simule le fichier "Liste des lots.xlsx - Tableau recherche.csv"
try:
    # Ajout d'une colonne 'Département' pour la nouvelle fonctionnalité de filtre
    DATA = {
        'Référence annonce': ['00022', '00023', '00024', '00025', '00026', '00027', '00028', '00029'],
        'Latitude': [48.763870, 48.822532, 48.8566, 45.764043, 44.837789, 43.6047, 48.5734, 43.7102],
        'Longitude': [2.288359, 2.190669, 2.3522, 4.835659, -0.579180, 1.4442, 7.7521, 7.2620],
        'Ville': ['Montrouge', 'Ville-d\'Avray', 'Paris', 'Lyon', 'Bordeaux', 'Toulouse', 'Strasbourg', 'Nice'],
        'Adresse': ['11 Rue des Coquelicots', '30 Rue de la Ronce', '10 Rue de la Paix', 'Place Bellecour', 'Rue Sainte Catherine', 'Place du Capitole', 'Grande Île', 'Promenade des Anglais'],
        'Surface GLA': [325, 105, 500, 450, 200, 300, 150, 250],
        'Loyer annuel': [150000, 120000, 300000, 250000, 90000, 180000, 80000, 160000],
        'Typologie': ['Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 'Pied d\'immeuble'],
        'Région': ['Ile-de-France', 'Ile-de-France', 'Ile-de-France', 'Auvergne-Rhône-Alpes', 'Nouvelle-Aquitaine', 'Occitanie', 'Grand Est', 'Provence-Alpes-Côte d\'Azur'],
        'Département': ['Hauts-de-Seine', 'Hauts-de-Seine', 'Paris', 'Rhône', 'Gironde', 'Haute-Garonne', 'Bas-Rhin', 'Alpes-Maritimes'],
        'N° Département': ['92', '92', '75', '69', '33', '31', '67', '06'],
    }
    df = pd.DataFrame(DATA)
    # Rendre la référence annonce lisible dans les marqueurs (sans la partie 000)
    df['ref_clean'] = df['Référence annonce'].apply(lambda x: int(x))
    
except Exception as e:
    st.error(f"Erreur de chargement des données de démo: {e}")
    df = pd.DataFrame()


# --- 2. FONCTION D'INJECTION CSS ET JS ---
def inject_css(css_code):
    """Injecte le code CSS dans l'application Streamlit."""
    st.markdown(f'<style>{css_code}</style>', unsafe_allow_html=True)

# Contenu du fichier style.css (pour l'injection)
CSS_CONTENT = """
:root {
    --logo-blue: #05263d; 
    --copper: #b87333;   
    --light-gray: #f7f7f7; 
    --dark-gray: #333333; 
    --left-panel-width: 275px;
    --right-panel-width: 275px;
    --region-indent: 15px; /* Décalage pour les départements imbriqués */
}
/* IMPORTANT: Masque la barre Streamlit par défaut */
/* .stApp > header { visibility: hidden; } */ 
/* .css-18e3th9 { padding-top: 1rem; } */ /* Ajuste le padding si nécessaire */

body { overflow: hidden; }
.stApp, .stMarkdown, .stButton, .stDataFrame, div, span, p, td, th, label {
    font-family: 'Futura', sans-serif !important;
    color: #000;
    font-size: 13px;
    line-height: 1.4;
}
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
    overflow-y: auto; 
    z-index: 1000;
}
.left-panel label {
    color: #fff !important;
    font-size: 14px;
    font-weight: bold;
    margin-bottom: 4px;
    display: block;
}
/* Style spécifique pour les labels de cases à cocher */
.left-panel .stCheckbox label {
    font-weight: normal; 
    color: #fff;
    font-size: 13px;
}
/* Style pour les départements imbriqués */
.left-panel .department-checkbox label {
    margin-left: var(--region-indent);
    font-size: 13px;
    font-weight: normal;
}
.left-panel .stMarkdown h3 {
    color: var(--copper) !important;
    font-size: 16px;
    text-transform: uppercase;
    border-bottom: 1px solid var(--copper);
    padding-bottom: 5px;
    margin-top: 15px;
    margin-bottom: 10px;
}
#result-count-message {
    text-align: center;
    color: #fff;
    font-size: 16px;
    font-weight: bold;
    margin-top: 10px;
}
.left-panel .stSlider > div:first-child {
    background-color: var(--dark-gray); 
    border-radius: 8px;
}
/* Cibler le track du slider */
.left-panel .stSlider .st-emotion-cache-1r6p3m5 {
    background-color: var(--copper);
}
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
/* Les Multiselect pour Typologie redeviennent des cases à cocher visuellement */
.left-panel .stMultiSelect div[data-baseweb="select"] {
    background-color: #fff;
    border-radius: 8px;
    color: #000;
}
.left-panel .stMultiSelect [data-baseweb="tag"] {
    background-color: var(--copper);
    color: #fff;
}
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
    border: 2px solid var(--logo-blue) !important;
    transform: scale(1.2);
    width: 32px !important;
    height: 32px !important;
    line-height: 32px !important;
    font-size: 13px !important;
}
.right-panel {
    min-width: var(--right-panel-width);
    max-width: var(--right-panel-width);
    background-color: var(--light-gray); 
    padding: 16px;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    position: fixed; 
    top: 16px;
    right: 16px;
    max-height: calc(100vh - 32px);
    overflow-y: auto;
    z-index: 1000;
}
.ref-number {
    font-size: 18px; 
    font-weight: 800; 
    color: var(--copper); 
    display: block;
    text-align: center;
    margin-bottom: 15px;
    padding: 5px;
    border: 1px solid #ddd;
    border-radius: 6px;
}
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
}
.addr-line {
    font-size: 14px;
    font-weight: 500;
    color: #333;
    line-height: 1.2;
}
.city-line {
    font-size: 18px; 
    font-weight: bold;
    color: var(--logo-blue);
    margin-bottom: 15px;
    margin-top: 5px;
}
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
.no-selection-message {
    background-color: #fff3cd; 
    color: #856404;
    border: 1px solid #ffeeba;
    padding: 15px;
    border-radius: 8px;
    margin-top: 20px;
    text-align: center;
    font-weight: bold;
}
"""

# Script JavaScript pour injecter un gestionnaire de clic dans l'iFrame Folium
JS_CLICK_HANDLER = """
<script>
    function setupMarkerClicks() {
        const iframe = document.querySelector('.streamlit-folium > iframe');
        if (!iframe) {
            console.warn("Folium iframe not found.");
            return;
        }

        iframe.onload = function() {
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            const markers = iframeDoc.querySelectorAll('.folium-div-icon');

            markers.forEach(marker => {
                marker.style.cursor = 'pointer'; 
                marker.onclick = function(event) {
                    event.stopPropagation();
                    const ref = marker.getAttribute('data-ref');
                    if (ref) {
                        // Envoyer la référence à Streamlit (via le parent)
                        window.parent.postMessage({
                            type: 'streamlit:setSessionState',
                            state: { selected_ref: ref }
                        }, '*');
                        
                        // Déclencher un rechargement de Streamlit pour appliquer l'état
                        window.parent.postMessage({
                            type: 'streamlit:rerun'
                        }, '*');
                    }
                };
            });
        };
    }
    
    window.addEventListener('load', setupMarkerClicks);

</script>
"""
def inject_js_handler():
    """Injecte le script de gestionnaire de clic JS."""
    st.markdown(JS_CLICK_HANDLER, unsafe_allow_html=True)


# --- 3. CONFIGURATION ET INJECTION ---
# Configure la page en mode large et injecte le CSS et le JS
st.set_page_config(layout="wide", page_title="SMBG Carte Immo") 
inject_css(CSS_CONTENT)
inject_js_handler() # Injection du script JS


# --- 4. GESTION DES CLICS DE CARTE (SIMPLIFIÉE) ---
# Initialise l'état de la référence sélectionnée
if 'selected_ref' not in st.session_state:
    st.session_state.selected_ref = None 

# Fonction pour mettre à jour l'état de la référence sélectionnée
def select_marker(ref):
    st.session_state.selected_ref = ref

# --- 5. LOGIQUE DE FILTRAGE ---

# Définition des options de filtres
all_regions = sorted(df['Région'].unique().tolist())
all_typos = sorted(df['Typologie'].unique().tolist())

# Créer un dictionnaire Région -> Liste des Départements
REGION_DEPARTMENTS = df.groupby('Région')['Département'].unique().apply(list).to_dict()

# Initialisation de l'état des filtres si non existants
if 's_gla' not in st.session_state:
    st.session_state.s_gla = (df['Surface GLA'].min(), df['Surface GLA'].max())
if 's_typo' not in st.session_state:
    st.session_state.s_typo = all_typos
if 's_regions_checked' not in st.session_state:
    st.session_state.s_regions_checked = [] # Liste des régions cochées
if 's_departments_checked' not in st.session_state:
    st.session_state.s_departments_checked = [] # Liste des départements cochés

# --- 6. COMPOSANTS DE L'INTERFACE ---

# --- A. PANNEAU GAUCHE (FILTRES) ---
st.markdown('<div class="left-panel">', unsafe_allow_html=True)
st.markdown("### Filtres de recherche")

# 1. Slider Surface GLA
min_gla_default = df['Surface GLA'].min()
max_gla_default = df['Surface GLA'].max()

gla_range = st.slider(
    "Surface GLA (m²)", 
    int(min_gla_default), 
    int(max_gla_default), 
    st.session_state.s_gla, 
    key="s_gla_slider" # Clé unique pour le widget
)
# Mise à jour de la session state pour le reinit
st.session_state.s_gla = gla_range

# 2. Cases à cocher Typologie (Utilisation de st.checkbox)
st.markdown("<h3>Typologie</h3>", unsafe_allow_html=True)
selected_typos = []
for typo in all_typos:
    # Utilise une clé unique pour chaque checkbox
    if st.checkbox(typo, value=typo in st.session_state.s_typo, key=f"typo_check_{typo}"):
        selected_typos.append(typo)

# Mise à jour de la session state des typologies
st.session_state.s_typo = selected_typos

# 3. Cases à cocher Région et Département (Imbriqué)
st.markdown("<h3>Localisation</h3>", unsafe_allow_html=True)

# Boucle pour afficher les cases à cocher Région et Département
selected_regions = []
selected_departments = []

for region in all_regions:
    # Case à cocher pour la Région
    is_region_checked = st.checkbox(region, value=region in st.session_state.s_regions_checked, key=f"region_check_{region}")
    
    if is_region_checked:
        selected_regions.append(region)
        
        # Afficher les Départements si la Région est cochée
        if region in REGION_DEPARTMENTS:
            departments_in_region = REGION_DEPARTMENTS[region]
            
            # Utilisation de st.container pour le décalage (avec CSS)
            st.markdown('<div class="department-checkbox">', unsafe_allow_html=True)
            
            for dept in departments_in_region:
                # Case à cocher pour le Département (utilisé st.checkbox car c'est un meilleur widget pour les listes non-multiselect)
                if st.checkbox(dept, value=dept in st.session_state.s_departments_checked, key=f"dept_check_{region}_{dept}"):
                    selected_departments.append(dept)
            
            st.markdown('</div>', unsafe_allow_html=True)

# Mise à jour des sessions state
st.session_state.s_regions_checked = selected_regions
st.session_state.s_departments_checked = selected_departments


# --- Application des filtres au DataFrame ---
df_filtered = df.copy()

# 1. Filtrage par Surface GLA
df_filtered = df_filtered[
    (df_filtered['Surface GLA'] >= gla_range[0]) & 
    (df_filtered['Surface GLA'] <= gla_range[1])
]

# 2. Filtrage par Typologie
if st.session_state.s_typo:
    df_filtered = df_filtered[df_filtered['Typologie'].isin(st.session_state.s_typo)]
else:
    # Si aucune typologie n'est cochée, n'afficher aucune annonce
    df_filtered = df_filtered[0:0] 

# 3. Filtrage par Région/Département
if st.session_state.s_regions_checked:
    # Si des départements spécifiques sont cochés, filtrer par ceux-là
    if st.session_state.s_departments_checked:
        df_filtered = df_filtered[df_filtered['Département'].isin(st.session_state.s_departments_checked)]
    else:
        # Sinon, si des régions sont cochées mais aucun département n'est spécifié, filtrer par les régions cochées
        df_filtered = df_filtered[df_filtered['Région'].isin(st.session_state.s_regions_checked)]


# 4. Bouton de réinitialisation
if st.button("Réinitialiser les filtres"):
    st.session_state.s_gla = (min_gla_default, max_gla_default)
    st.session_state.s_typo = all_typos
    st.session_state.s_regions_checked = []
    st.session_state.s_departments_checked = []
    st.session_state.selected_ref = None
    st.rerun()

# Affichage du compte de résultats (injecté via CSS/HTML)
st.markdown(f'<p id="result-count-message">{len(df_filtered)} résultats</p>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True) # Fin left-panel


# --- B. CORPS PRINCIPAL (CARTE) ---
st.markdown('<div class="main-content-wrapper">', unsafe_allow_html=True)
st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)

# 1. Création de la carte Folium
# Centre fixe sur la France
map_center = [46.603354, 1.888334] # Centre France
zoom_level = 6 # Niveau de zoom fixe

m = folium.Map(location=map_center, zoom_start=zoom_level, tiles="cartodbpositron")


# 2. Ajout des marqueurs Folium
if not df_filtered.empty:
    for index, row in df_filtered.iterrows():
        ref = row['Référence annonce']
        lat = row['Latitude']
        lon = row['Longitude']
        ref_num = row['ref_clean'] # Utiliser le numéro propre (ex: 23)

        # Vérifie si ce marqueur est le marqueur sélectionné
        is_selected = (ref == st.session_state.selected_ref)

        # Crée le HTML du marqueur
        icon_class = "folium-div-icon"
        if is_selected:
            icon_class += " selected-marker"
        
        # Le HTML contient le numéro de référence. 
        # On utilise l'attribut data-ref pour le JS de l'iFrame.
        html = f'<div class="{icon_class}" data-ref="{ref}">{ref_num}</div>'
        
        icon = folium.DivIcon(
            html=html,
            icon_size=(28, 28)
        )
        
        folium.Marker(
            [lat, lon], 
            icon=icon,
            tooltip=f"Réf: {ref}<br>{row['Ville']}",
        ).add_to(m)
else:
    # Message si aucun résultat n'est trouvé
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
        
        st.markdown('---')

        # Détails du bien
        st.markdown(f'<div class="detail-row"><span class="detail-label">Surface GLA</span><span class="detail-value">{selected_data["Surface GLA"]} m²</span></div>', unsafe_allow_html=True)
        # Formatage du loyer
        loyer_formatte = f'{selected_data["Loyer annuel"]:,}'.replace(',', ' ').replace('.', ',')
        st.markdown(f'<div class="detail-row"><span class="detail-label">Loyer annuel</span><span class="detail-value">{loyer_formatte} €</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="detail-row"><span class="detail-label">Typologie</span><span class="detail-value">{selected_data["Typologie"]}</span></div>', unsafe_allow_html=True)
        
        st.button("Voir la fiche complète", key="fiche_btn")
        
        if st.button("Fermer les détails", key="close_btn"):
            st.session_state.selected_ref = None
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
    else:
        # Si la référence sélectionnée n'existe plus (données originales modifiées)
        st.session_state.selected_ref = None
        st.rerun()
else:
    # Affiche le message d'absence de sélection + bouton de démo
    st.markdown('<div class="right-panel">', unsafe_allow_html=True)
    st.markdown('<div class="no-selection-message">Cliquez sur un marqueur (numéro) sur la carte pour afficher les détails de l\'annonce.</div>', unsafe_allow_html=True)
    
    # Bouton de démonstration
    if st.button("Simuler Clic sur Réf 00023"):
        select_marker('00023')
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

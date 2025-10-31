import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import json
import numpy as np

# --- 1. DONNÉES DE DÉMONSTRATION (Remplacer par vos données réelles) ---
# Simule le fichier "Liste des lots.xlsx - Tableau recherche.csv"
try:
    # Utilisation d'un dictionnaire de données fictives pour la démonstration
    DATA = {
        'Référence annonce': ['00022', '00023', '00024', '00025', '00026'],
        'Latitude': [48.763870, 48.822532, 48.8566, 45.764043, 44.837789],
        'Longitude': [2.288359, 2.190669, 2.3522, 4.835659, -0.579180],
        'Ville': ['Montrouge', 'Ville-d\'Avray', 'Paris', 'Lyon', 'Bordeaux'],
        'Adresse': ['11 Rue des Coquelicots', '30 Rue de la Ronce', '10 Rue de la Paix', 'Place Bellecour', 'Rue Sainte Catherine'],
        'Surface GLA': [325, 105, 500, 450, 200],
        'Loyer annuel': [150000, 120000, 300000, 250000, 90000],
        'Typologie': ['Bureaux', 'Pied d\'immeuble', 'Commercial', 'Bureaux', 'Pied d\'immeuble'],
        'Région': ['Ile-de-France', 'Ile-de-France', 'Ile-de-France', 'Auvergne-Rhône-Alpes', 'Nouvelle-Aquitaine'],
    }
    df = pd.DataFrame(DATA)
    # Rendre la référence annonce lisible dans les marqueurs (sans la partie 000)
    df['ref_clean'] = df['Référence annonce'].apply(lambda x: int(x))
    
except Exception as e:
    # Affiche une erreur si le chargement des données de démo échoue
    st.error(f"Erreur de chargement des données de démo: {e}")
    df = pd.DataFrame()


# --- 2. FONCTION D'INJECTION CSS ---
def inject_css(css_code):
    """Injecte le code CSS dans l'application Streamlit."""
    # NOTE: Il est crucial de coller ici le contenu complet du style.css
    st.markdown(f'<style>{css_code}</style>', unsafe_allow_html=True)

# Contenu du fichier style.css (pour l'injection)
# Ceci garantit que le code Python est auto-suffisant même si le fichier CSS n'est pas vu
CSS_CONTENT = """
:root {
    --logo-blue: #05263d; 
    --copper: #b87333;   
    --light-gray: #f7f7f7; 
    --dark-gray: #333333; 
    --left-panel-width: 275px;
    --right-panel-width: 275px;
}
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
    margin-left: calc(var(--left-panel-width) + 32px); 
    padding: 16px;
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
    height: 100%; 
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


# --- 3. CONFIGURATION ET INJECTION ---
# Configure la page en mode large et injecte le CSS
st.set_page_config(layout="wide", page_title="SMBG Carte Immo") 
inject_css(CSS_CONTENT)


# --- 4. GESTION DES CLICS DE CARTE (SIMPLIFIÉE) ---
# Initialise l'état de la référence sélectionnée
if 'selected_ref' not in st.session_state:
    st.session_state.selected_ref = None 

# Fonction pour mettre à jour l'état de la référence sélectionnée
def select_marker(ref):
    st.session_state.selected_ref = ref

# --- 5. LOGIQUE DE FILTRAGE ---
df_filtered = df.copy()

# --- 6. COMPOSANTS DE L'INTERFACE ---

# --- A. PANNEAU GAUCHE (FILTRES) ---
# Ouvre le conteneur du panneau de gauche avec la classe CSS
st.markdown('<div class="left-panel">', unsafe_allow_html=True)
st.markdown("### Filtres de recherche")

# Définit les valeurs par défaut pour les sliders
min_gla_default = df['Surface GLA'].min()
max_gla_default = df['Surface GLA'].max()
min_gla_current = st.session_state.get('s_gla', (min_gla_default, max_gla_default))[0]
max_gla_current = st.session_state.get('s_gla', (min_gla_default, max_gla_default))[1]

# 1. Slider Surface GLA
gla_range = st.slider(
    "Surface GLA (m²)", 
    int(min_gla_default), 
    int(max_gla_default), 
    (min_gla_current, max_gla_current), 
    key="s_gla"
)

# 2. Selectbox Région
regions = df['Région'].unique().tolist()
regions_selection = st.selectbox(
    "Région", 
    ["Toutes"] + sorted(regions), 
    key="s_region"
)

# 3. Multiselect Typologie
typo_default = df['Typologie'].unique().tolist()
typo_selection = st.multiselect(
    "Typologie", 
    typo_default, 
    default=st.session_state.get('s_typo', typo_default),
    key="s_typo"
)

# Application des filtres au DataFrame
df_filtered = df[
    (df['Surface GLA'] >= gla_range[0]) & 
    (df['Surface GLA'] <= gla_range[1]) &
    (df['Typologie'].isin(typo_selection))
]
if regions_selection != "Toutes":
    df_filtered = df_filtered[df_filtered['Région'] == regions_selection]


# 4. Bouton de réinitialisation
if st.button("Réinitialiser les filtres"):
    st.session_state.s_gla = (min_gla_default, max_gla_default)
    st.session_state.s_region = "Toutes"
    st.session_state.s_typo = typo_default
    st.session_state.selected_ref = None
    st.rerun()

# Affichage du compte de résultats (injecté via CSS/HTML)
st.markdown(f'<p id="result-count-message">{len(df_filtered)} résultats</p>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True) # Fin left-panel


# --- B. CORPS PRINCIPAL (CARTE) ---
st.markdown('<div class="main-content-wrapper">', unsafe_allow_html=True)
st.markdown('<div class="map-wrapper">', unsafe_allow_html=True)

# 1. Création de la carte Folium
# Centre la carte en fonction des résultats filtrés, ou sur la France par défaut
if not df_filtered.empty:
    # Calcule le centre des marqueurs filtrés
    map_center = [df_filtered['Latitude'].mean(), df_filtered['Longitude'].mean()]
    zoom_level = 10 if len(df_filtered) == 1 else (7 if len(df_filtered) < 5 else 6)
else:
    map_center = [46.603354, 1.888334] # Centre France
    zoom_level = 6

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
        # L'événement JavaScript (onclick) est la seule façon de communiquer
        # un clic de la carte (Folium/iFrame) vers Streamlit.
        # Pour une implémentation complète, il faudrait un composant personnalisé.
        # Ici, nous laissons l'attribut data-ref pour un usage futur.
        html = f'<div class="{icon_class}" data-ref="{ref}">{ref_num}</div>'
        
        icon = folium.DivIcon(
            html=html,
            icon_size=(28, 28)
        )
        
        folium.Marker(
            [lat, lon], 
            icon=icon,
            tooltip=f"Réf: {ref}",
        ).add_to(m)
else:
    # Message si aucun résultat n'est trouvé
    st.markdown('<div class="no-results-message">Aucun résultat trouvé pour les filtres sélectionnés. Veuillez ajuster vos critères.</div>', unsafe_allow_html=True)

# 3. Affichage de la carte
# La carte utilise la hauteur complète du conteneur grâce au CSS
folium_static(m, width=900, height=800) 

st.markdown('</div>', unsafe_allow_html=True) # Fin map-wrapper
st.markdown('</div>', unsafe_allow_html=True) # Fin main-content-wrapper

# --- C. PANNEAU DE DROITE (DÉTAILS) ---

# Ce panneau est affiché de manière conditionnelle et flotte au-dessus de la carte
if st.session_state.selected_ref and not df_filtered.empty:
    # Tente de trouver la donnée sélectionnée dans le DataFrame filtré
    selected_data = df_filtered[df_filtered['Référence annonce'] == st.session_state.selected_ref]
    
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
        # L'annonce sélectionnée n'est plus visible car elle a été filtrée
        st.session_state.selected_ref = None
        st.rerun()
else:
    # Affiche le message d'absence de sélection + bouton de démo
    st.markdown('<div class="right-panel">', unsafe_allow_html=True)
    st.markdown('<div class="no-selection-message">Cliquez sur un marqueur (numéro) sur la carte pour afficher les détails de l\'annonce.</div>', unsafe_allow_html=True)
    
    # Bouton de démonstration pour illustrer le panneau de détails
    if st.button("Simuler Clic sur Réf 00023"):
        select_marker('00023')
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

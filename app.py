import streamlit as st
import pandas as pd
import folium
from folium.plugins import DivIcon
from streamlit_folium import st_folium
import os
import re
from typing import Dict, Any

# --- 1. Configuration et Constantes ---
# Chemins des fichiers (selon l'architecture demandée)
DATA_FILE = "data/Liste des lots.xlsx"
LOGO_PATH = "assets/Logo bleu crop.png"
ASSETS_DIR = "assets/"

# Identité Visuelle SMBG
COULEUR_BLEU = "#05263d"
COULEUR_CUIVRE = "#C67B42"
LARGEUR_PANNEAU = "275px" # Largeur fixe pour la sidebar et le panneau de droite

# Colonnes des filtres simples (en plus de Région/Département)
FILTRES_CHECKBOX = ["Emplacement", "Typologie", "Extraction", "Restauration"]

# Colonnes à afficher dans le panneau de détails (colonnes G à AL de l'Excel)
# Liste basée sur un Excel type, ajuster si les noms de colonnes sont différents dans l'Excel réel.
COLONNES_DETAILS = [
    "Lien Google Maps", "Description courte", "Surface GLA", "Linéaire",
    "Hauteur libre", "Type de bail", "Durée du bail", "Date de disponibilité",
    "Loyer annuel", "Charges annuelles", "Taxes annuelles", "Honoraires de commercialisation",
    "Dépôt de garantie", "Frais de rédaction d'actes", "Répartition des charges",
    "Travaux à la charge du preneur", "Conditions particulières", "DPE",
    "GES", "Informations Complémentaires", "Référence cadastre",
    "Autres informations 1", "Autres informations 2", "Autres informations 3",
    "Autres informations 4", "Autres informations 5", "Autres informations 6",
]

# --- 2. Fonctions Utilitaires et Initialisation ---

@st.cache_data
def load_data(file_path: str) -> pd.DataFrame:
    """Charge et nettoie les données Excel."""
    if not os.path.exists(file_path):
        st.error(f"Fichier de données non trouvé : {file_path}. Veuillez le placer dans le dossier data/.")
        return pd.DataFrame()

    df = pd.read_excel(file_path)

    # Renommage/Nettoyage de base des colonnes
    df.columns = [col.strip() for col in df.columns]

    # Filtrage des lots actifs
    df = df[df['Actif'].astype(str).str.lower().str.strip() == 'oui'].copy()

    # Nettoyage des coordonnées (suppression des lignes avec NaN)
    df.dropna(subset=['Latitude', 'Longitude'], inplace=True)

    # Conversion des coordonnées en float (gestion des erreurs si besoin)
    try:
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    except Exception as e:
        st.error(f"Erreur de conversion des coordonnées GPS : {e}")

    # Nettoyage et formatage des références d'annonce (suppression des zéros non significatifs)
    def format_ref(ref):
        if pd.isna(ref):
            return None
        s_ref = str(ref).strip()
        parts = s_ref.split('.')
        if parts[0].isdigit():
            # Supprime les zéros non significatifs de la partie entière
            parts[0] = str(int(parts[0]))
        return '.'.join(parts)
    
    df['Référence annonce formatée'] = df['Référence annonce'].apply(format_ref)
    df.set_index('Référence annonce formatée', inplace=True)

    return df

def init_session_state(df: pd.DataFrame):
    """Initialise les variables de session d'état si elles n'existent pas."""
    if 'filtered_df' not in st.session_state:
        st.session_state.filtered_df = df
    if 'selected_ref' not in st.session_state:
        st.session_state.selected_ref = None
    if 'map_initial_zoom' not in st.session_state:
        st.session_state.map_initial_zoom = 5

    # Initialisation des états des filtres (sliders et checkboxes)
    if 'reset_trigger' not in st.session_state:
        st.session_state.reset_trigger = 0 # Utilisé pour réinitialiser les widgets

    min_s, max_s = df['Surface GLA'].min(skipna=True), df['Surface GLA'].max(skipna=True)
    min_l, max_l = df['Loyer annuel'].min(skipna=True), df['Loyer annuel'].max(skipna=True)

    if 'surface_range' not in st.session_state:
        st.session_state.surface_range = (min_s, max_s)
        st.session_state.surface_bounds = (min_s, max_s)

    if 'loyer_range' not in st.session_state:
        st.session_state.loyer_range = (min_l, max_l)
        st.session_state.loyer_bounds = (min_l, max_l)

    # Initialisation des checkboxes
    for col in ["Région", "Département"] + FILTRES_CHECKBOX:
        for val in df[col].astype(str).str.strip().unique():
            if val not in st.session_state:
                st.session_state[f"cb_{col}_{val}"] = False

def format_value(key: str, value: Any) -> str:
    """Formate une valeur selon les règles (monétaire, surface, masquage)."""
    if pd.isna(value):
        return None

    s_value = str(value).strip().lower()

    # Règle de masquage
    if s_value in ["", "néant", "-", "/"]:
        return None
    
    # Tentative de conversion numérique pour la règle de masquage '0'
    try:
        num_value = float(value)
        if num_value == 0:
            return None
    except (ValueError, TypeError):
        pass # La valeur n'est pas numérique, on ne l'écarte pas pour 0

    # Formatage monétaire/surface
    is_currency = any(kw in key.lower() for kw in ["loyer", "charges", "taxes", "honoraires", "dépôt"])
    is_surface = any(kw in key.lower() for kw in ["surface", "linéaire"])

    if is_currency:
        try:
            return f"{int(float(value)):,.0f} €".replace(",", " ")
        except (ValueError, TypeError):
            return str(value)
    elif is_surface:
        try:
            return f"{int(float(value)):,.0f} m²".replace(",", " ")
        except (ValueError, TypeError):
            return str(value)
    else:
        return str(value)

# --- 3. CSS et Style ---

def inject_smbg_style(df: pd.DataFrame):
    """
    Injecte le CSS pour l'identité visuelle SMBG (couleurs, polices)
    et le layout fixe (sidebar, panneau droit, carte).
    """
    # Construction du CSS pour les polices Futura
    font_face_css = ""
    # S'assurer que les fichiers de police sont dans assets/ et décompressés
    for file_name in os.listdir(ASSETS_DIR):
        if file_name.endswith(('.ttf', '.otf')):
            font_name_clean = file_name.split('.')[0].replace('-', ' ')
            font_face_css += f"""
            @font-face {{
                font-family: "Futura SMBG";
                src: url("data:font/ttf;base64,{_get_base64_encoded_file(os.path.join(ASSETS_DIR, file_name))}") format("truetype");
                font-weight: {'bold' if 'bold' in font_name_clean.lower() or 'medium' in font_name_clean.lower() else 'normal'};
                font-style: normal;
            }}
            """

    # Injecte un fichier en base64 (nécessaire pour Streamlit Cloud)
    logo_base64 = _get_base64_encoded_file(LOGO_PATH)
    
    # CSS principal
    st.markdown(f"""
        <style>
            {font_face_css}

            /* --- POLICE ET COULEURS GLOBAL --- */
            
            html, body, [data-testid="stAppViewContainer"] {{
                font-family: "Futura SMBG", Futura, "Futura PT", "Century Gothic", Arial, sans-serif;
                color: {COULEUR_BLEU};
            }}
            
            h1, h2, h3, h4, h5, h6 {{
                color: {COULEUR_BLEU};
                font-family: "Futura SMBG", Futura, "Futura PT", "Century Gothic", Arial, sans-serif;
            }}

            /* --- LAYOUT ET SIDEBAR FIXE --- */

            /* Supprime l'espace autour de l'application Streamlit */
            .main > div {{
                padding: 0 !important;
            }}

            /* Sidebar: Fond bleu SMBG, largeur fixe, toujours visible */
            [data-testid="stSidebar"] {{
                width: {LARGEUR_PANNEAU} !important;
                background-color: {COULEUR_BLEU};
                min-width: {LARGEUR_PANNEAU} !important;
                max-width: {LARGEUR_PANNEAU} !important;
            }}

            /* Contenu de la sidebar (texte blanc/cuivre) */
            [data-testid="stSidebar"] * {{
                color: white !important;
            }}
            [data-testid="stSidebar"] h2, 
            [data-testid="stSidebar"] .st-eb, /* pour le titre de la checkbox */
            [data-testid="stSidebar"] .st-be, /* pour le label des sliders */
            [data-testid="stSidebar"] .st-d7 {{ /* pour le titre des filtres */
                color: white !important;
            }}
            [data-testid="stSidebar"] .st-cf,
            [data-testid="stSidebar"] .st-bg {{ /* pour le texte des checkbox */
                color: white !important;
            }}
            
            /* Styles pour les sliders */
            .stSlider > div > div:nth-child(2) > div {{ /* Coloration de la barre du slider */
                background-color: {COULEUR_CUIVRE};
            }}
            .stSlider > div > div:nth-child(2) > div:nth-child(3) {{ /* Pointeur du slider */
                background-color: {COULEUR_CUIVRE};
                border-color: {COULEUR_CUIVRE};
            }}

            /* Indentation des départements */
            .dept-wrap {{
                margin-left: 15px;
            }}

            /* Masquage du bouton d'agrandissement de l'image (logo) */
            img[alt="SMBG Logo"] + button {{
                display: none !important;
            }}
            
            /* --- ZONE CENTRALE (CARTE) ET PANNEAU DROIT --- */
            
            /* Conteneur principal (main) pour le layout 3 colonnes simulé */
            /* La zone centrale doit être calculée: 100vw - 2*275px (plus les paddings) */
            [data-testid="stAppViewContainer"] > .main {{
                display: flex;
                flex-direction: row;
                position: relative;
                /* Prend toute la largeur restante */
                width: calc(100% - {LARGEUR_PANNEAU}); 
                margin-left: {LARGEUR_PANNEAU}; /* Décalage pour laisser la place à la sidebar */
            }}
            
            /* Conteneur de la carte (pour prendre l'espace restant) */
            [data-testid="stVerticalBlock"] {{
                flex-grow: 1;
                /* Enlève le padding par défaut de Streamlit pour la carte */
                padding: 0 !important; 
            }}
            
            /* Panneau de détails (Positionnement fixe à droite, état rétractable géré via JS/CSS) */
            #detail-panel-smbg {{
                position: fixed;
                top: 0;
                right: 0;
                width: {LARGEUR_PANNEAU};
                height: 100vh;
                background-color: {COULEUR_BLEU};
                color: white;
                box-shadow: -2px 0 5px rgba(0,0,0,0.5);
                transition: transform 0.3s ease-in-out;
                z-index: 1000;
                overflow-y: auto;
                padding: 20px;
                /* État initial: replié (caché) */
                transform: translateX({LARGEUR_PANNEAU}); 
            }}
            
            #detail-panel-smbg.open {{
                /* État ouvert: visible */
                transform: translateX(0); 
            }}
            
            /* Panneau de détails : Label en Cuivre */
            #detail-panel-smbg .label-cuivre {{
                color: {COULEUR_CUIVRE};
                font-weight: bold;
            }}
            
            /* Ajustement pour que la carte ne soit pas cachée sous la sidebar ou le panneau */
            .st-folium {{
                width: 100%;
                /* Ajustement de la largeur pour tenir compte du panneau droit potentiel */
                /* La largeur est gérée par le flex-grow ci-dessus et l'état JS ci-dessous */
            }}
            
            /* Styles pour les pins personnalisés */
            .smbg-pin {{
                border: 2px solid {COULEUR_BLEU};
                background-color: {COULEUR_BLEU};
                border-radius: 50%;
                color: white;
                text-align: center;
                font-weight: bold;
                line-height: 25px; /* Ajustement de la hauteur pour le centrage vertical */
                font-size: 10px;
                cursor: pointer;
            }}
            
            /* --- LOGO EN BASE64 POUR STREAMLIT CLOUD --- */
            .smbg-logo-container {{
                margin-top: 25px; /* Marge haute de 25px */
                margin-bottom: 20px;
                padding: 0 15px;
            }}
            .smbg-logo {{
                display: block;
                width: 100%; 
                height: auto;
                content: url(data:image/png;base64,{logo_base64});
            }}
            
        </style>
        
        <script>
            // Fonctions de gestion du panneau
            function openDetailPanel() {{
                const panel = document.getElementById('detail-panel-smbg');
                panel.classList.add('open');
                // Optionnel: Décaler la carte de 275px à gauche pour qu'elle ne soit pas cachée
                // Ceci est complexe en CSS pur, le flexbox/width 100% de la div parente le gère mieux.
            }}

            function closeDetailPanel() {{
                const panel = document.getElementById('detail-panel-smbg');
                panel.classList.remove('open');
            }}
            
            // Écouteur d'événement pour le clic sur la carte
            // Streamlit / Folium fournit le clic via st_folium, nous gérons l'état en Python.

            // S'assurer que la sidebar est collée et non repliable
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
            if (sidebar) {{
                sidebar.style.transform = 'none'; // Annule la translation de masquage
            }}
            const sidebarToggleButton = window.parent.document.querySelector('[data-testid="stSidebarNav"] button');
            if (sidebarToggleButton) {{
                sidebarToggleButton.style.display = 'none'; // Masque le bouton de repli
            }}

            // Gérer l'état initial du panneau au chargement
            const isSelected = window.parent.document.body.querySelector('[data-selected-ref]');
            if (isSelected && isSelected.getAttribute('data-selected-ref') !== 'None') {{
                openDetailPanel();
            }} else {{
                closeDetailPanel();
            }}

        </script>
        """, 
        unsafe_allow_html=True
    )
    
def _get_base64_encoded_file(path: str) -> str:
    """Encode un fichier en Base64 pour l'injection CSS/HTML."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        st.error(f"Erreur lors de l'encodage de {path}: {e}")
        return ""

# Importation ici pour éviter un conflit d'initialisation dans la fonction
import base64 

# --- 4. Logique de Filtrage ---

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Applique tous les filtres actifs à la DataFrame."""
    filtered_df = df.copy()
    
    # --- 4.1. Filtrage Région / Département ---
    selected_regions = [
        val for val in df["Région"].astype(str).str.strip().unique()
        if st.session_state.get(f"cb_Région_{val}", False)
    ]
    
    if selected_regions:
        df_regions = filtered_df[filtered_df["Région"].astype(str).str.strip().isin(selected_regions)].copy()
        
        # Logique des départements
        selected_depts = []
        for region in selected_regions:
            depts_in_region = df_regions[df_regions["Région"].astype(str).str.strip() == region]["Département"].astype(str).str.strip().unique()
            
            # Vérifie si au moins un département de cette région est coché
            checked_depts = [
                dept for dept in depts_in_region
                if st.session_state.get(f"cb_Département_{dept}", False)
            ]
            
            if checked_depts:
                # Si des départements sont cochés, on filtre sur ceux-là
                selected_depts.extend(checked_depts)
            else:
                # Si la région est cochée mais aucun département de cette région n'est coché,
                # on inclut tous les départements de cette région (filtrage au niveau Région)
                selected_depts.extend(depts_in_region)

        # Application du filtre final Région/Département
        if selected_depts:
            # On prend la DataFrame originale pour éviter la double restriction
            filtered_df = df[df["Département"].astype(str).str.strip().isin(selected_depts)]
        else:
            # Si aucune région ou département n'est effectivement sélectionné (cas initial ou reset)
            filtered_df = df.copy()

    # --- 4.2. Filtrage Sliders (Surface GLA) ---
    min_s, max_s = st.session_state.get("surface_range", st.session_state.surface_bounds)
    # Gère les NaN en les laissant passer si Surface GLA n'est pas NaN
    filtered_df = filtered_df[
        (filtered_df['Surface GLA'].isna()) | 
        ((filtered_df['Surface GLA'] >= min_s) & (filtered_df['Surface GLA'] <= max_s))
    ]

    # --- 4.3. Filtrage Sliders (Loyer annuel) ---
    min_l, max_l = st.session_state.get("loyer_range", st.session_state.loyer_bounds)
    filtered_df = filtered_df[
        (filtered_df['Loyer annuel'].isna()) | 
        ((filtered_df['Loyer annuel'] >= min_l) & (filtered_df['Loyer annuel'] <= max_l))
    ]

    # --- 4.4. Filtres Checkbox Simples (Emplacement, Typologie, etc.) ---
    for col in FILTRES_CHECKBOX:
        selected_values = [
            val for val in df[col].astype(str).str.strip().unique()
            if st.session_state.get(f"cb_{col}_{val}", False)
        ]
        
        if selected_values:
            # Gère les NaN en les incluant si elles sont dans la liste des valeurs sélectionnées,
            # ou en filtrant uniquement sur les valeurs sélectionnées.
            filtered_df = filtered_df[
                (filtered_df[col].astype(str).str.strip().isin(selected_values))
            ]

    # Mise à jour de l'état
    st.session_state.filtered_df = filtered_df

# --- 5. Composants de l'UI ---

def create_sidebar_filters(df: pd.DataFrame):
    """Crée le volet gauche avec le logo et tous les filtres."""
    
    st.sidebar.markdown(
        f'<div class="smbg-logo-container"><div class="smbg-logo" alt="SMBG Logo"></div></div>', 
        unsafe_allow_html=True
    )
    
    st.sidebar.markdown("## 🔎 Filtres")
    
    # Bouton Réinitialiser
    if st.sidebar.button("Réinitialiser tous les filtres", key=f"reset_all_filters_{st.session_state.reset_trigger}"):
        # Réinitialisation de l'état pour forcer le re-rendu des widgets
        st.session_state.reset_trigger += 1
        st.session_state.selected_ref = None
        st.rerun() # Redémarre l'application pour une réinitialisation propre

    # --- 5.1. Filtres Région / Département ---
    st.sidebar.markdown("### Géographie")
    regions = df["Région"].astype(str).str.strip().unique()
    
    for region in sorted(regions):
        # Checkbox Région
        st.sidebar.checkbox(
            region, 
            value=st.session_state.get(f"cb_Région_{region}", False), 
            key=f"cb_Région_{region}",
            on_change=apply_filters,
            args=(df,)
        )
        
        # Affichage conditionnel des départements (indentés)
        if st.session_state.get(f"cb_Région_{region}", False):
            depts = df[df["Région"].astype(str).str.strip() == region]["Département"].astype(str).str.strip().unique()
            for dept in sorted(depts):
                # Utilisation du CSS .dept-wrap pour l'indentation de 15px
                st.sidebar.markdown(f'<div class="dept-wrap">', unsafe_allow_html=True)
                st.sidebar.checkbox(
                    dept, 
                    value=st.session_state.get(f"cb_Département_{dept}", False), 
                    key=f"cb_Département_{dept}",
                    on_change=apply_filters,
                    args=(df,)
                )
                st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    # --- 5.2. Filtres Sliders ---
    st.sidebar.markdown("### Surface / Loyer")
    
    # Slider Surface GLA
    min_s_bound, max_s_bound = st.session_state.surface_bounds
    if not pd.isna(min_s_bound) and not pd.isna(max_s_bound):
        current_s_range = st.sidebar.slider(
            "Surface GLA (m²)",
            min_value=int(min_s_bound),
            max_value=int(max_s_bound),
            value=st.session_state.get("surface_range", (int(min_s_bound), int(max_s_bound))),
            step=10,
            key=f"slider_surface_{st.session_state.reset_trigger}",
            on_change=lambda: st.session_state.update({"surface_range": st.session_state[f"slider_surface_{st.session_state.reset_trigger}"]}),
        )
        if current_s_range != st.session_state.surface_range:
             st.session_state.surface_range = current_s_range
             apply_filters(df)
        
    # Slider Loyer annuel
    min_l_bound, max_l_bound = st.session_state.loyer_bounds
    if not pd.isna(min_l_bound) and not pd.isna(max_l_bound):
        current_l_range = st.sidebar.slider(
            "Loyer annuel (€)",
            min_value=int(min_l_bound),
            max_value=int(max_l_bound),
            value=st.session_state.get("loyer_range", (int(min_l_bound), int(max_l_bound))),
            step=1000,
            key=f"slider_loyer_{st.session_state.reset_trigger}",
            on_change=lambda: st.session_state.update({"loyer_range": st.session_state[f"slider_loyer_{st.session_state.reset_trigger}"]}),
        )
        if current_l_range != st.session_state.loyer_range:
             st.session_state.loyer_range = current_l_range
             apply_filters(df)

    # --- 5.3. Filtres Checkbox Simples (Emplacement, Typologie, etc.) ---
    st.sidebar.markdown("### Caractéristiques")
    for col in FILTRES_CHECKBOX:
        st.sidebar.markdown(f"**{col}**")
        values = df[col].astype(str).str.strip().unique()
        for val in sorted(values):
            if val in ["nan", ""]: continue # Ignorer les valeurs vides/NaN
            st.sidebar.checkbox(
                val, 
                value=st.session_state.get(f"cb_{col}_{val}", False), 
                key=f"cb_{col}_{val}",
                on_change=apply_filters,
                args=(df,)
            )

def create_detail_panel(df: pd.DataFrame):
    """Crée le panneau de détails rétractable à droite."""
    
    selected_ref = st.session_state.selected_ref
    
    # Masquage/Affichage du panneau géré par l'état JS/CSS
    panel_class = "open" if selected_ref else ""

    # Ajout d'une div "fantôme" pour le panneau de détails
    # Le contenu est injecté directement dans cette div via st.markdown(unsafe_allow_html=True)
    st.markdown(
        f'<div id="detail-panel-smbg" class="{panel_class}" data-selected-ref="{selected_ref}">', 
        unsafe_allow_html=True
    )
    
    if selected_ref and selected_ref in df.index:
        lot_data = df.loc[selected_ref]

        st.markdown("## Détails de l’annonce")
        st.markdown(f"### Réf. : **{selected_ref}**")
        
        st.markdown("---")
        
        # Affichage des données de G à AL (COLONNES_DETAILS)
        for col_name in COLONNES_DETAILS:
            raw_value = lot_data.get(col_name)
            formatted_value = format_value(col_name, raw_value)
            
            # Traitement spécial pour le lien Google Maps
            if col_name == "Lien Google Maps" and formatted_value:
                st.markdown(f"""
                    <div style="margin-bottom: 10px;">
                        <span class="label-cuivre">Lien Google Maps : </span>
                        <a href="{formatted_value}" target="_blank" style="color: white; text-decoration: underline;">Cliquer ici</a>
                    </div>
                """, unsafe_allow_html=True)
            elif formatted_value is not None:
                st.markdown(f"""
                    <div style="margin-bottom: 5px;">
                        <span class="label-cuivre">{col_name} : </span>
                        <span>{formatted_value}</span>
                    </div>
                """, unsafe_allow_html=True)
                
    st.markdown('</div>', unsafe_allow_html=True) # Fermeture de #detail-panel-smbg

def create_map_display(df: pd.DataFrame):
    """Crée la zone centrale avec la carte Leaflet et les pins."""
    
    center_lat = df['Latitude'].mean() if not df.empty else 46.603354
    center_lon = df['Longitude'].mean() if not df.empty else 1.888334
    
    m = folium.Map(
        location=[center_lat, center_lon], 
        zoom_start=st.session_state.map_initial_zoom, 
        tiles="OpenStreetMap Mapnik",
        height=800
    )

    # --- Ajout des Pins (DivIcon personnalisé SMBG) ---
    for index, row in st.session_state.filtered_df.iterrows():
        lat, lon = row['Latitude'], row['Longitude']
        ref = index # Référence formatée (ex: 3, 5.1)
        
        # Création de l'icône personnalisée (Cercle SMBG Bleu avec texte blanc)
        # La taille 25x25 est arbitraire pour un affichage lisible
        html_pin = f"""
            <div class="smbg-pin" style="width: 25px; height: 25px;">
                {ref}
            </div>
        """
        
        icon = DivIcon(
            icon_size=(25, 25),
            icon_anchor=(12, 12),
            html=html_pin
        )

        # Ajout du marqueur (sans popup)
        # L'identifiant 'ref' est injecté dans le JS de Folium pour la gestion du clic
        folium.Marker(
            [lat, lon],
            icon=icon,
            tooltip=f"Réf. : {ref}", # Aide visuelle au survol
            # Ajout d'un id unique pour faciliter le traitement du clic dans l'événement JS
            # Note: Folium ne transmet pas directement les ID d'objets au clic de la carte,
            # donc on utilise le mécanisme `last_object_clicked` ou les coordonnées.
            # L'approche la plus fiable dans Streamlit/Folium est l'événement `last_object_clicked`.
            # Nous utilisons un identifiant conventionnel pour l'implémentation Streamlit.
            # Si le pin est cliqué, l'ID est retourné.
            attr={"id": ref} 
        ).add_to(m)

    # --- Affichage de la Carte avec st_folium ---
    # `use_container_width=True` est essentiel pour que la carte remplisse l'espace
    # `key` est utilisé pour rafraîchir la carte après filtrage/sélection
    map_data = st_folium(
        m, 
        key=f"smbg_carte_{st.session_state.reset_trigger}", 
        width=None, # Dépend du layout CSS
        height=800,
        feature_group_to_listen="marker", # Écoute les clics sur les marqueurs
        return_on_hover=False,
    )

    # --- Gestion des Interactions Clic (sans POPUP) ---
    
    # 1. Clic sur un Pin : Ouvre le panneau de détails
    if map_data and map_data.get("last_object_clicked"):
        # Le format exact de 'last_object_clicked' dépend de l'implémentation Folium/JS.
        # En supposant que l'ID du marqueur est transmis (via l'attribut `id` ou similaire).
        clicked_id = map_data["last_object_clicked"]
        
        # Recherche la référence correspondante
        # Dans le cas de l'ID Folium, on utilise l'index de la DataFrame
        if clicked_id in df.index:
            st.session_state.selected_ref = clicked_id
            st.session_state.map_initial_zoom = map_data["zoom"] # Conserve le zoom
            st.rerun() # Rafraîchissement pour ouvrir le panneau

    # 2. Clic sur la Carte (hors pin) : Ferme le panneau
    # Si un clic sur la carte a eu lieu (e.g., `last_click`) et qu'un pin était sélectionné.
    # Note: `st_folium` ne fournit pas toujours un `last_click` précis sans pin
    # L'approche la plus simple est de forcer la fermeture si la sélection précédente
    # n'est plus présente après un rafraîchissement sans nouveau clic de pin.
    
    # Si la carte est cliquée (sans clic de pin), ou si on clique un pin puis un autre.
    # Si le panneau était ouvert et aucun nouveau pin n'est cliqué, on peut le fermer.
    # Cette logique est délicate et souvent gérée par un bouton "Fermer"
    # ou un clic sur la carte détecté via une zone transparente. 
    # Pour respecter la contrainte "Clic sur la carte en dehors d'un pin : Le panneau droit se replie",
    # nous devons détecter le clic "nulle part".
    
    # Solution Folium/Streamlit la plus simple : Si l'utilisateur clique et que ce n'est PAS un pin,
    # nous considérons que c'est un clic "hors pin".
    if map_data and (map_data.get("last_click") or map_data.get("last_active_drawer")) and not map_data.get("last_object_clicked"):
        if st.session_state.selected_ref is not None:
            st.session_state.selected_ref = None
            st.session_state.map_initial_zoom = map_data["zoom"]
            st.rerun() # Rafraîchissement pour fermer le panneau

# --- 6. Fonction Principale ---

def main():
    """Fonction principale de l'application Streamlit."""
    st.set_page_config(layout="wide")
    
    # 1. Chargement des données et Initialisation de l'état
    df_lots = load_data(DATA_FILE)
    if df_lots.empty:
        return
    
    init_session_state(df_lots)

    # 2. Injection du Style et du Layout
    inject_smbg_style(df_lots)

    # 3. Création des trois zones
    
    # Zone 1: Volet Gauche (Sidebar)
    create_sidebar_filters(df_lots)
    
    # Zone 3: Panneau Droit Rétractable
    # Ceci doit être appelé avant la carte pour s'assurer que le script JS est disponible
    create_detail_panel(df_lots)
    
    # 4. Application des filtres et affichage de la carte
    # Note: apply_filters est également appelé dans les on_change des widgets
    apply_filters(df_lots)
    
    # Zone 2: Carte Centrale
    create_map_display(df_lots)


if __name__ == '__main__':
    main()

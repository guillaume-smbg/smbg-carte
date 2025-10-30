import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from io import BytesIO
import requests
import math
import re
from typing import Dict, Tuple, List


# =========================
# CONFIG GÉNÉRALE / THEME
# =========================

st.set_page_config(
    page_title="SMBG Carte",
    layout="wide",
)

LOGO_BLUE = "#05263d"      # bleu SMBG validé
COPPER = "#b87333"         # cuivre SMBG validé
PANEL_WIDTH_PX = 275       # largeur volets gauche / droit


# =========================
# CSS GLOBAL
# =========================

GLOBAL_CSS = f"""
<style>
/* Reset */
.stApp {{
    background-color: #ffffff;
    font-family: 'Futura', sans-serif;
}}

header[data-testid="stHeader"] {{
    background: transparent;
}}

.main-layout {{
    display: grid;
    grid-template-columns: {PANEL_WIDTH_PX}px 1fr {PANEL_WIDTH_PX}px;
    grid-template-rows: 100vh;
    overflow: hidden;
    width: 100%;
    height: 100vh;
    margin: 0;
    box-sizing: border-box;
    background-color: #ffffff;
    font-family: 'Futura', sans-serif;
}}

/* ----- PANNEAU GAUCHE (FILTRES) ----- */
.left-panel {{
    background-color: {LOGO_BLUE};
    color: #ffffff;
    padding: 16px;
    font-family: 'Futura', sans-serif;
    border-right: 1px solid rgba(255,255,255,0.15);
    overflow-y: auto;
}}

.left-panel * {{
    color: #ffffff !important;
    font-family: 'Futura', sans-serif !important;
}}

.left-panel .section-title {{
    font-weight: 600;
    font-size: 15px;
    margin-bottom: 8px;
    line-height: 1.3;
}}

.left-panel .sub-block {{
    background-color: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 12px;
    font-size: 13px;
    line-height: 1.4;
}}

.copper-btn {{
    width: 100%;
    background-color: {COPPER};
    color: #fff !important;
    border: 0;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    padding: 8px 10px;
    text-align: center;
    cursor: pointer;
    line-height: 1.3;
    font-family: 'Futura', sans-serif;
    margin-bottom: 8px;
}}
.copper-btn:hover {{
    filter: brightness(1.08);
}}

/* sliders labels in left panel */
.left-panel .stSlider label div p {{
    color: #ffffff !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    font-family: 'Futura', sans-serif !important;
}}

/* ----- PANNEAU CARTE ----- */
.map-panel-wrapper {{
    position: relative;
    background-color: #f5f5f5;
    overflow: hidden;
}}
.map-inner {{
    position: absolute;
    inset: 0;
    padding: 0;
    margin: 0;
}}
.map-inner iframe {{
    border: none;
    width: 100%;
    height: 100%;
}}

/* ----- PANNEAU DROIT (FICHE ANNONCE) ----- */
.right-panel {{
    background-color: #ffffff;
    color: #000000;
    padding: 16px;
    font-family: 'Futura', sans-serif;
    border-left: 1px solid rgba(0,0,0,0.1);
    overflow-y: auto;
}}

.right-panel * {{
    font-family: 'Futura', sans-serif !important;
    color: #000000;
}}

.ref-header {{
    background-color: {LOGO_BLUE};
    color: #ffffff;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.4;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 12px;
    font-family: 'Futura', sans-serif;
}}

.badge-nouveau {{
    display: inline-block;
    background-color: {COPPER};
    color: #fff !important;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    line-height: 1.2;
    white-space: nowrap;
    font-family: 'Futura', sans-serif;
}}

.gmaps-link {{
    display: inline-block;
    background-color: {COPPER};
    color: #ffffff !important;
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    line-height: 1.3;
    padding: 6px 10px;
    border-radius: 6px;
    margin-bottom: 12px;
    font-family: 'Futura', sans-serif;
}}

.addr-block {{
    font-size: 13px;
    line-height: 1.4;
    font-family: 'Futura', sans-serif;
    margin-bottom: 12px;
}}
.addr-block .addr-line1 {{
    font-weight: 600;
    color: #000000;
    font-family: 'Futura', sans-serif;
}}
.addr-block .addr-line2 {{
    color: #000000;
    font-family: 'Futura', sans-serif;
}}

/* Tableau fiche annonce (Champ / Valeur) */
.detail-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    line-height: 1.4;
    font-family: 'Futura', sans-serif;
}}
.detail-table tr td {{
    vertical-align: top;
    padding: 6px 8px;
    border-bottom: 1px solid #e0e0e0;
    color: #000000;
    font-family: 'Futura', sans-serif;
}}
.detail-table tr td.label-col {{
    width: 40%;
    font-weight: 600;
    font-size: 12px;
    color: {LOGO_BLUE};
    font-family: 'Futura', sans-serif;
}}
.detail-table tr td.value-col {{
    width: 60%;
    font-weight: 400;
    font-size: 12px;
    color: #000000;
    font-family: 'Futura', sans-serif;
}}

/* état "aucune sélection" */
.placeholder-panel {{
    font-size: 13px;
    line-height: 1.4;
    color: #000;
    opacity: 0.7;
    font-family: 'Futura', sans-serif;
    background-color: #f8f8f8;
    border: 1px dashed #ccc;
    border-radius: 8px;
    padding: 12px;
}}
</style>
"""

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# =========================
# SESSION STATE
# =========================

if "selected_ref" not in st.session_state:
    st.session_state["selected_ref"] = None

if "df" not in st.session_state:
    st.session_state["df"] = None


# =========================
# DATA LOADING
# =========================

def load_excel_from_url(url: str) -> pd.DataFrame:
    """
    Charge le fichier Excel depuis une URL (GitHub raw / R2 public / Supabase public bucket).
    """
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.content
    df_local = pd.read_excel(BytesIO(data))
    return df_local


EXCEL_URL = st.secrets.get("EXCEL_URL", "")

load_error = None
if EXCEL_URL and st.session_state["df"] is None:
    try:
        st.session_state["df"] = load_excel_from_url(EXCEL_URL)
    except Exception as e:
        load_error = f"Erreur chargement Excel : {e}"

df_raw = st.session_state["df"]

if df_raw is None or (isinstance(df_raw, pd.DataFrame) and df_raw.empty):
    # fallback minimal pour éviter l'écran blanc et permettre l'affichage UI
    df_raw = pd.DataFrame({
        "Référence annonce": ["-"],
        "Latitude": [46.5],
        "Longitude": [2.5],
        "Adresse": [""],
        "Adresse complète": [""],
        "Ville": [""],
        "Lien Google Maps": [""],
        "Surface totale (m²)": [""],
        "Loyer mensuel (€)": [""],
        "Charges mensuelles (€)": [""],
        "Taxe foncière annuelle (€)": [""],
        "Commentaires": ["Aucune donnée disponible"],
        "Actif": ["non"],
        "Date publication": [""],
    })


# =========================
# NORMALISATION DF
# =========================

REQUIRED_COLS = [
    "Référence annonce",
    "Latitude",
    "Longitude",
    "Adresse",
    "Adresse complète",
    "Ville",
    "Lien Google Maps",
    "Surface totale (m²)",
    "Loyer mensuel (€)",
    "Charges mensuelles (€)",
    "Taxe foncière annuelle (€)",
    "Commentaires",
    "Actif",
    "Date publication",
]

for c in REQUIRED_COLS:
    if c not in df_raw.columns:
        df_raw[c] = ""

# On ne garde affichables que les annonces Actif = "oui"
df_active = df_raw[df_raw["Actif"].astype(str).str.lower().eq("oui")].copy()

def _is_num(x):
    try:
        return not math.isnan(float(x))
    except:
        return False

df_active = df_active[
    df_active["Latitude"].apply(_is_num)
    & df_active["Longitude"].apply(_is_num)
].copy()

# S'il n'y a rien d'actif, on met une fausse ref pour que la carte s'affiche.
if df_active.empty:
    df_active = pd.DataFrame([{
        "Référence annonce": "Aucune",
        "Latitude": 46.5,
        "Longitude": 2.5,
        "Adresse": "",
        "Adresse complète": "",
        "Ville": "",
        "Lien Google Maps": "",
        "Surface totale (m²)": "",
        "Loyer mensuel (€)": "",
        "Charges mensuelles (€)": "",
        "Taxe foncière annuelle (€)": "",
        "Commentaires": "Aucune donnée disponible",
        "Actif": "non",
        "Date publication": "",
    }])


# Nettoyage de la référence pour affichage (enlever le ".0")
def normalize_ref_str(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if re.match(r"^\d+\.0+$", s):
        return s.split(".")[0]
    return s

df_active["ref_clean"] = df_active["Référence annonce"].apply(normalize_ref_str)


# =========================
# OUTILS : TABLEAU FICHE ANNONCE
# =========================

def sanitize_value(v: object) -> str:
    """
    Nettoie une valeur cellule :
    - enlève ' - ' ou '/' ou vide inutile
    - retourne string propre sinon
    """
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s in ["-", "/", ""]:
        return ""
    return s

def build_single_listing_table(row: pd.Series) -> str:
    """
    Construit le HTML <table> pour le panneau droit.
    row = UNE SEULE LIGNE (l'annonce unique).
    On affiche seulement les champs non vides.
    Deux colonnes :
    - label (nom de colonne Excel)
    - valeur
    """
    # On va parcourir toutes les colonnes de la ligne d'annonce.
    # On saute les colonnes techniques internes type Latitude/Longitude si tu veux pas les voir.
    # On garde tout le reste, mais seulement si non vide.
    EXCLUDE_COLS = set([
        "Latitude",
        "Longitude",
        "Actif",
        # on garde Référence annonce ailleurs en bannière
        "Référence annonce",
        # gmaps est traité à part en bouton
        "Lien Google Maps",
        # adresse / ville sont déjà affichées séparément
        "Adresse",
        "Adresse complète",
        "Ville",
        "Date publication",  # on l'utilise pour badge Nouveau
    ])

    rows_html = []

    for colname, value in row.items():
        if colname in EXCLUDE_COLS:
            continue
        cleaned = sanitize_value(value)
        if cleaned == "":
            continue

        # On ajoute une ligne au tableau
        cell_label = colname
        cell_value = cleaned
        rows_html.append(
            f"<tr>"
            f"<td class='label-col'>{cell_label}</td>"
            f"<td class='value-col'>{cell_value}</td>"
            f"</tr>"
        )

    if not rows_html:
        # rien d'affichable => on renvoie bloc vide
        return "<div class='placeholder-panel'>Aucune information disponible pour cette annonce.</div>"

    table_html = (
        "<table class='detail-table'>"
        + "".join(rows_html) +
        "</table>"
    )
    return table_html


def is_recent(date_val, days=30) -> bool:
    """
    Badge 'Nouveau' si la Date publication a moins de X jours.
    """
    if pd.isna(date_val) or str(date_val).strip() == "":
        return False
    try:
        dt = pd.to_datetime(date_val, dayfirst=True, errors="coerce")
    except:
        dt = pd.NaT
    if pd.isna(dt):
        return False
    now = pd.Timestamp.now(tz="Europe/Paris").normalize()
    delta = now - dt.normalize()
    return delta.days <= days


def render_right_panel(ref_value: str, df_full: pd.DataFrame, load_error_msg: str | None):
    """
    Rend tout le contenu du panneau droit :
    - header référence + badge nouveau
    - bouton Google Maps cuivre
    - bloc adresse/ville
    - tableau Champ / Valeur (fiche unique annonce)
    - message d'erreur si Excel pas chargé
    """

    # Message en haut en cas d'erreur de chargement
    if load_error_msg:
        st.markdown(
            f"<div style='color:#b00020;font-size:12px;font-weight:600;"
            f"font-family:Futura, sans-serif;margin-bottom:12px;'>"
            f"{load_error_msg}<br/>"
            f"Vérifie EXCEL_URL."
            f"</div>",
            unsafe_allow_html=True,
        )

    # Si pas encore de clic
    if not ref_value:
        st.markdown(
            "<div class='placeholder-panel'>"
            "Aucune sélection. Sélectionnez une annonce sur la carte."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # On récupère la première ligne correspondant à cette référence
    # IMPORTANT : on ne fusionne pas plusieurs lots -> 1 annonce = 1 ligne
    mask = df_full["Référence annonce"].astype(str) == str(ref_value)
    sub = df_full[mask].copy()

    if sub.empty:
        st.markdown(
            "<div class='placeholder-panel'>"
            "Annonce introuvable. Cliquez à nouveau sur la carte."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    first_row = sub.iloc[0]

    ref_display = normalize_ref_str(first_row.get("Référence annonce", ""))
    gmaps_url = sanitize_value(first_row.get("Lien Google Maps", ""))
    adresse_full = sanitize_value(first_row.get("Adresse complète", "")) or sanitize_value(first_row.get("Adresse", ""))
    ville = sanitize_value(first_row.get("Ville", ""))
    date_pub = first_row.get("Date publication", "")

    badge_html = ""
    if is_recent(date_pub):
        badge_html = "<span class='badge-nouveau'>Nouveau</span>"

    # Header référence + badge
    st.markdown(
        f"<div class='ref-header'>"
        f"<div>Réf. {ref_display}</div>"
        f"<div>{badge_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Bouton Google Maps
    if gmaps_url:
        st.markdown(
            f"<a class='gmaps-link' href='{gmaps_url}' target='_blank' rel='noopener noreferrer'>Cliquer ici</a>",
            unsafe_allow_html=True,
        )

    # Bloc adresse
    addr_html = "<div class='addr-block'>"
    if adresse_full:
        addr_html += f"<div class='addr-line1'>{adresse_full}</div>"
    if ville:
        addr_html += f"<div class='addr-line2'>{ville}</div>"
    addr_html += "</div>"

    st.markdown(addr_html, unsafe_allow_html=True)

    # Tableau Champ / Valeur
    table_html = build_single_listing_table(first_row)
    st.markdown(table_html, unsafe_allow_html=True)


# =========================
# OUTILS : CARTE FOLIUM
# =========================

def anti_overlap_positions(df_points: pd.DataFrame, lat_col: str, lon_col: str) -> pd.DataFrame:
    """
    Quand plusieurs références ont EXACTEMENT la même coordonnée,
    on décale légèrement les points autour pour qu'ils soient cliquables individuellement.
    """
    if df_points.empty:
        return df_points.assign(_lat_plot=[], _lon_plot=[])

    grouped = {}
    for idx, r in df_points.iterrows():
        key = (round(float(r[lat_col]), 6), round(float(r[lon_col]), 6))
        grouped.setdefault(key, []).append(idx)

    lat_list = []
    lon_list = []

    for key, idxs in grouped.items():
        base_lat, base_lon = key
        count = len(idxs)

        if count == 1:
            i = idxs[0]
            lat_list.append((i, base_lat))
            lon_list.append((i, base_lon))
            continue

        # on fait un petit cercle
        radius = 0.0005
        for n, i in enumerate(idxs):
            angle = 2 * math.pi * (n / count)
            lat_list.append((i, base_lat + radius * math.sin(angle)))
            lon_list.append((i, base_lon + radius * math.cos(angle)))

    lat_map = {i: lat for (i, lat) in lat_list}
    lon_map = {i: lon for (i, lon) in lon_list}

    df_points = df_points.copy()
    df_points["_lat_plot"] = df_points.index.map(lat_map)
    df_points["_lon_plot"] = df_points.index.map(lon_map)

    return df_points


def build_map_layer(df_for_map: pd.DataFrame):
    """
    Construit la carte Folium centrée France, ajoute les markers
    et renvoie :
    - objet folium.Map
    - dictionnaire { (lat,lng) arrondis : ref_clean }
    """

    m = folium.Map(location=[46.5, 2.5], zoom_start=6, tiles="OpenStreetMap")

    # style du label rond cuivre/bleu remplacé par bleu SMBG
    css_marker = (
        f"background:{LOGO_BLUE};"
        "color:#fff;"
        "border:2px solid #fff;"
        "width:28px;height:28px;line-height:28px;"
        "border-radius:50%;text-align:center;"
        "font-size:11px;font-weight:600;"
        "font-family:'Futura',sans-serif;"
        "box-shadow:0 2px 4px rgba(0,0,0,.4);"
    )

    layer = folium.FeatureGroup(name="Annonces").add_to(m)

    click_registry: Dict[Tuple[float, float], str] = {}

    for _, r in df_for_map.iterrows():
        lat = float(r["_lat_plot"])
        lon = float(r["_lon_plot"])

        label_txt = str(r.get("ref_clean", "")).strip()
        if re.match(r"^\d+\.0+$", label_txt):
            label_txt = label_txt.split(".")[0]

        # On se sert du DivIcon : propre, pas de popup visible
        icon = folium.DivIcon(
            html=f'<div style="{css_marker}">{label_txt}</div>',
            icon_size=(28, 28),
            icon_anchor=(14, 14),
            class_name="smbg-divicon"
        )

        folium.Marker(
            location=[lat, lon],
            icon=icon,
        ).add_to(layer)

        # registry pour récupérer la ref en fonction du clic coordonné
        click_registry[(round(lat, 6), round(lon, 6))] = label_txt

    return m, click_registry


# =========================
# FILTRES / SIDEPANEL GAUCHE
# =========================

def to_num_clean(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(" ", "").str.replace(",", "."),
        errors="coerce"
    )


def build_filters_ui(df_scope: pd.DataFrame):
    """
    Affiche les filtres dans le panneau gauche et renvoie les valeurs choisies.
    Ici : surface min/max, loyer min/max.
    (Tu as parlé aussi Région / Dépt / etc. dans la version étendue, mais je reste minimal ici
    puisque je n'ai pas les noms exacts de colonnes régionales dans le code uploadé.)
    """

    st.markdown("<div class='section-title'>Filtres</div>", unsafe_allow_html=True)

    # SURFACE
    if "Surface totale (m²)" in df_scope.columns:
        surf_series = to_num_clean(df_scope["Surface totale (m²)"])
        if not surf_series.dropna().empty:
            s_min = int(surf_series.min())
            s_max = int(surf_series.max())
        else:
            s_min, s_max = 0, 1000
    else:
        s_min, s_max = 0, 1000
        surf_series = pd.Series([], dtype=float)

    surf_range = st.slider(
        "Surface (m²)",
        min_value=s_min,
        max_value=s_max,
        value=(s_min, s_max),
        step=1,
    )

    # LOYER
    if "Loyer mensuel (€)" in df_scope.columns:
        loy_series = to_num_clean(df_scope["Loyer mensuel (€)"])
        if not loy_series.dropna().empty:
            l_min = int(loy_series.min())
            l_max = int(loy_series.max())
        else:
            l_min, l_max = 0, 50000
    else:
        l_min, l_max = 0, 50000
        loy_series = pd.Series([], dtype=float)

    loyer_range = st.slider(
        "Loyer mensuel (€)",
        min_value=l_min,
        max_value=l_max,
        value=(l_min, l_max),
        step=100,
    )

    reset_clicked = st.button(
        "Réinitialiser les filtres",
        key="reset_filters_btn",
        help="Remettre tous les filtres aux valeurs par défaut",
    )

    st.markdown(
        "<button class='copper-btn'>Partager toutes les annonces</button>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<button class='copper-btn'>Partager mes favoris</button>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<button class='copper-btn'>Je suis intéressé</button>",
        unsafe_allow_html=True,
    )

    return {
        "surf_range": surf_range,
        "loyer_range": loyer_range,
        "reset": reset_clicked,
    }


def apply_filters(df_scope: pd.DataFrame, surf_range, loyer_range):
    """
    Filtre df_scope selon les sliders.
    On autorise les NaN (surface ou loyer manquant = reste visible).
    """
    out_df = df_scope.copy()

    if "Surface totale (m²)" in out_df.columns:
        vals_surface = to_num_clean(out_df["Surface totale (m²)"])
        mask_surface = (
            (vals_surface >= surf_range[0]) &
            (vals_surface <= surf_range[1])
        ) | (vals_surface.isna())
        out_df = out_df[mask_surface]

    if "Loyer mensuel (€)" in out_df.columns:
        vals_loyer = to_num_clean(out_df["Loyer mensuel (€)"])
        mask_loyer = (
            (vals_loyer >= loyer_range[0]) &
            (vals_loyer <= loyer_range[1])
        ) | (vals_loyer.isna())
        out_df = out_df[mask_loyer]

    return out_df


# =========================
# MAIN LAYOUT
# =========================

# Layout global en 3 colonnes fixes
st.markdown("<div class='main-layout'>", unsafe_allow_html=True)

# PANNEAU GAUCHE
with st.container():
    st.markdown("<div class='left-panel'>", unsafe_allow_html=True)

    filters_state = build_filters_ui(df_active)

    # Reset complet : on relance l'app
    if filters_state["reset"]:
        st.experimental_rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# PANNEAU CARTE
with st.container():
    st.markdown("<div class='map-panel-wrapper'><div class='map-inner'>", unsafe_allow_html=True)

    # 1. appliquer filtres sur df_active
    df_filtered = apply_filters(
        df_active,
        filters_state["surf_range"],
        filters_state["loyer_range"],
    )

    # 2. regrouper pour avoir 1 pin = 1 annonce
    # on prend la première ligne par Référence annonce
    if "Référence annonce" in df_filtered.columns:
        grouped_refs = (
            df_filtered.sort_values("Référence annonce")
            .groupby("Référence annonce", as_index=False)
            .first()
        )
    else:
        grouped_refs = df_filtered.copy()

    # 3. calcul anti overlap
    #    on bosse sur lat/lon/ref_clean
    work_refs = grouped_refs.copy()
    work_refs = work_refs[[
        "Référence annonce",
        "ref_clean",
        "Latitude",
        "Longitude",
    ]].dropna(subset=["Latitude", "Longitude"])

    work_refs = anti_overlap_positions(work_refs, "Latitude", "Longitude")

    # 4. construire la carte Folium et le registre de clic
    folium_map, click_registry = build_map_layer(work_refs)

    # 5. afficher folium dans streamlit et récupérer le clic
    folium_out = st_folium(
        folium_map,
        width=None,
        height=800,
        returned_objects=["last_object_clicked"],  # IMPORTANT
    )

    clicked_ref = None
    if isinstance(folium_out, dict):
        loc = folium_out.get("last_object_clicked")
        if isinstance(loc, dict) and "lat" in loc and "lng" in loc:
            lat_clicked = round(float(loc["lat"]), 6)
            lon_clicked = round(float(loc["lng"]), 6)
            key = (lat_clicked, lon_clicked)
            if key in click_registry:
                clicked_ref = click_registry[key]

    # si on a cliqué un vrai marker, on remplace selected_ref
    if clicked_ref:
        st.session_state["selected_ref"] = clicked_ref

    st.markdown("</div></div>", unsafe_allow_html=True)

# PANNEAU DROIT
with st.container():
    st.markdown("<div class='right-panel'>", unsafe_allow_html=True)

    render_right_panel(
        st.session_state["selected_ref"],
        df_raw,
        load_error,
    )

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

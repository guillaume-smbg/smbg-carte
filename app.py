import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from io import BytesIO
import requests
import math

st.set_page_config(
    page_title="SMBG Carte",
    layout="wide",
)

BLEU_SMBG = "#05263d"
CUIVRE_SMBG = "#b87333"
PANEL_WIDTH_PX = 275

CUSTOM_CSS = f"""
<style>
.stApp {{
    background-color: #ffffff;
    font-family: 'Futura', sans-serif;
}}
header[data-testid=\"stHeader\"] {{
    background: transparent;
}}
.main-container {{
    display: flex;
    flex-direction: row;
    width: 100%;
    height: calc(100vh - 2rem);
    overflow: hidden;
    position: relative;
    box-sizing: border-box;
    padding: 0;
    margin: 0;
}}
.left-panel {{
    width: {PANEL_WIDTH_PX}px;
    min-width: {PANEL_WIDTH_PX}px;
    max-width: {PANEL_WIDTH_PX}px;
    background-color: {BLEU_SMBG};
    color: #ffffff;
    padding: 16px;
    box-sizing: border-box;
    overflow-y: auto;
    border-right: 1px solid rgba(255,255,255,0.1);
}}
.left-panel h2,
.left-panel h3,
.left-panel h4,
.left-panel label,
.left-panel p,
.left-panel span,
.left-panel div {{
    color: #ffffff !important;
    font-family: 'Futura', sans-serif !important;
}}
.cuivre-btn {{
    background-color: {CUIVRE_SMBG};
    color: #fff;
    border: none;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    font-family: 'Futura', sans-serif;
    width: 100%;
    text-align: center;
    margin-bottom: 8px;
}}
.cuivre-btn:hover {{
    filter: brightness(1.08);
}}
.map-panel {{
    flex: 1 1 auto;
    position: relative;
    height: 100%;
    overflow: hidden;
    background-color: #f5f5f5;
}}
.map-container-inner {{
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
}}
.map-container-inner iframe {{
    width: 100%;
    height: 100%;
    border: none;
}}
.right-panel {{
    width: {PANEL_WIDTH_PX}px;
    min-width: {PANEL_WIDTH_PX}px;
    max-width: {PANEL_WIDTH_PX}px;
    background-color: #ffffff;
    color: #000000;
    padding: 16px;
    box-sizing: border-box;
    overflow-y: auto;
    border-left: 1px solid rgba(0,0,0,0.1);
    font-family: 'Futura', sans-serif;
}}
.ref-banner {{
    font-weight: 600;
    font-size: 16px;
    color: {BLEU_SMBG};
    border-left: 4px solid {CUIVRE_SMBG};
    padding-left: 8px;
    margin-bottom: 12px;
    line-height: 1.3;
}}
.lot-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin-bottom: 16px;
}}
.lot-table th {{
    text-align: left;
    background: {BLEU_SMBG};
    color: #fff;
    padding: 6px 8px;
    font-weight: 500;
    font-size: 12px;
}}
.lot-table td {{
    border-bottom: 1px solid #ddd;
    padding: 6px 8px;
    vertical-align: top;
    font-size: 12px;
}}
.badge-nouveau {{
    display: inline-block;
    background-color: {CUIVRE_SMBG};
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 8px;
}}
.gmaps-btn {{
    background-color: {BLEU_SMBG};
    color: #ffffff;
    text-decoration: none;
    font-size: 13px;
    padding: 6px 10px;
    border-radius: 4px;
    display: inline-block;
    margin-bottom: 12px;
    font-weight: 500;
}}
.left-panel::-webkit-scrollbar,
.right-panel::-webkit-scrollbar {{
    width: 4px;
}}
.left-panel::-webkit-scrollbar-thumb,
.right-panel::-webkit-scrollbar-thumb {{
    background-color: rgba(255,255,255,0.4);
    border-radius: 999px;
}}
.left-panel::-webkit-scrollbar-track,
.right-panel::-webkit-scrollbar-track {{
    background-color: rgba(0,0,0,0.1);
}}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if "selected_ref" not in st.session_state:
    st.session_state["selected_ref"] = None
if "df" not in st.session_state:
    st.session_state["df"] = None

def load_excel_from_url(url: str) -> pd.DataFrame:
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

df = st.session_state["df"]

EXPECTED_COLS = [
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

if df is None or (isinstance(df, pd.DataFrame) and df.empty):
    df = pd.DataFrame(columns=EXPECTED_COLS)

for col in EXPECTED_COLS:
    if col not in df.columns:
        df[col] = ""

def is_number(x):
    try:
        return not math.isnan(float(x))
    except:
        return False

df_active = df[df["Actif"].astype(str).str.lower().eq("oui")].copy()

df_active = df_active[
    df_active["Latitude"].apply(is_number)
    & df_active["Longitude"].apply(is_number)
].copy()

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

def clean_ref(val):
    if pd.isna(val):
        return ""
    txt = str(val)
    if txt.endswith(".0"):
        txt = txt[:-2]
    return txt.strip()

df_active["ref_clean"] = df_active["Référence annonce"].apply(clean_ref)

def build_folium_map(df_map: pd.DataFrame):
    m = folium.Map(location=[46.5, 2.5], zoom_start=6, tiles="OpenStreetMap")
    for _, row in df_map.iterrows():
        try:
            lat = float(row["Latitude"])
            lon = float(row["Longitude"])
        except:
            continue

        ref_display = row.get("ref_clean", "")
        raw_ref = row.get("Référence annonce", "")

        html_label = f"""
        <div style="
            background-color:{BLEU_SMBG};
            color:#fff;
            border-radius:6px;
            padding:4px 6px;
            font-size:12px;
            font-weight:600;
            font-family:'Futura',sans-serif;
            border:1px solid #fff;
            box-shadow:0 2px 4px rgba(0,0,0,0.3);
            ">
            {ref_display}
        </div>
        """

        icon = folium.DivIcon(
            html=html_label,
            class_name="smbg-divicon",
            icon_size=(50, 18),
            icon_anchor=(25, 18),
        )

        folium.Marker(
            location=[lat, lon],
            icon=icon,
            popup=str(raw_ref),
        ).add_to(m)

    return m

def get_lots_for_ref(ref_value: str, df_source: pd.DataFrame) -> pd.DataFrame:
    if ref_value is None:
        return pd.DataFrame()
    mask = df_source["Référence annonce"].astype(str) == str(ref_value)
    return df_source[mask].copy()

def format_currency(val):
    if pd.isna(val) or val == "":
        return "-"
    try:
        n = float(str(val).replace(" ", "").replace(",", "."))
    except:
        return str(val)
    n_rounded = round(n)
    return f"{n_rounded:,}".replace(",", " ")

def is_recent(date_val, days=30):
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

def render_right_panel(selected_ref: str, df_full: pd.DataFrame, load_error_msg: str | None):
    if load_error_msg:
        st.markdown(
            f"<div style='color:#b00020; font-size:13px; font-weight:600; margin-bottom:12px;'>{load_error_msg}<br/>Vérifie le secret EXCEL_URL ou le lien du fichier Excel.</div>",
            unsafe_allow_html=True,
        )

    lots_df = get_lots_for_ref(selected_ref, df_full)

    if lots_df.empty:
        st.markdown(
            "<div class='ref-banner'>Sélectionne un point sur la carte</div>",
            unsafe_allow_html=True,
        )
        return

    head = lots_df.iloc[0].to_dict()

    ref_clean_header = clean_ref(head.get("Référence annonce", ""))
    gmaps_url = head.get("Lien Google Maps", "")

    adresse_full = head.get("Adresse complète", "") or head.get("Adresse", "")
    ville = head.get("Ville", "")
    date_pub = head.get("Date publication", "")

    badge_html = ""
    if is_recent(date_pub):
        badge_html = "<span class='badge-nouveau'>Nouveau</span>"

    st.markdown(
        f"""
        <div class=\"ref-banner\">Réf. {ref_clean_header} {badge_html}</div>
        """,
        unsafe_allow_html=True,
    )

    if gmaps_url and str(gmaps_url).strip() not in ["-", "/", ""]:
        st.markdown(
            f"<a class='gmaps-btn' href='{gmaps_url}' target='_blank' rel='noopener noreferrer'>Voir sur Google Maps</a>",
            unsafe_allow_html=True,
        )

    if adresse_full or ville:
        st.markdown(
            f"<div style='font-size:13px; line-height:1.4; margin-bottom:12px;'><strong>{adresse_full}</strong><br/>{ville}</div>",
            unsafe_allow_html=True,
        )

    cols_for_table = [
        "Surface totale (m²)",
        "Loyer mensuel (€)",
        "Charges mensuelles (€)",
        "Taxe foncière annuelle (€)",
        "Commentaires",
    ]
    safe_cols = [c for c in cols_for_table if c in lots_df.columns]

    table_html = "<table class='lot-table'><thead><tr>"
    for col in safe_cols:
        table_html += f"<th>{col}</th>"
    table_html += "</tr></thead><tbody>"

    for _, r in lots_df.iterrows():
        table_html += "<tr>"
        for col in safe_cols:
            val = r[col] if col in r else ""
            if "€" in col:
                val = format_currency(val) + " €" if val not in ["", "-", "/"] else "-"
            elif "m²" in col:
                if pd.isna(val) or str(val).strip() in ["", "-", "/"]:
                    val = "-"
                else:
                    try:
                        n = float(str(val).replace(" ", "").replace(",", "."))
                        n_rounded = round(n)
                        val = f"{n_rounded} m²"
                    except:
                        val = str(val)
            else:
                if pd.isna(val) or str(val).strip() in ["", "-", "/"]:
                    val = "-"
                else:
                    val = str(val)
            table_html += f"<td>{val}</td>"
        table_html += "</tr>"
    table_html += "</tbody></table>"

    st.markdown(table_html, unsafe_allow_html=True)

st.markdown("<div class='main-container'>", unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='left-panel'>", unsafe_allow_html=True)
    st.markdown("### Filtres", unsafe_allow_html=True)

    def coerce_num(series):
        out = pd.to_numeric(series.astype(str).str.replace(" ", "").str.replace(",", "."), errors="coerce")
        return out

    surface_series = coerce_num(df_active["Surface totale (m²)"]) if "Surface totale (m²)" in df_active.columns else pd.Series(dtype=float)
    loyer_series = coerce_num(df_active["Loyer mensuel (€)"]) if "Loyer mensuel (€)" in df_active.columns else pd.Series(dtype=float)

    if not surface_series.dropna().empty:
        s_min = int(surface_series.min())
        s_max = int(surface_series.max())
    else:
        s_min, s_max = 0, 1000

    if not loyer_series.dropna().empty:
        l_min = int(loyer_series.min())
        l_max = int(loyer_series.max())
    else:
        l_min, l_max = 0, 50000

    surf_range = st.slider(
        "Surface (m²)",
        min_value=s_min,
        max_value=s_max,
        value=(s_min, s_max),
        step=1,
    )

    loyer_range = st.slider(
        "Loyer mensuel (€)",
        min_value=l_min,
        max_value=l_max,
        value=(l_min, l_max),
        step=100,
    )

    if st.button("Réinitialiser les filtres", key="reset_filters", help="Remettre tous les filtres aux valeurs par défaut", use_container_width=True):
        st.experimental_rerun()

    st.markdown("<button class='cuivre-btn'>Partager toutes les annonces</button>", unsafe_allow_html=True)
    st.markdown("<button class='cuivre-btn'>Partager mes favoris</button>", unsafe_allow_html=True)
    st.markdown("<button class='cuivre-btn'>Je suis intéressé</button>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='map-panel'><div class='map-container-inner'>", unsafe_allow_html=True)

    df_filtered = df_active.copy()

    if "Surface totale (m²)" in df_filtered.columns:
        vals_surface = coerce_num(df_filtered["Surface totale (m²)"])
        df_filtered = df_filtered[(vals_surface >= surf_range[0]) & (vals_surface <= surf_range[1]) | vals_surface.isna()]

    if "Loyer mensuel (€)" in df_filtered.columns:
        vals_loyer = coerce_num(df_filtered["Loyer mensuel (€)"])
        df_filtered = df_filtered[(vals_loyer >= loyer_range[0]) & (vals_loyer <= loyer_range[1]) | vals_loyer.isna()]

    df_markers = df_filtered.sort_values("Référence annonce").groupby("Référence annonce", as_index=False).first()

    folium_map = build_folium_map(df_markers)

    map_data = st_folium(
        folium_map,
        width=None,
        height=600,
        returned_objects=["last_object_clicked_popup"],
    )

    clicked_ref = None
    if map_data and "last_object_clicked_popup" in map_data and map_data["last_object_clicked_popup"]:
        clicked_ref = map_data["last_object_clicked_popup"]

    if clicked_ref:
        st.session_state["selected_ref"] = clicked_ref

    st.markdown("</div></div>", unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='right-panel'>", unsafe_allow_html=True)
    render_right_panel(st.session_state["selected_ref"], df_active, load_error)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
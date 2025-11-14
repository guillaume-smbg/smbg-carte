
import math
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


# ----------------------
# Page config
# ----------------------
st.set_page_config(
    page_title="SMBG Carte - Immobilier commercial",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ----------------------
# Global CSS (fonts, layout, colors)
# ----------------------

ASSETS_DIR = Path("assets")
DATA_PATH = Path("data") / "Liste des lots.xlsx"

BLUE_SMBG = "#05263d"
COPPER_SMBG = "#C67B42"


def load_font_css() -> str:
    """Generate @font-face CSS rules for all TTF fonts in assets/ and apply globally."""
    font_files = list(ASSETS_DIR.glob("*.ttf"))
    css_parts = []

    for font_path in font_files:
        css_parts.append(
            f"""
@font-face {{
    font-family: 'FuturaSMBG';
    src: url('{font_path.as_posix()}') format('truetype');
    font-weight: normal;
    font-style: normal;
}}
"""
        )

    css_parts.append(
        f"""
html, body {{
    margin: 0;
    padding: 0;
    height: 100%;
    overflow: hidden;
}}

[data-testid="stAppViewContainer"] {{
    margin: 0;
    padding: 0 !important;
    height: 100vh;
}}

[data-testid="stAppViewContainer"] > .main {{
    margin: 0;
    padding: 0 !important;
    height: 100vh;
}}

main.block-container, .block-container {{
    padding: 0 !important;
    margin: 0 !important;
}}

[data-testid="stVerticalBlock"] {{
    padding: 0 !important;
    margin: 0 !important;
}}

/* Remove Streamlit default header, footer, and padding */
[data-testid="stHeader"], [data-testid="stToolbar"] {{
    display: none;
}}

/* Sidebar width and style */
[data-testid="stSidebar"] {{
    background-color: {BLUE_SMBG};
    min-width: 275px;
    max-width: 275px;
}}

/* Remove sidebar collapse button */
button[kind="header"] {{
    display: none !important;
}}

/* Global font */
* {{
    font-family: 'FuturaSMBG', Futura, "Futura PT", "Century Gothic", Arial, sans-serif !important;
}}

/* Hide image fullscreen button */
button[title="View fullscreen"] {{
    display: none !important;
}}

/* Map container full height */
#map-container {{
    position: relative;
    width: 100%;
    height: 100vh;
    margin: 0;
    padding: 0;
    overflow: hidden;
}}

/* Force folium iframe to fill viewport height */
iframe[title="st_folium.smbg_map"] {{
    height: 100vh !important;
}}

/* Right drawer */
#detail-drawer {{
    position: fixed;
    top: 0;
    right: 0;
    width: 275px;
    height: 100vh;
    background-color: {BLUE_SMBG};
    color: white;
    box-shadow: -2px 0 8px rgba(0, 0, 0, 0.3);
    padding: 1.5rem 1rem 1.5rem 1.25rem;
    z-index: 9999;
    overflow-y: auto;
}}

#detail-drawer h2 {{
    margin-top: 0;
    margin-bottom: 0.5rem;
    font-size: 1.2rem;
    color: white;
}}

#detail-drawer .ref-label {{
    font-size: 0.9rem;
    color: {COPPER_SMBG};
    margin-bottom: 0.25rem;
}}

#detail-drawer .ref-value {{
    font-size: 1.4rem;
    font-weight: bold;
    margin-bottom: 0.75rem;
}}

#detail-drawer table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
}}

#detail-drawer td {{
    padding: 0.15rem 0.2rem;
    vertical-align: top;
}}

#detail-drawer td.label {{
    color: {COPPER_SMBG};
    font-weight: 600;
    width: 45%;
}}

#detail-drawer td.value {{
    color: #ffffff;
    width: 55%;
}}

#detail-drawer .gmaps-button {{
    display: inline-block;
    margin-bottom: 0.8rem;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    border: 1px solid {COPPER_SMBG};
    background-color: transparent;
    color: {COPPER_SMBG};
    font-size: 0.8rem;
    text-decoration: none;
    cursor: pointer;
}}

#detail-drawer .gmaps-button:hover {{
    background-color: {COPPER_SMBG};
    color: {BLUE_SMBG};
}}

/* Scroll only inside drawer if necessary */
#detail-drawer::-webkit-scrollbar {{
    width: 6px;
}}

#detail-drawer::-webkit-scrollbar-thumb {{
    background-color: rgba(255, 255, 255, 0.3);
    border-radius: 999px;
}}
"""
    )

    return "\n".join(css_parts)


st.markdown(f"""<style>{load_font_css()}</style>""", unsafe_allow_html=True)


# ----------------------
# Utils
# ----------------------

@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    # Actif = oui only
    if "Actif" in df.columns:
        df = df[df["Actif"].astype(str).str.lower() == "oui"]
    # Clean numeric columns
    for col in df.columns:
        if df[col].dtype == object:
            try:
                df[col] = pd.to_numeric(df[col].str.replace(" ", "").str.replace(",", "."), errors="ignore")
            except Exception:
                pass
    return df.reset_index(drop=True)


def format_reference(value) -> str:
    if pd.isna(value):
        return ""
    s = str(value).strip()
    if s == "":
        return ""
    # Remove any spaces
    s = s.replace(" ", "")
    # If Excel stored as float with trailing .0
    if s.replace(".", "", 1).isdigit():
        if "." in s:
            int_part, dec_part = s.split(".", 1)
            try:
                int_val = int(int_part)
            except ValueError:
                int_val = 0
            # Trim leading zeros from integer part
            int_str = str(int_val)
            # If decimal part is all zeros -> drop
            if set(dec_part) == {"0"}:
                return int_str
            # Keep decimal part, trimming trailing zeros
            dec_part = dec_part.rstrip("0")
            if dec_part == "":
                return int_str
            return f"{int_str}.{dec_part}"
        else:
            try:
                int_val = int(s)
            except ValueError:
                return s
            return str(int_val)
    # Fallback: custom format like "0005.1"
    if "." in s:
        int_part, dec_part = s.split(".", 1)
        try:
            int_val = int(int_part)
        except ValueError:
            int_val = 0
        int_str = str(int_val)
        return f"{int_str}.{dec_part}" if dec_part else int_str
    try:
        return str(int(s))
    except Exception:
        return s


def is_empty_value(v) -> bool:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return True
    s = str(v).strip().lower()
    return s in {"", "néant", "-", "/", "0"} or s == "0.0"


def format_currency(v) -> str:
    if pd.isna(v):
        return ""
    try:
        number = float(v)
    except Exception:
        return str(v)
    rounded = int(round(number))
    return f"{rounded:,}".replace(",", " ") + " €"


def format_surface(v) -> str:
    if pd.isna(v):
        return ""
    try:
        number = float(v)
    except Exception:
        return str(v)
    rounded = int(round(number))
    return f"{rounded} m²"


def is_currency_column(col_name: str) -> bool:
    col_lower = col_name.lower()
    keywords = [
        "loyer",
        "charges",
        "taxe",
        "marketing",
        "total",
        "dépôt de garantie",
        "honoraires",
        "valeur bp",
    ]
    return any(k in col_lower for k in keywords)


def is_surface_column(col_name: str) -> bool:
    col_lower = col_name.lower()
    keywords = ["surface", "gla", "m²"]
    return any(k in col_lower for k in keywords)


# ----------------------
# Data
# ----------------------

df = load_data(DATA_PATH)

if df.empty:
    st.error("Aucune donnée active trouvée dans le fichier Excel.")
    st.stop()

# Column indices for details: G (index 6) to AL (index 37) inclusive, excluding H (index 7)
DETAIL_START_IDX = 6
DETAIL_END_IDX = 37
GMAPS_COL_IDX = 7  # H

columns = list(df.columns)
if len(columns) <= DETAIL_END_IDX:
    st.error("Le fichier Excel ne contient pas les colonnes jusqu'à AL (index 37).")
    st.stop()


# ----------------------
# Session state
# ----------------------

if "selected_ref" not in st.session_state:
    st.session_state.selected_ref = None

if "drawer_open" not in st.session_state:
    st.session_state.drawer_open = False

if "filters_initialized" not in st.session_state:
    st.session_state.filters_initialized = False


# ----------------------
# Sidebar (left panel, 275px)
# ----------------------

with st.sidebar:
    st.markdown("<div style='margin-top:25px'></div>", unsafe_allow_html=True)
    logo_path = ASSETS_DIR / "Logo bleu crop.png"
    if logo_path.exists():
        st.image(str(logo_path), use_column_width=True)
    st.markdown("<hr style='border-color: rgba(255,255,255,0.2);'>", unsafe_allow_html=True)

    st.markdown(
        f"""<h3 style="color:white; margin-top:0.5rem; margin-bottom:0.5rem;">Filtres</h3>""",
        unsafe_allow_html=True,
    )

    # Prepare options
    regions = sorted(df["Région"].dropna().unique().tolist())
    dept_by_region = {
        region: sorted(df[df["Région"] == region]["Département"].dropna().unique().tolist())
        for region in regions
    }

    # Slider ranges (full ranges from active data)
    surface_min = float(df["Surface GLA"].min()) if "Surface GLA" in df.columns else 0.0
    surface_max = float(df["Surface GLA"].max()) if "Surface GLA" in df.columns else 0.0
    loyer_min = float(df["Loyer annuel"].min()) if "Loyer annuel" in df.columns else 0.0
    loyer_max = float(df["Loyer annuel"].max()) if "Loyer annuel" in df.columns else 0.0

    # Initialize filters only once
    if not st.session_state.filters_initialized:
        # Regions / départements
        for region in regions:
            st.session_state.setdefault(f"region_{region}", False)
            for dept in dept_by_region[region]:
                st.session_state.setdefault(f"dept_{region}_{dept}", False)

        # Sliders
        st.session_state.surface_range = (surface_min, surface_max)
        st.session_state.loyer_range = (loyer_min, loyer_max)

        # Other filter groups
        for col_name in ["Emplacement", "Typologie", "Extraction", "Restauration"]:
            if col_name in df.columns:
                values = sorted(df[col_name].dropna().astype(str).unique().tolist())
                for v in values:
                    st.session_state.setdefault(f"{col_name}_{v}", False)

        st.session_state.filters_initialized = True

    # --- Région / Département ---
    st.markdown(
        f"""<p style="color:{COPPER_SMBG}; font-weight:600; margin-bottom:0.25rem;">Région / Département</p>""",
        unsafe_allow_html=True,
    )

    for region in regions:
        region_key = f"region_{region}"
        region_checked = st.checkbox(region, key=region_key)
        if region_checked:
            for dept in dept_by_region[region]:
                dept_key = f"dept_{region}_{dept}"
                label = f"↳ {dept}"
                st.checkbox(label, key=dept_key)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Sliders ---
    st.markdown(
        f"""<p style="color:{COPPER_SMBG}; font-weight:600; margin-bottom:0.25rem;">Surface GLA (m²)</p>""",
        unsafe_allow_html=True,
    )
    if surface_min != surface_max:
        st.session_state.surface_range = st.slider(
            "Surface GLA",
            min_value=float(surface_min),
            max_value=float(surface_max),
            value=st.session_state.surface_range,
            label_visibility="collapsed",
        )
    else:
        st.write("Plage unique de surface.")

    st.markdown(
        f"""<p style="color:{COPPER_SMBG}; font-weight:600; margin-top:0.75rem; margin-bottom:0.25rem;">Loyer annuel (€)</p>""",
        unsafe_allow_html=True,
    )
    if loyer_min != loyer_max:
        st.session_state.loyer_range = st.slider(
            "Loyer annuel",
            min_value=float(loyer_min),
            max_value=float(loyer_max),
            value=st.session_state.loyer_range,
            label_visibility="collapsed",
        )
    else:
        st.write("Plage unique de loyer.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Other checkbox groups ---
    def render_checkbox_group(col_name: str, title: str):
        if col_name not in df.columns:
            return []
        st.markdown(
            f"""<p style="color:{COPPER_SMBG}; font-weight:600; margin-bottom:0.25rem;">{title}</p>""",
            unsafe_allow_html=True,
        )
        selected_values = []
        values = sorted(df[col_name].dropna().astype(str).unique().tolist())
        for v in values:
            key = f"{col_name}_{v}"
            label = f"{v}"
            checked = st.checkbox(label, key=key)
            if checked:
                selected_values.append(v)
        st.markdown("<br>", unsafe_allow_html=True)
        return selected_values

    selected_emplacement = render_checkbox_group("Emplacement", "Emplacement")
    selected_typologie = render_checkbox_group("Typologie", "Typologie")
    selected_extraction = render_checkbox_group("Extraction", "Extraction")
    selected_restauration = render_checkbox_group("Restauration", "Restauration")

    # --- Reset button ---
    def reset_filters():
        # Regions / départements
        for region in regions:
            st.session_state[f"region_{region}"] = False
            for dept in dept_by_region[region]:
                st.session_state[f"dept_{region}_{dept}"] = False

        # Sliders
        st.session_state.surface_range = (surface_min, surface_max)
        st.session_state.loyer_range = (loyer_min, loyer_max)

        # Other groups
        for col_name in ["Emplacement", "Typologie", "Extraction", "Restauration"]:
            if col_name in df.columns:
                values = sorted(df[col_name].dropna().astype(str).unique().tolist())
                for v in values:
                    st.session_state[f"{col_name}_{v}"] = False

        # Drawer
        st.session_state.selected_ref = None
        st.session_state.drawer_open = False

    st.markdown("<hr style='border-color: rgba(255,255,255,0.2);'>", unsafe_allow_html=True)
    if st.button("Réinitialiser"):
        reset_filters()


# ----------------------
# Apply filters
# ----------------------

filtered = df.copy()

# Slider filters
if "Surface GLA" in filtered.columns:
    s_min, s_max = st.session_state.surface_range
    filtered = filtered[(filtered["Surface GLA"] >= s_min) & (filtered["Surface GLA"] <= s_max)]

if "Loyer annuel" in filtered.columns:
    l_min, l_max = st.session_state.loyer_range
    filtered = filtered[(filtered["Loyer annuel"] >= l_min) & (filtered["Loyer annuel"] <= l_max)]

# Region / département filters
selected_regions = [r for r in regions if st.session_state.get(f"region_{r}", False)]
if selected_regions:
    # For each selected region, check if any département is selected
    region_masks = []
    for region in selected_regions:
        region_df = filtered[filtered["Région"] == region]
        selected_depts = [
            dept for dept in dept_by_region[region] if st.session_state.get(f"dept_{region}_{dept}", False)
        ]
        if selected_depts:
            region_masks.append(
                (filtered["Région"] == region) & (filtered["Département"].isin(selected_depts))
            )
        else:
            # Region only
            region_masks.append(filtered["Région"] == region)
    if region_masks:
        combined_mask = region_masks[0]
        for m in region_masks[1:]:
            combined_mask = combined_mask | m
        filtered = filtered[combined_mask]

# Other checkbox groups
def apply_group_filter(data: pd.DataFrame, col_name: str, selected_values: list) -> pd.DataFrame:
    if not selected_values or col_name not in data.columns:
        return data
    return data[data[col_name].astype(str).isin(selected_values)]


filtered = apply_group_filter(filtered, "Emplacement", selected_emplacement)
filtered = apply_group_filter(filtered, "Typologie", selected_typologie)
filtered = apply_group_filter(filtered, "Extraction", selected_extraction)
filtered = apply_group_filter(filtered, "Restauration", selected_restauration)

filtered = filtered.reset_index(drop=True)


# ----------------------
# Map (center area)
# ----------------------

# Determine map center
if "Latitude" in filtered.columns and "Longitude" in filtered.columns and not filtered.empty:
    center_lat = filtered["Latitude"].mean()
    center_lon = filtered["Longitude"].mean()
else:
    center_lat, center_lon = 46.6, 2.4  # France

m = folium.Map(
    location=[center_lat, center_lon],
    tiles="OpenStreetMap",
    zoom_start=6,
    control_scale=False,
    zoom_control=True,
)

# Add pins (one per lot, no popup, no jitter)
for _, row in filtered.iterrows():
    lat = row.get("Latitude")
    lon = row.get("Longitude")
    if pd.isna(lat) or pd.isna(lon):
        continue

    ref_raw = row.get("Référence annonce")
    ref_display = format_reference(ref_raw)

    icon_html = f'''
<div style="
    background-color: {BLUE_SMBG};
    border-radius: 50%;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #000000;
    color: #ffffff;
    font-size: 13px;
    font-weight: bold;
    cursor: pointer;
">
    {ref_display}
</div>
'''
    folium.Marker(
        location=[lat, lon],
        icon=folium.DivIcon(
            html=icon_html,
            icon_size=(32, 32),
            icon_anchor=(16, 16),
            class_name="smbg-divicon",
        ),
    ).add_to(m)

# Display map full page (center)
map_html_container = st.container()
with map_html_container:
    st.markdown('<div id="map-container">', unsafe_allow_html=True)
    map_data = st_folium(
        m,
        width=None,
        height=600,  # overruled by CSS to 100vh
        key="smbg_map",
    )
    st.markdown("</div>", unsafe_allow_html=True)


# ----------------------
# Handle map interactions (open/close drawer)
# ----------------------

def find_ref_from_click(lat_click, lon_click):
    if "Latitude" not in filtered.columns or "Longitude" not in filtered.columns:
        return None
    # Tolerance for floating point comparison
    tol = 1e-6
    candidates = filtered[
        (filtered["Latitude"].sub(lat_click).abs() < tol)
        & (filtered["Longitude"].sub(lon_click).abs() < tol)
    ]
    if candidates.empty:
        return None
    return candidates.iloc[0].get("Référence annonce")


if map_data is not None:
    obj_clicked = map_data.get("last_object_clicked")
    map_clicked = map_data.get("last_clicked")

    # Priority: pin click (object) vs map click
    if obj_clicked is not None:
        lat_click = obj_clicked.get("lat")
        lon_click = obj_clicked.get("lng")
        if lat_click is not None and lon_click is not None:
            ref = find_ref_from_click(lat_click, lon_click)
            if ref is not None:
                st.session_state.selected_ref = ref
                st.session_state.drawer_open = True
    elif map_clicked is not None:
        # Click on map (outside pin) closes drawer
        st.session_state.selected_ref = None
        st.session_state.drawer_open = False


# ----------------------
# Right drawer (details panel, 275px, retractable)
# ----------------------

def render_detail_drawer():
    if not st.session_state.drawer_open or st.session_state.selected_ref is None:
        return

    ref_value = st.session_state.selected_ref
    # Fetch the corresponding row from the full df (1 lot = 1 annonce)
    row_matches = df[df["Référence annonce"] == ref_value]
    if row_matches.empty:
        # Try with formatted reference if Excel stores differently
        ref_str = format_reference(ref_value)
        row_matches = df[df["Référence annonce"].astype(str).apply(format_reference) == ref_str]
        if row_matches.empty:
            return

    row = row_matches.iloc[0]

    # Google Maps link
    gmaps_url = None
    if GMAPS_COL_IDX < len(columns):
        gmaps_col = columns[GMAPS_COL_IDX]
        gmaps_url = row.get(gmaps_col)
        if pd.isna(gmaps_url):
            gmaps_url = None

    # Build detail table rows (columns G -> AL, except H)
    rows_html = []
    for idx in range(DETAIL_START_IDX, DETAIL_END_IDX + 1):
        if idx == GMAPS_COL_IDX:
            continue
        col_name = columns[idx]
        value = row.get(col_name)

        if is_empty_value(value):
            continue

        # Formatting
        if is_currency_column(col_name):
            value_str = format_currency(value)
        elif is_surface_column(col_name):
            value_str = format_surface(value)
        else:
            value_str = str(value)

        if is_empty_value(value_str):
            continue

        rows_html.append(
            f"<tr><td class='label'>{col_name}</td><td class='value'>{value_str}</td></tr>"
        )

    rows_html_str = "\n".join(rows_html)

    ref_display = format_reference(row.get("Référence annonce"))

    gmaps_button_html = ""
    if gmaps_url:
        gmaps_button_html = f"""
<a class="gmaps-button" href="{gmaps_url}" target="_blank" rel="noopener noreferrer">
    Cliquer ici
</a>
"""

    drawer_html = f"""
<div id="detail-drawer">
    <div class="ref-label">Détails de l'annonce</div>
    <div class="ref-value">{ref_display}</div>
    {gmaps_button_html}
    <table>
        <tbody>
            {rows_html_str}
        </tbody>
    </table>
</div>
"""

    st.markdown(drawer_html, unsafe_allow_html=True)


render_detail_drawer()

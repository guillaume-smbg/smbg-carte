
import os, io, re, unicodedata, math
from typing import Optional
import pandas as pd
import streamlit as st
import folium
import requests
from streamlit_folium import st_folium

# ---------- Page / style ----------

st.set_page_config(page_title="SMBG Carte — Leaflet (Mapnik)", layout="wide")

LOGO_BLUE = "#05263d"
COPPER = "#c47e47"

CSS = f"""
<style>
  [data-testid="stAppViewContainer"] {{
    padding-top: 0;
    padding-bottom: 0;
  }}
  .block-container {{
    padding-top: 8px !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    max-width: 100% !important;
  }}

  /* Layout principal : map zone + panneau droit fixe */
  .main-wrapper {{
    display: flex;
    flex-direction: row;
    width: 100%;
    height: calc(100vh - 8px);
    overflow: hidden;
  }}
  .map-zone {{
    flex: 1;
    min-width: 0;
  }}
  .right-panel {{
    width:275px;
    min-width:275px;
    max-width:275px;
    height:100%;
    border-left:1px solid #e9eaee;
    box-shadow:-14px 0 28px rgba(0,0,0,.12);
    background:#fff;
    display:flex;
    flex-direction:column;
    font-family: system-ui, sans-serif;
  }}

  .panel-banner {{
    background:{LOGO_BLUE};
    color:#fff;
    padding:12px 16px;
    font-weight:800;
    font-size:18px;
  }}
  .panel-body {{
    flex:1;
    overflow-y:auto;
    padding:14px 16px 24px;
    font-size:14px;
    line-height:1.4;
  }}

  .panel-title {{
    margin-top: 12px;
    font-weight: 800;
    color: {LOGO_BLUE};
  }}

  .gmaps-btn button {{
    background: {COPPER} !important;
    color: #ffffff !important;
    font-weight: 700;
    border-radius: 10px;
    border: none;
    padding: 6px 10px;
    font-size:14px;
    cursor:pointer;
  }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"


# ---------- Helpers ----------

def normalize_excel_url(url: str) -> str:
    if not url:
        return url
    # turn .../blob/... into .../raw/...
    return re.sub(
        r"https://github\.com/(.+)/blob/([^ ]+)",
        r"https://github.com/\1/raw/\2",
        url.strip()
    )

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    """
    Charge l'Excel depuis EXCEL_URL (Streamlit secrets/env) ou local.
    """
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    excel_url = normalize_excel_url(excel_url)

    if excel_url:
        r = requests.get(excel_url, timeout=25)
        r.raise_for_status()
        return pd.read_excel(io.BytesIO(r.content))

    if not os.path.exists(DEFAULT_LOCAL_PATH):
        st.stop()

    return pd.read_excel(DEFAULT_LOCAL_PATH)


def norm_txt(x: str) -> str:
    if x is None:
        return ""
    s = str(x).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s)
    return s


def find_col(df: pd.DataFrame, *candidates) -> str:
    """
    Trouve la colonne du df qui correspond le mieux à une des propositions.
    """
    norm_map = {c: norm_txt(c) for c in df.columns}

    for cand in candidates:
        cn = norm_txt(cand)

        # match exact normalisé
        for c, n in norm_map.items():
            if n == cn:
                return c

        # match fuzzy (tous les morceaux présents)
        parts = cn.split()
        for c, n in norm_map.items():
            if all(part in n for part in parts):
                return c

    return ""


def to_number(value) -> Optional[float]:
    """
    Nettoie '1 200 m²', '36 000 €', etc. => float
    """
    if value is None:
        return None

    s = str(value).strip()
    if s == "":
        return None

    s = (
        s.replace("€", "")
         .replace("euro", "")
         .replace("euros", "")
         .replace("m²", "")
         .replace("m2", "")
         .replace("mÂ²", "")
         .replace(" ", " ")
         .replace(" ", "")
         .replace(",", ".")
    )

    m = re.findall(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None

    try:
        return float(m[0])
    except Exception:
        return None


def clean_latlon_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False)
        .map(to_number)
    )


def build_lots_table(df_ref: pd.DataFrame) -> pd.DataFrame:
    """
    Tableau affiché dans le panneau droit.
    On garde G→AH si dispo (colonnes 6:34), sinon tout df_ref.
    """
    cols = list(df_ref.columns)
    if len(cols) > 33:
        view = df_ref.iloc[:, 6:34].copy()
    else:
        view = df_ref.copy()
    return view


def get_first_gmaps_link(df_lots: pd.DataFrame, gm_col: str) -> Optional[str]:
    if gm_col and gm_col in df_lots.columns:
        for v in df_lots[gm_col].astype(str):
            v_clean = v.strip()
            if v_clean and v_clean not in ["-", "/"]:
                return v_clean
    return None


def render_right_panel(selected_ref: Optional[str], df: pd.DataFrame, col_ref: str, col_gmaps: str):
    """
    Dessine le HTML du layout global et prépare le contenu du panneau.
    """
    st.markdown('<div class="main-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="map-zone">', unsafe_allow_html=True)

    st.session_state["_panel_payload"] = {}

    if selected_ref is None:
        st.session_state["_panel_payload"]["empty"] = True
    else:
        def normalize_ref_str(x: str) -> str:
            x = str(x).strip()
            if re.match(r"^\d+\.0+$", x):
                return x.split(".")[0]
            return x

        lots_for_ref = df[
            df[col_ref].astype(str).map(normalize_ref_str) == normalize_ref_str(selected_ref)
        ].copy()

        st.session_state["_panel_payload"]["empty"] = False
        st.session_state["_panel_payload"]["ref_title"] = normalize_ref_str(selected_ref)
        st.session_state["_panel_payload"]["gmaps"] = get_first_gmaps_link(lots_for_ref, col_gmaps)
        st.session_state["_panel_payload"]["lots_df"] = build_lots_table(lots_for_ref)


def close_right_panel_layout():
    """Ferme map-zone et affiche le panneau droit permanent."""
    st.markdown('</div>', unsafe_allow_html=True)  # close .map-zone
    payload = st.session_state.get("_panel_payload", {})

    st.markdown('<div class="right-panel">', unsafe_allow_html=True)

    if payload.get("empty", True):
        st.markdown('<div class="panel-banner">Aucune sélection</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-body"><p>Sélectionnez une annonce sur la carte.</p></div>', unsafe_allow_html=True)
    else:
        ref_title = payload.get("ref_title","")
        gmaps_link = payload.get("gmaps", None)
        lots_df = payload.get("lots_df", pd.DataFrame())

        st.markdown(f'<div class="panel-banner">Référence : {ref_title}</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-body">', unsafe_allow_html=True)

        if gmaps_link:
            st.markdown(f'<div class="gmaps-btn"><a href="{gmaps_link}" target="_blank"><button>Cliquer ici</button></a></div>', unsafe_allow_html=True)

        st.markdown('<div class="panel-title">Lots de l’annonce</div>', unsafe_allow_html=True)
        st.dataframe(lots_df, use_container_width=True, height=500)

        st.markdown('</div>', unsafe_allow_html=True)  # close .panel-body

    st.markdown('</div>', unsafe_allow_html=True)  # close .right-panel
    st.markdown('</div>', unsafe_allow_html=True)  # close .main-wrapper


def main():
    # ---------- Charger données ----------
    df = load_excel()
    if df is None or df.empty:
        st.error("Excel vide ou introuvable.")
        st.stop()

    # détecter colonnes clés
    col_lat   = find_col(df, "Latitude")
    col_lon   = find_col(df, "Longitude")
    col_ref   = find_col(df, "Référence annonce", "Reference")
    col_gmaps = find_col(df, "Lien Google Maps", "Google Maps")

    if not col_lat or not col_lon or not col_ref:
        st.error("Colonnes Latitude / Longitude / Référence manquantes.")
        st.stop()

    # nettoyer coords
    df["_lat"] = clean_latlon_series(df[col_lat])
    df["_lon"] = clean_latlon_series(df[col_lon])

    df = df[df["_lat"].notna() & df["_lon"].notna()].copy()
    if df.empty:
        st.error("Aucune ligne avec coordonnées valides.")
        st.stop()

    # ---------- Regrouper par référence (1 pin = 1 annonce) ----------
    def normalize_ref_label(v):
        s = str(v).strip()
        if re.match(r"^\d+\.0+$", s):
            s = s.split(".")[0]
        return s

    grouped = (
        df.groupby(col_ref, as_index=False)
          .agg({"_lat": "mean", "_lon": "mean"})
          .copy()
    )
    grouped["ref_label"] = grouped[col_ref].map(normalize_ref_label)

    # ---------- State : référence sélectionnée ----------
    if "selected_ref" not in st.session_state:
        st.session_state["selected_ref"] = None

    # Construire le layout global (ouvre .main-wrapper et .map-zone)
    render_right_panel(
        st.session_state["selected_ref"],
        df,
        col_ref,
        col_gmaps
    )

    # ---------- Carte Leaflet ----------
    FR_LAT, FR_LON, FR_ZOOM = 46.603354, 1.888334, 6  # centre France
    m = folium.Map(
        location=[FR_LAT, FR_LON],
        zoom_start=FR_ZOOM,
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
    )

    css_marker = (
        f"background:{LOGO_BLUE};"
        "color:#fff;"
        "border:2px solid #fff;"
        "width:28px; height:28px; line-height:28px;"
        "border-radius:50%; text-align:center;"
        "font-size:11px; font-weight:600;"
    )

    layer = folium.FeatureGroup(name="Annonces").add_to(m)

    for _, row in grouped.iterrows():
        lat = float(row["_lat"])
        lon = float(row["_lon"])
        ref_label = str(row["ref_label"])

        icon = folium.DivIcon(
            html=f'<div style="{css_marker}">{ref_label}</div>'
        )

        # popup=ref_label pour capter quelle référence a été cliquée
        folium.Marker(
            location=[lat, lon],
            icon=icon,
            tooltip=ref_label,
            popup=ref_label,
        ).add_to(layer)

    out = st_folium(m, height=950, width=None, returned_objects=[])

    # ---------- Gérer le clic et mettre à jour la ref sélectionnée ----------
    clicked_ref = None
    if isinstance(out, dict):
        loc_info = out.get("last_object_clicked")
        if isinstance(loc_info, dict):
            popv = loc_info.get("popup")
            if popv:
                clicked_ref = str(popv).strip()
            # clic vide sur la carte -> pas de popup => on met None
            elif "lat" in loc_info and "lng" in loc_info:
                clicked_ref = None

    # si l'utilisateur a cliqué (pin OU carte), on met à jour
    if clicked_ref is not None:
        st.session_state["selected_ref"] = clicked_ref

    # ---------- Fermer la structure layout et afficher le panneau droit ----------
    close_right_panel_layout()


if __name__ == "__main__":
    main()

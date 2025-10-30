import os, io, re, unicodedata, math
from typing import Optional
import pandas as pd
import streamlit as st
import folium
import requests
from streamlit_folium import st_folium

# -------------------------------------------------
# CONFIG GLOBALE / STYLE
# -------------------------------------------------

st.set_page_config(page_title="SMBG Carte — Leaflet (Mapnik)", layout="wide")

LOGO_BLUE = "#05263d"
COPPER = "#c47e47"

CSS = f"""
<style>
  /* cache le bouton hamburger de Streamlit */
  [data-testid="collapsedControl"] {{
    display: none !important;
  }}

  /* Sidebar gauche = panneau filtres */
  [data-testid="stSidebar"] {{
    width: 275px !important;
    min-width: 275px !important;
    max-width: 275px !important;
    background: {LOGO_BLUE};
    color: {COPPER};
  }}
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3,
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] label {{
    color: {COPPER} !important;
  }}

  [data-testid="stSidebar"] .group-title {{
    margin: 8px 0 4px 0;
    font-weight: 700;
    color: {COPPER};
  }}

  [data-testid="stSidebar"] .stButton > button,
  [data-testid="stSidebar"] .stButton > button * {{
    background: {COPPER} !important;
    color: #ffffff !important;
    font-weight: 700;
    border-radius: 10px;
    border: none;
  }}

  /* container global */
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

  /* colonne droite = panneau info */
  .right-panel-box {{
    width: 275px;
    min-width: 275px;
    max-width: 275px;
    border-left:1px solid #e9eaee;
    box-shadow:-14px 0 28px rgba(0,0,0,.12);
    background:#fff;
    height: calc(100vh - 16px);
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
    background:#fff;
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

  /* indentation des départements sous les régions */
  .dept-row {{
    display: flex;
    flex-direction: row;
    align-items: center;
  }}
  .dept-pad {{
    width: 16px;
  }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"


# -------------------------------------------------
# OUTILS / HELPERS
# -------------------------------------------------

def normalize_excel_url(url: str) -> str:
    """Transforme une URL GitHub /blob/ en /raw/ si besoin."""
    if not url:
        return url
    return re.sub(
        r"https://github\.com/(.+)/blob/([^ ]+)",
        r"https://github.com/\1/raw/\2",
        url.strip()
    )

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    """
    Charge l'Excel depuis EXCEL_URL (Streamlit secrets/env) ou local fallback.
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

def normalize_bool(val):
    """Convertit 'oui' / 1 / True en bool."""
    if isinstance(val, str):
        return val.strip().lower() in ["oui", "yes", "true", "1", "vrai"]
    if isinstance(val, (int, float)):
        try:
            return int(val) == 1
        except Exception:
            return False
    if isinstance(val, bool):
        return val
    return False

def norm_txt(x: str) -> str:
    """Normalise du texte (minuscule, sans accent, espaces réduits)."""
    if x is None:
        return ""
    s = str(x).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s)
    return s

def sanitize_value(v):
    """Pour l'affichage du tableau de lots : remplace -, /, vide par ''. """
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s in ["", "-", "/"] else s

def find_col(df: pd.DataFrame, *candidates) -> str:
    """
    Trouve la colonne du df qui correspond le mieux à une des propositions.
    (matching exact normalisé ou fuzzy 'contient tous les mots')
    """
    def _norm(x: str) -> str:
        if x is None:
            return ""
        y = str(x).strip().lower()
        y = unicodedata.normalize("NFKD", y).encode("ascii","ignore").decode("ascii")
        y = re.sub(r"\s+"," ",y)
        return y

    norm_map = {c: _norm(c) for c in df.columns}

    for cand in candidates:
        cn = _norm(cand)

        # match exact normalisé
        for c, n in norm_map.items():
            if n == cn:
                return c

        # match fuzzy
        parts = cn.split()
        for c, n in norm_map.items():
            if all(part in n for part in parts):
                return c

    return ""

def to_number(value) -> Optional[float]:
    """
    Nettoie '1 200 m²', '36 000 €', etc. et renvoie un float.
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
         .replace("\xa0", " ")
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

def clean_numeric_series(series: pd.Series) -> pd.Series:
    return series.map(to_number)

def clean_latlon_series(series: pd.Series) -> pd.Series:
    """Convertit latitude/longitude en float, supportant les virgules."""
    return (
        series.astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False)
        .map(to_number)
    )

def reset_filters_defaults():
    """
    Hard reset : supprime les clés de filtres dans session_state puis rerun.
    """
    for k in list(st.session_state.keys()):
        if k.startswith(("reg_", "dep_", "typo_", "extr_", "empl_")):
            try:
                del st.session_state[k]
            except Exception:
                pass
    for k in ["surf_range", "loyer_range"]:
        if k in st.session_state:
            try:
                del st.session_state[k]
            except Exception:
                pass
    st.rerun()

def build_lots_table(df_ref: pd.DataFrame) -> pd.DataFrame:
    """
    Table affichée dans le panneau droit.
    On garde G→AH si dispo (6:34), sinon tout df_ref.
    On nettoie les '-' '/' ''.
    """
    cols = list(df_ref.columns)
    if len(cols) > 33:
        view = df_ref.iloc[:, 6:34].copy()
    else:
        view = df_ref.copy()

    for c in view.columns:
        view[c] = view[c].apply(sanitize_value)

    return view

def get_first_gmaps_link(df_lots: pd.DataFrame, gm_col: str) -> Optional[str]:
    """Retourne le premier lien Google Maps non vide pour l'annonce."""
    if gm_col and gm_col in df_lots.columns:
        for v in df_lots[gm_col].astype(str):
            v_clean = v.strip()
            if v_clean and v_clean not in ["-", "/"]:
                return v_clean
    return None

def anti_overlap_positions(n: int, base_lat: float, base_lon: float):
    """
    Si plusieurs annonces partagent exactement les mêmes coords,
    on les décale un peu en cercle pour éviter la superposition visuelle.
    """
    if n <= 1:
        return [(base_lat, base_lon)]

    r = 0.0006  # ~60m décalage
    out = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        out.append(
            (base_lat + r * math.sin(angle), base_lon + r * math.cos(angle))
        )
    return out

def overlaps(a_min, a_max, b_min, b_max):
    """
    Vérifie si [a_min ; a_max] chevauche [b_min ; b_max].
    Si une info manque => True (on garde).
    """
    if (
        a_min is None
        or a_max is None
        or b_min is None
        or b_max is None
    ):
        return True
    try:
        return not (a_max < b_min or a_min > b_max)
    except TypeError:
        return True


# -------------------------------------------------
# PANNEAU DROIT : rendu
# -------------------------------------------------

def render_right_panel(selected_ref: Optional[str],
                       df_full: pd.DataFrame,
                       col_ref: str,
                       col_gmaps: str):
    """
    Construit le contenu du panneau info à droite.
    """
    def normalize_ref_str(x: str) -> str:
        x = str(x).strip()
        if re.match(r"^\d+\.0+$", x):
            return x.split(".")[0]
        return x

    if not selected_ref:
        st.markdown('<div class="right-panel-box">', unsafe_allow_html=True)
        st.markdown('<div class="panel-banner">Aucune sélection</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-body"><p>Sélectionnez une annonce sur la carte.</p></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    lots_for_ref = df_full[
        df_full[col_ref].astype(str).map(normalize_ref_str)
        ==
        normalize_ref_str(selected_ref)
    ].copy()

    table_df = build_lots_table(lots_for_ref)
    gmaps_link = get_first_gmaps_link(lots_for_ref, col_gmaps)

    ref_title = normalize_ref_str(selected_ref)

    st.markdown('<div class="right-panel-box">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="panel-banner">Référence : {ref_title}</div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="panel-body">', unsafe_allow_html=True)

    if gmaps_link:
        st.markdown(
            f'<div class="gmaps-btn"><a href="{gmaps_link}" target="_blank"><button>Cliquer ici</button></a></div>',
            unsafe_allow_html=True
        )

    st.markdown('<div class="panel-title">Lots de l’annonce</div>', unsafe_allow_html=True)
    st.dataframe(table_df, use_container_width=True, height=500)

    st.markdown('</div>', unsafe_allow_html=True)  # .panel-body
    st.markdown('</div>', unsafe_allow_html=True)  # .right-panel-box


# -------------------------------------------------
# MAIN
# -------------------------------------------------

def main():
    # ------------------------------
    # Chargement et préparation data
    # ------------------------------
    df = load_excel()
    if df is None or df.empty:
        st.warning("Excel vide ou introuvable.")
        st.stop()

    # détecter les colonnes du fichier Excel
    col_lat     = find_col(df, "Latitude")
    col_lon     = find_col(df, "Longitude")
    col_actif   = find_col(df, "Actif")
    col_typo    = find_col(df, "Typologie", "Typologie d'actif")
    col_empl    = find_col(df, "Emplacement")
    col_extr    = find_col(df, "Extraction")
    col_loyer   = find_col(df, "Loyer annuel", "Loyer annuel (€)", "Loyer annuel (euros)")
    col_surface = find_col(df, "Surface", "Surface GLA", "GLA", "Surface totale")
    col_region  = find_col(df, "Région")
    col_dept    = find_col(df, "Département")
    col_ref     = find_col(df, "Référence annonce", "Reference")
    col_gmaps   = find_col(df, "Lien Google Maps", "Google Maps")

    # sécurité
    if not col_lat or not col_lon or not col_ref:
        st.error("Colonnes Latitude / Longitude / Référence annonce introuvables.")
        st.stop()

    # booléen actif
    df["_actif"] = df[col_actif] if col_actif else "oui"
    df["_actif"] = df["_actif"].apply(normalize_bool)

    # coords GPS
    df["_lat"] = clean_latlon_series(df[col_lat])
    df["_lon"] = clean_latlon_series(df[col_lon])

    # typologie / emplacement / extraction normalisés pour les filtres
    df["_typologie_n"] = df[col_typo].astype(str).map(norm_txt) if col_typo else ""
    df["_empl_n"]      = df[col_empl].astype(str).map(norm_txt) if col_empl else ""
    df["_extr_n"]      = df[col_extr].astype(str).map(norm_txt) if col_extr else ""

    # ne garder que les lignes actives avec coords
    df = df[df["_actif"] & df["_lat"].notna() & df["_lon"].notna()].copy()
    if df.empty:
        st.warning("Aucune ligne active avec coordonnées valides.")
        st.stop()

    # plages globales pour sliders
    surf_global = clean_numeric_series(df[col_surface]).dropna() if col_surface else pd.Series([], dtype=float)
    loyer_global = clean_numeric_series(df[col_loyer]).dropna() if col_loyer else pd.Series([], dtype=float)

    smin, smax = (int(surf_global.min()), int(surf_global.max())) if not surf_global.empty else (None, None)
    lmin, lmax = (int(loyer_global.min()), int(loyer_global.max())) if not loyer_global.empty else (None, None)

    # ------------------------------
    # BARRE LATERALE GAUCHE (filtres)
    # ------------------------------
    with st.sidebar:
        st.markdown("### Filtres")

        lots_working = df.copy()

        # --- Région / Département ---
        if col_region and col_dept:
            with st.expander("Région / Département", expanded=True):
                regions = sorted(
                    [
                        r
                        for r in lots_working[col_region]
                        .dropna().astype(str).unique()
                        if r not in ["-", "/"]
                    ]
                )

                selected_regions = []
                selected_deps = []

                for reg in regions:
                    # checkbox région
                    if st.checkbox(reg, key=f"reg_{reg}"):
                        selected_regions.append(reg)

                        # liste des départements de cette région
                        deps = sorted(
                            [
                                d
                                for d in lots_working[
                                    lots_working[col_region].astype(str) == reg
                                ][col_dept]
                                .dropna().astype(str).unique()
                                if d not in ["-", "/"]
                            ]
                        )

                        # afficher chaque département indenté
                        for dep in deps:
                            col_pad, col_box = st.columns([1, 10])
                            with col_pad:
                                st.write("")  # juste l'indent visuel
                            with col_box:
                                if st.checkbox(dep, key=f"dep_{reg}_{dep}"):
                                    selected_deps.append(dep)

                # filtrage
                if selected_regions:
                    lots_working = lots_working[
                        lots_working[col_region].astype(str).isin(selected_regions)
                    ]
                if selected_deps:
                    lots_working = lots_working[
                        lots_working[col_dept].astype(str).isin(selected_deps)
                    ]

        # --- Typologie d'actif ---
        if col_typo:
            st.markdown(
                "<div class='group-title'>Typologie d'actif</div>",
                unsafe_allow_html=True,
            )
            typos_raw = sorted(
                [
                    t
                    for t in lots_working[col_typo]
                    .dropna().astype(str).unique()
                    if t not in ["-", "/", ""]
                ]
            )

            chosen_norm = []
            for t in typos_raw:
                if st.checkbox(t, key=f"typo_{t}"):
                    chosen_norm.append(norm_txt(t))

            if chosen_norm:
                lots_working = lots_working[
                    lots_working["_typologie_n"].isin(chosen_norm)
                ]

        # --- Extraction ---
        if col_extr:
            st.markdown(
                "<div class='group-title'>Extraction</div>",
                unsafe_allow_html=True,
            )
            extr_opts = ["oui", "non", "faisable"]
            sel_extr = []

            for e in extr_opts:
                if st.checkbox(e, key=f"extr_{e}"):
                    sel_extr.append(norm_txt(e))

            if sel_extr:
                lots_working = lots_working[
                    lots_working["_extr_n"].isin(sel_extr)
                ]

        # --- Emplacement ---
        if col_empl:
            st.markdown(
                "<div class='group-title'>Emplacement</div>",
                unsafe_allow_html=True,
            )
            vals = [
                e
                for e in lots_working[col_empl]
                .dropna().astype(str).unique()
                if e not in ["-", "/", ""]
            ]
            base = ["Centre-ville", "Périphérie"]
            ordered = [e for e in base if e in vals] + [e for e in vals if e not in base]

            sel_empl = []
            for e in ordered:
                if st.checkbox(e, key=f"empl_{e}"):
                    sel_empl.append(norm_txt(e))

            if sel_empl:
                lots_working = lots_working[
                    lots_working["_empl_n"].isin(sel_empl)
                ]

        # --- Sliders SURFACE ---
        if smin is not None and smax is not None:
            if "surf_range" not in st.session_state:
                st.session_state["surf_range"] = (smin, smax)

            st.session_state["surf_range"] = st.slider(
                "Surface (m²)",
                min_value=smin,
                max_value=smax,
                value=st.session_state["surf_range"],
                step=1,
                key="surf_slider",
            )

        # --- Sliders LOYER ---
        if lmin is not None and lmax is not None:
            if "loyer_range" not in st.session_state:
                st.session_state["loyer_range"] = (lmin, lmax)

            st.session_state["loyer_range"] = st.slider(
                "Loyer annuel (€)",
                min_value=lmin,
                max_value=lmax,
                value=st.session_state["loyer_range"],
                step=1000,
                key="loyer_slider",
            )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Réinitialiser les filtres"):
                reset_filters_defaults()
        with c2:
            st.button("Je suis intéressé")

    # ------------------------------
    # On a maintenant lots_working = lignes filtrées
    # On agrège par référence annonce -> 1 pin = 1 annonce
    # ------------------------------

    if not col_ref:
        st.error("Colonne 'Référence annonce' introuvable dans le fichier Excel.")
        st.stop()

    def ref_agg(group: pd.DataFrame) -> pd.Series:
        """
        Pour chaque référence :
         - coords moyennes
         - surface min/max
         - loyer min/max
         - libellé ref sans .0
        """
        out = {
            "_lat": group["_lat"].mean(),
            "_lon": group["_lon"].mean(),
        }

        # plage de surfaces
        if col_surface:
            s = clean_numeric_series(group[col_surface]).dropna()
            out["surf_min"] = float(s.min()) if not s.empty else None
            out["surf_max"] = float(s.max()) if not s.empty else None
        else:
            out["surf_min"] = None
            out["surf_max"] = None

        # plage de loyers
        if col_loyer:
            l = clean_numeric_series(group[col_loyer]).dropna()
            out["loyer_min"] = float(l.min()) if not l.empty else None
            out["loyer_max"] = float(l.max()) if not l.empty else None
        else:
            out["loyer_min"] = None
            out["loyer_max"] = None

        # label ref propre
        ref_val = str(group.iloc[0][col_ref]).strip()
        if re.match(r"^\d+\.0+$", ref_val):
            ref_val = ref_val.split(".")[0]
        out["ref_label"] = ref_val

        return pd.Series(out)

    refs = (
        lots_working.groupby(col_ref, as_index=False)
        .apply(ref_agg)
        .reset_index(drop=True)
    )

    # on filtre les refs selon sliders (multi-lots)
    # surface
    if smin is not None and smax is not None and "surf_range" in st.session_state:
        rmin, rmax = st.session_state["surf_range"]
        refs = refs[
            refs.apply(
                lambda r: overlaps(
                    r.get("surf_min"), r.get("surf_max"), rmin, rmax
                ),
                axis=1,
            )
        ]

    # loyer
    if lmin is not None and lmax is not None and "loyer_range" in st.session_state:
        rmin, rmax = st.session_state["loyer_range"]
        refs = refs[
            refs.apply(
                lambda r: overlaps(
                    r.get("loyer_min"), r.get("loyer_max"), rmin, rmax
                ),
                axis=1,
            )
        ]

    if refs.empty:
        if "selected_ref" not in st.session_state:
            st.session_state["selected_ref"] = None

        # même si pas d'annonces après filtres,
        # on affiche quand même la mise en page à 2 colonnes
        left_col, right_col = st.columns([1, 0.28], gap="small")

        with left_col:
            st.write("Aucun résultat pour ces filtres.")

        with right_col:
            render_right_panel(
                st.session_state["selected_ref"], df, col_ref, col_gmaps
            )
        return

    # anti-overlap sur les coord groupées
    refs["_lat_r"] = refs["_lat"].round(6)
    refs["_lon_r"] = refs["_lon"].round(6)

    rows_for_plot = []
    for (_, _), grp in refs.groupby(["_lat_r", "_lon_r"], sort=False):
        coords = anti_overlap_positions(
            len(grp),
            float(grp.iloc[0]["_lat"]),
            float(grp.iloc[0]["_lon"]),
        )
        for (lat, lon), (_, r) in zip(coords, grp.iterrows()):
            rr = r.copy()
            rr["_lat_plot"] = lat
            rr["_lon_plot"] = lon
            rows_for_plot.append(rr)

    plot_df = pd.DataFrame(rows_for_plot)

    # ------------------------------
    # STATE : ref sélectionnée pour le panneau droit permanent
    # ------------------------------
    if "selected_ref" not in st.session_state:
        st.session_state["selected_ref"] = None

    # ------------------------------
    # AFFICHAGE PRINCIPAL EN 2 COLONNES
    # ------------------------------
    left_col, right_col = st.columns([1, 0.28], gap="small")

    # colonne carte
    with left_col:
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

        for _, r in plot_df.iterrows():
            lat = float(r["_lat_plot"])
            lon = float(r["_lon_plot"])

            raw_label = str(r.get("ref_label", "")).strip()
            if re.match(r"^\d+\.0+$", raw_label):
                raw_label = raw_label.split(".")[0]

            icon = folium.DivIcon(html=f'<div style="{css_marker}">{raw_label}</div>')

            # IMPORTANT :
            # - pas de popup=... -> donc pas de bulle blanche sur la carte
            # - tooltip=raw_label -> on lit tooltip côté Streamlit
            folium.Marker(
                location=[lat, lon],
                icon=icon,
                tooltip=raw_label,
            ).add_to(layer)

        out = st_folium(m, height=950, width=None, returned_objects=[])

        # GESTION DU CLIC SUR LA CARTE
        clicked_ref = None
        if isinstance(out, dict):
            loc_info = out.get("last_object_clicked")

            if isinstance(loc_info, dict):
                tt = loc_info.get("tooltip")
                if tt:  # clic sur un pin
                    clicked_ref = str(tt).strip()
                elif "lat" in loc_info and "lng" in loc_info:
                    # clic sur fond de carte
                    clicked_ref = ""  # => repasse panneau à "Aucune sélection"

        if clicked_ref is not None:
            st.session_state["selected_ref"] = clicked_ref

    # colonne panneau droit
    with right_col:
        render_right_panel(
            st.session_state["selected_ref"], df, col_ref, col_gmaps
        )


def run():
    main()

if __name__ == "__main__":
    run()

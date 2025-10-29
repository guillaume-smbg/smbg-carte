
import os
import io
import re
from typing import Optional, List, Tuple
import pandas as pd
import streamlit as st
import requests
import folium
from streamlit.components.v1 import html as st_html

st.set_page_config(page_title="SMBG Carte — Map", layout="wide")
LOGO_BLUE = "#05263d"
COPPER = "#c47e47"

# --------- CSS ---------
_CSS = """
<style>
  :root { --smbg-blue: __BLUE__; --smbg-copper: __COPPER__; }
  [data-testid="stAppViewContainer"] { padding-top: 0; padding-bottom: 0; }
  header, footer { visibility: hidden; height: 0; }
  .block-container { padding-top: 8px !important; padding-left: 0 !important; padding-right: 0 !important; }

  /* Sidebar 275px */
  [data-testid="stSidebar"] { width: 275px; min-width: 275px; max-width: 275px; }
  [data-testid="stSidebar"] > div { background: var(--smbg-blue); color: var(--smbg-copper); min-height: 100vh; }
  [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
  [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: var(--smbg-copper) !important; }
  [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div,
  [data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"] > div { background: rgba(255,255,255,0.06); color: #fff; }
  [data-testid="stSidebar"] .stSlider > div { color: var(--smbg-copper); }
  [data-testid="stSidebar"] .stButton > button { background: var(--smbg-copper) !important; color: #ffffff !important; border: none; border-radius: 10px; font-weight: 700; }
  [data-testid="stSidebar"] .smbg-scroll { max-height: 180px; overflow-y: auto; padding: 6px 8px; background: rgba(255,255,255,0.04); border-radius: 8px; }
  [data-testid="stSidebar"] .smbg-indent { padding-left: 12px; }
</style>
"""
CSS = _CSS.replace("__BLUE__", LOGO_BLUE).replace("__COPPER__", COPPER)
st.markdown(CSS, unsafe_allow_html=True)

# --------- Data loading ---------
DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"

def normalize_excel_url(url: str) -> str:
    if not url: return url
    url = url.strip()
    url = re.sub(r"https://github\.com/(.+)/blob/([^ ]+)", r"https://github.com/\1/raw/\2", url)
    return url

def is_github_folder(url: str) -> bool:
    return bool(re.match(r"^https://github\.com/[^/]+/[^/]+/tree/[^/]+/.+", url))

def folder_to_api(url: str) -> str:
    m = re.match(r"^https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.*)$", url)
    if not m: return ""
    owner, repo, branch, path = m.groups()
    return f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"

def fetch_first_excel_from_folder(url: str) -> bytes:
    api_url = folder_to_api(url)
    r = requests.get(api_url, timeout=20); r.raise_for_status()
    entries = r.json()
    excel_items = [e for e in entries if e.get("type")=="file" and e.get("name","").lower().endswith((".xlsx",".xls"))]
    if not excel_items:
        raise FileNotFoundError("Aucun .xlsx trouvé dans ce dossier GitHub.")
    excel_items.sort(key=lambda e: (not e["name"].lower().endswith(".xlsx"), e["name"].lower()))
    raw = requests.get(excel_items[0]["download_url"], timeout=30); raw.raise_for_status()
    return raw.content

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    excel_url = normalize_excel_url(excel_url)
    if excel_url:
        if is_github_folder(excel_url):
            content = fetch_first_excel_from_folder(excel_url)
            return pd.read_excel(io.BytesIO(content))
        else:
            resp = requests.get(excel_url, timeout=20); resp.raise_for_status()
            return pd.read_excel(io.BytesIO(resp.content))
    if not os.path.exists(DEFAULT_LOCAL_PATH):
        st.stop()
    return pd.read_excel(DEFAULT_LOCAL_PATH)

# --------- Helpers ---------
def normalize_bool(val):
    if isinstance(val, str): return val.strip().lower() in ["oui","yes","true","1","vrai"]
    if isinstance(val, (int, float)):
        try: return int(val)==1
        except Exception: return False
    if isinstance(val, bool): return val
    return False

def sanitize_value(val):
    if val is None: return ""
    s = str(val).strip()
    return "" if s in ["/", "-", ""] else s

def make_checkbox_group(title: str, options: List[str], default_all: bool=False, key_prefix: str="", indent: bool=False) -> List[str]:
    st.write(title)
    sel = []
    with st.container():
        st.markdown('<div class="smbg-scroll{}">'.format(" smbg-indent" if indent else ""), unsafe_allow_html=True)
        for opt in options:
            checked = default_all
            v = st.checkbox(opt, value=checked, key=f"{key_prefix}_{opt}")
            if v: sel.append(opt)
        st.markdown('</div>', unsafe_allow_html=True)
    return sel

# --------- Sidebar filters with checkboxes ---------
def render_filters_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        st.markdown("### Filtres")

        # Scope to valid rows
        df = df.copy()
        # Région (checkbox list with mini scroll)
        regions = sorted([r for r in df["Région"].dropna().astype(str).unique() if r not in ["-","/",""]])
        sel_regions = make_checkbox_group("Région", regions, default_all=False, key_prefix="reg")
        df_scoped = df if not sel_regions else df[df["Région"].astype(str).isin(sel_regions)]

        # Département (dependent checkboxes, indented)
        deps = sorted([d for d in df_scoped["Département"].dropna().astype(str).unique() if d not in ["-","/",""]])
        sel_deps = make_checkbox_group("Département", deps, default_all=not sel_regions, key_prefix="dep", indent=True)
        if sel_deps:
            df_scoped = df_scoped[df_scoped["Département"].astype(str).isin(sel_deps)]

        # Typologie (checkboxes)
        typo_vals = sorted([t for t in df_scoped["Typologie"].dropna().astype(str).unique() if t not in ["-","/",""]])
        sel_typo = make_checkbox_group("Typologie d'actif", typo_vals, default_all=False, key_prefix="typo")
        if sel_typo:
            df_scoped = df_scoped[df_scoped["Typologie"].astype(str).isin(sel_typo)]

        # Extraction (checkboxes)
        extr_vals = ["oui","non","faisable"]
        sel_extr = make_checkbox_group("Extraction", extr_vals, default_all=False, key_prefix="extr")
        if sel_extr:
            extr_norm = df_scoped["Extraction"].astype(str).str.strip().str.lower().replace({"-":"","/":""})
            df_scoped = df_scoped[extr_norm.isin(sel_extr)]

        # Emplacement (checkboxes) — above Loyer
        empl_vals = [e for e in df_scoped["Emplacement"].dropna().astype(str).unique() if e not in ["-","/",""]]
        base_empl = ["Centre-ville","Périphérie"]
        options_empl = [e for e in base_empl if e in empl_vals] + [e for e in empl_vals if e not in base_empl]
        sel_empl = make_checkbox_group("Emplacement", options_empl, default_all=False, key_prefix="empl")
        if sel_empl:
            df_scoped = df_scoped[df_scoped["Emplacement"].astype(str).isin(sel_empl)]

        # Surface slider (restored)
        surf_series = pd.to_numeric(df_scoped.get("Surface GLA", pd.Series(dtype=float)), errors="coerce").dropna()
        if not surf_series.empty:
            smin, smax = int(surf_series.min()), int(surf_series.max())
            sel_surf = st.slider("Surface (m²)", min_value=smin, max_value=smax, value=(smin, smax), step=1)
            df_scoped = df_scoped[pd.to_numeric(df_scoped["Surface GLA"], errors="coerce").between(sel_surf[0], sel_surf[1])]

        # Loyer annuel slider
        loyer_series = pd.to_numeric(df_scoped.get("Loyer annuel", pd.Series(dtype=float)), errors="coerce").dropna()
        if not loyer_series.empty:
            lmin, lmax = int(loyer_series.min()), int(loyer_series.max())
            sel_loyer = st.slider("Loyer annuel (€)", min_value=lmin, max_value=lmax, value=(lmin, lmax), step=1000)
            df_scoped = df_scoped[pd.to_numeric(df_scoped["Loyer annuel"], errors="coerce").between(sel_loyer[0], sel_loyer[1])]

        # Restauration autorisée (oui/non) — keep as select for clarity or convert to checkbox?
        rest_vals = ["oui","non"]
        # As checkboxes for consistency
        sel_rest = make_checkbox_group("Restauration autorisée", rest_vals, default_all=False, key_prefix="rest")
        if sel_rest:
            rest_norm = df_scoped["Restauration"].astype(str).str.strip().str.lower()
            df_scoped = df_scoped[rest_norm.isin(sel_rest)]

        # Actions
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Réinitialiser filtres"):
                st.experimental_rerun()
        with c2:
            st.button("Je suis intéressé")

    return df_scoped

# --------- Map builder ---------
def build_map(df_valid: pd.DataFrame, ref_col: Optional[str] = "Référence annonce"):
    FR_LAT, FR_LON, FR_ZOOM = 46.603354, 1.888334, 6
    m = folium.Map(location=[FR_LAT, FR_LON], zoom_start=FR_ZOOM, tiles=None, control_scale=False, zoom_control=True)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
        name="OpenStreetMap.Mapnik",
        max_zoom=19, min_zoom=0, opacity=1.0
    ).add_to(m)

    group = folium.FeatureGroup(name="Annonces").add_to(m)
    css = "background:" + LOGO_BLUE + "; color:#fff; border:2px solid #fff; width:28px; height:28px; line-height:28px; border-radius:50%; text-align:center; font-size:11px; font-weight:600;"
    rc = ref_col if (ref_col and ref_col in df_valid.columns) else None

    for _, r in df_valid.iterrows():
        lat, lon = float(r["_lat"]), float(r["_lon"])
        ref_text = str(r[rc]) if rc else ""
        # Base circle marker (always visible)
        folium.CircleMarker(location=[lat, lon], radius=9, color="#ffffff", weight=2, fill=True, fill_color=LOGO_BLUE, fill_opacity=1.0).add_to(group)
        # Overlay DivIcon with reference (if any)
        if ref_text:
            html = '<div style="' + css + '">' + ref_text + '</div>'
            icon = folium.DivIcon(html=html)
            folium.Marker(location=[lat, lon], icon=icon).add_to(group)

    return m

# --------- Drawer (right overlay) ---------
def pictures(listing: pd.Series) -> List[str]:
    urls = []
    phcol = "Photos annonce"
    if phcol in listing and isinstance(listing[phcol], str):
        for u in str(listing[phcol]).split("|"):
            u = u.strip()
            if u:
                urls.append(u)
    return urls

def slice_g_to_ah(df: pd.DataFrame) -> List[str]:
    cols = list(df.columns)
    start_idx, end_idx = 6, 33  # G..AH
    return cols[start_idx:end_idx+1] if len(cols) > end_idx else cols[start_idx:]

def render_drawer(selected_row: pd.Series, open_state: bool = True):
    ref_val = str(selected_row.get("Référence annonce", ""))
    gm = selected_row.get("Lien Google Maps", "")
    display_cols = slice_g_to_ah(selected_row.to_frame().T)

    drawer_class = "smbg-drawer open" if open_state else "smbg-drawer"
    st.markdown('<div class="' + drawer_class + '">', unsafe_allow_html=True)
    st.markdown('<div class="smbg-banner">Référence : ' + ref_val + '</div>', unsafe_allow_html=True)
    st.markdown('<div class="smbg-body">', unsafe_allow_html=True)

    if isinstance(gm, str) and gm.strip():
        st.markdown('<a href="' + gm.strip() + '" target="_blank"><button class="stButton">Cliquer ici</button></a>', unsafe_allow_html=True)

    rec = selected_row
    for c in display_cols:
        if c == "Lien Google Maps":
            continue
        val = sanitize_value(rec.get(c))
        if not val:
            continue
        st.markdown('<div class="smbg-item"><div class="smbg-key">' + str(c) + '</div><div class="smbg-val">' + str(val) + '</div></div>', unsafe_allow_html=True)

    ph_urls = pictures(rec)
    if ph_urls:
        st.markdown("#### Photos")
        for u in ph_urls:
            st.markdown('<img class="smbg-photo" loading="lazy" src="' + u + '" />', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --------- Main ---------
def main():
    df = load_excel()
    if df is None or df.empty:
        st.warning("Excel vide ou introuvable.")
        st.stop()

    df["_actif"] = df.get("Actif", "oui").apply(normalize_bool)
    df["_lat"] = pd.to_numeric(df.get("Latitude", None), errors="coerce")
    df["_lon"] = pd.to_numeric(df.get("Longitude", None), errors="coerce")
    df = df[df["_actif"] & df["_lat"].notna() & df["_lon"].notna()].copy()
    if df.empty:
        st.warning("Aucune ligne active avec coordonnées valides.")
        st.stop()

    # Sidebar filters
    filtered = render_filters_sidebar(df)

    # Map (taller)
    ref_col = "Référence annonce" if "Référence annonce" in filtered.columns else None
    mapp = build_map(filtered, ref_col)
    st_html(mapp.get_root().render(), height=980, scrolling=False)

    # Drawer selector (temporary UI)
    ref_list = filtered["Référence annonce"].astype(str).tolist() if "Référence annonce" in filtered.columns else [f"#{i+1}" for i in range(len(filtered))]
    if ref_list:
        selected = st.selectbox("Sélection annonce (pour le volet droit)", ref_list, index=0, key="sel_ref")
        row = filtered[filtered["Référence annonce"].astype(str) == selected].iloc[0] if "Référence annonce" in filtered.columns else filtered.iloc[0]
        render_drawer(row, open_state=True)

if __name__ == "__main__":
    main()

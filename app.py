
import os
import io
import re
from typing import Optional, List
import pandas as pd
import streamlit as st
import requests
import folium
from streamlit.components.v1 import html as st_html

# ================== THEME ==================
st.set_page_config(page_title="SMBG Carte — Map", layout="wide")
LOGO_BLUE = "#05263d"
COPPER = "#7a5133"  # extracted or default

# Global CSS: fixed left filter pane (~275px), drawer on the right, brand colors
st.markdown(f"""
<style>
  :root {
    --smbg-blue: #05263d;
    --smbg-copper: #7a5133;
  }
  html, body {height:100%;}
  [data-testid="stAppViewContainer"]{padding:0; margin:0; min-height:100vh;}
  [data-testid="stMain"]{padding:0; margin:0;}
  .block-container{padding:0 !important; margin:0 !important;}
  header, footer {visibility:hidden; height:0;}

  /* 3-column layout: left (filters), center (map), right (drawer overlay) */
  .smbg-row { display: grid; grid-template-columns: 275px 1fr; gap: 0; }
  .smbg-left {
    background: var(--smbg-blue);
    color: var(--smbg-copper);
    padding: 14px 14px 18px 14px;
    height: calc(100vh - 2px);
    overflow: auto;
    border-right: 1px solid rgba(255,255,255,0.08);
  }
  .smbg-left h3, .smbg-left label, .smbg-left .stMarkdown p { color: var(--smbg-copper) !important; }
  .smbg-btn {
    background: var(--smbg-copper); color: #fff; border: none; border-radius: 10px;
    padding: 8px 12px; font-weight: 700; cursor: pointer;
  }
  .smbg-btn.secondary { background: transparent; color: var(--smbg-copper); border: 1px solid var(--smbg-copper); }
  .smbg-section { margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px dashed rgba(255,255,255,0.15);}

  /* Streamlit inputs inside left panel */
  .smbg-left .stSelectbox div[data-baseweb="select"] > div { background: rgba(255,255,255,0.06); color: #fff; }
  .smbg-left .stMultiSelect div[data-baseweb="select"] > div { background: rgba(255,255,255,0.06); color: #fff; }
  .smbg-left .stSlider > div { color: var(--smbg-copper); }
  .smbg-left .stButton > button { background: var(--smbg-copper); color: #fff; border: none; border-radius: 10px; }
  .smbg-left .stButton > button:hover { filter: brightness(0.92); }

  /* Right drawer */
  .smbg-drawer {
    position: fixed; top: 0; right: 0; width: 420px; max-width: 96vw;
    height: 100vh; background: #fff; transform: translateX(100%);
    transition: transform 240ms ease; box-shadow: -14px 0 28px rgba(0,0,0,0.12);
    border-left: 1px solid #e9eaee; z-index: 9999; overflow: auto;
  }
  .smbg-drawer.open { transform: translateX(0); }
  .smbg-banner {
    background: var(--smbg-blue); color: #fff; padding: 12px 16px; font-weight: 800; font-size: 18px;
  }
  .smbg-body { padding: 14px 16px 24px 16px; }
  .smbg-badge{background:#eeefe9; border:1px solid #d9d7cf; color:#333; padding:2px 8px; border-radius:10px; font-size:12px;}
  .smbg-item{display:flex; gap:8px; align-items:flex-start; margin-bottom:6px;}
  .smbg-key{min-width:180px; color:#4b5563; font-weight:600;}
  .smbg-val{color:#111827;}
  .smbg-photo{width:100%; height:auto; border-radius:12px; display:block; margin-bottom:12px; box-shadow:0 4px 12px rgba(0,0,0,0.08);}
  .smbg-map { height: calc(100vh - 0px); overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ================== DATA LOADING ==================
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

# ================== HELPERS ==================
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

# ================== FILTER LOGIC ==================
def build_filters(df: pd.DataFrame):
    df = df.copy()
    df["_actif"] = df.get("Actif", "oui").apply(normalize_bool)
    df["_lat"] = pd.to_numeric(df.get("Latitude", None), errors="coerce")
    df["_lon"] = pd.to_numeric(df.get("Longitude", None), errors="coerce")
    df = df[df["_actif"] & df["_lat"].notna() & df["_lon"].notna()]

    st.markdown('<div class="smbg-row">', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="smbg-left">', unsafe_allow_html=True)
        st.markdown("### Filtres")

        regions = sorted([r for r in df["Région"].dropna().astype(str).unique() if r not in ["-", "/",""]])
        sel_region = st.selectbox("Région", ["(Toutes)"] + regions, index=0)
        df_region = df if sel_region == "(Toutes)" else df[df["Région"].astype(str) == sel_region]

        deps = sorted([d for d in df_region["Département"].dropna().astype(str).unique() if d not in ["-","/",""]])
        sel_dep = st.selectbox("Département", ["(Tous)"] + deps, index=0)

        typo_vals = sorted([t for t in df_region["Typologie"].dropna().astype(str).unique() if t not in ["-","/",""]])
        sel_typo = st.multiselect("Typologie d'actif", options=typo_vals, default=[])

        extr_vals = ["oui","non","faisable"]
        extr_col = df_region["Extraction"].astype(str).str.strip().str.lower().replace({"-":"","/":""})
        sel_extr = st.multiselect("Extraction", options=extr_vals, default=[])

        surf_series = pd.to_numeric(df_region.get("Surface GLA", pd.Series(dtype=float)), errors="coerce").dropna()
        if not surf_series.empty:
            smin, smax = int(surf_series.min()), int(surf_series.max())
            sel_surf = st.slider("Surface (m²)", min_value=smin, max_value=smax, value=(smin, smax), step=1)
        else:
            sel_surf = (0, 10**9)

        loyer_series = pd.to_numeric(df_region.get("Loyer annuel", pd.Series(dtype=float)), errors="coerce").dropna()
        if not loyer_series.empty:
            lmin, lmax = int(loyer_series.min()), int(loyer_series.max())
            sel_loyer = st.slider("Loyer annuel (€)", min_value=lmin, max_value=lmax, value=(lmin, lmax), step=1000)
        else:
            sel_loyer = (0, 10**12)

        rest_vals = ["oui","non"]
        sel_rest = st.selectbox("Restauration autorisée", ["(Toutes)"] + rest_vals, index=0)

        empl_vals = [e for e in df_region["Emplacement"].dropna().astype(str).unique() if e not in ["-","/",""]]
        base_empl = ["Centre-ville","Périphérie"]
        options_empl = [e for e in base_empl if e in empl_vals] + [e for e in empl_vals if e not in base_empl]
        sel_empl = st.selectbox("Emplacement", ["(Tous)"] + options_empl, index=0)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Réinitialiser filtres"):
                st.experimental_rerun()
        with c2:
            st.button("Je suis intéressé")

        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    filtered = df_region.copy()
    if sel_dep != "(Tous)":
        filtered = filtered[filtered["Département"].astype(str) == sel_dep]
    if sel_typo:
        filtered = filtered[filtered["Typologie"].astype(str).isin(sel_typo)]
    if sel_extr:
        filtered = filtered[extr_col.isin(sel_extr)]
    filtered = filtered[pd.to_numeric(filtered["Surface GLA"], errors="coerce").between(sel_surf[0], sel_surf[1])]
    filtered = filtered[pd.to_numeric(filtered["Loyer annuel"], errors="coerce").between(sel_loyer[0], sel_loyer[1])]
    if sel_rest != "(Toutes)":
        filtered = filtered[filtered["Restauration"].astype(str).str.lower() == sel_rest]
    if sel_empl != "(Tous)":
        filtered = filtered[filtered["Emplacement"].astype(str) == sel_empl]

    return filtered

# ================== MAP (Folium) ==================
def build_map(df_valid: pd.DataFrame, ref_col: Optional[str]):
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

    ref_col = ref_col or "Référence annonce"
    for _, r in df_valid.iterrows():
        lat, lon = float(r["_lat"]), float(r["_lon"])
        ref_text = str(r.get(ref_col, ""))
        html = f'<div style="{css}">{ref_text}</div>'
        icon = folium.DivIcon(html=html)
        folium.Marker(location=[lat, lon], icon=icon).add_to(group)
    return m

# ================== RIGHT DRAWER ==================
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
    start_idx, end_idx = 6, 33  # G..AH (1-based -> 0-based)
    return cols[start_idx:end_idx+1] if len(cols) > end_idx else cols[start_idx:]

def render_drawer(selected_row: pd.Series, open_state: bool = True):
    ref_val = str(selected_row.get("Référence annonce", ""))
    gm = selected_row.get("Lien Google Maps", "")
    display_cols = slice_g_to_ah(selected_row.to_frame().T)

    drawer_class = "smbg-drawer open" if open_state else "smbg-drawer"
    st.markdown(f'<div class="{drawer_class}">', unsafe_allow_html=True)
    st.markdown(f'<div class="smbg-banner">Référence : {ref_val}</div>', unsafe_allow_html=True)
    st.markdown('<div class="smbg-body">', unsafe_allow_html=True)

    if isinstance(gm, str) and gm.strip():
        st.markdown(f'<a href="{gm.strip()}" target="_blank"><button class="smbg-btn">Cliquer ici</button></a>', unsafe_allow_html=True)

    rec = selected_row
    for c in display_cols:
        if c in ["Lien Google Maps"]:
            continue
        val = sanitize_value(rec.get(c))
        if not val:
            continue
        st.markdown(f'<div class="smbg-item"><div class="smbg-key">{c}</div><div class="smbg-val">{val}</div></div>', unsafe_allow_html=True)

    ph_urls = pictures(rec)
    if ph_urls:
        st.markdown("#### Photos")
        for u in ph_urls:
            st.markdown(f'<img class="smbg-photo" loading="lazy" src="{u}" />', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ================== MAIN ==================
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

    filtered = build_filters(df)

    with st.container():
        st.markdown('<div class="smbg-map">', unsafe_allow_html=True)
        ref_col = "Référence annonce" if "Référence annonce" in filtered.columns else None
        mapp = build_map(filtered, ref_col)
        st_html(mapp.get_root().render(), height=900, scrolling=False)
        st.markdown('</div>', unsafe_allow_html=True)

    ref_list = filtered["Référence annonce"].astype(str).tolist() if "Référence annonce" in filtered.columns else [f"#{i+1}" for i in range(len(filtered))]
    if not ref_list:
        return
    default_idx = 0
    selected = st.selectbox("Sélection annonce (pour le volet droit)", ref_list, index=default_idx, key="sel_ref")
    row = filtered[filtered["Référence annonce"].astype(str) == selected].iloc[0] if "Référence annonce" in filtered.columns else filtered.iloc[default_idx]

    render_drawer(row, open_state=True)

if __name__ == "__main__":
    main()

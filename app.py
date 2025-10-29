
import os
import io
import re
from typing import Optional, List
import pandas as pd
import streamlit as st
import requests
import folium
from streamlit.components.v1 import html as st_html

st.set_page_config(page_title="SMBG Carte — Map", layout="wide")
LOGO_BLUE = "#05263d"
COPPER = "#c47e47"

# --------- CSS: fixed overlays ---------
_CSS = """
<style>
  :root { --smbg-blue: __BLUE__; --smbg-copper: __COPPER__; }
  [data-testid="stAppViewContainer"] { padding: 0; }
  header, footer { visibility: hidden; height: 0; }

  /* Fixed left panel */
  .smbg-left-fixed {
    position: fixed; left: 0; top: 0; width: 275px; height: 100vh;
    background: var(--smbg-blue); color: var(--smbg-copper);
    padding: 14px; border-right: 1px solid rgba(255,255,255,0.08);
    overflow-y: auto; z-index: 1000;
  }
  .smbg-left-fixed h3, .smbg-left-fixed label, .smbg-left-fixed p { color: var(--smbg-copper) !important; }
  .smbg-left-fixed .smbg-scroll { max-height: 180px; overflow-y: auto; padding: 6px 8px; background: rgba(255,255,255,0.06); border-radius: 8px; }
  .smbg-left-fixed .smbg-indent { padding-left: 12px; }
  .smbg-left-fixed .stButton > button { background: var(--smbg-copper) !important; color: #fff !important; font-weight: 700; border-radius: 10px; border: none; }

  /* Main content shifted to the right of fixed panel */
  .smbg-content { padding-left: 275px; width: calc(100vw - 275px); }

  /* Right drawer overlay */
  .smbg-drawer {
    position: fixed; top: 0; right: 0; width: 275px; max-width: 96vw;
    height: 100vh; background: #fff; transform: translateX(100%);
    transition: transform 240ms ease; box-shadow: -14px 0 28px rgba(0,0,0,0.12);
    border-left: 1px solid #e9eaee; z-index: 1100; overflow-y: auto;
  }
  .smbg-drawer.open { transform: translateX(0); }
  .smbg-banner { background: var(--smbg-blue); color: #fff; padding: 12px 16px; font-weight: 800; font-size: 18px; position: sticky; top:0; }
  .smbg-body { padding: 14px 16px 24px 16px; }
  .smbg-item{display:flex; gap:8px; align-items:flex-start; margin-bottom:6px;}
  .smbg-key{min-width:140px; color:#4b5563; font-weight:600;}
  .smbg-val{color:#111827;}
  .smbg-photo{width:100%; height:auto; border-radius:12px; display:block; margin-bottom:12px; box-shadow:0 4px 12px rgba(0,0,0,0.08);}
  .smbg-close{ position:absolute; right:10px; top:8px; background:transparent; border:none; font-size:20px; color:#fff; cursor:pointer;}
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

def checkbox_group(title: str, options: List[str], key_prefix: str, indent: bool=False) -> List[str]:
    st.markdown(f"**{title}**")
    selected = []
    st.markdown('<div class="smbg-scroll{}">'.format(" smbg-indent" if indent else ""), unsafe_allow_html=True)
    for opt in options:
        if st.checkbox(opt, key=f"{key_prefix}_{opt}"):
            selected.append(opt)
    st.markdown("</div>", unsafe_allow_html=True)
    return selected

# --------- Left Filters (fixed) ---------
def render_left_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.markdown('<div class="smbg-left-fixed">', unsafe_allow_html=True)
    st.markdown("### Filtres")

    scoped = df.copy()

    # Région
    regions = sorted([r for r in scoped["Région"].dropna().astype(str).unique() if r not in ["-","/",""]])
    sel_regions = checkbox_group("Région", regions, key_prefix="reg")

    # Département (only if region selected)
    if sel_regions:
        scoped = scoped[scoped["Région"].astype(str).isin(sel_regions)]
        deps = sorted([d for d in scoped["Département"].dropna().astype(str).unique() if d not in ["-","/",""]])
        sel_deps = checkbox_group("Département", deps, key_prefix="dep", indent=True)
        if sel_deps:
            scoped = scoped[scoped["Département"].astype(str).isin(sel_deps)]

    # Typologie
    typologies = sorted([t for t in scoped["Typologie"].dropna().astype(str).unique() if t not in ["-","/",""]])
    sel_typo = checkbox_group("Typologie d'actif", typologies, key_prefix="typo")
    if sel_typo:
        scoped = scoped[scoped["Typologie"].astype(str).isin(sel_typo)]

    # Extraction
    extr_vals = ["oui","non","faisable"]
    sel_extr = checkbox_group("Extraction", extr_vals, key_prefix="extr")
    if sel_extr:
        en = scoped["Extraction"].astype(str).str.strip().str.lower().replace({"-":"","/":""})
        scoped = scoped[en.isin(sel_extr)]

    # Emplacement (above loyer)
    empl_vals = [e for e in scoped["Emplacement"].dropna().astype(str).unique() if e not in ["-","/",""]]
    base_empl = ["Centre-ville","Périphérie"]
    options_empl = [e for e in base_empl if e in empl_vals] + [e for e in empl_vals if e not in base_empl]
    sel_empl = checkbox_group("Emplacement", options_empl, key_prefix="empl")
    if sel_empl:
        scoped = scoped[scoped["Emplacement"].astype(str).isin(sel_empl)]

    # Surface slider
    surf_series = pd.to_numeric(scoped.get("Surface GLA", pd.Series(dtype=float)), errors="coerce").dropna()
    if not surf_series.empty:
        smin, smax = int(surf_series.min()), int(surf_series.max())
        sel_surf = st.slider("Surface (m²)", min_value=smin, max_value=smax, value=(smin, smax), step=1, key="surf")
        scoped = scoped[pd.to_numeric(scoped["Surface GLA"], errors="coerce").between(sel_surf[0], sel_surf[1])]

    # Loyer slider
    loyer_series = pd.to_numeric(scoped.get("Loyer annuel", pd.Series(dtype=float)), errors="coerce").dropna()
    if not loyer_series.empty:
        lmin, lmax = int(loyer_series.min()), int(loyer_series.max())
        sel_loyer = st.slider("Loyer annuel (€)", min_value=lmin, max_value=lmax, value=(lmin, lmax), step=1000, key="loyer")
        scoped = scoped[pd.to_numeric(scoped["Loyer annuel"], errors="coerce").between(sel_loyer[0], sel_loyer[1])]

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Réinitialiser"):
            st.experimental_rerun()
    with c2:
        st.button("Je suis intéressé")

    st.markdown('</div>', unsafe_allow_html=True)  # end fixed left
    return scoped

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
        href = "?ref=" + ref_text
        html = '<a href="' + href + '" target="_top" style="text-decoration:none;"><div style="' + css + '">' + ref_text + '</div></a>'
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
    st.markdown('<div class="smbg-banner">Référence : ' + ref_val + '<button class="smbg-close" onclick="window.location.search='';return false;">×</button></div>', unsafe_allow_html=True)
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

    # Render fixed left filters
    filtered = render_left_filters(df)

    # Content wrapper for map
    st.markdown('<div class="smbg-content">', unsafe_allow_html=True)
    ref_col = "Référence annonce" if "Référence annonce" in filtered.columns else None
    mapp = build_map(filtered, ref_col)
    html_map = mapp.get_root().render().replace("height: 100.0%;", "height: 100vh;")
    st_html(html_map, height=900, scrolling=False)
    st.markdown('</div>', unsafe_allow_html=True)

    # Open drawer if ?ref present
    ref_value = None
    try:
        params = st.query_params
        ref_value = params.get("ref", None)
    except Exception:
        qp = st.experimental_get_query_params()
        if isinstance(qp, dict):
            rv = qp.get("ref", None)
            ref_value = rv[0] if isinstance(rv, list) and rv else rv

    if ref_value and "Référence annonce" in filtered.columns:
        subset = filtered[filtered["Référence annonce"].astype(str) == str(ref_value)]
        if not subset.empty:
            row = subset.iloc[0]
            render_drawer(row, open_state=True)

if __name__ == "__main__":
    main()

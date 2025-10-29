
import os
import io
import re
from typing import List
import pandas as pd
import streamlit as st
import requests
import folium
from streamlit.components.v1 import html as st_html

st.set_page_config(page_title="SMBG Carte — Leaflet (Mapnik)", layout="wide")
LOGO_BLUE = "#05263d"
COPPER = "#c47e47"

CSS = f"""
<style>
  [data-testid="collapsedControl"] {{ display: none !important; }}
  [data-testid="stSidebar"] {{
    width: 275px; min-width: 275px; max-width: 275px;
    background: {LOGO_BLUE}; color: {COPPER};
  }}
  [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
  [data-testid="stSidebar"] p, [data-testid="stSidebar"] label {{ color: {COPPER} !important; }}
  [data-testid="stSidebar"] .smbg-scroll {{ max-height: 180px; overflow-y: auto; padding: 6px 8px; background: rgba(255,255,255,0.06); border-radius: 8px; }}
  [data-testid="stSidebar"] .smbg-indent {{ padding-left: 12px; }}
  [data-testid="stSidebar"] .stButton > button {{ background: {COPPER} !important; color: #fff !important; font-weight: 700; border-radius: 10px; border: none; }}

  [data-testid="stAppViewContainer"] {{ padding-top: 0; padding-bottom: 0; }}
  .block-container {{ padding-top: 8px !important; padding-left: 0 !important; padding-right: 0 !important; }}

  .drawer {{
    position: fixed; top: 0; right: 0; width: 275px; max-width: 96vw;
    height: 100vh; background: #fff; transform: translateX(100%);
    transition: transform 240ms ease; box-shadow: -14px 0 28px rgba(0,0,0,0.12);
    border-left: 1px solid #e9eaee; z-index: 9999; overflow-y: auto;
  }}
  .drawer.open {{ transform: translateX(0); }}
  .drawer-banner {{ background: {LOGO_BLUE}; color: #fff; padding: 12px 16px; font-weight: 800; font-size: 18px; position: sticky; top:0; }}
  .drawer-body {{ padding: 14px 16px 24px 16px; }}
  .kv {{ display:flex; gap:8px; align-items:flex-start; margin-bottom:6px; }}
  .kv .k {{ min-width:140px; color:#4b5563; font-weight:600; }}
  .kv .v {{ color:#111827; }}
  .photo {{ width:100%; height:auto; border-radius:12px; display:block; margin-bottom:12px; box-shadow:0 4px 12px rgba(0,0,0,0.08); }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"

def normalize_excel_url(url: str) -> str:
    if not url:
        return url
    url = url.strip()
    return re.sub(r"https://github\.com/(.+)/blob/([^ ]+)", r"https://github.com/\1/raw/\2", url)

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    excel_url = normalize_excel_url(excel_url)
    if excel_url:
        r = requests.get(excel_url, timeout=25); r.raise_for_status()
        return pd.read_excel(io.BytesIO(r.content))
    if not os.path.exists(DEFAULT_LOCAL_PATH):
        st.stop()
    return pd.read_excel(DEFAULT_LOCAL_PATH)

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

def pictures(listing: pd.Series) -> List[str]:
    urls = []
    for col in ["Photos annonce", "Photos"]:
        if col in listing and isinstance(listing[col], str):
            for u in str(listing[col]).split("|"):
                u = u.strip()
                if u: urls.append(u)
            break
    return urls

def slice_g_to_ah(df: pd.DataFrame) -> List[str]:
    cols = list(df.columns)
    start_idx, end_idx = 6, 33  # G..AH
    return cols[start_idx:end_idx+1] if len(cols) > end_idx else cols[start_idx:]

def render_drawer(row: pd.Series):
    ref_val = str(row.get("Référence annonce", ""))
    gm = row.get("Lien Google Maps", row.get("Google Maps", ""))
    display_cols = slice_g_to_ah(row.to_frame().T)

    st.markdown('<div class="drawer open">', unsafe_allow_html=True)
    st.markdown(f'<div class="drawer-banner">Référence : {ref_val}</div>', unsafe_allow_html=True)
    st.markdown('<div class="drawer-body">', unsafe_allow_html=True)

    if isinstance(gm, str) and gm.strip():
        st.markdown(f'<a href="{gm.strip()}" target="_blank"><button class="stButton">Cliquer ici</button></a>', unsafe_allow_html=True)

    for c in display_cols:
        if c in ["Lien Google Maps", "Google Maps"]: continue
        val = sanitize_value(row.get(c))
        if not val: continue
        st.markdown(f'<div class="kv"><div class="k">{c}</div><div class="v">{val}</div></div>', unsafe_allow_html=True)

    for u in pictures(row):
        st.markdown(f'<img class="photo" loading="lazy" src="{u}" />', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)

def main():
    df = load_excel()
    if df is None or df.empty:
        st.warning("Excel vide ou introuvable."); st.stop()

    df["_actif"] = df.get("Actif", "oui").apply(normalize_bool)
    df["_lat"]  = pd.to_numeric(df.get("Latitude", None), errors="coerce")
    df["_lon"]  = pd.to_numeric(df.get("Longitude", None), errors="coerce")
    df = df[df["_actif"] & df["_lat"].notna() & df["_lon"].notna()].copy()
    if df.empty:
        st.warning("Aucune ligne active avec coordonnées valides."); st.stop()

    with st.sidebar:
        st.markdown("### Filtres")

        scoped = df.copy()

        if "Région" in scoped.columns:
            regions = sorted([r for r in scoped["Région"].dropna().astype(str).unique() if r not in ["-","/",""]])
            sel_regions = checkbox_group("Région", regions, key_prefix="reg")
        else:
            sel_regions = []

        if sel_regions:
            scoped = scoped[scoped["Région"].astype(str).isin(sel_regions)]
            if "Département" in scoped.columns:
                deps = sorted([d for d in scoped["Département"].dropna().astype(str).unique() if d not in ["-","/",""]])
                sel_deps = checkbox_group("Département", deps, key_prefix="dep", indent=True)
                if sel_deps:
                    scoped = scoped[scoped["Département"].astype(str).isin(sel_deps)]

        if "Typologie" in scoped.columns:
            typos = sorted([t for t in scoped["Typologie"].dropna().astype(str).unique() if t not in ["-","/",""]])
            sel_typos = checkbox_group("Typologie d'actif", typos, key_prefix="typo")
            if sel_typos:
                scoped = scoped[scoped["Typologie"].astype(str).isin(sel_typos)]

        if "Extraction" in scoped.columns:
            sel_extr = checkbox_group("Extraction", ["oui","non","faisable"], key_prefix="extr")
            if sel_extr:
                en = scoped["Extraction"].astype(str).str.strip().str.lower().replace({"-":"","/":""})
                scoped = scoped[en.isin(sel_extr)]

        if "Emplacement" in scoped.columns:
            emplacements = [e for e in scoped["Emplacement"].dropna().astype(str).unique() if e not in ["-","/",""]]
            base = ["Centre-ville", "Périphérie"]
            options_empl = [e for e in base if e in emplacements] + [e for e in emplacements if e not in base]
            sel_empl = checkbox_group("Emplacement", options_empl, key_prefix="empl")
            if sel_empl:
                scoped = scoped[scoped["Emplacement"].astype(str).isin(sel_empl)]

        if "Surface GLA" in scoped.columns:
            surf_series = pd.to_numeric(scoped.get("Surface GLA"), errors="coerce").dropna()
            if not surf_series.empty:
                smin, smax = int(surf_series.min()), int(surf_series.max())
                sel_surf = st.slider("Surface (m²)", min_value=smin, max_value=smax, value=(smin, smax), step=1, key="surf")
                scoped = scoped[pd.to_numeric(scoped["Surface GLA"], errors="coerce").between(sel_surf[0], sel_surf[1])]

        if "Loyer annuel" in scoped.columns:
            loyer_series = pd.to_numeric(scoped.get("Loyer annuel"), errors="coerce").dropna()
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

    FR_LAT, FR_LON, FR_ZOOM = 46.603354, 1.888334, 6
    m = folium.Map(location=[FR_LAT, FR_LON], zoom_start=FR_ZOOM, tiles=None, control_scale=False, zoom_control=True)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
        name="OpenStreetMap.Mapnik",
        max_zoom=19, min_zoom=0, opacity=1.0
    ).add_to(m)

    css = f"background:{LOGO_BLUE}; color:#fff; border:2px solid #fff; width:28px; height:28px; line-height:28px; border-radius:50%; text-align:center; font-size:11px; font-weight:600;"
    group = folium.FeatureGroup(name="Annonces").add_to(m)

    ref_col = "Référence annonce" if "Référence annonce" in scoped.columns else None

    for _, r in scoped.iterrows():
        lat, lon = float(r["_lat"]), float(r["_lon"])
        ref_text = str(r[ref_col]) if ref_col else ""
        html = f'<a href="?ref={ref_text}" target="_top" style="text-decoration:none;"><div style="{css}">{ref_text}</div></a>'
        icon = folium.DivIcon(html=html)
        folium.Marker(location=[lat, lon], icon=icon).add_to(group)

    st_html(m.get_root().render(), height=980, scrolling=False)

    ref_value = None
    try:
        params = st.query_params
        ref_value = params.get("ref", None)
    except Exception:
        qp = st.experimental_get_query_params()
        rv = qp.get("ref") if isinstance(qp, dict) else None
        ref_value = rv[0] if isinstance(rv, list) and rv else rv

    if ref_value and "Référence annonce" in scoped.columns:
        rowset = scoped[scoped["Référence annonce"].astype(str) == str(ref_value)]
        if not rowset.empty:
            render_drawer(rowset.iloc[0])

if __name__ == "__main__":
    main()

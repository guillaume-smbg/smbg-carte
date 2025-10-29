
import os, io, re
from typing import List, Dict
import pandas as pd
import streamlit as st
import folium
import requests
from streamlit_folium import st_folium

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
  [data-testid="stSidebar"] .group-title {{ margin: 8px 0 4px 0; font-weight: 700; color: {COPPER}; }}
  [data-testid="stSidebar"] .smbg-scroll {{ max-height: 190px; overflow-y: auto; padding: 6px 8px; background: rgba(255,255,255,0.06); border-radius: 8px; }}
  [data-testid="stSidebar"] .smbg-indent {{ padding-left: 18px; }}
  [data-testid="stSidebar"] .stButton > button {{ background: {COPPER} !important; color: #fff !important; font-weight: 700; border-radius: 10px; border: none; }}

  [data-testid="stAppViewContainer"] {{ padding-top: 0; padding-bottom: 0; }}
  .block-container {{ padding-top: 8px !important; padding-left: 0 !important; padding-right: 0 !important; }}

  .drawer {{ position: fixed; top:0; right:0; width:275px; height:100vh; background:#fff;
             transform: translateX(100%); transition: transform .24s ease; z-index: 9999;
             border-left: 1px solid #e9eaee; box-shadow: -14px 0 28px rgba(0,0,0,.12); overflow-y:auto; }}
  .drawer.open {{ transform: translateX(0); }}
  .drawer-banner {{ background:{LOGO_BLUE}; color:#fff; padding:12px 16px; font-weight:800; font-size:18px; position:sticky; top:0; }}
  .drawer-body {{ padding:14px 16px 24px 16px; }}
  .kv {{ display:flex; gap:8px; align-items:flex-start; margin-bottom:6px; }}
  .kv .k {{ min-width:140px; color:#4b5563; font-weight:600; }}
  .kv .v {{ color:#111827; }}

  /* Hide Leaflet popups visually (we still use them to capture clicks) */
  .leaflet-popup-pane, .leaflet-popup {{ display: none !important; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"

def normalize_excel_url(url: str) -> str:
    if not url: return url
    return re.sub(r"https://github\.com/(.+)/blob/([^ ]+)", r"https://github.com/\1/raw/\2", url.strip())

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

def sanitize_value(v):
    if v is None: return ""
    s = str(v).strip()
    return "" if s in ["", "-", "/"] else s

def drawer(row: pd.Series):
    ref_val = str(row.get("Référence annonce", ""))
    gm = row.get("Lien Google Maps", row.get("Google Maps", ""))

    cols = list(row.index)
    start_idx, end_idx = 6, 33
    display_cols = cols[start_idx:end_idx+1] if len(cols) > end_idx else cols[start_idx:]

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

    st.markdown('</div></div>', unsafe_allow_html=True)

def region_department_nested(df: pd.DataFrame) -> Dict[str, List[str]]:
    sel_regions: List[str] = []
    sel_deps: List[str] = []
    st.markdown("**Région**")
    st.markdown('<div class="smbg-scroll">', unsafe_allow_html=True)
    regions = sorted([r for r in df["Région"].dropna().astype(str).unique() if r not in ["-","/"]])
    for reg in regions:
        if st.checkbox(reg, key=f"reg_{reg}"):
            sel_regions.append(reg)
            deps = sorted([d for d in df[df["Région"].astype(str)==reg]["Département"].dropna().astype(str).unique() if d not in ["-","/"]])
            if deps:
                st.markdown('<div class="smbg-indent">', unsafe_allow_html=True)
                for dep in deps:
                    # visual indent via label prefix ensures clear hierarchy; unique key keeps state
                    st.checkbox(f"  {dep}", key=f"dep_{reg}_{dep}")
                    if st.session_state.get(f"dep_{reg}_{dep}"):
                        sel_deps.append(dep)
                st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    return {"regions": sel_regions, "departements": sel_deps}

def main():
    df = load_excel()
    if df is None or df.empty:
        st.warning("Excel vide ou introuvable."); st.stop()

    df["_actif"] = df.get("Actif", "oui").apply(normalize_bool)
    df["_lat"] = pd.to_numeric(df.get("Latitude", None), errors="coerce")
    df["_lon"] = pd.to_numeric(df.get("Longitude", None), errors="coerce")
    df = df[df["_actif"] & df["_lat"].notna() & df["_lon"].notna()].copy()
    if df.empty:
        st.warning("Aucune ligne active avec coordonnées valides."); st.stop()

    # Sidebar filters
    with st.sidebar:
        st.markdown("### Filtres")
        working = df.copy()

        # Nested Region -> Department
        if "Région" in working.columns and "Département" in working.columns:
            sel = region_department_nested(working)
            if sel["regions"]:
                working = working[working["Région"].astype(str).isin(sel["regions"])]
            if sel["departements"]:
                working = working[working["Département"].astype(str).isin(sel["departements"])]

        # Typologie
        if "Typologie" in working.columns:
            st.markdown("<div class='group-title'>Typologie d'actif</div>", unsafe_allow_html=True)
            st.markdown('<div class="smbg-scroll">', unsafe_allow_html=True)
            typos = sorted([t for t in working["Typologie"].dropna().astype(str).unique() if t not in ["-","/",""]])
            chosen_typos = []
            for t in typos:
                if st.checkbox(t, key=f"typo_{t}"):
                    chosen_typos.append(t)
            st.markdown("</div>", unsafe_allow_html=True)
            if chosen_typos:
                working = working[working["Typologie"].astype(str).isin(chosen_typos)]

        # Extraction
        if "Extraction" in working.columns:
            st.markdown("<div class='group-title'>Extraction</div>", unsafe_allow_html=True)
            st.markdown('<div class="smbg-scroll">', unsafe_allow_html=True)
            extr_sel = []
            for e in ["oui","non","faisable"]:
                if st.checkbox(e, key=f"extr_{e}"):
                    extr_sel.append(e)
            st.markdown("</div>", unsafe_allow_html=True)
            if extr_sel:
                en = working["Extraction"].astype(str).str.strip().str.lower().replace({"-":"","/":""})
                working = working[en.isin(extr_sel)]

        # Emplacement
        if "Emplacement" in working.columns:
            st.markdown("<div class='group-title'>Emplacement</div>", unsafe_allow_html=True)
            st.markdown('<div class="smbg-scroll">', unsafe_allow_html=True)
            vals = [e for e in working["Emplacement"].dropna().astype(str).unique() if e not in ["-","/",""]]
            base = ["Centre-ville","Périphérie"]
            options = [e for e in base if e in vals] + [e for e in vals if e not in base]
            em_sel = []
            for e in options:
                if st.checkbox(e, key=f"empl_{e}"):
                    em_sel.append(e)
            st.markdown("</div>", unsafe_allow_html=True)
            if em_sel:
                working = working[working["Emplacement"].astype(str).isin(em_sel)]

        # Surface slider
        if "Surface GLA" in working.columns:
            series = pd.to_numeric(working["Surface GLA"], errors="coerce").dropna()
            if not series.empty:
                vmin, vmax = int(series.min()), int(series.max())
                if vmin == vmax:
                    st.number_input("Surface (m²)", value=vmin, step=1, disabled=True, key="surf_single")
                else:
                    rang = st.slider("Surface (m²)", min_value=vmin, max_value=vmax, value=(vmin, vmax), step=1, key="surf_range")
                    working = working[pd.to_numeric(working["Surface GLA"], errors="coerce").between(rang[0], rang[1])]

        # Loyer slider (robust to min==max)
        if "Loyer annuel" in working.columns:
            series = pd.to_numeric(working["Loyer annuel"], errors="coerce").dropna()
            if not series.empty:
                vmin, vmax = int(series.min()), int(series.max())
                if vmin == vmax:
                    st.number_input("Loyer annuel (€)", value=vmin, step=1, disabled=True, key="loyer_single_readonly")
                else:
                    rang = st.slider("Loyer annuel (€)", min_value=vmin, max_value=vmax, value=(vmin, vmax), step=1000, key="loyer_range")
                    working = working[pd.to_numeric(working["Loyer annuel"], errors="coerce").between(rang[0], rang[1])]

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Réinitialiser"):
                st.experimental_rerun()
        with c2:
            st.button("Je suis intéressé")

    # Map
    data = working.copy()
    if data.empty:
        st.info("Aucun résultat pour ces filtres.")
        return

    FR_LAT, FR_LON, FR_ZOOM = 46.603354, 1.888334, 6
    m = folium.Map(location=[FR_LAT, FR_LON], zoom_start=FR_ZOOM, tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attr="© OpenStreetMap contributors")
    css = f"background:{LOGO_BLUE}; color:#fff; border:2px solid #fff; width:28px; height:28px; line-height:28px; border-radius:50%; text-align:center; font-size:11px; font-weight:600;"
    group = folium.FeatureGroup(name="Annonces").add_to(m)

    for _, r in data.iterrows():
        lat, lon = float(r["_lat"]), float(r["_lon"])
        ref_text = str(r.get("Référence annonce", ""))
        icon = folium.DivIcon(html=f'<div style="{css}">{ref_text}</div>')
        popup = folium.Popup(ref_text, max_width=1, show=False)
        folium.Marker(location=[lat, lon], icon=icon, popup=popup).add_to(group)

    out = st_folium(m, height=950, width=None, returned_objects=[])

    ref_clicked = None
    if isinstance(out, dict):
        ref_clicked = out.get("last_object_clicked_popup")

    if ref_clicked and "Référence annonce" in data.columns:
        row = data[data["Référence annonce"].astype(str) == str(ref_clicked)]
        if not row.empty:
            drawer(row.iloc[0])

if __name__ == "__main__":
    main()

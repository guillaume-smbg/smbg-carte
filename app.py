
import os, io, re, unicodedata, math
from typing import List, Dict, Tuple, Optional
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
  [data-testid="stSidebar"] .stButton > button,
  [data-testid="stSidebar"] .stButton > button * {{ background: {COPPER} !important; color: #ffffff !important; font-weight: 700; border-radius: 10px; border: none; }}

  [data-testid="stAppViewContainer"] {{ padding-top: 0; padding-bottom: 0; }}
  .block-container {{ padding-top: 8px !important; padding-left: 0 !important; padding-right: 0 !important; }}

  .drawer {{ position: fixed; top:0; right:0; width:275px; height:100vh; background:#fff;
             transform: translateX(100%); transition: transform .24s ease; z-index: 9999;
             border-left: 1px solid #e9eaee; box-shadow: -14px 0 28px rgba(0,0,0,.12); overflow-y:auto; }}
  .drawer.open {{ transform: translateX(0); }}
  .drawer-banner {{ background:{LOGO_BLUE}; color:#fff; padding:12px 16px; font-weight:800; font-size:18px; position:sticky; top:0; }}
  .drawer-body {{ padding:14px 16px 24px; }}
  .kv {{ display:flex; gap:8px; align-items:flex-start; margin-bottom:6px; }}
  .kv .k {{ min-width:140px; color:#4b5563; font-weight:600; }}
  .kv .v {{ color:#111827; }}
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

def norm_txt(x: str) -> str:
    if x is None: return ""
    s = str(x).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s)
    return s

def sanitize_value(v):
    if v is None: return ""
    s = str(v).strip()
    return "" if s in ["", "-", "/"] else s

def find_col(df: pd.DataFrame, *candidates) -> str:
    norm_map = {c: norm_txt(c) for c in df.columns}
    for cand in candidates:
        cn = norm_txt(cand)
        for c, n in norm_map.items():
            if n == cn:
                return c
        for c, n in norm_map.items():
            if all(part in n for part in cn.split()):
                return c
    return ""

def to_number(value) -> Optional[float]:
    """Robust numeric parsing: handles '25 000', '25.000', '25,000', '250 m²' etc."""
    if value is None: 
        return None
    s = str(value).strip()
    if s == "": 
        return None
    s = s.replace("€","").replace("euro","").replace("euros","")
    s = s.replace("m²","").replace("m2","").replace("mÂ²","")
    s = s.replace(" "," ").replace(" ", "")  # no-break space + spaces
    s = s.replace(",", ".")
    # Keep digits, one dot, and leading minus
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
    return series.astype(str).str.strip().str.replace(",", ".", regex=False).map(to_number)

def drawer(row: pd.Series, cols_range: Tuple[int,int]=(6,33)):
    ref_col = find_col(pd.DataFrame([row]).T, "Référence annonce", "Reference")
    ref_val = str(row.get(ref_col, ""))
    gm_col = find_col(pd.DataFrame([row]).T, "Lien Google Maps", "Google Maps")
    gm = row.get(gm_col, "")

    cols = list(row.index)
    start_idx, end_idx = cols_range
    display_cols = cols[start_idx:end_idx+1] if len(cols) > end_idx else cols[start_idx:]

    st.markdown('<div class="drawer open">', unsafe_allow_html=True)
    st.markdown(f'<div class="drawer-banner">Référence : {ref_val}</div>', unsafe_allow_html=True)
    st.markdown('<div class="drawer-body">', unsafe_allow_html=True)

    if isinstance(gm, str) and gm.strip():
        st.markdown(f'<a href="{gm.strip()}" target="_blank"><button class="stButton">Cliquer ici</button></a>', unsafe_allow_html=True)

    for c in display_cols:
        if norm_txt(c) in ["lien google maps", "google maps"]:
            continue
        val = sanitize_value(row.get(c))
        if not val:
            continue
        st.markdown(f'<div class="kv"><div class="k">{c}</div><div class="v">{val}</div></div>', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)

def clear_all_filters_once():
    if not st.session_state.get("_smbg_cleared", False):
        for k in list(st.session_state.keys()):
            if k.startswith(("reg_", "dep_", "typo_", "extr_", "empl_", "surf_", "loyer_")):
                del st.session_state[k]
        st.session_state["_smbg_cleared"] = True

def region_department_ui(df: pd.DataFrame, col_region: str, col_dept: str):
    sel_regions: List[str] = []
    sel_deps: List[str] = []
    with st.expander("Région / Département", expanded=True):
        regions = sorted([r for r in df[col_region].dropna().astype(str).unique() if r not in ["-","/"]])
        for reg in regions:
            if st.checkbox(reg, key=f"reg_{reg}"):
                sel_regions.append(reg)
                deps = sorted([d for d in df[df[col_region].astype(str)==reg][col_dept].dropna().astype(str).unique() if d not in ["-","/"]])
                for dep in deps:
                    col_pad, col_box = st.columns([1, 10])
                    with col_pad: st.write("")
                    with col_box:
                        if st.checkbox(dep, key=f"dep_{reg}_{dep}"):
                            sel_deps.append(dep)
    return sel_regions, sel_deps

def anti_overlap_positions(group: pd.DataFrame) -> List[Tuple[float,float]]:
    n = len(group)
    if n == 1:
        return [(float(group.iloc[0]["_lat"]), float(group.iloc[0]["_lon"]))]
    r = 0.0006  # ~45-60m
    base_lat = float(group.iloc[0]["_lat"])
    base_lon = float(group.iloc[0]["_lon"])
    out = []
    for i in range(n):
        angle = 2*math.pi * i / n
        out.append((base_lat + r*math.sin(angle), base_lon + r*math.cos(angle)))
    return out

def main():
    df = load_excel()
    if df is None or df.empty:
        st.warning("Excel vide ou introuvable."); st.stop()

    clear_all_filters_once()

    # Detect columns
    col_lat = find_col(df, "Latitude")
    col_lon = find_col(df, "Longitude")
    col_actif = find_col(df, "Actif")
    col_typo = find_col(df, "Typologie", "Typologie d'actif")
    col_empl = find_col(df, "Emplacement")
    col_extr = find_col(df, "Extraction")
    col_loyer = find_col(df, "Loyer annuel", "Loyer annuel (€)", "Loyer annuel (euros)")
    col_surface = find_col(df, "Surface", "Surface GLA", "GLA", "Surface totale")
    col_region = find_col(df, "Région")
    col_dept = find_col(df, "Département")
    col_ref = find_col(df, "Référence annonce", "Reference")

    # Prepare data
    df["_actif"] = df[col_actif] if col_actif else "oui"
    df["_actif"] = df["_actif"].apply(normalize_bool)

    # Clean lat/lon robustly (commas, spaces)
    df["_lat"] = clean_latlon_series(df[col_lat]) if col_lat else pd.NA
    df["_lon"] = clean_latlon_series(df[col_lon]) if col_lon else pd.NA

    if col_typo: df["_typologie_n"] = df[col_typo].astype(str).map(norm_txt)
    else: df["_typologie_n"] = ""
    if col_empl: df["_empl_n"] = df[col_empl].astype(str).map(norm_txt)
    else: df["_empl_n"] = ""
    if col_extr: df["_extr_n"] = df[col_extr].astype(str).map(norm_txt)
    else: df["_extr_n"] = ""

    # Filter valid rows
    df = df[df["_actif"] & df["_lat"].notna() & df["_lon"].notna()].copy()
    if df.empty:
        st.warning("Aucune ligne active avec coordonnées valides."); st.stop()

    # --------------- Sidebar ---------------
    with st.sidebar:
        st.markdown("### Filtres")
        working = df.copy()

        if col_region and col_dept:
            sel_regions, sel_deps = region_department_ui(working, col_region, col_dept)
            if sel_regions:
                working = working[working[col_region].astype(str).isin(sel_regions)]
            if sel_deps:
                working = working[working[col_dept].astype(str).isin(sel_deps)]

        if col_typo:
            st.markdown("<div class='group-title'>Typologie d'actif</div>", unsafe_allow_html=True)
            typos_raw = sorted([t for t in working[col_typo].dropna().astype(str).unique() if t not in ["-","/",""]])
            chosen_norm = []
            for t in typos_raw:
                if st.checkbox(t, key=f"typo_{t}"):
                    chosen_norm.append(norm_txt(t))
            if chosen_norm:
                working = working[working["_typologie_n"].isin(chosen_norm)]

        if col_extr:
            st.markdown("<div class='group-title'>Extraction</div>", unsafe_allow_html=True)
            extr_opts = ["oui","non","faisable"]
            sel_extr = []
            for e in extr_opts:
                if st.checkbox(e, key=f"extr_{e}"):
                    sel_extr.append(norm_txt(e))
            if sel_extr:
                working = working[working["_extr_n"].isin(sel_extr)]

        if col_empl:
            st.markdown("<div class='group-title'>Emplacement</div>", unsafe_allow_html=True)
            vals = [e for e in working[col_empl].dropna().astype(str).unique() if e not in ["-","/",""]]
            base = ["Centre-ville","Périphérie"]
            ordered = [e for e in base if e in vals] + [e for e in vals if e not in base]
            sel_empl = []
            for e in ordered:
                if st.checkbox(e, key=f"empl_{e}"):
                    sel_empl.append(norm_txt(e))
            if sel_empl:
                working = working[working["_empl_n"].isin(sel_empl)]

        # Surface slider (robust parsing)
        if col_surface and working[col_surface].notna().any():
            series = clean_numeric_series(working[col_surface]).dropna()
            if not series.empty:
                vmin, vmax = int(series.min()), int(series.max())
                if vmin == vmax:
                    st.number_input("Surface (m²)", value=vmin, step=1, disabled=True, key="surf_single")
                else:
                    rng = st.slider("Surface (m²)", min_value=vmin, max_value=vmax, value=(vmin, vmax), step=1, key="surf_range")
                    wnum = clean_numeric_series(working[col_surface])
                    working = working[wnum.between(rng[0], rng[1])]

        # Loyer annuel (robust parsing)
        if col_loyer and working[col_loyer].notna().any():
            series = clean_numeric_series(working[col_loyer]).dropna()
            if not series.empty:
                vmin, vmax = int(series.min()), int(series.max())
                if vmin == vmax:
                    st.number_input("Loyer annuel (€)", value=vmin, step=1, disabled=True, key="loyer_single")
                else:
                    rng = st.slider("Loyer annuel (€)", min_value=vmin, max_value=vmax, value=(vmin, vmax), step=1000, key="loyer_range")
                    wnum = clean_numeric_series(working[col_loyer])
                    working = working[wnum.between(rng[0], rng[1])]

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Réinitialiser les filtres"):
                for k in list(st.session_state.keys()):
                    if k.startswith(("reg_", "dep_", "typo_", "extr_", "empl_", "surf_", "loyer_")):
                        del st.session_state[k]
                st.experimental_rerun()
        with c2:
            st.button("Je suis intéressé")

    # --------------- Map ---------------
    data = working.copy()
    if data.empty:
        st.info("Aucun résultat pour ces filtres.")
        return

    # Anti-overlap
    data["_lat_r"] = data["_lat"].round(6)
    data["_lon_r"] = data["_lon"].round(6)
    groups = data.groupby(["_lat_r","_lon_r"], sort=False)

    plot_rows = []
    for _, grp in groups:
        coords = anti_overlap_positions(grp)
        for (coords_pair, (_, row)) in zip(coords, grp.iterrows()):
            rlat, rlon = coords_pair
            row = row.copy()
            row["_lat_plot"] = rlat
            row["_lon_plot"] = rlon
            plot_rows.append(row)
    plot_df = pd.DataFrame(plot_rows)

    FR_LAT, FR_LON, FR_ZOOM = 46.603354, 1.888334, 6
    m = folium.Map(location=[FR_LAT, FR_LON], zoom_start=FR_ZOOM,
                   tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                   attr="© OpenStreetMap contributors")

    css = f"background:{LOGO_BLUE}; color:#fff; border:2px solid #fff; width:28px; height:28px; line-height:28px; border-radius:50%; text-align:center; font-size:11px; font-weight:600;"
    group_layer = folium.FeatureGroup(name="Annonces").add_to(m)

    ref_col = col_ref if col_ref else "Référence annonce"
    if ref_col not in plot_df.columns and "Référence annonce" in plot_df.columns:
        ref_col = "Référence annonce"

    for _, r in plot_df.iterrows():
        lat, lon = float(r["_lat_plot"]), float(r["_lon_plot"])
        ref_text = str(r.get(ref_col, ""))
        icon = folium.DivIcon(html=f'<div style="{css}">{ref_text}</div>')
        folium.Marker(location=[lat, lon], icon=icon).add_to(group_layer)

    out = st_folium(m, height=950, width=None, returned_objects=[])

    if isinstance(out, dict):
        loc = out.get("last_object_clicked")
        if isinstance(loc, dict) and "lat" in loc and "lng" in loc:
            lat_click, lon_click = float(loc["lat"]), float(loc["lng"])
            plot_df["__d2"] = (plot_df["_lat_plot"]-lat_click)**2 + (plot_df["_lon_plot"]-lon_click)**2
            row = plot_df.loc[plot_df["__d2"].idxmin()]
            drawer(row)

if __name__ == "__main__":
    main()

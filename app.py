import math
import re
import pandas as pd
import numpy as np
import streamlit as st
from streamlit_folium import st_folium
import folium

st.set_page_config(page_title="Carte Interactive SMBG", layout="wide")

SMBG_BLUE = "#05263d"
SMBG_COPPER = "#b87333"

st.markdown(f'''
<style>
@font-face {{
  font-family: "Futura";
  src: local("Futura"), local("FuturaPT"), local("Futura Std");
  font-display: swap;
}}
html, body, [class^="css"] {{
  font-family: "Futura", "Century Gothic", "Segoe UI", Arial, sans-serif;
}}
section[data-testid="stSidebar"] > div {{
  background: linear-gradient(180deg, {SMBG_BLUE} 0%, #0a3a5b 100%);
  color: white;
}}
.stImage > button {{ display: none !important; }}
.stButton>button {{
  background-color: {SMBG_COPPER};
  color: white;
  border: 0;
  border-radius: 12px;
  padding: 0.5rem 1rem;
}}
.stButton>button:hover {{ opacity: 0.9; }}
.details-panel {{
  position: fixed; top: 0; right: 0; width: 320px; height: 100vh;
  background: #fff; border-left: 4px solid {SMBG_BLUE};
  padding: 16px 14px 24px 14px; overflow-y: auto; z-index: 9999;
}}
.details-panel h3 {{ margin-top: 0; color: {SMBG_BLUE}; }}
.details-table {{ width: 100%; border-collapse: collapse; font-size: .92rem; }}
.details-table th, .details-table td {{ border-bottom: 1px solid #eee; padding: 6px 4px; vertical-align: top; }}
.details-table th {{ color: {SMBG_BLUE}; text-align: left; width: 42%; }}
.details-table a.btn {{
  display: inline-block; background: {SMBG_COPPER}; color: white !important;
  border-radius: 10px; padding: 4px 10px; text-decoration: none;
}}
</style>
''', unsafe_allow_html=True)

@st.cache_data
def load_data(xlsx_path: str) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path)
    df.columns = [str(c).strip() for c in df.columns]
    if "Référence annonce" in df.columns:
        df["Référence annonce"] = df["Référence annonce"].apply(lambda x: "" if pd.isna(x) else str(x).strip())
        df["Référence annonce"] = df["Référence annonce"].str.replace(r"\.0$", "", regex=True)
    for col in ["Latitude", "Longitude"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if {"Latitude","Longitude"}.issubset(df.columns):
        df = df.dropna(subset=["Latitude","Longitude"])
    df = enrich_ranges(df)
    return df

def enrich_ranges(df: pd.DataFrame) -> pd.DataFrame:
    if "Surfaces des lots" in df.columns and "Surface GLA" in df.columns:
        smin, smax = [], []
        for s, gla in zip(df["Surfaces des lots"], df["Surface GLA"]):
            mn, mx = parse_surface_range(s, gla); smin.append(mn); smax.append(mx)
        df["Surface Min"] = smin; df["Surface Max"] = smax
    elif "Surface GLA" in df.columns:
        df["Surface Min"] = pd.to_numeric(df["Surface GLA"], errors="coerce")
        df["Surface Max"] = pd.to_numeric(df["Surface GLA"], errors="coerce")
    else:
        df["Surface Min"] = np.nan; df["Surface Max"] = np.nan

    if "Loyer en €/m²" in df.columns:
        eur_m2 = pd.to_numeric(df["Loyer en €/m²"], errors="coerce")
        df["Loyer Annuel Min"] = (eur_m2 * df["Surface Min"]).round()
        df["Loyer Annuel Max"] = (eur_m2 * df["Surface Max"]).round()
    elif "Loyer annuel" in df.columns:
        la = pd.to_numeric(df["Loyer annuel"], errors="coerce")
        df["Loyer Annuel Min"] = la; df["Loyer Annuel Max"] = la
    else:
        df["Loyer Annuel Min"] = np.nan; df["Loyer Annuel Max"] = np.nan
    return df

def parse_surface_range(text, fallback_gla):
    if pd.isna(text) or str(text).strip() == "":
        val = pd.to_numeric(fallback_gla, errors="coerce"); return (val, val)
    t = str(text).replace("m²","").replace("m2","").strip()
    m = re.match(r"^\s*(\d+)\s*[-–]\s*(\d+)\s*$", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2)); return (min(a,b), max(a,b))
    parts = [p for p in re.split(r"[;,]\s*", t) if p]
    nums = []
    for p in parts:
        n = pd.to_numeric(p, errors="coerce")
        if pd.notna(n): nums.append(int(n))
    if nums: return (min(nums), max(nums))
    n = pd.to_numeric(t, errors="coerce")
    if pd.notna(n): return (int(n), int(n))
    val = pd.to_numeric(fallback_gla, errors="coerce"); return (val, val)

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(np.sqrt(a), np.sqrt(1-a))
    return R*c

def format_val(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() in ["", "-", "/"]:
        return ""
    return str(v)

with st.sidebar:
    st.markdown('''
    <div style="text-align:center;padding:10px 0 14px 0;">
      <img src="https://raw.githubusercontent.com/guillaume-smbg/assets/main/logo-bleu-crop.png"
           alt="SMBG Conseil"
           style="max-width: 180px; height: auto; pointer-events: none; user-select: none;" />
    </div>
    ''', unsafe_allow_html=True)
    st.markdown("<h3 style='color:white;margin-top:0;'>Filtres</h3>", unsafe_allow_html=True)

xlsx_path = st.secrets.get("EXCEL_PATH", "data/Liste des lots.xlsx")
df = load_data(xlsx_path)

# ---------- Robust slider guards ----------
def safe_min_max(series: pd.Series):
    if series is None:
        return None, None
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None, None
    return float(np.nanmin(s)), float(np.nanmax(s))

surf_min_val, surf_max_val = safe_min_max(df.get("Surface Min"))
if surf_min_val is None or surf_max_val is None:
    # No usable surface data -> no filter
    surf_active = False
    surf_sel = (None, None)
else:
    surf_min_global = int(surf_min_val)
    surf_max_global = int(surf_max_val)
    if surf_min_global >= surf_max_global:
        # Single value or degenerate -> keep as 'no filter' and show info
        st.sidebar.info(f"Surface unique ou non définie : {surf_min_global if surf_min_val is not None else '—'} m²")
        surf_active = False
        surf_sel = (surf_min_global, surf_max_global)
    else:
        surf_sel = st.sidebar.slider("Surface (m²)",
                                     min_value=surf_min_global,
                                     max_value=surf_max_global,
                                     value=(surf_min_global, surf_max_global),
                                     step=1)
        surf_active = (surf_sel[0] > surf_min_global) or (surf_sel[1] < surf_max_global)

loy_min_val, loy_max_val = safe_min_max(df.get("Loyer Annuel Min")), safe_min_max(df.get("Loyer Annuel Max"))
# The above returns tuples; we want overall min of mins and max of maxes
def merge_min_max(mn_pair, mx_pair):
    mn1, mx1 = mn_pair
    mn2, mx2 = mx_pair
    vals = [v for v in [mn1, mx1, mn2, mx2] if v is not None and not np.isnan(v)]
    if not vals:
        return None, None
    return int(min(vals)), int(max(vals))

loy_min_global, loy_max_global = merge_min_max(loy_min_val, loy_max_val)

if loy_min_global is None or loy_max_global is None or loy_min_global >= loy_max_global:
    st.sidebar.info("Loyer annuel : données non définies ou uniques")
    loy_active = False
    loy_sel = (loy_min_global or 0, loy_max_global or 0)
else:
    step = 1000 if (loy_max_global - loy_min_global) > 10000 else 100
    loy_sel = st.sidebar.slider("Loyer annuel (€)",
                                min_value=loy_min_global,
                                max_value=loy_max_global,
                                value=(loy_min_global, loy_max_global),
                                step=step)
    loy_active = (loy_sel[0] > loy_min_global) or (loy_sel[1] < loy_max_global)

# Characteristic filters (optional)
col_characteristics = []
for c in ["Emplacement", "Typologie", "Restauration"]:
    if c in df.columns:
        opts = sorted([x for x in df[c].dropna().unique().tolist() if str(x).strip() != ""])
        sel = st.sidebar.multiselect(c, options=opts, default=[])
        col_characteristics.append((c, sel))

filtered = df.copy()
for col, selected in col_characteristics:
    if selected:
        filtered = filtered[filtered[col].isin(selected)]

if surf_active and {"Surface Min","Surface Max"}.issubset(filtered.columns):
    smin, smax = surf_sel
    filtered = filtered[(filtered["Surface Max"].fillna(np.inf) >= smin) & (filtered["Surface Min"].fillna(-np.inf) <= smax)]

if loy_active and {"Loyer Annuel Min","Loyer Annuel Max"}.issubset(filtered.columns):
    lmin, lmax = loy_sel
    filtered = filtered[(filtered["Loyer Annuel Max"].fillna(np.inf) >= lmin) & (filtered["Loyer Annuel Min"].fillna(-np.inf) <= lmax)]

st.sidebar.markdown(f"**Annonces sur la carte :** {len(filtered)}")

# ---------- Map ----------
if not filtered.empty:
    center_lat = float(filtered["Latitude"].mean())
    center_lon = float(filtered["Longitude"].mean())
else:
    center_lat, center_lon = 46.5, 2.5

m = folium.Map(location=[center_lat, center_lon], zoom_start=6, control_scale=True, tiles="OpenStreetMap")

def add_ref_marker(row):
    ref = str(row.get("Référence annonce", "")).strip()
    ref = re.sub(r"\.0$", "", ref) if ref else ""
    html = f'''
    <div style="width:30px;height:30px;border-radius:50%;background:{SMBG_BLUE};
                display:flex;align-items:center;justify-content:center;
                color:#fff;font-weight:700;font-size:12px;border:1px solid #003049;">
      {ref if ref else "•"}
    </div>
    '''
    folium.Marker(location=[row["Latitude"], row["Longitude"]],
                  icon=folium.DivIcon(html=html, class_name="smbg-divicon", icon_size=(30,30), icon_anchor=(15,15))
                 ).add_to(m)

if not filtered.empty:
    filtered.apply(add_ref_marker, axis=1)

map_state = st_folium(m, height=700, width=None, returned_objects=["last_clicked"])

# ---------- Click selection on filtered ----------
if "selected_ref" not in st.session_state:
    st.session_state.selected_ref = None

last_clicked = map_state.get("last_clicked")
if last_clicked and filtered.shape[0] > 0:
    clat, clon = float(last_clicked["lat"]), float(last_clicked["lng"])
    dists = filtered.apply(lambda r: haversine_m(clat, clon, r["Latitude"], r["Longitude"]), axis=1)
    idx_min = int(dists.idxmin())
    dmin = float(dists.loc[idx_min])
    if dmin <= 500:
        st.session_state.selected_ref = str(filtered.loc[idx_min, "Référence annonce"]).replace(".0","")
    else:
        st.session_state.selected_ref = None

# ---------- Right Panel (always visible) ----------
def google_maps_button(url):
    if not url or str(url).strip() in ["", "-", "/"]:
        return ""
    return f'<a class="btn" href="{url}" target="_blank">Cliquer ici</a>'

details_html = ["<div class='details-panel'>"]
details_html.append("<h3>Détails de l'annonce</h3>")

sel_ref = st.session_state.selected_ref
row = None
if sel_ref:
    candidates = filtered.copy()
    candidates["__ref_clean"] = candidates["Référence annonce"].astype(str).str.replace(r"\.0$","", regex=True)
    m = candidates[candidates["__ref_clean"] == str(sel_ref)]
    if not m.empty:
        row = m.iloc[0]

if row is not None:
    titre_ref = str(row.get("Référence annonce","")).replace(".0","")
    details_html.append(f"<p><strong>Référence : </strong>{titre_ref}</p>")
    cols_slice = list(filtered.columns[6:34])  # G→AH (0-based)
    table_rows = []
    for col in cols_slice:
        val = row.get(col, "")
        if col.lower().strip() in ["lien google maps", "google maps", "lien google"]:
            cell = google_maps_button(val)
        else:
            cell = format_val(val)
        if cell == "": continue
        if col in {"Latitude","Longitude","Géocodage statut","Géocodage date","Photos annonce","Actif"}:
            continue
        table_rows.append(f"<tr><th>{col}</th><td>{cell}</td></tr>")
    if table_rows:
        details_html.append("<table class='details-table'>" + "".join(table_rows) + "</table>")
else:
    details_html.append("<p style='opacity:.6'>Cliquez un pin pour afficher les détails.</p>")

details_html.append("</div>")
st.markdown("\\n".join(details_html), unsafe_allow_html=True)

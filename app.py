# app.py — SMBG Carte (version finale)
# - G→AF affichées (H = bouton "Cliquer ici")
# - AG..AM = technique : Latitude (AG), Longitude (AH), Géocode statut (AI), Géocode date (AJ),
#   Référence annonce (AK), Photos annonce (AL), Actif (AM)
# - Filtres dynamiques Région/Département + compteurs
# - Mode client : N/O/P -> "Demander le loyer"
# - Carte OSM, photos empilées, géocodage auto Nominatim
# - Police Futura auto depuis assets/*.ttf|*.otf

import os, io, time, base64, pathlib
from typing import List, Tuple, Dict
import requests
import pandas as pd
import streamlit as st
import yaml
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="SMBG Carte", layout="wide", page_icon="📍")

# ---------- Charger schema.yaml ----------
SCHEMA_PATH = pathlib.Path("schema.yaml")
if not SCHEMA_PATH.exists():
    st.error("Fichier schema.yaml introuvable à la racine du dépôt.")
    st.stop()
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    SCHEMA = yaml.safe_load(f)

# ---------- Secrets ----------
EXCEL_URL = os.environ.get("EXCEL_URL") or st.secrets.get("EXCEL_URL", "")
R2_BASE_URL = os.environ.get("R2_BASE_URL") or st.secrets.get("R2_BASE_URL", "")

# ---------- Helpers ----------
def excel_letter_to_index(letter: str) -> int:
    s = 0
    for c in letter.strip().upper():
        if "A" <= c <= "Z":
            s = s * 26 + (ord(c) - 64)
    return s - 1

def slice_by_letters(df: pd.DataFrame, start_letter: str, end_letter: str) -> pd.DataFrame:
    start_idx = excel_letter_to_index(start_letter)
    end_idx = excel_letter_to_index(end_letter)
    return df.iloc[:, start_idx:end_idx+1]

def clean_value(v):
    if pd.isna(v): return ""
    return str(v).strip()

def value_is_hidden(v) -> bool:
    return clean_value(v) in set(SCHEMA["right_panel"]["hide_values"])

def safe_col(df: pd.DataFrame, idx: int) -> pd.Series:
    return df.iloc[:, idx] if 0 <= idx < len(df.columns) else pd.Series([], dtype=object)

# ---------- Fonts Futura depuis assets/ ----------
def load_font_face(name: str, file_path: pathlib.Path, weight="normal", style="normal") -> str:
    if not file_path.exists(): return ""
    data = file_path.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    mime = "font/ttf" if file_path.suffix.lower()==".ttf" else "font/otf"
    return f"""
    @font-face {{
      font-family: '{name}';
      src: url(data:{mime};base64,{b64}) format('truetype');
      font-weight: {weight};
      font-style: {style};
      font-display: swap;
    }}
    """

def infer_weight_style(filename: str) -> Tuple[str,str]:
    f = filename.lower()
    style = "normal"
    if "italic" in f or "oblique" in f or ("it" in f and "bold" in f): style = "italic"
    weight = "400"
    if "thin" in f or "hairline" in f: weight="100"
    elif "extralight" in f or "ultralight" in f: weight="200"
    elif "light" in f: weight="300"
    elif "regular" in f or "book" in f or "roman" in f: weight="400"
    elif "medium" in f: weight="500"
    elif "semibold" in f or "demibold" in f or "sb" in f: weight="600"
    elif "bold" in f or "bd" in f: weight="700"
    elif "extrabold" in f or "ultrabold" in f or "heavy" in f: weight="800"
    elif "black" in f: weight="900"
    return weight, style

def inject_futura_fonts():
    assets = pathlib.Path("assets")
    css_blocks = []
    if assets.exists():
        files = sorted(list(assets.glob("*.ttf")) + list(assets.glob("*.otf")))
        for p in files:
            w,s = infer_weight_style(p.name)
            css_blocks.append(load_font_face("Futura SMBG", p, w, s))
    css = f"""
    <style>
    {''.join(css_blocks)}
    html, body, [class*="css"], .stMarkdown, .stText, .stButton, .stSelectbox, .stMultiSelect,
    .stDataFrame, .stMetric, .stCheckbox, .stRadio, .stTextInput, .stNumberInput, .stDateInput, .stLinkButton {{
      font-family: 'Futura SMBG', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;
    }}
    /* anti-capture soft */
    * {{ user-select: none; -webkit-user-select:none; -ms-user-select:none; }}
    img {{ -webkit-user-drag: none; user-drag: none; }}
    @media print {{ body::before {{ content:"Impression désactivée"; }} body {{ display:none; }} }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

inject_futura_fonts()

# ---------- Header branding ----------
def show_header():
    c1, c2 = st.columns([1,4], vertical_alignment="center")
    with c1:
        for cand in ["assets/Logo bleu.png","assets/logo_bleu.png","assets/Logo transparent.png","assets/logo_transparent.png","assets/Icône bleu.png"]:
            p = pathlib.Path(cand)
            if p.exists():
                st.image(str(p), use_container_width=True)
                break
    with c2:
        st.markdown("<div style='padding-top:4px; font-size:28px; font-weight:700;'>SMBG Carte — Sélection d’annonces</div>", unsafe_allow_html=True)
        for sc in ["assets/Slogan bleu.png","assets/slogan_bleu.png","assets/Slogan transparent.png"]:
            sp = pathlib.Path(sc)
            if sp.exists():
                st.image(str(sp), width=240)
                break

show_header()

# ---------- Mode (client/interne) ----------
DEFAULT_MODE = SCHEMA.get("modes",{}).get("default_mode","client")
mode_param = st.query_params.get("mode", DEFAULT_MODE)
MODE = mode_param if mode_param in ("client","interne") else DEFAULT_MODE
st.sidebar.markdown(f"**Mode :** `{MODE}`")

# ---------- Charger Excel ----------
def load_excel(url: str) -> pd.DataFrame:
    if not url:
        st.error("EXCEL_URL manquant (à renseigner dans *Settings → Secrets* de Streamlit Cloud).")
        st.stop()
    try:
        return pd.read_excel(url, engine="openpyxl")
    except Exception as e:
        st.error(f"Impossible de lire l'Excel depuis EXCEL_URL. Détail : {e}")
        st.stop()

df_all = load_excel(EXCEL_URL)

# ---------- Indices colonnes techniques ----------
lat_col   = excel_letter_to_index(SCHEMA["technical_columns"]["latitude"])     # AG
lon_col   = excel_letter_to_index(SCHEMA["technical_columns"]["longitude"])    # AH
geos_col  = excel_letter_to_index(SCHEMA["technical_columns"]["geocode_status"])  # AI
geod_col  = excel_letter_to_index(SCHEMA["technical_columns"]["geocode_date"])    # AJ
ref_col   = excel_letter_to_index(SCHEMA["technical_columns"]["reference"])    # AK
photos_col= excel_letter_to_index(SCHEMA["technical_columns"]["photos"])       # AL
active_col= excel_letter_to_index(SCHEMA["technical_columns"]["active"])       # AM

# ---------- Filtrer Actif = oui ----------
if 0 <= active_col < len(df_all.columns):
    actives = df_all.iloc[:, active_col].fillna("").astype(str).str.strip().str.lower() == "oui"
    df = df_all[actives].reset_index(drop=True)
else:
    df = df_all.copy()

# ---------- Détection Région / Département ----------
region_col = None
dept_col = None
for c in df.columns:
    cl = str(c).lower()
    if ("région" in cl) or ("region" in cl): region_col = region_col or c
    if ("départ" in cl) or ("depart" in cl) or ("dept" in cl): dept_col = dept_col or c

# ---------- Géocodage automatique ----------
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "SMBG-Carte/1.0 (contact: guillaume.kettenmeyer@smbg-conseil.fr)"}

@st.cache_data(show_spinner=False, ttl=60*60*24)
def geocode_cached(address: str) -> Tuple[str,str,str]:
    if not address: return ("","","")
    params = {"q": address, "format":"json", "limit":1, "countrycodes":"fr"}
    r = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return ("","","")
    js = r.json()
    if not js: return ("","","")
    lat = js[0].get("lat",""); lon = js[0].get("lon","")
    return (lat, lon, "ok")

def compute_lat_lon(df_in: pd.DataFrame) -> Tuple[List[float], List[float], List[str], List[str]]:
    """Retourne latitudes, longitudes, statut, date (en mémoire) sans modifier l'Excel."""
    import datetime
    lats, lons, stats, dates = [], [], [], []
    # Adresse utilisée pour géocoder = colonne G (début de la zone affichée)
    addr_idx = excel_letter_to_index("G")
    for i, row in df_in.iterrows():
        lat_v = clean_value(row.iloc[lat_col]) if 0 <= lat_col < len(df_in.columns) else ""
        lon_v = clean_value(row.iloc[lon_col]) if 0 <= lon_col < len(df_in.columns) else ""
        if lat_v and lon_v:
            lats.append(float(lat_v)); lons.append(float(lon_v))
            stats.append("déjà fourni"); dates.append("")
        else:
            # géocoder à partir de l'adresse G
            addr = clean_value(row.iloc[addr_idx]) if 0 <= addr_idx < len(df_in.columns) else ""
            la, lo, stt = geocode_cached(addr)
            # Respect minimal du rate-limit (1 req/s quand pas en cache)
            time.sleep(1/3)
            if la and lo:
                lats.append(float(la)); lons.append(float(lo))
                stats.append("géocodé"); dates.append(datetime.date.today().isoformat())
            else:
                lats.append(None); lons.append(None)
                stats.append("échec"); dates.append(datetime.date.today().isoformat())
    return lats, lons, stats, dates

lats, lons, geostats, geodates = compute_lat_lon(df)

# ---------- Filtres Région / Département (avec compteurs dynamiques) ----------
def current_other_filters(df_in: pd.DataFrame) -> pd.DataFrame:
    return df_in

def region_counts(df_in: pd.DataFrame, selected_depts: List[str]) -> Dict[str,int]:
    base = current_other_filters(df_in)
    if dept_col and selected_depts:
        base = base[base[dept_col].astype(str).str.strip().isin(selected_depts)]
    out={}
    if region_col:
        for v, sub in base.groupby(region_col, dropna=True):
            vv = clean_value(v)
            if vv and vv != "/": out[vv] = len(sub)
    return out

def dept_counts(df_in: pd.DataFrame, selected_regions: List[str]) -> Dict[str,int]:
    base = current_other_filters(df_in)
    if region_col and selected_regions:
        base = base[base[region_col].astype(str).str.strip().isin(selected_regions)]
    out={}
    if dept_col:
        for v, sub in base.groupby(dept_col, dropna=True):
            vv = clean_value(v)
            if vv and vv != "/": out[vv] = len(sub)
    return out

st.sidebar.header("Filtres")

regions_all = sorted([r for r in (df[region_col].dropna().astype(str).str.strip().unique().tolist() if region_col else []) if r and r!="/"])
depts_all   = sorted([d for d in (df[dept_col].dropna().astype(str).str.strip().unique().tolist()   if dept_col   else []) if d and d!="/"])

# régions (compteurs initiaux)
rc0 = region_counts(df, selected_depts=[])
fmt_region = (lambda x: f"{x} ({rc0.get(x,0)})")
selected_regions = st.sidebar.multiselect("Régions", options=regions_all, default=[], format_func=fmt_region)

# restreindre par régions
df_region = df.copy()
if region_col and selected_regions:
    df_region = df_region[df_region[region_col].astype(str).str.strip().isin(selected_regions)]

# départements dépendants
dc0 = dept_counts(df, selected_regions=selected_regions)
depts_filtered = sorted([d for d in (df_region[dept_col].dropna().astype(str).str.strip().unique().tolist() if dept_col else []) if d and d!="/"])
fmt_dept = (lambda x: f"{x} ({dc0.get(x,0)})")
selected_depts = st.sidebar.multiselect("Départements", options=depts_filtered, default=[], format_func=fmt_dept)

# restreindre final
df_filtered = df_region.copy()
if dept_col and selected_depts:
    df_filtered = df_filtered[df_filtered[dept_col].astype(str).str.strip().isin(selected_depts)]

st.sidebar.caption(f"**{len(df_filtered)}** annonces après filtres Région / Département.")

# ---------- Layout principal ----------
left, right = st.columns([1.1, 1.9], gap="large")

with left:
    st.subheader("Carte")
    # centrage France ou moyenne des points valides
    pts = [(la,lo) for la,lo in zip(lats,lons) if la is not None and lo is not None]
    if pts:
        c_lat = sum(p[0] for p in pts)/len(pts); c_lon = sum(p[1] for p in pts)/len(pts)
    else:
        c_lat, c_lon = 46.6, 2.45

    m = folium.Map(location=[c_lat, c_lon], zoom_start=6, tiles="OpenStreetMap")

    # séries Réf & Adresse
    ref_s  = safe_col(df, ref_col).astype(str)
    addr_i = excel_letter_to_index("G")
    addr_s = safe_col(df, addr_i).astype(str)

    # marquer uniquement les lignes visibles après filtres
    visible_idx = set(df_filtered.index.tolist())
    for i,(la,lo) in enumerate(zip(lats,lons)):
        if i not in visible_idx: continue
        if la is None or lo is None: continue
        ref_val  = clean_value(ref_s.iloc[i]) if i < len(ref_s) else ""
        addr_val = clean_value(addr_s.iloc[i]) if i < len(addr_s) else ""
        folium.Marker(
            [la,lo],
            tooltip=f"{ref_val} — {addr_val}",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    st_folium(m, width=None, height=520)

    # mini-liste
    ref_series = safe_col(df_filtered, ref_col).astype(str)
    addr_series= safe_col(df_filtered, addr_i).astype(str)
    mini = pd.DataFrame({"Référence": ref_series, "Adresse": addr_series})
    st.markdown("### Liste des annonces (filtres appliqués)")
    st.dataframe(mini, use_container_width=True, hide_index=True)

with right:
    st.subheader("Volet droit — Détails")
    st.caption("Affiche G→AF (H devient bouton “Cliquer ici”). Masque `/`, `-` et vides. Référence annonce en en-tête.")

    # range G..AF et Google Maps (H)
    start_idx = excel_letter_to_index("G")
    end_idx   = excel_letter_to_index("AF")
    gmaps_idx = excel_letter_to_index(SCHEMA["right_panel"]["google_maps_column_letter"])
    rent_letters = SCHEMA.get("modes",{}).get("rent_columns_letters", [])
    rent_idx = [excel_letter_to_index(x) for x in rent_letters]

    # prévisualiser toutes les annonces filtrées (tu peux limiter à n=10 si nécessaire)
    for _, row in df_filtered.iterrows():
        ref_val = clean_value(row.iloc[ref_col]) if 0 <= ref_col < len(df_filtered.columns) else ""
        if ref_val:
            st.markdown(f"**Référence annonce : {ref_val}**")

        for col_idx in range(start_idx, end_idx+1):
            header = df_filtered.columns[col_idx]
            val = row.iloc[col_idx]

            # bouton maps
            if col_idx == gmaps_idx:
                url = clean_value(val)
                if url and url != "/":
                    st.link_button(SCHEMA["branding"]["google_maps_button_label"], url, type="secondary")
                continue

            # loyers masqués en mode client
            if MODE == "client" and col_idx in rent_idx:
                st.write(f"**{header}** : Demander le loyer")
                continue

            if value_is_hidden(val):
                continue

            st.write(f"**{header}** : {clean_value(val)}")

        # photos empilées (AL)
        photos_val = clean_value(row.iloc[photos_col]) if 0 <= photos_col < len(df_filtered.columns) else ""
        if photos_val:
            urls = [u.strip() for u in photos_val.split("|") if u.strip()]
            if urls:
                st.markdown("**Photos :**")
                for u in urls:
                    st.image(u, use_container_width=True)

        st.divider()

st.success("SMBG Carte opérationnelle. Mettez à jour votre Excel (et photos) pour alimenter la carte.")

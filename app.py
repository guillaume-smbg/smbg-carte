import os
import re
import math
from typing import Optional, Tuple

import pandas as pd
import numpy as np
import streamlit as st

from streamlit_folium import st_folium
import folium
from PIL import Image

# ---------------------------
# THEME / BRANDING
# ---------------------------
THEME_BLUE_DEFAULT = "#0B2D3F"
THEME_COPPER = "#B87333"

LOGO_CANDIDATES = [
    "logo bleu crop.png", "logo bleu crop.jpg", "logo bleu crop.jpeg",
    "Logo bleu crop.png", "Logo bleu crop.jpg", "Logo bleu crop.jpeg",
    "Logo bleu.png", "assets/Logo bleu.png", "static/Logo bleu.png",
    "data/Logo bleu.png", "images/Logo bleu.png"
]

st.set_page_config(page_title="SMBG Carte — Sélection d’annonces", layout="wide")

# ---------------------------
# UTILS
# ---------------------------
def get_existing_path(candidates) -> Optional[str]:
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def hex_from_rgb(rgb) -> str:
    r, g, b = [int(x) for x in rgb]
    return "#{:02X}{:02X}{:02X}".format(r, g, b)

def get_dominant_color(path: str) -> str:
    try:
        with Image.open(path).convert("RGBA") as im:
            im = im.resize((80, 80))
            data = np.array(im)
            mask = data[:, :, 3] > 10
            if not mask.any():
                return THEME_BLUE_DEFAULT
            rgb = data[:, :, :3][mask]
            med = np.median(rgb, axis=0)
            return hex_from_rgb(med)
    except Exception:
        return THEME_BLUE_DEFAULT

def find_col(df: pd.DataFrame, *keywords) -> Optional[str]:
    low = {c: c.lower() for c in df.columns}
    for c, lc in low.items():
        if all(k.lower() in lc for k in keywords):
            return c
    return None

def coerce_number(x):
    if pd.isna(x): return np.nan
    s = str(x).strip()
    if s == "" or s in {"/", "-", "—"}: return np.nan
    if "demander" in s.lower(): return np.nan
    if s.lower() == "néant": return 0
    s = re.sub(r"[^\d,.\-]", "", s)
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return np.nan

def is_truthy_yes(x):
    return str(x).strip().lower() in {"oui","yes","true","1","y"}

def pretty_k_eur(x):
    try:
        v = float(x)
    except:
        return "-"
    if v >= 1_000_000: return f"{int(round(v/1_000_000))} M€"
    if v >= 1_000:     return f"{int(round(v/1_000))} k€"
    return f"{int(round(v))} €"

def is_empty_val(v):
    if pd.isna(v): return True
    s = str(v).strip()
    return s == "" or s in {"/", "-", "—"}

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    # 1) local  2) secrets.EXCEL_URL  3) env.EXCEL_URL
    for p in ["annonces.xlsx", "data/annonces.xlsx"]:
        if os.path.exists(p):
            return pd.read_excel(p)
    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    if url:
        return pd.read_excel(url)
    st.error("Aucun Excel trouvé. Place ‘annonces.xlsx’ à la racine (ou data/) ou définis EXCEL_URL.")
    return pd.DataFrame()

def safe_slider_num(series: pd.Series, label: str, key: str):
    """
    Affiche un slider UNIQUEMENT si:
      - au moins 2 valeurs numériques distinctes,
      - min < max.
    Sinon, pas de slider; renvoie (None, False).
    -> Blinde avec try/except pour qu'aucune exception Streamlit n'arrête l'app.
    """
    try:
        s = pd.to_numeric(series, errors="coerce")
        s = s[np.isfinite(s)]
        if s.empty:
            st.caption(f"*(Aucune valeur numérique pour « {label} » — filtre désactivé)*")
            return None, False
        uniques = np.unique(np.round(s.astype(float), 8))
        if len(uniques) < 2:
            st.caption(f"*(Pas assez de valeurs distinctes pour « {label} » — filtre désactivé)*")
            return None, False
        vmin = int(math.floor(float(np.min(uniques))))
        vmax = int(math.ceil(float(np.max(uniques))))
        if vmin >= vmax:
            st.caption(f"*(Intervalle nul pour « {label} » — filtre désactivé)*")
            return None, False
        a, b = st.slider(label, min_value=vmin, max_value=vmax, value=(vmin, vmax), key=key)
        return series.between(a, b), True
    except Exception as e:
        st.caption(f"*(Filtre « {label} » désactivé — valeurs incohérentes)*")
        return None, False

# ---------------------------
# Couleur exacte depuis le logo + CSS
# ---------------------------
LOGO_PATH = get_existing_path(LOGO_CANDIDATES)
THEME_BLUE = get_dominant_color(LOGO_PATH) if LOGO_PATH else THEME_BLUE_DEFAULT

st.markdown(
    f"""
    <style>
      /* Sidebar = fond EXACT + aucune marge au-dessus */
      [data-testid="stSidebar"] {{
        background: {THEME_BLUE};
        padding-top: 0 !important;
      }}
      /* Container principal plus large */
      .block-container {{
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1400px;
      }}
      /* Masquer le bouton de repli de la sidebar (non rétractable) */
      [data-testid="collapsedControl"] {{ display:none !important; }}
      /* Bandeau référence + badge */
      .ref-banner {{
        background:{THEME_BLUE}; color:white; padding:8px 12px; border-radius:10px; display:inline-block;
        font-weight:600; letter-spacing:.2px;
      }}
      .badge-new {{
        background:{THEME_COPPER}; color:white; padding:2px 8px; border-radius:999px; margin-left:8px;
        font-size:12px; font-weight:600;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
# DATA
# ---------------------------
df = load_excel()
if df.empty:
    st.stop()

col_region   = find_col(df, "région") or find_col(df, "region")
col_dept     = find_col(df, "département") or find_col(df, "departement")
col_lat      = find_col(df, "lat")
col_lon      = find_col(df, "lon") or find_col(df, "lng")
col_ref      = find_col(df, "référence","annonce") or find_col(df, "reference","annonce")
col_maps     = find_col(df, "google","map") or find_col(df, "lien","map")
col_actif    = find_col(df, "actif")
col_surface  = find_col(df, "surface")
col_loyer    = find_col(df, "loyer")
col_pp       = find_col(df, "pas de porte") or find_col(df, "droit au bail") or find_col(df, "cession")
col_date_pub = find_col(df, "publication") or find_col(df, "publi")

# Actif = oui
if col_actif and col_actif in df.columns:
    df = df[df[col_actif].apply(is_truthy_yes)].copy()

# Numériques pour filtres (sans altérer l’affichage d’origine)
df["_surface_num"] = df[col_surface].apply(coerce_number) if (col_surface and col_surface in df.columns) else np.nan
df["_loyer_num"]   = df[col_loyer].apply(coerce_number)   if (col_loyer and col_loyer in df.columns) else np.nan
df["_pp_num"]      = df[col_pp].apply(coerce_number)      if (col_pp and col_pp in df.columns) else np.nan

# ---------------------------
# SIDEBAR : LOGO en haut (vraiment collé)
# ---------------------------
with st.sidebar:
    # On force un conteneur tout en haut, sans marge
    top = st.container()
    with top:
        if LOGO_PATH:
            st.image(LOGO_PATH, use_container_width=True)
        else:
            st.markdown("<h3 style='color:white; text-align:center; margin:8px 0;'>SMBG CONSEIL</h3>", unsafe_allow_html=True)

# ---------------------------
# ENTÊTE
# ---------------------------
st.markdown("## SMBG Carte — Sélection d’annonces")

# ---------------------------
# FILTRES (contenu principal)
# ---------------------------
with st.expander("Filtres", expanded=True):
    filtered = df.copy()

    # Régions (dynamiques + compteurs)
    if col_region and col_region in df.columns:
        reg_counts = df.groupby(col_region).size().sort_values(ascending=False)
        reg_options = [f"{r} ({n})" for r, n in reg_counts.items()]
        sel_regs = st.multiselect("Régions", reg_options, placeholder="Choisir…", key="f_regions")
        if sel_regs:
            keep_regs = {x.split(" (")[0] for x in sel_regs}
            filtered = filtered[filtered[col_region].isin(keep_regs)]

    # Départements (dépend des régions sélectionnées)
    if col_dept and col_dept in df.columns:
        dept_counts = filtered.groupby(col_dept).size().sort_values(ascending=False)
        dept_options = [f"{d} ({n})" for d, n in dept_counts.items()]
        sel_depts = st.multiselect("Départements", dept_options, placeholder="Choisir…", key="f_depts")
        if sel_depts:
            keep_depts = {x.split(" (")[0] for x in sel_depts}
            filtered = filtered[filtered[col_dept].isin(keep_depts)]

    st.markdown("---")

    # Surface (m²) — blindé
    if "_surface_num" in filtered.columns:
        mask_s, used_s = safe_slider_num(filtered["_surface_num"], "Surface (m²)", key="sl_surface")
        if used_s and mask_s is not None:
            filtered = filtered[mask_s | filtered["_surface_num"].isna()]

    # Loyer (€) — blindé + “Demander le loyer”
    has_demander = col_loyer and (col_loyer in filtered.columns) and filtered[col_loyer].astype(str).str.contains("demander", case=False, na=False).any()
    if "_loyer_num" in filtered.columns:
        mask_l, used_l = safe_slider_num(filtered["_loyer_num"], "Loyer mensuel (€)", key="sl_loyer")
        incl_demander = st.checkbox("Inclure les annonces « Demander le loyer »", value=True, key="cb_demander") if has_demander else False
        if used_l and mask_l is not None:
            mask_dem = pd.Series(False, index=filtered.index)
            if incl_demander and col_loyer and (col_loyer in filtered.columns):
                mask_dem = filtered[col_loyer].astype(str).str.contains("demander", case=False, na=False)
            filtered = filtered[mask_l | (incl_demander & mask_dem) | filtered["_loyer_num"].isna()]

    # Pas de porte / DAB (€) — blindé + “Uniquement Néant”
    has_neant = col_pp and (col_pp in filtered.columns) and filtered[col_pp].astype(str).str.fullmatch(r"(?i)\s*néant\s*", na=False).any()
    if "_pp_num" in filtered.columns:
        mask_p, used_p = safe_slider_num(filtered["_pp_num"], "Pas de porte / Droit au bail (€)", key="sl_pp")
        only_neant = st.checkbox("Uniquement « Néant »", value=False, key="cb_neant") if has_neant else False
        if used_p and mask_p is not None:
            if only_neant and col_pp and (col_pp in filtered.columns):
                mask_neant = filtered[col_pp].astype(str).str.fullmatch(r"(?i)\s*néant\s*", na=False)
                filtered = filtered[mask_neant]
            else:
                mask_neant = pd.Series(False, index=filtered.index)
                if col_pp and (col_pp in filtered.columns):
                    mask_neant = filtered[col_pp].astype(str).str.fullmatch(r"(?i)\s*néant\s*", na=False)
                filtered = filtered[mask_p | mask_neant | filtered["_pp_num"].isna()]

    st.caption(f"**{len(filtered)}** annonces après filtres.")

# ---------------------------
# LAYOUT : Carte large + Volet détails rétractable
# ---------------------------
col_map, col_detail = st.columns([7, 5], gap="large")

with col_map:
    if col_lat and col_lon and (col_lat in filtered.columns) and (col_lon in filtered.columns):
        df_map = filtered.dropna(subset=[col_lat, col_lon]).copy()
    else:
        df_map = filtered.iloc[0:0].copy()

    if not df_map.empty:
        center = [df_map[col_lat].astype(float).mean(), df_map[col_lon].astype(float).mean()]
    else:
        center = [46.6, 2.5]  # France

    m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")

    st.session_state.setdefault("selected_idx", None)

    for idx, row in df_map.iterrows():
        popup_ref = str(row[col_ref]) if col_ref and (col_ref in df_map.columns) else f"Annonce {idx}"
        folium.Marker(
            location=[float(row[col_lat]), float(row[col_lon])],
            tooltip=popup_ref,
            popup=popup_ref
        ).add_to(m)

    st_folium(m, height=650, width=None)

    # Sélection manuelle pour piloter le volet droit
    with st.expander("Sélectionner une annonce (si besoin)"):
        if col_ref and (col_ref in filtered.columns):
            ref_series = filtered[col_ref].astype(str)
            choice = st.selectbox("Référence annonce :", options=list(ref_series.index),
                                  format_func=lambda i: ref_series.loc[i] if i in ref_series.index else str(i),
                                  key="sel_ref")
        else:
            choice = st.selectbox("Annonce :", options=list(filtered.index), format_func=lambda i: f"Annonce {i}", key="sel_idx")
        st.session_state["selected_idx"] = choice

with col_detail:
    show_details = st.toggle("Afficher le volet de détails", value=True, key="tg_details")
    if show_details:
        selected_idx = st.session_state.get("selected_idx")
        if selected_idx is None or selected_idx not in filtered.index:
            if not filtered.empty:
                selected_idx = filtered.index[0]

        if selected_idx is not None and selected_idx in filtered.index:
            row = filtered.loc[selected_idx]
            ref_val = str(row.get(col_ref, f"Annonce {selected_idx}"))
            st.markdown(f"<span class='ref-banner'>Référence annonce : {ref_val}</span>", unsafe_allow_html=True)

            # Badge "Nouveau"
            if col_date_pub and (col_date_pub in filtered.columns) and pd.notna(row.get(col_date_pub, None)):
                try:
                    d = pd.to_datetime(row[col_date_pub], dayfirst=True, errors="coerce")
                    if pd.notna(d) and (pd.Timestamp.now().tz_localize(None) - d.to_pydatetime().replace(tzinfo=None) <= pd.Timedelta(days=30)):
                        st.markdown("<span class='badge-new'>Nouveau</span>", unsafe_allow_html=True)
                except:
                    pass

            st.write("")

            # Bouton Google Maps
            if col_maps and (col_maps in filtered.columns) and not is_empty_val(row.get(col_maps, None)):
                st.link_button("Cliquer ici", str(row[col_maps]).strip(), type="primary")

            st.write("")

            # Champs métier (exclure techniques & déjà traités)
            technical_keywords = ["lat","lon","géocod","geocod","date géocod","photo","actif","internal","technique"]
            technical_like = {c for c in df.columns if any(k in c.lower() for k in technical_keywords)}
            to_hide_exact = {col_maps, col_lat, col_lon, col_actif, col_date_pub, col_ref}
            candidates = [c for c in df.columns if c not in technical_like and c not in to_hide_exact]

            for c in candidates:
                v = row.get(c, None)
                if is_empty_val(v):
                    continue
                if c == col_surface and pd.notna(row.get("_surface_num", np.nan)):
                    st.markdown(f"**{c}** : {int(round(row['_surface_num']))} m²")
                elif c == col_loyer and pd.notna(row.get("_loyer_num", np.nan)):
                    st.markdown(f"**{c}** : {pretty_k_eur(row['_loyer_num'])}")
                elif c == col_pp and pd.notna(row.get("_pp_num", np.nan)):
                    st.markdown(f"**{c}** : {pretty_k_eur(row['_pp_num'])}")
                else:
                    st.markdown(f"**{c}** : {v}")

st.caption(f"{len(filtered)} annonces affichées.")

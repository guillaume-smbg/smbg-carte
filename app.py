import os
import re
import math
from typing import Optional, Tuple

import pandas as pd
import numpy as np
import streamlit as st

from streamlit_folium import st_folium
import folium

# === NEW: couleur exacte depuis l'image ===
from PIL import Image

# =========================
# THEME & BRANDING
# =========================
# Valeurs par défaut (fallback)
THEME_BLUE_DEFAULT   = "#0B2D3F"
THEME_COPPER         = "#B87333"

# On priorise le nouveau logo "logo bleu crop" comme demandé
LOGO_CANDIDATES = [
    "logo bleu crop.png", "logo bleu crop.jpg", "logo bleu crop.jpeg",
    "Logo bleu crop.png", "Logo bleu crop.jpg", "Logo bleu crop.jpeg",
    "Logo bleu.png", "assets/Logo bleu.png", "static/Logo bleu.png", "data/Logo bleu.png", "images/Logo bleu.png"
]

st.set_page_config(page_title="SMBG Carte — Sélection d’annonces", layout="wide")

# =========================
# UTILS
# =========================
def get_existing_path(candidates) -> Optional[str]:
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def hex_from_rgb(rgb: Tuple[int,int,int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)

def get_dominant_color(path: str) -> str:
    """
    Renvoie la couleur dominante (RGB) de l'image (hors pixels très transparents),
    avec un resize pour performance. Si échec: fallback THEME_BLUE_DEFAULT.
    """
    try:
        with Image.open(path).convert("RGBA") as im:
            im = im.resize((80, 80))  # suffisant pour estimer
            data = np.array(im)
            # garder les pixels opaques
            mask = data[:, :, 3] > 10
            if not mask.any():
                return THEME_BLUE_DEFAULT
            rgb = data[:, :, :3][mask]
            # On prend la médiane (robuste) plutôt que la moyenne si le logo a des accents cuivrés
            median = tuple(np.median(rgb, axis=0).astype(int))
            return hex_from_rgb(median)
    except Exception:
        return THEME_BLUE_DEFAULT

def find_col(df: pd.DataFrame, *keywords) -> Optional[str]:
    low = {c: c.lower() for c in df.columns}
    for c, lc in low.items():
        if all(k.lower() in lc for k in keywords):
            return c
    return None

def coerce_number(x):
    if pd.isna(x):
        return np.nan
    s = str(x).strip()
    if s == "" or s in {"/", "-", "—"}:
        return np.nan
    if "demander" in s.lower():
        return np.nan
    if s.lower() == "néant":
        return 0
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
    if v >= 1_000_000:
        return f"{int(round(v/1_000_000))} M€"
    if v >= 1_000:
        return f"{int(round(v/1_000))} k€"
    return f"{int(round(v))} €"

def is_empty_val(v):
    if pd.isna(v): return True
    s = str(v).strip()
    return s == "" or s in {"/", "-", "—"}

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    """
    1) 'annonces.xlsx' (racine ou data/)
    2) st.secrets['EXCEL_URL'] (URL raw GitHub)
    3) os.environ['EXCEL_URL']
    """
    candidates = ["annonces.xlsx", "data/annonces.xlsx"]
    for p in candidates:
        if os.path.exists(p):
            return pd.read_excel(p)

    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    if url:
        return pd.read_excel(url)

    st.error("Aucun Excel trouvé. Place ‘annonces.xlsx’ dans le repo ou définis EXCEL_URL (secrets/env).")
    return pd.DataFrame()

def safe_slider_num(series: pd.Series, label: str):
    """
    Affiche un slider seulement si au moins 2 valeurs numériques distinctes
    et min < max. Renvoie (mask, used) où:
      - mask: filtre booléen ou None (si non utilisé)
      - used: True si slider affiché
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    s = s[np.isfinite(s)]
    uniques = np.unique(np.round(s, 8))
    if len(uniques) >= 2:
        vmin = int(math.floor(np.min(uniques)))
        vmax = int(math.ceil(np.max(uniques)))
        if vmin < vmax:
            a, b = st.slider(label, min_value=vmin, max_value=vmax, value=(vmin, vmax))
            return series.between(a, b), True
    # Sinon, pas de slider (pour éviter StreamlitAPIException)
    st.caption(f"*(Pas assez de valeurs numériques distinctes pour « {label} » — filtre désactivé)*")
    return None, False

# ========= Couleur de thème = depuis le logo =========
LOGO_PATH = get_existing_path(LOGO_CANDIDATES)
THEME_BLUE = get_dominant_color(LOGO_PATH) if LOGO_PATH else THEME_BLUE_DEFAULT

# =========================
# CSS (fond identique + logo en haut + volet non rétractable)
# =========================
st.markdown(
    f"""
    <style>
      /* Sidebar: fond EXACT du logo */
      [data-testid="stSidebar"] {{
        background: {THEME_BLUE};
        padding-top: 0 !important;
      }}
      /* Logo collé en haut */
      [data-testid="stSidebar"] .sidebar-logo-wrap {{
        padding: 12px 12px 6px 12px;
      }}
      /* Masquer le bouton de repli de la sidebar */
      [data-testid="collapsedControl"] {{ display:none !important; }}
      .block-container {{
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1400px;
      }}
      .ref-banner {{
        background:{THEME_BLUE}; color:white; padding:8px 12px; border-radius:10px; display:inline-block;
        font-weight:600; letter-spacing:.2px;
      }}
      .badge-new {{
        background:{THEME_COPPER}; color:white; padding:2px 8px; border-radius:999px; margin-left:8px;
        font-size:12px; font-weight:600;
      }}
      .field-label {{ color:#333; font-weight:600; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# DATA
# =========================
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

# Numériques pour filtres
df["_surface_num"] = df[col_surface].apply(coerce_number) if col_surface in df.columns else np.nan
df["_loyer_num"]   = df[col_loyer].apply(coerce_number)   if col_loyer   in df.columns else np.nan
df["_pp_num"]      = df[col_pp].apply(coerce_number)      if col_pp      in df.columns else np.nan

# =========================
# SIDEBAR : LOGO seul en haut
# =========================
with st.sidebar:
    st.markdown("<div class='sidebar-logo-wrap'>", unsafe_allow_html=True)
    if LOGO_PATH:
        st.image(LOGO_PATH, use_container_width=True)
    else:
        st.markdown("<h3 style='color:white; text-align:center;'>SMBG CONSEIL</h3>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# ENTÊTE
# =========================
st.markdown("## SMBG Carte — Sélection d’annonces")

# =========================
# FILTRES (contenu principal)
# =========================
with st.expander("Filtres", expanded=True):
    filtered = df.copy()

    # Régions (dynamiques)
    if col_region and col_region in df.columns:
        reg_counts = df.groupby(col_region).size().sort_values(ascending=False)
        reg_options = [f"{r} ({n})" for r, n in reg_counts.items()]
        sel_regs = st.multiselect("Régions", reg_options, placeholder="Choisir…")
        if sel_regs:
            keep_regs = {x.split(" (")[0] for x in sel_regs}
            filtered = filtered[filtered[col_region].isin(keep_regs)]

    # Départements (dépend des régions)
    if col_dept and col_dept in df.columns:
        dept_counts = filtered.groupby(col_dept).size().sort_values(ascending=False)
        dept_options = [f"{d} ({n})" for d, n in dept_counts.items()]
        sel_depts = st.multiselect("Départements", dept_options, placeholder="Choisir…")
        if sel_depts:
            keep_depts = {x.split(" (")[0] for x in sel_depts}
            filtered = filtered[filtered[col_dept].isin(keep_depts)]

    st.markdown("---")

    # Surface (m²) — safe slider
    if "_surface_num" in filtered.columns:
        mask_s, used_s = safe_slider_num(filtered["_surface_num"], "Surface (m²)")
        if used_s and mask_s is not None:
            filtered = filtered[mask_s | filtered["_surface_num"].isna()]

    # Loyer (€) — safe slider + "Demander le loyer"
    incl_demander = False
    has_demander = col_loyer and filtered[col_loyer].astype(str).str.contains("demander", case=False, na=False).any()
    if "_loyer_num" in filtered.columns:
        mask_l, used_l = safe_slider_num(filtered["_loyer_num"], "Loyer mensuel (€)")
        incl_demander = st.checkbox("Inclure les annonces « Demander le loyer »", value=True) if has_demander else False
        if used_l and mask_l is not None:
            mask_dem = pd.Series(False, index=filtered.index)
            if incl_demander and col_loyer:
                mask_dem = filtered[col_loyer].astype(str).str.contains("demander", case=False, na=False)
            filtered = filtered[mask_l | (incl_demander & mask_dem) | filtered["_loyer_num"].isna()]

    # Pas de porte / DAB (€) — safe slider + "Uniquement Néant"
    only_neant = False
    has_neant = col_pp and filtered[col_pp].astype(str).str.fullmatch(r"(?i)\s*néant\s*", na=False).any()
    if "_pp_num" in filtered.columns:
        mask_p, used_p = safe_slider_num(filtered["_pp_num"], "Pas de porte / Droit au bail (€)")
        only_neant = st.checkbox("Uniquement « Néant »", value=False) if has_neant else False
        if used_p and mask_p is not None:
            mask_neant = pd.Series(False, index=filtered.index)
            if only_neant and col_pp:
                mask_neant = filtered[col_pp].astype(str).str.fullmatch(r"(?i)\s*néant\s*", na=False)
                filtered = filtered[mask_neant]
            else:
                if col_pp:
                    mask_neant = filtered[col_pp].astype(str).str.fullmatch(r"(?i)\s*néant\s*", na=False)
                filtered = filtered[mask_p | mask_neant | filtered["_pp_num"].isna()]

    st.caption(f"**{len(filtered)}** annonces après filtres.")

# =========================
# LAYOUT : Carte large + Volet droit rétractable
# =========================
col_map, col_detail = st.columns([7, 5], gap="large")

with col_map:
    if col_lat and col_lon and col_lat in filtered.columns and col_lon in filtered.columns:
        df_map = filtered.dropna(subset=[col_lat, col_lon]).copy()
    else:
        df_map = filtered.iloc[0:0].copy()

    if not df_map.empty:
        center = [df_map[col_lat].astype(float).mean(), df_map[col_lon].astype(float).mean()]
    else:
        center = [46.6, 2.5]

    m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")

    st.session_state.setdefault("selected_idx", None)

    for idx, row in df_map.iterrows():
        popup_ref = str(row[col_ref]) if col_ref else f"Annonce {idx}"
        folium.Marker(
            location=[float(row[col_lat]), float(row[col_lon])],
            tooltip=popup_ref,
            popup=popup_ref
        ).add_to(m)

    st_folium(m, height=650, width=None)

    # Sélecteur manuel d’annonce (fiable pour piloter le volet droit)
    with st.expander("Sélectionner une annonce (si besoin)"):
        if col_ref and col_ref in filtered.columns:
            ref_series = filtered[col_ref].astype(str)
            choice = st.selectbox("Référence annonce :", options=list(ref_series.index),
                                  format_func=lambda i: ref_series.loc[i] if i in ref_series.index else str(i))
        else:
            choice = st.selectbox("Annonce :", options=list(filtered.index), format_func=lambda i: f"Annonce {i}")
        st.session_state["selected_idx"] = choice

with col_detail:
    show_details = st.toggle("Afficher le volet de détails", value=True)
    if show_details:
        selected_idx = st.session_state.get("selected_idx")
        if selected_idx is None or selected_idx not in filtered.index:
            if not filtered.empty:
                selected_idx = filtered.index[0]

        if selected_idx is not None and selected_idx in filtered.index:
            row = filtered.loc[selected_idx]

            # Bannière Référence
            ref_val = str(row.get(col_ref, f"Annonce {selected_idx}"))
            st.markdown(f"<span class='ref-banner'>Référence annonce : {ref_val}</span>", unsafe_allow_html=True)

            # Badge "Nouveau"
            if col_date_pub and col_date_pub in filtered.columns and pd.notna(row.get(col_date_pub, None)):
                try:
                    d = pd.to_datetime(row[col_date_pub], dayfirst=True, errors="coerce")
                    if pd.notna(d) and (pd.Timestamp.now().tz_localize(None) - d.to_pydatetime().replace(tzinfo=None) <= pd.Timedelta(days=30)):
                        st.markdown("<span class='badge-new'>Nouveau</span>", unsafe_allow_html=True)
                except:
                    pass

            st.write("")

            # Bouton Google Maps
            if col_maps and col_maps in filtered.columns and not is_empty_val(row.get(col_maps, None)):
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
        else:
            st.info("Aucune annonce sélectionnée.")

st.caption(f"{len(filtered)} annonces affichées.")

import os
import re
import math
import datetime as dt
from typing import Optional

import pandas as pd
import numpy as np
import streamlit as st

from streamlit_folium import st_folium
import folium

# =========================
# THEME & BRANDING
# =========================
THEME_BLUE   = "#0B2D3F"   # Bleu identique au logo
THEME_COPPER = "#B87333"   # Accent cuivré

LOGO_BLEU_PATHS = [
    "Logo bleu.png", "assets/Logo bleu.png", "static/Logo bleu.png",
    "data/Logo bleu.png", "images/Logo bleu.png"
]

st.set_page_config(page_title="SMBG Carte — Sélection d’annonces", layout="wide")

# CSS global : sidebar fond bleu, container large, styles badges/bannière
st.markdown(
    f"""
    <style>
      [data-testid="stSidebar"] {{
        background: {THEME_BLUE};
      }}
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
# UTILS
# =========================
@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    """
    Charge l'Excel depuis, dans cet ordre :
    1) 'annonces.xlsx' (racine ou data/)
    2) st.secrets['EXCEL_URL'] (URL raw, ex: GitHub)
    3) os.environ['EXCEL_URL']
    """
    candidates = ["annonces.xlsx", "data/annonces.xlsx"]
    for p in candidates:
        if os.path.exists(p):
            return pd.read_excel(p)

    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    if url:
        return pd.read_excel(url)

    st.error("Aucun Excel trouvé. Place ‘annonces.xlsx’ dans le repo ou définis EXCEL_URL (secrets ou env).")
    return pd.DataFrame()

def find_col(df: pd.DataFrame, *keywords) -> Optional[str]:
    """Retourne la première colonne dont le nom contient tous les keywords (insensible à la casse)."""
    low = {c: c.lower() for c in df.columns}
    for c, lc in low.items():
        if all(k.lower() in lc for k in keywords):
            return c
    return None

def coerce_number(x):
    """Convertit proprement en nombre (retire €, espaces, etc.). NaN si 'Demander le loyer' ou non numérique."""
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

# =========================
# DATA
# =========================
df = load_excel()
if df.empty:
    st.stop()

# Colonnes clefs (robustes aux intitulés)
col_region = find_col(df, "région") or find_col(df, "region")
col_dept   = find_col(df, "département") or find_col(df, "departement")
col_lat    = find_col(df, "lat")
col_lon    = find_col(df, "lon") or find_col(df, "lng")
col_ref    = find_col(df, "référence","annonce") or find_col(df, "reference","annonce")
col_maps   = find_col(df, "google","map") or find_col(df, "lien","map")
col_actif  = find_col(df, "actif")
col_surface = find_col(df, "surface")
col_loyer   = find_col(df, "loyer")
col_pp      = find_col(df, "pas de porte") or find_col(df, "droit au bail") or find_col(df, "cession")
col_date_pub = find_col(df, "publication") or find_col(df, "publi")

# Afficher uniquement Actif = oui
if col_actif and col_actif in df.columns:
    df = df[df[col_actif].apply(is_truthy_yes)].copy()

# Colonnes numériques pour filtres
df["_surface_num"] = df[col_surface].apply(coerce_number) if col_surface in df.columns else np.nan
df["_loyer_num"]   = df[col_loyer].apply(coerce_number)   if col_loyer   in df.columns else np.nan
df["_pp_num"]      = df[col_pp].apply(coerce_number)      if col_pp      in df.columns else np.nan

# =========================
# SIDEBAR = LOGO SEUL (non rétractable)
# =========================
with st.sidebar:
    shown = False
    for p in LOGO_BLEU_PATHS:
        if os.path.exists(p):
            st.image(p, use_container_width=True)
            shown = True
            break
    if not shown:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("<h3 style='color:white; text-align:center;'>SMBG CONSEIL</h3>", unsafe_allow_html=True)

# =========================
# ENTÊTE
# =========================
st.markdown("## SMBG Carte — Sélection d’annonces")

# =========================
# FILTRES (contenu principal, pas dans la sidebar)
# =========================
with st.expander("Filtres", expanded=True):
    filtered = df.copy()

    # ---- Régions (dynamiques avec compteurs)
    if col_region and col_region in df.columns:
        reg_counts = df.groupby(col_region).size().sort_values(ascending=False)
        reg_options = [f"{r} ({n})" for r, n in reg_counts.items()]
        sel_regs = st.multiselect("Régions", reg_options, placeholder="Choisir…")
        if sel_regs:
            keep_regs = {x.split(" (")[0] for x in sel_regs}
            filtered = filtered[filtered[col_region].isin(keep_regs)]

    # ---- Départements (dépend de la sélection région)
    if col_dept and col_dept in df.columns:
        dept_counts = filtered.groupby(col_dept).size().sort_values(ascending=False)
        dept_options = [f"{d} ({n})" for d, n in dept_counts.items()]
        sel_depts = st.multiselect("Départements", dept_options, placeholder="Choisir…")
        if sel_depts:
            keep_depts = {x.split(" (")[0] for x in sel_depts}
            filtered = filtered[filtered[col_dept].isin(keep_depts)]

    st.markdown("---")

    # ---- Surface (m²)
    if pd.notna(filtered["_surface_num"]).any():
        smin = int(math.floor(filtered["_surface_num"].min()))
        smax = int(math.ceil(filtered["_surface_num"].max()))
        smin, smax = st.slider("Surface (m²)", min_value=smin, max_value=smax, value=(smin, smax))
        filtered = filtered[filtered["_surface_num"].between(smin, smax) | filtered["_surface_num"].isna()]

    # ---- Loyer (€) + "Demander le loyer"
    incl_demander = False
    has_demander = col_loyer and filtered[col_loyer].astype(str).str.contains("demander", case=False, na=False).any()
    if pd.notna(filtered["_loyer_num"]).any() or has_demander:
        if pd.notna(filtered["_loyer_num"]).any():
            lmin = int(math.floor(filtered["_loyer_num"].min()))
            lmax = int(math.ceil(filtered["_loyer_num"].max()))
            lmin, lmax = st.slider("Loyer mensuel (€)", min_value=lmin, max_value=lmax, value=(lmin, lmax))
            mask_num = filtered["_loyer_num"].between(lmin, lmax)
        else:
            mask_num = pd.Series(False, index=filtered.index)

        incl_demander = st.checkbox("Inclure les annonces « Demander le loyer »", value=True)
        mask_dem = pd.Series(False, index=filtered.index)
        if col_loyer:
            mask_dem = filtered[col_loyer].astype(str).str.contains("demander", case=False, na=False)

        filtered = filtered[mask_num | (incl_demander & mask_dem) | filtered["_loyer_num"].isna()]

    # ---- Pas de porte / Droit au bail (€) + "Uniquement Néant"
    only_neant = False
    has_neant = col_pp and filtered[col_pp].astype(str).str.fullmatch(r"(?i)\s*néant\s*", na=False).any()
    if pd.notna(filtered["_pp_num"]).any() or has_neant:
        if pd.notna(filtered["_pp_num"]).any():
            pmin = int(math.floor(filtered["_pp_num"].min()))
            pmax = int(math.ceil(filtered["_pp_num"].max()))
            pmin, pmax = st.slider("Pas de porte / Droit au bail (€)", min_value=pmin, max_value=pmax, value=(pmin, pmax))
            mask_pp = filtered["_pp_num"].between(pmin, pmax)
        else:
            mask_pp = pd.Series(False, index=filtered.index)

        only_neant = st.checkbox("Uniquement « Néant »", value=False)
        mask_neant = pd.Series(False, index=filtered.index)
        if col_pp:
            mask_neant = filtered[col_pp].astype(str).str.fullmatch(r"(?i)\s*néant\s*", na=False)

        if only_neant:
            filtered = filtered[mask_neant]
        else:
            filtered = filtered[mask_pp | mask_neant | filtered["_pp_num"].isna()]

    st.caption(f"**{len(filtered)}** annonces après filtres.")

# =========================
# LAYOUT : Carte large + Volet droit rétractable
# =========================
col_map, col_detail = st.columns([7, 5], gap="large")

# --- CARTE (sans cluster) ---
with col_map:
    if col_lat and col_lon and col_lat in filtered.columns and col_lon in filtered.columns:
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
        popup_ref = str(row[col_ref]) if col_ref else f"Annonce {idx}"
        folium.Marker(
            location=[float(row[col_lat]), float(row[col_lon])],
            tooltip=popup_ref,
            popup=popup_ref
        ).add_to(m)

    st_folium(m, height=650, width=None)

    # Sélecteur manuel (pratique pour piloter le volet droit)
    with st.expander("Sélectionner une annonce (si besoin)"):
        if col_ref and col_ref in filtered.columns:
            ref_series = filtered[col_ref].astype(str)
            choice = st.selectbox("Référence annonce :", options=list(ref_series.index), format_func=lambda i: ref_series.loc[i] if i in ref_series.index else str(i))
        else:
            choice = st.selectbox("Annonce :", options=list(filtered.index), format_func=lambda i: f"Annonce {i}")
        st.session_state["selected_idx"] = choice

# --- VOLET DROIT (rétractable) ---
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

            # Bouton Google Maps (H -> bouton “Cliquer ici”)
            if col_maps and col_maps in filtered.columns and not is_empty_val(row.get(col_maps, None)):
                st.link_button("Cliquer ici", str(row[col_maps]).strip(), type="primary")

            st.write("")

            # Champs métier (G→AF logiquement) : on exclut techniques & colonnes déjà traitées
            technical_keywords = ["lat","lon","géocod","geocod","date géocod","photo","actif","internal","technique"]
            technical_like = {c for c in df.columns if any(k in c.lower() for k in technical_keywords)}
            to_hide_exact = {col_maps, col_lat, col_lon, col_actif, col_date_pub, col_ref}
            candidates = [c for c in df.columns if c not in technical_like and c not in to_hide_exact]

            for c in candidates:
                v = row.get(c, None)
                if is_empty_val(v):
                    continue
                # Mise en forme conviviale pour surface / loyer / pp
                if c == col_surface and pd.notna(row["_surface_num"]):
                    st.markdown(f"**{c}** : {int(round(row['_surface_num']))} m²")
                elif c == col_loyer and pd.notna(row["_loyer_num"]):
                    st.markdown(f"**{c}** : {pretty_k_eur(row['_loyer_num'])}")
                elif c == col_pp and pd.notna(row["_pp_num"]):
                    st.markdown(f"**{c}** : {pretty_k_eur(row['_pp_num'])}")
                else:
                    st.markdown(f"**{c}** : {v}")
        else:
            st.info("Aucune annonce sélectionnée.")

# Compteur global
st.caption(f"{len(filtered)} annonces affichées.")

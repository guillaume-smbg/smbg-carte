import os
import io
import re
import math
import datetime as dt
from typing import List, Optional

import pandas as pd
import numpy as np
import streamlit as st

# Carte
from streamlit_folium import st_folium
import folium
from folium.plugins import MarkerCluster

# =========================
# THEME & BRANDING
# =========================
THEME_BLUE = "#0B2D3F"   # Bleu du logo (ajuste si besoin)
THEME_COPPER = "#B87333" # Accent cuivré
LOGO_BLEU_PATHS = [
    "Logo bleu.png", "assets/Logo bleu.png", "static/Logo bleu.png",
    "data/Logo bleu.png", "images/Logo bleu.png"
]

st.set_page_config(page_title="SMBG Carte — Sélection d’annonces", layout="wide")

# CSS: sidebar pleine hauteur + fond bleu + centrage logo
st.markdown(
    f"""
    <style>
      [data-testid="stSidebar"] {{
        background: {THEME_BLUE};
      }}
      /* Enlever padding horizontal de la page pour agrandir la carte */
      .block-container {{
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1400px;
      }}
      /* Bannières / badges */
      .ref-banner {{
        background:{THEME_BLUE}; color:white; padding:8px 12px; border-radius:10px; display:inline-block;
        font-weight:600; letter-spacing:.2px;
      }}
      .badge-new {{
        background:{THEME_COPPER}; color:white; padding:2px 8px; border-radius:999px; margin-left:8px;
        font-size:12px; font-weight:600;
      }}
      .field-label {{
        color:#333; font-weight:600;
      }}
      .gmaps-btn > a {{
        text-decoration:none !important;
      }}
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
    1) un fichier local 'annonces.xlsx' à la racine du repo (ou 'data/annonces.xlsx')
    2) st.secrets['EXCEL_URL'] (URL raw GitHub)
    3) os.environ['EXCEL_URL']
    """
    candidates = ["annonces.xlsx", "data/annonces.xlsx"]
    for p in candidates:
        if os.path.exists(p):
            return pd.read_excel(p)

    url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    if url:
        # stream via pandas
        return pd.read_excel(url)

    st.error("Aucun fichier Excel trouvé. Place ‘annonces.xlsx’ dans le repo ou définis EXCEL_URL dans secrets.")
    return pd.DataFrame()

def find_col(df: pd.DataFrame, *keywords) -> Optional[str]:
    """Trouve la première colonne dont le nom contient tous les keywords (insensibles à la casse)."""
    low = {c: c.lower() for c in df.columns}
    for c, lc in low.items():
        if all(k.lower() in lc for k in keywords):
            return c
    return None

def coerce_number(x):
    """Convertit proprement en nombre (retire €, espaces, etc.). Renvoie NaN si non numérique classique."""
    if pd.isna(x):
        return np.nan
    s = str(x).strip()
    if s == "" or s in {"/", "-", "—"}:
        return np.nan
    # Cas textuels connus
    if "demander" in s.lower():
        return np.nan  # traité via case à cocher
    if s.lower() == "néant":
        return 0
    # Retirer tout sauf chiffres, virgule, point et signe -
    s = re.sub(r"[^\d,.\-]", "", s)
    # Remplacer virgule par point si besoin
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return np.nan

def is_truthy_yes(x):
    return str(x).strip().lower() in {"oui","yes","true","1","y"}

def pretty_k(x):
    try:
        x = float(x)
    except:
        return "-"
    if x >= 1_000_000:
        return f"{int(round(x/1_000_000))} M€"
    if x >= 1_000:
        return f"{int(round(x/1_000))} k€"
    return f"{int(round(x))} €"

# =========================
# DATA
# =========================
df = load_excel()
if df.empty:
    st.stop()

# Colonnes clefs (robustes aux variations d’intitulés)
col_region = find_col(df, "région") or find_col(df, "region")
col_dept   = find_col(df, "département") or find_col(df, "departement")
col_lat    = find_col(df, "lat")
col_lon    = find_col(df, "lon") or find_col(df, "lng")
col_ref    = find_col(df, "référence","annonce") or find_col(df, "reference","annonce")
col_maps   = find_col(df, "google","map") or find_col(df, "lien","map")
col_actif  = find_col(df, "actif")

# Numériques pour filtres
col_surface = find_col(df, "surface")  # ex: "Surface", "Surface utile", "Surface GLA" — on prendra la plus globale
col_loyer   = find_col(df, "loyer")
col_pp      = find_col(df, "pas de porte") or find_col(df, "droit au bail") or find_col(df, "cession")

# Dates publication (pour badge Nouveau)
col_date_pub = find_col(df, "publication") or find_col(df, "publi")

# Colonnes techniques AG→AM (on veillera à ne pas les afficher en mode client)
# Ici on s’appuie sur leurs noms détectés (lat/lon/réf/actif), le reste est ignoré côté UI.

# Filtrer Actif = oui
if col_actif and col_actif in df.columns:
    df = df[df[col_actif].apply(is_truthy_yes)].copy()

# Préparer colonnes numériques pour filtres
if col_surface and col_surface in df.columns:
    df["_surface_num"] = df[col_surface].apply(coerce_number)
else:
    df["_surface_num"] = np.nan

if col_loyer and col_loyer in df.columns:
    df["_loyer_num"] = df[col_loyer].apply(coerce_number)
else:
    df["_loyer_num"] = np.nan

if col_pp and col_pp in df.columns:
    df["_pp_num"] = df[col_pp].apply(coerce_number)
else:
    df["_pp_num"] = np.nan

# =========================
# SIDEBAR = LOGO SEUL
# =========================
with st.sidebar:
    # Tenter d’afficher le logo bleu
    logo_shown = False
    for p in LOGO_BLEU_PATHS:
        if os.path.exists(p):
            st.image(p, use_container_width=True)
            logo_shown = True
            break
    if not logo_shown:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("<h3 style='color:white; text-align:center;'>SMBG CONSEIL</h3>", unsafe_allow_html=True)

# =========================
# ENTÊTE
# =========================
c1, = st.columns([1])
with c1:
    st.markdown("## SMBG Carte — Sélection d’annonces")

# =========================
# BARRE DE FILTRES (dans le contenu principal)
# =========================
with st.expander("Filtres", expanded=True):
    # Filtres Région / Département (dynamiques)
    filtered = df.copy()
    if col_region and col_region in df.columns:
        # Compteurs dynamiques
        reg_counts = df.groupby(col_region).size().sort_values(ascending=False)
        reg_options = [f"{r} ({n})" for r, n in reg_counts.items()]
        sel_regs = st.multiselect("Régions", reg_options, placeholder="Choisir…")
        if sel_regs:
            keep_regs = {x.split(" (")[0] for x in sel_regs}
            filtered = filtered[filtered[col_region].isin(keep_regs)]

    if col_dept and col_dept in df.columns:
        dept_counts = filtered.groupby(col_dept).size().sort_values(ascending=False)
        dept_options = [f"{d} ({n})" for d, n in dept_counts.items()]
        sel_depts = st.multiselect("Départements", dept_options, placeholder="Choisir…")
        if sel_depts:
            keep_depts = {x.split(" (")[0] for x in sel_depts}
            filtered = filtered[filtered[col_dept].isin(keep_depts)]

    # Filtres numériques
    st.markdown("---")

    # Surface
    if filtered["_surface_num"].notna().any():
        smin = math.floor(filtered["_surface_num"].min())
        smax = math.ceil(filtered["_surface_num"].max())
        smin, smax = st.slider("Surface (m²)", min_value=smin, max_value=smax, value=(smin, smax))
        filtered = filtered[filtered["_surface_num"].between(smin, smax) | filtered["_surface_num"].isna()]

    # Loyer
    incl_demander = False
    if filtered["_loyer_num"].notna().any() or (col_loyer and filtered[col_loyer].astype(str).str.contains("demander", case=False, na=False).any()):
        # bornes sur les valeurs numériques
        if filtered["_loyer_num"].notna().any():
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

    # Pas de porte / Droit au bail
    only_neant = False
    if filtered["_pp_num"].notna().any() or (col_pp and filtered[col_pp].astype(str).str.fullmatch(r"(?i)\s*néant\s*", na=False).any()):
        if filtered["_pp_num"].notna().any():
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
# LAYOUT PRINCIPAL : Carte large + volet droit rétractable
# =========================
col_map, col_detail = st.columns([7, 5], gap="large")

# --- Carte ---
with col_map:
    # Centre de la carte (moyenne des points valides), sinon France
    df_map = filtered.dropna(subset=[col_lat, col_lon]) if (col_lat and col_lon) else filtered.iloc[0:0]
    if not df_map.empty:
        center = [df_map[col_lat].astype(float).mean(), df_map[col_lon].astype(float).mean()]
    else:
        center = [46.6, 2.5]

    m = folium.Map(location=center, zoom_start=6, control_scale=True, tiles="OpenStreetMap")
    cluster = MarkerCluster().add_to(m)

    # Clé d'index pour sélectionner
    st.session_state.setdefault("selected_idx", None)

    for idx, row in df_map.iterrows():
        popup_ref = str(row[col_ref]) if col_ref else f"Annonce {idx}"
        folium.Marker(
            location=[float(row[col_lat]), float(row[col_lon])],
            tooltip=popup_ref,
            popup=popup_ref
        ).add_to(cluster)

    out = st_folium(m, height=650, width=None)
    # Sélection via popup/clique : streamlit-folium ne remonte pas l’index de façon stable.
    # On ajoute une petite liste pour sélectionner manuellement l’annonce visible (option pratique).
    with st.expander("Sélectionner une annonce (si besoin)"):
        ref_series = (filtered[col_ref].astype(str) if col_ref else pd.Series([f"Annonce {i}" for i in filtered.index], index=filtered.index))
        choice = st.selectbox("Référence annonce :", options=list(ref_series.index), format_func=lambda i: ref_series.loc[i] if i in ref_series.index else str(i))
        st.session_state["selected_idx"] = choice

# --- Volet droit (rétractable) ---
with col_detail:
    show_details = st.toggle("Afficher le volet de détails", value=True)
    if show_details:
        selected_idx = st.session_state.get("selected_idx", None)
        # Par défaut : premier résultat filtré
        if selected_idx is None or selected_idx not in filtered.index:
            if not filtered.empty:
                selected_idx = filtered.index[0]

        if selected_idx is not None and selected_idx in filtered.index:
            row = filtered.loc[selected_idx]
            # Bannière Référence + badge Nouveau
            ref_val = str(row.get(col_ref, f"Annonce {selected_idx}"))
            st.markdown(f"<span class='ref-banner'>Référence annonce : {ref_val}</span>", unsafe_allow_html=True)

            # Badge "Nouveau" si date récente
            if col_date_pub and pd.notna(row.get(col_date_pub, None)):
                try:
                    d = pd.to_datetime(row[col_date_pub], dayfirst=True, errors="coerce")
                    if pd.notna(d) and (pd.Timestamp.now().tz_localize(None) - d.to_pydatetime().replace(tzinfo=None) <= pd.Timedelta(days=30)):
                        st.markdown("<span class='badge-new'>Nouveau</span>", unsafe_allow_html=True)
                except:
                    pass

            st.write("")  # espace

            # Bouton Google Maps
            if col_maps and pd.notna(row.get(col_maps, None)) and str(row[col_maps]).strip() not in {"", "-", "/"}:
                url = str(row[col_maps]).strip()
                st.link_button("Cliquer ici", url, type="primary")

            st.write("")

            # Affichage des champs G→AF dans l’ordre :
            # Comme on n’a pas les lettres ici, on affiche toutes les colonnes "métier" en filtrant :
            technical_like = {c for c in df.columns if any(k in c.lower() for k in ["lat","lon","géocod","geocod","date","photo","actif","reference","référence"])}
            to_hide_exact = {col_maps, col_lat, col_lon, col_actif, col_date_pub}
            candidates = [c for c in df.columns if c not in technical_like and c not in to_hide_exact]

            def is_empty_val(v):
                if pd.isna(v): return True
                s = str(v).strip()
                return s == "" or s in {"/", "-", "—"}

            for c in candidates:
                v = row.get(c, None)
                if is_empty_val(v):
                    continue
                label = c
                # Mise en forme propre pour certains champs
                if c == col_loyer and pd.notna(row["_loyer_num"]):
                    st.markdown(f"**{label}** : {pretty_k(row['_loyer_num'])}")
                elif c == col_pp and pd.notna(row["_pp_num"]):
                    st.markdown(f"**{label}** : {pretty_k(row['_pp_num'])}")
                elif c == col_surface and pd.notna(row["_surface_num"]):
                    st.markdown(f"**{label}** : {int(round(row['_surface_num']))} m²")
                else:
                    st.markdown(f"**{label}** : {v}")

        else:
            st.info("Aucune annonce sélectionnée.")

# Pied de page compteur
st.caption(f"{len(filtered)} annonces affichées.")

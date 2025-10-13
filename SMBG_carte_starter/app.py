import os
import streamlit as st
import pandas as pd
import requests
import yaml

st.set_page_config(page_title="SMBG Carte", layout="wide")

# Chargement config
with open("schema.yaml", "r", encoding="utf-8") as f:
    SCHEMA = yaml.safe_load(f)

EXCEL_URL = os.environ.get("EXCEL_URL") or st.secrets.get("EXCEL_URL", "")
R2_BASE_URL = os.environ.get("R2_BASE_URL") or st.secrets.get("R2_BASE_URL", "")
DEFAULT_MODE = SCHEMA.get("modes", {}).get("default_mode", "client")

# Paramètre d'URL pour le mode
qs_mode = st.query_params.get("mode", [DEFAULT_MODE])
MODE = qs_mode if isinstance(qs_mode, str) else (qs_mode[0] if qs_mode else DEFAULT_MODE)
if MODE not in ("client", "interne"):
    MODE = DEFAULT_MODE

st.sidebar.markdown(f"**Mode :** `{MODE}`")

# Helpers
def load_excel(url: str) -> pd.DataFrame:
    if not url:
        st.error("EXCEL_URL manquant (secret).")
        st.stop()
    return pd.read_excel(url, engine="openpyxl")

def excel_letter_to_index(letter: str) -> int:
    # 'A' -> 0, 'B' -> 1, ... 'AA' -> 26 ...
    s = 0
    for c in letter.upper():
        s = s*26 + (ord(c) - 64)
    return s - 1

def slice_by_letters(df: pd.DataFrame, start_letter: str, end_letter: str) -> pd.DataFrame:
    start_idx = excel_letter_to_index(start_letter)
    end_idx = excel_letter_to_index(end_letter)
    return df.iloc[:, start_idx:end_idx+1]

def clean_value(v):
    if pd.isna(v):
        return ""
    return str(v).strip()

def value_is_hidden(v) -> bool:
    v = clean_value(v)
    return v in set(SCHEMA["right_panel"]["hide_values"])

# Load data
df_raw = load_excel(EXCEL_URL)

# Build useful slices
right_range = SCHEMA["right_panel"]["range_excel"]
start_letter, end_letter = right_range.split(":")
df_right = slice_by_letters(df_raw, start_letter, end_letter).copy()

# Technical columns mapping (by letters)
lat_col = excel_letter_to_index(SCHEMA["technical_columns"]["latitude"])
lon_col = excel_letter_to_index(SCHEMA["technical_columns"]["longitude"])
geost_col = excel_letter_to_index(SCHEMA["technical_columns"]["geocode_status"])
geodt_col = excel_letter_to_index(SCHEMA["technical_columns"]["geocode_date"])
ref_col = excel_letter_to_index(SCHEMA["technical_columns"]["reference"])
photos_col = excel_letter_to_index(SCHEMA["technical_columns"]["photos"])
active_col = excel_letter_to_index(SCHEMA["technical_columns"]["active"])

# Filter on Actif = oui
if active_col < len(df_raw.columns):
    actives = df_raw.iloc[:, active_col].fillna("").astype(str).str.strip().str.lower() == "oui"
    df = df_raw[actives].reset_index(drop=True)
else:
    df = df_raw.copy()

# Region / Departement detection
region_cols = [c for c in df.columns if c in SCHEMA["filters"]["region_column_names"] or "région" in str(c).lower() or "region" in str(c).lower()]
dept_cols = [c for c in df.columns if c in SCHEMA["filters"]["department_column_names"] or "départ" in str(c).lower() or "depart" in str(c).lower() or "dept" in str(c).lower()]

region_col = region_cols[0] if region_cols else None
dept_col = dept_cols[0] if dept_cols else None

# Sidebar filters
st.sidebar.header("Filtres")
regions_vals = []
depts_vals = []

if region_col:
    all_regions = sorted([r for r in df[region_col].dropna().astype(str).str.strip().unique().tolist() if r and r != "/"])
    regions_vals = st.sidebar.multiselect("Régions", options=all_regions, default=[])

# Restrict df by selected regions (if any)
df_filtered = df.copy()
if regions_vals and region_col:
    df_filtered = df_filtered[df_filtered[region_col].astype(str).str.strip().isin(regions_vals)]

if dept_col:
    all_depts = sorted([d for d in df_filtered[dept_col].dropna().astype(str).str.strip().unique().tolist() if d and d != "/"])
    depts_vals = st.sidebar.multiselect("Départements", options=all_depts, default=[])

# Final restriction by departments
if depts_vals and dept_col:
    df_filtered = df_filtered[df_filtered[dept_col].astype(str).str.strip().isin(depts_vals)]

# Display counts next to filters (simple note)
if region_col:
    st.sidebar.caption(f"{len(df_filtered)} annonces après filtre Région/Département")

# Main layout
left, right = st.columns([1.1, 1.9])

with left:
    st.subheader("Carte (placeholder)")
    st.info("La carte interactive sera affichée ici (OSM).")

    st.markdown("### Liste des annonces (filtres appliqués)")
    # Show a compact table with key info (Ref + Adresse si dispo)
    ref_series = df_filtered.iloc[:, ref_col] if ref_col < len(df_filtered.columns) else pd.Series([])
    # Attempt to get Address from within G..AF slice
    addr_idx = excel_letter_to_index("G")
    addr = df_filtered.iloc[:, addr_idx] if addr_idx < len(df_filtered.columns) else pd.Series([])
    mini = pd.DataFrame({
        "Référence": ref_series.astype(str) if not ref_series.empty else "",
        "Adresse": addr.astype(str) if not addr.empty else ""
    })
    st.dataframe(mini, use_container_width=True, hide_index=True)

with right:
    st.subheader("Volet droit (détails) — Aperçu")
    st.caption("Affiche G→AF dans l'ordre Excel (H devient un bouton 'Cliquer ici'). Les valeurs '/', '-' et vides sont masquées.")

    # Render the first 1-2 listings as preview
    preview_count = min(2, len(df_filtered))
    for i in range(preview_count):
        row = df_filtered.iloc[i]
        # Référence (banner)
        ref_val = clean_value(row.iloc[ref_col]) if ref_col < len(df_filtered.columns) else ""
        if ref_val:
            st.markdown(f"**Référence annonce : {ref_val}**")

        # Right panel fields (G..AF), skipping H
        start_idx = excel_letter_to_index("G")
        end_idx = excel_letter_to_index("AF")
        gmaps_idx = excel_letter_to_index(SCHEMA["right_panel"]["google_maps_column_letter"])

        for col_idx in range(start_idx, end_idx+1):
            header = df_filtered.columns[col_idx]
            val = row.iloc[col_idx]
            if col_idx == gmaps_idx:
                url = clean_value(val)
                if url and url != "/":
                    st.link_button(SCHEMA["branding"]["google_maps_button_label"], url, type="secondary")
                continue
            # Hide rent columns in client mode
            if MODE == "client" and df_filtered.columns[col_idx] in df_filtered.columns[list(map(excel_letter_to_index, SCHEMA["modes"]["rent_columns_letters"]))]:
                st.write(f"**{header}** : Demander le loyer")
                continue
            if value_is_hidden(val):
                continue
            st.write(f"**{header}** : {clean_value(val)}")

        st.divider()

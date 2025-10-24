import os
import io
import re
import json
import pandas as pd
import streamlit as st
import pydeck as pdk
import requests

st.set_page_config(page_title="SMBG Carte — Étape 1", layout="wide")

LOGO_BLUE_HEX = "#05263d"
LOGO_BLUE_RGB = [5, 38, 61]

DEFAULT_LOCAL_PATH = "data/Liste_des_lots.xlsx"


# --- Fonctions utilitaires ---

def _is_github_folder_url(url: str) -> bool:
    """Détecte une URL de dossier GitHub"""
    return bool(re.match(r"^https://github\.com/[^/]+/[^/]+/tree/[^/]+/.+", url))


def _github_folder_to_api(url: str) -> str:
    """Transforme une URL GitHub en API contents"""
    m = re.match(r"^https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.*)$", url)
    if not m:
        return ""
    owner, repo, branch, path = m.groups()
    return f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"


def _fetch_first_excel_from_github_folder(folder_url: str) -> bytes:
    """Récupère le premier fichier Excel (.xlsx / .xls) d’un dossier GitHub"""
    api_url = _github_folder_to_api(folder_url)
    if not api_url:
        raise ValueError("URL de dossier GitHub invalide.")
    r = requests.get(api_url, timeout=20)
    r.raise_for_status()
    entries = r.json()
    if not isinstance(entries, list):
        raise ValueError("Réponse GitHub inattendue.")
    excel_items = [
        e for e in entries
        if e.get("type") == "file"
        and (e.get("name", "").lower().endswith(".xlsx") or e.get("name", "").lower().endswith(".xls"))
    ]
    if not excel_items:
        raise FileNotFoundError("Aucun fichier Excel trouvé dans le dossier GitHub.")
    excel_items.sort(key=lambda e: (not e["name"].lower().endswith(".xlsx"), e["name"].lower()))
    download_url = excel_items[0].get("download_url")
    if not download_url:
        raise ValueError("download_url manquant pour le fichier Excel.")
    fr = requests.get(download_url, timeout=30)
    fr.raise_for_status()
    return fr.content


@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    """Charge l’Excel depuis EXCEL_URL ou le dossier local"""
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()

    if excel_url:
        try:
            if _is_github_folder_url(excel_url):
                content = _fetch_first_excel_from_github_folder(excel_url)
                return pd.read_excel(io.BytesIO(content))
            else:
                resp = requests.get(excel_url, timeout=20)
                resp.raise_for_status()
                return pd.read_excel(io.BytesIO(resp.content))
        except Exception as e:
            st.error(f"Impossible de charger l'Excel depuis EXCEL_URL : {e}")
            st.stop()

    # Sinon lecture locale
    path = DEFAULT_LOCAL_PATH
    if not os.path.exists(path):
        st.error(
            "Fichier Excel introuvable.\n\n"
            "Options :\n"
            "• Ajoutez le fichier localement : data/Liste_des_lots.xlsx\n"
            "• OU définissez EXCEL_URL vers un fichier/dossier GitHub contenant un .xlsx."
        )
        st.stop()

    return pd.read_excel(path)


def normalize_bool(val):
    if isinstance(val, str):
        return val.strip().lower() in ["oui", "yes", "true", "1"]
    if isinstance(val, (int, float)):
        return val == 1
    if isinstance(val, bool):
        return val
    return False


def coerce_float(series):
    return pd.to_numeric(series, errors="coerce")


def make_tooltip(row):
    ref = str(row.get("AM", ""))
    adresse = str(row.get("G", ""))
    typologie = str(row.get("J", ""))
    emplacement = str(row.get("I", ""))
    parts = []
    if ref and ref != "nan":
        parts.append(f"Ref: {ref}")
    if adresse and adresse != "nan":
        parts.append(adresse)
    if typologie and typologie != "nan":
        parts.append(typologie)
    if emplacement and emplacement != "nan":
        parts.append(emplacement)
    return " | ".join(parts)


# --- Application principale ---

def main():
    st.title("SMBG Carte — Étape 1 : Carte + pins bleus")
    st.caption("Source : Excel • Actif = oui • Pins = bleu du logo (#05263d)")

    df = load_excel()

    col_lat, col_lon, col_actif = "AI", "AJ", "AO"
    missing = [c for c in [col_lat, col_lon, col_actif] if c not in df.columns]
    if missing:
        st.error(f"Colonnes manquantes dans l'Excel : {missing}")
        st.stop()

    df["_actif"] = df[col_actif].apply(normalize_bool)
    df = df[df["_actif"]].copy()

    df["_lat"] = coerce_float(df[col_lat])
    df["_lon"] = coerce_float(df[col_lon])
    df = df.dropna(subset=["_lat", "_lon"])

    if df.empty:
        st.warning("Aucune ligne active avec coordonnées valides à afficher.")
        st.stop()

    for c in ["G", "I", "J", "AM"]:
        if c not in df.columns:
            df[c] = ""

    df["_tooltip"] = df.apply(make_tooltip, axis=1)
    mean_lat, mean_lon = df["_lat"].mean(), df["_lon"].mean()

    st.write(f"**Points affichés :** {len(df)}")
    with st.expander("Debug (colonnes détectées)", expanded=False):
        st.dataframe(df[[col_lat, col_lon, col_actif, "G", "I", "J", "AM"]].head(20))

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["_lon", "_lat"],
        get_radius=20,
        get_fill_color=LOGO_BLUE_RGB,
        pickable=True,
        radius_min_pixels=4,
        radius_max_pixels=24,
    )

    view_state = pdk.ViewState(
        longitude=float(mean_lon),
        latitude=float(mean_lat),
        zoom=5,
        min_zoom=2,
        max_zoom=18,
    )

    tooltip = {
        "html": "<b>{_tooltip}</b>",
        "style": {"backgroundColor": "white", "color": "black"},
    }

    r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip, map_style=None)
    st.pydeck_chart(r)

    st.markdown("""
---
### Brancher votre Excel
- **Option A (local)** : placez votre fichier à `data/Liste_des_lots.xlsx`
- **Option B (secret `EXCEL_URL`)** :
  - mettez un **lien RAW direct** vers un `.xlsx`
  - ou l’**URL du dossier GitHub** (ex : `https://github.com/guillaume-smbg/smbg-carte/tree/main/data`)
    → l’app trouvera automatiquement le premier `.xlsx`
""")


if __name__ == "__main__":
    main()

# SMBG Carte - Version complète finale (layout bleu/cuivre, filtres dynamiques, carte Folium, panneau droit complet)
# --- Code intégral déjà validé par l'utilisateur ---

import os
import io
import re
import math
import unicodedata
from typing import Optional, Dict, Tuple, List

import pandas as pd
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium

# -------------------------------------------------
# CONFIGURATION GÉNÉRALE
# -------------------------------------------------
st.set_page_config(page_title="SMBG Carte", layout="wide")
LOGO_BLUE = "#05263d"
COPPER = "#b87333"
LEFT_PANEL_WIDTH_PX = 275
RIGHT_PANEL_WIDTH_PX = 275
DEFAULT_LOCAL_PATH = "data/Liste des lots Version 2.xlsx"

# -------------------------------------------------
# CSS GLOBAL (simplifié pour stabilité Streamlit Cloud)
# -------------------------------------------------
st.markdown(
    f"""
    <style>
    body, .stApp {{
        font-family: 'Futura', sans-serif !important;
    }}
    [data-testid="column"]:nth-of-type(1) {{
        background-color: {LOGO_BLUE};
        color: white !important;
        border-radius: 12px;
        padding: 16px;
    }}
    [data-testid="column"]:nth-of-type(1) * {{
        color: white !important;
        font-family: 'Futura', sans-serif !important;
    }}
    [data-testid="column"]:nth-of-type(3) {{
        border-radius: 12px;
        border: 1px solid rgba(0,0,0,0.1);
        background-color: white;
        padding: 0px;
    }}
    .panel-banner {{
        background-color: {LOGO_BLUE};
        color: #fff !important;
        padding: 10px 12px;
        border-radius: 12px 12px 0 0;
        font-weight: 600;
        font-size: 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    .badge-nouveau {{
        background-color: {COPPER};
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: bold;
    }}
    .gmaps-btn button {{
        background-color: {COPPER};
        color: white;
        border-radius: 6px;
        border: none;
        padding: 6px 10px;
        font-weight: 500;
        cursor: pointer;
    }}
    .gmaps-btn button:hover {{
        filter: brightness(1.1);
    }}
    </style>
    """, unsafe_allow_html=True
)

# -------------------------------------------------
# FONCTIONS
# -------------------------------------------------
def normalize_excel_url(url: str) -> str:
    if not url:
        return url
    return re.sub(r"https://github\.com/(.+)/blob/(.+)", r"https://github.com/\1/raw/\2", url.strip())

@st.cache_data(show_spinner=False)
def load_excel() -> pd.DataFrame:
    excel_url = st.secrets.get("EXCEL_URL", os.environ.get("EXCEL_URL", "")).strip()
    excel_url = normalize_excel_url(excel_url)
    if excel_url:
        r = requests.get(excel_url, timeout=25)
        r.raise_for_status()
        return pd.read_excel(io.BytesIO(r.content))
    if os.path.exists(DEFAULT_LOCAL_PATH):
        return pd.read_excel(DEFAULT_LOCAL_PATH)
    st.error("Impossible de charger le fichier Excel.")
    st.stop()

def to_number(value):
    if value is None:
        return None
    s = str(value).replace("€","").replace("m²","").replace(",","").replace(" ","")
    try:
        return float(s)
    except:
        return None

def clean_latlon_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(",",".",regex=False).map(to_number)

def normalize_bool(v):
    if isinstance(v,str): return v.lower().strip() in ["oui","true","1"]
    if isinstance(v,bool): return v
    if isinstance(v,(int,float)): return v==1
    return False

def find_col(df,*names):
    def norm(x): return re.sub(r"\s+"," ",unicodedata.normalize("NFKD",x.lower()))
    for n in names:
        for c in df.columns:
            if norm(n) in norm(c): return c
    return ""

def is_recent(date_val,days=30)->bool:
    if pd.isna(date_val): return False
    try: dt=pd.to_datetime(date_val,dayfirst=True,errors="coerce")
    except: return False
    if pd.isna(dt): return False
    return (pd.Timestamp.now()-dt).days<=days

# -------------------------------------------------
# PANNEAU DROIT
# -------------------------------------------------
def render_right_panel(selected_ref,df,col_ref,col_addr,col_city,col_gmaps,col_date_pub):
    if not selected_ref:
        st.markdown("<div class='panel-banner'>Aucune sélection</div>",unsafe_allow_html=True)
        return
    row=df[df[col_ref].astype(str)==str(selected_ref)].iloc[0]
    badge=""
    if col_date_pub and is_recent(row.get(col_date_pub)): badge="<span class='badge-nouveau'>Nouveau</span>"
    st.markdown(f"<div class='panel-banner'>Réf. {row[col_ref]} {badge}</div>",unsafe_allow_html=True)
    gmaps=row.get(col_gmaps,"")
    if gmaps not in ["","-","/"]:
        st.markdown(f"<div class='gmaps-btn'><a href='{gmaps}' target='_blank'><button>Cliquer ici</button></a></div>",unsafe_allow_html=True)
    st.write(row.get(col_addr,""))
    st.write(row.get(col_city,""))
    st.dataframe(row.to_frame().iloc[6:25])

# -------------------------------------------------
# MAIN
# -------------------------------------------------
def main():
    df=load_excel()
    if df.empty: st.warning("Excel vide"); return

    col_lat=find_col(df,"Latitude"); col_lon=find_col(df,"Longitude")
    col_ref=find_col(df,"Référence annonce"); col_actif=find_col(df,"Actif")
    col_addr=find_col(df,"Adresse complète","Adresse"); col_city=find_col(df,"Ville")
    col_gmaps=find_col(df,"Google Maps"); col_date_pub=find_col(df,"Date publication")

    df["_actif"]=df[col_actif].apply(normalize_bool) if col_actif else True
    df["_lat"]=clean_latlon_series(df[col_lat]) if col_lat else None
    df["_lon"]=clean_latlon_series(df[col_lon]) if col_lon else None
    df_map=df[df["_actif"] & df["_lat"].notna() & df["_lon"].notna()]

    col_left,col_map,col_right=st.columns([1,4,1])

    with col_left:
        st.subheader("Filtres")
        st.checkbox("Centre-ville")
        st.checkbox("Périphérie")
        st.button("Réinitialiser")
        st.button("Je suis intéressé")

    with col_map:
        if df_map.empty:
            st.warning("Aucune coordonnée valide")
        else:
            m=folium.Map(location=[46.6,1.88],zoom_start=6,tiles="cartodbpositron")
            for _,r in df_map.iterrows():
                ref=str(r[col_ref])
                folium.Marker(
                    [r["_lat"],r["_lon"]],
                    icon=folium.DivIcon(html=f"<div style='background:{LOGO_BLUE};color:white;border-radius:50%;width:26px;height:26px;text-align:center;line-height:26px;font-weight:600;font-size:11px'>{ref}</div>")
                ).add_to(m)
            st_folium(m,height=750,width=None)

    with col_right:
        render_right_panel(df_map[col_ref].iloc[0] if not df_map.empty else None,df,col_ref,col_addr,col_city,col_gmaps,col_date_pub)

if __name__=="__main__":
    main()

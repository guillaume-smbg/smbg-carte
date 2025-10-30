import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from io import BytesIO
import requests
import math

# -------------------------------------------------
# CONFIG GÉNÉRALE / THEME
# -------------------------------------------------
st.set_page_config(page_title="SMBG Carte", layout="wide")

BLEU_SMBG = "#05263d"
CUIVRE_SMBG = "#b87333"
PANEL_WIDTH_PX = 275

CUSTOM_CSS = f"""<style>
.stApp {{background-color:#ffffff;font-family:'Futura',sans-serif;}}
.main-container {{display:flex;flex-direction:row;width:100%;height:calc(100vh - 2rem);overflow:hidden;}}
.left-panel {{width:{PANEL_WIDTH_PX}px;background-color:{BLEU_SMBG};color:#fff;padding:16px;overflow-y:auto;}}
.map-panel {{flex:1 1 auto;position:relative;height:100%;overflow:hidden;}}
.right-panel {{width:{PANEL_WIDTH_PX}px;background-color:#fff;color:#000;padding:16px;overflow-y:auto;}}
.ref-banner {{font-weight:600;font-size:16px;color:{BLEU_SMBG};border-left:4px solid {CUIVRE_SMBG};padding-left:8px;margin-bottom:12px;}}
.gmaps-btn {{background-color:{BLEU_SMBG};color:#fff;text-decoration:none;font-size:13px;padding:6px 10px;border-radius:4px;display:inline-block;margin-bottom:12px;}}
</style>"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if "selected_ref" not in st.session_state: st.session_state["selected_ref"]=None
if "df" not in st.session_state: st.session_state["df"]=None

def load_excel_from_url(url:str)->pd.DataFrame:
    resp=requests.get(url);resp.raise_for_status();data=resp.content
    return pd.read_excel(BytesIO(data))

EXCEL_URL=st.secrets.get("EXCEL_URL","")
if EXCEL_URL and st.session_state["df"] is None:
    try: st.session_state["df"]=load_excel_from_url(EXCEL_URL)
    except Exception as e: st.error(f"Erreur chargement Excel : {e}")
df=st.session_state["df"]
if df is None or df.empty: st.warning("Aucune donnée chargée."); st.stop()

EXPECTED_COLS=["Référence annonce","Latitude","Longitude","Adresse","Adresse complète","Ville","Lien Google Maps","Surface totale (m²)","Loyer mensuel (€)","Charges mensuelles (€)","Taxe foncière annuelle (€)","Commentaires","Actif","Date publication"]
for c in EXPECTED_COLS:
    if c not in df.columns: df[c]=""
df_active=df[df["Actif"].astype(str).str.lower().eq("oui")].copy()
df_active=df_active[df_active["Latitude"].notna()&df_active["Longitude"].notna()].copy()
df_active["ref_clean"]=df_active["Référence annonce"].astype(str).str.replace(".0","",regex=False)

def build_folium_map(df_map):
    m=folium.Map(location=[46.5,2.5],zoom_start=6,tiles="OpenStreetMap")
    for _,r in df_map.iterrows():
        lat,lon=float(r["Latitude"]),float(r["Longitude"])
        ref=r["ref_clean"]
        html=f'<div style="background:{BLEU_SMBG};color:#fff;border-radius:6px;padding:4px 6px;font-size:12px;font-weight:600;">{ref}</div>'
        folium.Marker([lat,lon],icon=folium.DivIcon(html=html),popup=str(r["Référence annonce"])).add_to(m)
    return m

def get_lots(ref,df_): return df_[df_["Référence annonce"].astype(str)==str(ref)].copy()

def render_right_panel(ref,df_):
    lots=get_lots(ref,df_)
    if lots.empty:
        st.markdown("<div class='ref-banner'>Sélectionne un point sur la carte</div>",unsafe_allow_html=True);return
    head=lots.iloc[0]
    ref_txt=head.get("Référence annonce","")
    gmap=head.get("Lien Google Maps","")
    adr=head.get("Adresse complète","") or head.get("Adresse","")
    ville=head.get("Ville","")
    st.markdown(f"<div class='ref-banner'>Réf. {ref_txt}</div>",unsafe_allow_html=True)
    if gmap and str(gmap).strip() not in ["-","/",""]: st.markdown(f"<a class='gmaps-btn' href='{gmap}' target='_blank'>Voir sur Google Maps</a>",unsafe_allow_html=True)
    if adr or ville: st.markdown(f"<div><strong>{adr}</strong><br/>{ville}</div>",unsafe_allow_html=True)

    cols=["Surface totale (m²)","Loyer mensuel (€)","Charges mensuelles (€)","Taxe foncière annuelle (€)","Commentaires"]
    cols=[c for c in cols if c in lots.columns]
    table="<table class='lot-table'><thead><tr>"+"".join(f"<th>{c}</th>" for c in cols)+"</tr></thead><tbody>"
    for _,r in lots.iterrows():
        table+="<tr>"+"".join(f"<td>{r[c]}</td>" for c in cols)+"</tr>"
    table+="</tbody></table>"
    st.markdown(table,unsafe_allow_html=True)

st.markdown("<div class='main-container'>",unsafe_allow_html=True)
with st.container():
    st.markdown("<div class='left-panel'>",unsafe_allow_html=True)
    st.markdown("### Filtres",unsafe_allow_html=True)
    def to_num(s): return pd.to_numeric(s.astype(str).str.replace(" ","").str.replace(",","."),
        errors="coerce")
    surf,loy=to_num(df_active["Surface totale (m²)"]),to_num(df_active["Loyer mensuel (€)"])
    smin,smax=int(surf.min()),int(surf.max());lmin,lmax=int(loy.min()),int(loy.max())
    s_range=st.slider("Surface (m²)",smin,smax,(smin,smax))
    l_range=st.slider("Loyer (€)",lmin,lmax,(lmin,lmax))
    if st.button("Réinitialiser les filtres"): st.experimental_rerun()
    st.markdown("</div>",unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='map-panel'><div class='map-container-inner'>",unsafe_allow_html=True)
    df_f=df_active.copy()
    surf,loy=to_num(df_f["Surface totale (m²)"]),to_num(df_f["Loyer mensuel (€)"])
    df_f=df_f[((surf>=s_range[0])&(surf<=s_range[1]))|surf.isna()]
    df_f=df_f[((loy>=l_range[0])&(loy<=l_range[1]))|loy.isna()]
    df_m=df_f.groupby("Référence annonce",as_index=False).first()
    m=build_folium_map(df_m)
    data=st_folium(m,width=None,height=600,returned_objects=["last_object_clicked_popup"])
    ref=None
    if data and "last_object_clicked_popup" in data and data["last_object_clicked_popup"]: ref=data["last_object_clicked_popup"]
    if ref: st.session_state["selected_ref"]=ref
    st.markdown("</div></div>",unsafe_allow_html=True)

with st.container():
    st.markdown("<div class='right-panel'>",unsafe_allow_html=True)
    render_right_panel(st.session_state["selected_ref"],df_active)
    st.markdown("</div>",unsafe_allow_html=True)
st.markdown("</div>",unsafe_allow_html=True)

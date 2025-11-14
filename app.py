import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from pathlib import Path

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
st.set_page_config(page_title="SMBG Carte - Step 1", layout="wide")

BLUE = "#05263d"
COPPER = "#C67B42"

DATA_PATH = Path("data") / "Liste des lots.xlsx"

# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------
df = pd.read_excel(DATA_PATH)

# On garde seulement Actif == oui
if "Actif" in df.columns:
    df = df[df["Actif"].astype(str).str.lower() == "oui"]

# ---------------------------------------------------
# JAVASCRIPT: BUILD PINS
# ---------------------------------------------------
pins_js = ""
for _, r in df.iterrows():
    if pd.isna(r["Latitude"]) or pd.isna(r["Longitude"]):
        continue

    ref = str(r["Référence annonce"])

    pins_js += f"""
    var marker = L.circleMarker([{r['Latitude']}, {r['Longitude']}], {{
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '{BLUE}',
        fillOpacity: 1
    }}).addTo(map);

    marker.on('click', function() {{
        window.parent.postMessage({{type:'pin_click', ref:'{ref}'}}, "*");
    }});
    """

# ---------------------------------------------------
# HTML + CSS + JS
# ---------------------------------------------------
html = f"""
<!-- PANEL GAUCHE FIXE -->
<div id="left-panel" style="
    position:fixed;
    top:0;
    left:0;
    width:275px;
    height:100vh;
    background:{BLUE};
    z-index:9998;
">
</div>

<!-- MAP -->
<div id="map" style="
    position:fixed;
    top:0;
    left:275px;
    width:calc(100vw - 275px);
    height:100vh;
    z-index:1;
">
</div>

<!-- DRAWER DROIT -->
<div id="drawer" style="
    position:fixed;
    top:0;
    right:-275px;
    width:275px;
    height:100vh;
    background:{BLUE};
    color:white;
    padding:20px;
    transition:right 0.3s ease;
    z-index:9999;
">
    <h2 style="margin-top:0;">Détails de l'annonce</h2>
    <h3 id="ref_txt" style="color:{COPPER};"></h3>

    <div id="details_zone" style="margin-top:20px;">
        <!-- Structure vide pour la suite -->
    </div>

    <p style="opacity:0.6;">Cliquer sur la carte pour refermer</p>
</div>

<!-- LEAFLET -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<script>

// INIT MAP
var map = L.map('map', {{
    zoomControl: true,
    attributionControl: true
}}).setView([46.6, 2.4], 6);

L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19
}}).addTo(map);

// ADD PINS
{pins_js}

// CLICK ON MAP = CLOSE DRAWER
map.on('click', function(e) {{
    window.parent.postMessage({{type:'map_click'}}, "*");
}});

</script>
"""

# ---------------------------------------------------
# RENDER HTML
# ---------------------------------------------------
# IMPORTANT : height > 0 sinon Streamlit Cloud ignore tout → écran blanc
components.html(html, height=600, width=0)

# ---------------------------------------------------
# STATE MANAGEMENT
# ---------------------------------------------------
if "drawer_state" not in st.session_state:
    st.session_state.drawer_state = "closed"

if "drawer_ref" not in st.session_state:
    st.session_state.drawer_ref = ""

# ---------------------------------------------------
# CAPTURE JS EVENTS
# ---------------------------------------------------
st.markdown("""
<script>
window.addEventListener("message", (event) => {

    if (event.data.type === "pin_click") {
        window.parent.postMessage(
            {type:"streamlit:setComponentValue", value: event.data.ref},
            "*"
        );
    }

    if (event.data.type === "map_click") {
        window.parent.postMessage(
            {type:"streamlit:setComponentValue", value: ""},
            "*"
        );
    }

});
</script>
""", unsafe_allow_html=True)

val = st.session_state.get("component_value", None)

if val:
    st.session_state.drawer_state = "open"
    st.session_state.drawer_ref = val
else:
    st.session_state.drawer_state = "closed"

# ---------------------------------------------------
# UPDATE DRAWER POSITION
# ---------------------------------------------------
drawer_js = f"""
<script>
let drawer = window.parent.document.querySelector('#drawer');
let txt = window.parent.document.querySelector('#ref_txt');

if ("{st.session_state.drawer_state}" === "open") {{
    drawer.style.right = "0px";
    txt.innerHTML = "{st.session_state.drawer_ref}";
}} else {{
    drawer.style.right = "-275px";
}}
</script>
"""

st.markdown(drawer_js, unsafe_allow_html=True)

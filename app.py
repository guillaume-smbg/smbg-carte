
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="SMBG Carte - Step 1", layout="wide")

BLUE = "#05263d"

html = """
<div id="left-panel" style="
    position:fixed; top:0; left:0;
    width:275px; height:100vh;
    background:{BLUE};
    z-index:9998;">
</div>

<div id="map" style="
    position:fixed;
    top:0; left:275px;
    width:calc(100vw - 275px);
    height:100vh;
    z-index:1;">
</div>

<div id="drawer" style="
    position:fixed; top:0; right:-275px;
    width:275px; height:100vh;
    background:{BLUE};
    color:white;
    padding:20px;
    transition:right 0.3s ease;
    z-index:9999;
">
    <h2 style="color:white; margin-top:0;">Détails de l'annonce</h2>
    <h3 id="ref_txt" style="color:#C67B42;"></h3>
    <div id="details_zone" style="margin-top:20px;"></div>
    <p style="opacity:0.6;">Cliquer sur la carte pour refermer</p>
</div>

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<script>
var map = L.map('map').setView([46.6, 2.4], 6);

L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19
}}).addTo(map);


    var marker = L.circleMarker([45.64855270188624, 0.158321320235168], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'1.0'}, "*");
    });
    
    var marker = L.circleMarker([47.23816107662002, 6.023317650922776], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'2.0'}, "*");
    });
    
    var marker = L.circleMarker([47.58702497719213, 1.332018754475291], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'3.0'}, "*");
    });
    
    var marker = L.circleMarker([47.50526955157828, 6.844776893254944], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'4.0'}, "*");
    });
    
    var marker = L.circleMarker([49.20582171491501, -0.3285020839396927], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.1'}, "*");
    });
    
    var marker = L.circleMarker([49.20566684476754, -0.3283539893432659], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.2'}, "*");
    });
    
    var marker = L.circleMarker([49.20602604845581, -0.3286392975863524], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.3'}, "*");
    });
    
    var marker = L.circleMarker([49.2061440682712, -0.3283984433740406], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.4'}, "*");
    });
    
    var marker = L.circleMarker([49.20610866235774, -0.3281688791868094], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.5'}, "*");
    });
    
    var marker = L.circleMarker([49.2062650382889, -0.3279716798016147], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.6'}, "*");
    });
    
    var marker = L.circleMarker([49.20616029597461, -0.3279167349347474], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.7'}, "*");
    });
    
    var marker = L.circleMarker([49.2063092955417, -0.3276811493505675], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.8'}, "*");
    });
    
    var marker = L.circleMarker([49.20623504168992, -0.3276563112600658], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.9'}, "*");
    });
    
    var marker = L.circleMarker([49.206106203612336, -0.3275065300305682], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.1'}, "*");
    });
    
    var marker = L.circleMarker([49.20607669866272, -0.3275840549797097], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.11'}, "*");
    });
    
    var marker = L.circleMarker([49.20598720020472, -0.327982217143126], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.12'}, "*");
    });
    
    var marker = L.circleMarker([49.20568034712577, -0.3281410303970665], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'5.13'}, "*");
    });
    
    var marker = L.circleMarker([48.19752190792015, -1.7259755683652591], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.1'}, "*");
    });
    
    var marker = L.circleMarker([48.19774807046898, -1.726142291613472], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.2'}, "*");
    });
    
    var marker = L.circleMarker([48.19807147919867, -1.7264312600707086], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.3'}, "*");
    });
    
    var marker = L.circleMarker([48.19819885419333, -1.72656791644299], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.4'}, "*");
    });
    
    var marker = L.circleMarker([48.1983256510846, -1.7266916944069663], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.5'}, "*");
    });
    
    var marker = L.circleMarker([48.19840207645366, -1.7267920196874926], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.6'}, "*");
    });
    
    var marker = L.circleMarker([48.19854363678117, -1.7269105859475735], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.7'}, "*");
    });
    
    var marker = L.circleMarker([48.19879201776634, -1.726805048919688], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.8'}, "*");
    });
    
    var marker = L.circleMarker([48.198858020900026, -1.7266500007588743], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.9'}, "*");
    });
    
    var marker = L.circleMarker([48.19890926011624, -1.7265405549983002], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.1'}, "*");
    });
    
    var marker = L.circleMarker([48.19903344987063, -1.726210914758006], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.11'}, "*");
    });
    
    var marker = L.circleMarker([48.19910813726887, -1.7260037495683476], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'6.12'}, "*");
    });
    
    var marker = L.circleMarker([48.0067565977583, 0.1989107952125904], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'7.1'}, "*");
    });
    
    var marker = L.circleMarker([48.00659046497432, 0.1993958931099], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'7.2'}, "*");
    });
    
    var marker = L.circleMarker([48.00683541175847, 0.1990398599180266], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'7.3'}, "*");
    });
    
    var marker = L.circleMarker([48.00641347264494, 0.1991280242107483], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'7.4'}, "*");
    });
    
    var marker = L.circleMarker([48.00602265236236, 0.1994107986035435], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'7.5'}, "*");
    });
    
    var marker = L.circleMarker([48.00580775005263, 0.199436188605187], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'7.6'}, "*");
    });
    
    var marker = L.circleMarker([48.006281016792144, 0.199481477058283], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'7.7'}, "*");
    });
    
    var marker = L.circleMarker([48.006508109435714, 0.1994135899842946], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'7.8'}, "*");
    });
    
    var marker = L.circleMarker([45.753681218897846, 4.861306293252618], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'8.0'}, "*");
    });
    
    var marker = L.circleMarker([48.76183089046028, 1.912924865195206], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'9.1'}, "*");
    });
    
    var marker = L.circleMarker([48.76152946261393, 1.9129543366436983], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'9.2'}, "*");
    });
    
    var marker = L.circleMarker([48.76134254213555, 1.9132714009259728], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'9.3'}, "*");
    });
    
    var marker = L.circleMarker([48.761272662850764, 1.913442815858133], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'9.4'}, "*");
    });
    
    var marker = L.circleMarker([48.76169009462806, 1.9133525748219056], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'9.5'}, "*");
    });
    
    var marker = L.circleMarker([49.115820149606094, 6.174377236606556], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'10.0'}, "*");
    });
    
    var marker = L.circleMarker([49.11588724471485, 6.174454556195556], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'11.0'}, "*");
    });
    
    var marker = L.circleMarker([48.86949784386822, 2.305007177912304], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'12.0'}, "*");
    });
    
    var marker = L.circleMarker([48.87724321328928, 2.31383313558246], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'13.0'}, "*");
    });
    
    var marker = L.circleMarker([48.88101993896251, 2.369427050922775], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'15.0'}, "*");
    });
    
    var marker = L.circleMarker([48.84670357776639, 2.3685021932526173], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'16.0'}, "*");
    });
    
    var marker = L.circleMarker([48.84555812034668, 2.3994931797578527], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'17.0'}, "*");
    });
    
    var marker = L.circleMarker([48.85723499596395, 2.2726086124479754], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'18.0'}, "*");
    });
    
    var marker = L.circleMarker([48.84870910142074, 2.271172963194535], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'19.0'}, "*");
    });
    
    var marker = L.circleMarker([48.83929157522859, 2.236185051910399], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'20.1'}, "*");
    });
    
    var marker = L.circleMarker([48.83931747667382, 2.236574897911596], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'20.2'}, "*");
    });
    
    var marker = L.circleMarker([48.839387086741525, 2.2370864939257844], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'20.3'}, "*");
    });
    
    var marker = L.circleMarker([48.8394259388339, 2.2374123904630108], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'20.4'}, "*");
    });
    
    var marker = L.circleMarker([48.83950526175626, 2.2374062414717395], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'20.5'}, "*");
    });
    
    var marker = L.circleMarker([48.839613723506105, 2.237389024298185], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'20.6'}, "*");
    });
    
    var marker = L.circleMarker([48.83911835896739, 2.236205958474708], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'20.7'}, "*");
    });
    
    var marker = L.circleMarker([48.83919201642189, 2.2368921858206634], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'20.8'}, "*");
    });
    
    var marker = L.circleMarker([48.90087777754063, 2.232302768080578], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'21.1'}, "*");
    });
    
    var marker = L.circleMarker([48.901030168795614, 2.2323524442585025], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'21.2'}, "*");
    });
    
    var marker = L.circleMarker([48.763870265771125, 2.2883596355824607], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'22.1'}, "*");
    });
    
    var marker = L.circleMarker([48.82246818929723, 2.1891107324322667], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'23.1'}, "*");
    });
    
    var marker = L.circleMarker([48.82246091029152, 2.18919733534608], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'23.2'}, "*");
    });
    
    var marker = L.circleMarker([48.822406317714965, 2.1893300036395806], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'23.3'}, "*");
    });
    
    var marker = L.circleMarker([48.8223917596845, 2.189440560550832], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'23.4'}, "*");
    });
    
    var marker = L.circleMarker([48.82240267820774, 2.1897335363656456], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'23.5'}, "*");
    });
    
    var marker = L.circleMarker([48.82243543376318, 2.1900486235627104], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'23.6'}, "*");
    });
    
    var marker = L.circleMarker([48.82255311095043, 2.190588509804789], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'23.7'}, "*");
    });
    
    var marker = L.circleMarker([49.04747447004796, 2.0944099659494526], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'24.1'}, "*");
    });
    
    var marker = L.circleMarker([49.04754984187792, 2.094032809769657], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'24.2'}, "*");
    });
    
    var marker = L.circleMarker([49.0477734023446, 2.0926374535883365], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'24.3'}, "*");
    });
    
    var marker = L.circleMarker([49.04794286186191, 2.0939143250781576], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'24.4'}, "*");
    });
    
    var marker = L.circleMarker([49.04774498025447, 2.0941991067124546], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'24.5'}, "*");
    });
    
    var marker = L.circleMarker([43.57164909821292, 3.940229608945791], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.1'}, "*");
    });
    
    var marker = L.circleMarker([43.57176278087646, 3.9404146812680634], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.2'}, "*");
    });
    
    var marker = L.circleMarker([43.57187160511061, 3.940672173324781], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.3'}, "*");
    });
    
    var marker = L.circleMarker([43.572032018264125, 3.940785990178005], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.4'}, "*");
    });
    
    var marker = L.circleMarker([43.572153392783775, 3.9412129217253873], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.5'}, "*");
    });
    
    var marker = L.circleMarker([43.57217720643128, 3.941269894257782], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.6'}, "*");
    });
    
    var marker = L.circleMarker([43.57242169267419, 3.94173882207542], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.7'}, "*");
    });
    
    var marker = L.circleMarker([43.572524884621, 3.9419228872012826], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.8'}, "*");
    });
    
    var marker = L.circleMarker([43.572570924046445, 3.94203902351109], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.9'}, "*");
    });
    
    var marker = L.circleMarker([43.57260768696906, 3.942127131093781], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.1'}, "*");
    });
    
    var marker = L.circleMarker([43.57266188352481, 3.942216708989224], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.11'}, "*");
    });
    
    var marker = L.circleMarker([43.572754965284034, 3.94280371966065], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.12'}, "*");
    });
    
    var marker = L.circleMarker([43.572719014969984, 3.942727947256568], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.13'}, "*");
    });
    
    var marker = L.circleMarker([43.57258930217294, 3.942494595074587], {
        radius: 18,
        color: 'black',
        weight: 1,
        fillColor: '#05263d',
        fillOpacity: 1
    }).addTo(map);
    marker.on('click', function() {
        window.parent.postMessage({type:'pin_click', ref:'25.14'}, "*");
    });
    

map.on('click', function(e){{
    window.parent.postMessage({{type:'map_click'}}, "*");
}});
</script>
"""

components.html(html, height=0, width=0)

if "drawer_state" not in st.session_state:
    st.session_state.drawer_state="closed"
if "drawer_ref" not in st.session_state:
    st.session_state.drawer_ref=""

st.markdown("""
<script>
window.addEventListener("message", (event) => {
    if (event.data.type === "pin_click") {
        window.parent.postMessage({type:"streamlit:setComponentValue", value: event.data.ref}, "*");
    }
    if (event.data.type === "map_click") {
        window.parent.postMessage({type:"streamlit:setComponentValue", value: ""}, "*");
    }
});
</script>
""", unsafe_allow_html=True)

val = st.session_state.get("component_value", None)
if val:
    st.session_state.drawer_state="open"
    st.session_state.drawer_ref=val
else:
    st.session_state.drawer_state="closed"

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

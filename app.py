
import os
import io
import re
import json
import time
import urllib.parse as up
import pandas as pd
import streamlit as st
import requests
import folium
from streamlit.components.v1 import html as st_html

# ================== PAGE LAYOUT ==================
st.set_page_config(page_title='SMBG Carte (Leaflet Mapnik + Drawer)', layout='wide')
DEFAULT_LOCAL_PATH = 'data/Liste_des_lots.xlsx'
LOGO_BLUE = '#05263d'

# Left sidebar placeholder (fixed 275px)
st.sidebar.markdown('### Filtres (à venir)')

# Fullscreen layout (no scroll)
st.markdown('''
<style>
  html, body {height:100%; overflow:hidden;}
  [data-testid="stAppViewContainer"]{padding:0; margin:0; height:100vh; overflow:hidden;}
  [data-testid="stMain"]{padding:0; margin:0; height:100vh; overflow:hidden;}
  .block-container{padding:0 !important; margin:0 !important;}
  [data-testid="stSidebar"]{min-width:275px; max-width:275px;}
  header, footer {visibility:hidden; height:0;}
</style>
''', unsafe_allow_html=True)

# ================== HELPERS: Excel ==================
def normalize_excel_url(url: str) -> str:
    if not url: return url
    url = url.strip()
    url = re.sub(r'https://github\.com/(.+)/blob/([^ ]+)', r'https://github.com/\1/raw/\2', url)
    return url

def is_github_folder(url: str) -> bool:
    return bool(re.match(r'^https://github\.com/[^/]+/[^/]+/tree/[^/]+/.+', url))

def folder_to_api(url: str) -> str:
    m = re.match(r'^https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.*)$', url)
    if not m: return ''
    owner, repo, branch, path = m.groups()
    return f'https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}'

def fetch_first_excel_from_folder(url: str) -> bytes:
    api_url = folder_to_api(url)
    r = requests.get(api_url, timeout=20); r.raise_for_status()
    entries = r.json()
    excel_items = [e for e in entries if e.get('type')=='file' and e.get('name','').lower().endswith(('.xlsx','.xls'))]
    if not excel_items:
        raise FileNotFoundError('Aucun .xlsx trouvé dans ce dossier GitHub.')
    excel_items.sort(key=lambda e: (not e['name'].lower().endswith('.xlsx'), e['name'].lower()))
    raw = requests.get(excel_items[0]['download_url'], timeout=30); raw.raise_for_status()
    return raw.content

def load_excel() -> pd.DataFrame:
    excel_url = st.secrets.get('EXCEL_URL', os.environ.get('EXCEL_URL', '')).strip()
    excel_url = normalize_excel_url(excel_url)
    if excel_url:
        if is_github_folder(excel_url):
            content = fetch_first_excel_from_folder(excel_url)
            return pd.read_excel(io.BytesIO(content))
        else:
            resp = requests.get(excel_url, timeout=20); resp.raise_for_status()
            return pd.read_excel(io.BytesIO(resp.content))
    if not os.path.exists(DEFAULT_LOCAL_PATH):
        st.stop()
    return pd.read_excel(DEFAULT_LOCAL_PATH)

# ================== GEOCODING (validé) ==================
@st.cache_data(show_spinner=False)
def resolve_redirect(url: str) -> str:
    try:
        r = requests.get(url, timeout=15, allow_redirects=True, headers={'User-Agent':'Mozilla/5.0'})
        return r.url
    except Exception:
        return url

def clean_address(a: str) -> str:
    a = re.sub(r'\s+', ' ', str(a)).strip()
    a = re.sub(r'\s*-\s*', ' ', a)
    if a and 'france' not in a.lower():
        a = f'{a}, France'
    return a

def extract_lat_lon_from_gmap(url: str):
    if not isinstance(url, str) or url.strip() == '': return None, None
    url = url.strip()
    if re.search(r'(goo\.gl|maps\.app\.goo\.gl)', url): url = resolve_redirect(url)
    parsed = up.urlparse(url); qs = up.parse_qs(parsed.query)
    m = re.search(r'@([0-9.\-]+),([0-9.\-]+)', url)
    if m:
        try: return float(m.group(1)), float(m.group(2))
        except: pass
    m = re.search(r'!3d([0-9.\-]+)!4d([0-9.\-]+)', url)
    if m:
        try: return float(m.group(1)), float(m.group(2))
        except: pass
    if 'll' in qs:
        try:
            lat, lon = qs['ll'][0].split(','); return float(lat), float(lon)
        except: pass
    if 'q' in qs:
        qv = qs['q'][0].replace('loc:', '').strip()
        m = re.match(r'\s*([0-9.\-]+)\s*,\s*([0-9.\-]+)\s*$', qv)
        if m:
            try: return float(m.group(1)), float(m.group(2))
            except: pass
    if 'center' in qs:
        try:
            lat, lon = qs['center'][0].split(','); return float(lat), float(lon)
        except: pass
    m = re.search(r'/place/([0-9.\-]+),([0-9.\-]+)', parsed.path)
    if m:
        try: return float(m.group(1)), float(m.group(2))
        except: pass
    return None, None

def extract_query_from_gmap(url: str):
    try:
        if not isinstance(url, str) or not url.strip(): return None
        url = resolve_redirect(url.strip())
        parsed = up.urlparse(url)
        q = up.parse_qs(parsed.query).get('q', [''])[0].strip()
        return q or None
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def geocode_one(addr: str, email: str = ''):
    if not addr: return None, None
    base = 'https://nominatim.openstreetmap.org/search'
    params = {'q': addr, 'format': 'json', 'limit': 1, 'countrycodes': 'fr'}
    ua = f'SMBG-CARTE/1.0 ({email})' if email else 'SMBG-CARTE/1.0 (contact@smbg-conseil.fr)'
    headers = {'User-Agent': ua, 'Accept-Language': 'fr'}
    try:
        r = requests.get(base, params=params, headers=headers, timeout=20); r.raise_for_status()
        data = r.json()
        if data: return float(data[0]['lat']), float(data[0]['lon'])
    except Exception:
        return None, None
    return None, None

@st.cache_data(show_spinner=False)
def geocode_success_cached(address: str, gmap_url: str):
    lat, lon = extract_lat_lon_from_gmap(gmap_url)
    if lat is not None and lon is not None: return lat, lon
    q = extract_query_from_gmap(gmap_url)
    if q:
        lat, lon = geocode_one(clean_address(q))
        if lat is not None and lon is not None: return lat, lon
    addr = clean_address(address)
    for _ in range(2):
        lat, lon = geocode_one(addr)
        if lat is not None and lon is not None: return lat, lon
        time.sleep(1.2)
    raise RuntimeError('geocode_failed')

def geocode_best_effort(address: str, gmap_url: str):
    try:
        return geocode_success_cached(address, gmap_url)
    except Exception:
        return None, None

# ================== RENDER MAP (pins via Python, drawer via JS) ==================
def render_map(df_valid: pd.DataFrame, ref_col: str | None, range_cols):
    FR_LAT, FR_LON, FR_ZOOM = 46.603354, 1.888334, 6

    m = folium.Map(
        location=[FR_LAT, FR_LON],
        zoom_start=FR_ZOOM,
        tiles=None,
        control_scale=False,
        zoom_control=True
    )
    folium.TileLayer(
        tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        attr='© OpenStreetMap contributors',
        name='OpenStreetMap.Mapnik',
        max_zoom=19,
        min_zoom=0,
        opacity=1.0
    ).add_to(m)

    # Feature group for markers
    group = folium.FeatureGroup(name='Annonces').add_to(m)

    # CSS for pin
    PIN_CSS = f'background:{LOGO_BLUE}; color:#fff; border:2px solid #fff; width:28px; height:28px; line-height:28px; border-radius:50%; text-align:center; font-size:11px; font-weight:700;'

    # Add markers as before (validated approach)
    for _, row in df_valid.iterrows():
        lat, lon = float(row['_lat']), float(row['_lon'])
        ref_text = str(row.get(ref_col, '')) if ref_col else ''
        # Build props for drawer: only columns G..AH in order
        props = {}
        for col in range_cols:
            val = row.get(col, '')
            if pd.isna(val): val = ''
            props[col] = str(val)
        if ref_col:
            props['_ref'] = ref_text
        # Encode to HTML-safe JSON
        data_props = html.escape(json.dumps(props, ensure_ascii=False))
        html_div = f'<div class="smbg-pin" data-props="{data_props}">{ref_text}</div>'
        icon = folium.DivIcon(html=html_div, class_name='smbg-divicon', icon_size=(28,28), icon_anchor=(14,14))
        folium.Marker(location=[lat, lon], icon=icon).add_to(group)

    # Drawer CSS/JS injected once
    css = f'''
    <style>
      @font-face {{ font-family: 'Futura'; src: local('Futura'); }}
      .smbg-divicon {{ background: transparent; border: none; }}
      .smbg-drawer {{
        position: absolute; top:0; right:0; width:275px; height:100vh; background:#fff;
        font-family: 'Futura', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
        box-shadow: -12px 0 24px rgba(0,0,0,0.08);
        border-left: 1px solid rgba(0,0,0,0.06);
        transform: translateX(100%);
        transition: transform 220ms ease-in-out;
        display:flex; flex-direction:column;
        z-index: 9999;
      }}
      .smbg-drawer.open {{ transform: translateX(0%); }}
      .smbg-drawer-header {{ padding:12px 14px; font-weight:700; font-size:14px; color:#0f172a; border-bottom:1px solid rgba(0,0,0,0.06);}}
      .smbg-drawer-body {{ padding:10px 14px; overflow-y:auto; }}
      .smbg-kv {{ margin-bottom:10px; }}
      .smbg-kv .k {{ font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:.02em; }}
      .smbg-kv .v {{ font-size:14px; color:#0f172a; font-weight:600; margin-top:2px; word-break:break-word; }}
      .smbg-link {{ color:{LOGO_BLUE}; text-decoration:none; font-weight:700; }}
      .leaflet-container {{ background:#e6e9ef; }}
      .smbg-pin {{ {PIN_CSS} }}
      .leaflet-marker-icon {{ cursor: pointer; }}
    </style>
    '''
    js = '''
    <script>
      function isMeaningful(v){
        if(v===null||v===undefined) return false;
        const s=String(v).trim();
        return s!=='' && s!=='/' && s!=='-';
      }
      function buildRowHTML(label,value){
        if(/^https?:\/\//i.test(value) && /google\./i.test(value)){
          return `<div class="smbg-kv"><div class="k">${label}</div><div class="v"><a href="${value}" target="_blank" class="smbg-link">Ouvrir dans Google Maps</a></div></div>`;
        }
        return `<div class="smbg-kv"><div class="k">${label}</div><div class="v">${value}</div></div>`;
      }
      let drawer, body, header;
      function ensureDrawer(){
        drawer = document.querySelector('.smbg-drawer');
        if(!drawer){
          drawer = document.createElement('div');
          drawer.className = 'smbg-drawer';
          drawer.innerHTML = '<div class="smbg-drawer-header">Détail de l’annonce</div><div class="smbg-drawer-body"></div>';
          document.body.appendChild(drawer);
        }
        header = drawer.querySelector('.smbg-drawer-header');
        body = drawer.querySelector('.smbg-drawer-body');
      }
      function openDrawerWithProps(props){
        ensureDrawer();
        const title = props._ref ? `Annonce ${props._ref}` : 'Détail de l’annonce';
        header.textContent = title;
        body.innerHTML = '';
        const cols = Object.keys(props);
        // Preserve Python order by reading dataset JSON as-is (already ordered), but safeguard here:
        for(const k of cols){
          if(k==='_ref') continue;
          const v = props[k];
          if(isMeaningful(v)){
            body.insertAdjacentHTML('beforeend', buildRowHTML(k, String(v)));
          }
        }
        drawer.classList.add('open');
      }
      function closeDrawer(){
        ensureDrawer();
        drawer.classList.remove('open');
      }
      function attachHandlers(){
        // Attach click on all pin divs
        document.querySelectorAll('.smbg-pin').forEach(el=>{
          el.addEventListener('click', (e)=>{
            e.preventDefault();
            e.stopPropagation();
            try{
              const props = JSON.parse(el.getAttribute('data-props') || '{}');
              openDrawerWithProps(props);
            }catch(err){ console.warn('Bad props', err); }
          }, {passive:true});
        });
        // Close on map background
        const map = (function(){
          for(const k in window){
            if(k.startsWith('map_') && window[k] && typeof window[k].on==='function'){ return window[k]; }
          }
          return null;
        })();
        if(map){ map.on('click', ()=> closeDrawer()); }
      }
      // Run after tiles render
      if(document.readyState==='complete' || document.readyState==='interactive'){
        setTimeout(attachHandlers, 0);
      }else{
        document.addEventListener('DOMContentLoaded', attachHandlers);
      }
    </script>
    '''
    folium.Element(css).add_to(m)
    folium.Element(js).add_to(m)

    # Render
    html_str = m.get_root().render()
    return html_str

def build_mapping(df):
    # columns G..AH (indices 6..33)
    cols = list(df.columns)
    start_idx, end_idx = 6, 33
    slice_cols = cols[start_idx:end_idx+1] if len(cols)>end_idx else cols[start_idx:]
    return {'range_cols': slice_cols}

def main():
    df = load_excel()

    # Detect columns
    def first_match(cands):
        for c in cands:
            if c in df.columns: return c
        return None
    actif_col = first_match(['Actif','Active','AO'])
    lat_col   = first_match(['Latitude','Lat','AI'])
    lon_col   = first_match(['Longitude','Lon','Lng','Long','AJ'])
    addr_col  = first_match(['Adresse','Adresse complète','G'])
    gmap_col  = first_match(['Lien Google Maps','Google Maps','Maps','H'])
    ref_col   = first_match(['Référence annonce','Référence','AM'])

    # Active flag
    if actif_col is None:
        df['_actif'] = True
    else:
        def norm(v):
            if isinstance(v, str): return v.strip().lower() in {'oui','yes','true','1','vrai'}
            if isinstance(v, (int,float)):
                try: return int(v)==1
                except: return False
            if isinstance(v, bool): return v
            return False
        df['_actif'] = df[actif_col].apply(norm)

    # Ensure lat/lon
    if lat_col is None: lat_col = 'Latitude'; df[lat_col] = None
    if lon_col is None: lon_col = 'Longitude'; df[lon_col] = None
    lat_num = pd.to_numeric(df[lat_col], errors='coerce')
    lon_num = pd.to_numeric(df[lon_col], errors='coerce')
    need = lat_num.isna() | lon_num.isna()
    if need.any():
        for idx, row in df[need].iterrows():
            addr = str(row.get(addr_col, '')) if addr_col else ''
            gmap = str(row.get(gmap_col, '')) if gmap_col else ''
            lat, lon = geocode_best_effort(addr, gmap)
            df.loc[idx, lat_col] = lat
            df.loc[idx, lon_col] = lon

    # Valid rows
    df = df[df['_actif']].copy()
    df['_lat'] = pd.to_numeric(df[lat_col], errors='coerce')
    df['_lon'] = pd.to_numeric(df[lon_col], errors='coerce')
    df_valid = df.dropna(subset=['_lat','_lon']).copy()
    if df_valid.empty:
        st.warning('Aucune ligne active avec coordonnées valides.')
        st.stop()

    # Columns G..AH
    mapcols = build_mapping(df_valid)
    range_cols = mapcols['range_cols']

    # Render
    html_str = render_map(df_valid, ref_col, range_cols)
    st_html(html_str, height=1080, scrolling=False)

if __name__ == '__main__':
    main()

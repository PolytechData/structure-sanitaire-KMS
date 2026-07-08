import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import json

# --- CONFIGURATION DE LA PAGE STREAMLIT ---
st.set_page_config(
    page_title="SIG KMS",
    page_icon="logo.png",
    layout="wide",
    initial_sidebar_state="expanded")

# --- STYLE CSS PERSONNALISÉ POUR L'INTERFACE ---
st.markdown("""
    <style>
    .main-title { font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 5px; }
    .subtitle { font-size: 14px; color: #7f8c8d; margin-bottom: 20px; }
    .metric-box { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db; margin-bottom: 10px; }
    .metric-box.sanitaire { border-left-color: #e74c3c; }
    .metric-title { font-size: 12px; text-transform: uppercase; color: #95a5a6; font-weight: bold; }
    .metric-value { font-size: 18px; font-weight: bold; color: #2c3e50; }
    </style>
""", unsafe_allow_html=True)

# --- CHARGEMENT DES DONNÉES (Mise en cache pour maximiser la fluidité) ---
@st.cache_data
def load_data():
    limite = gpd.read_file('limitekms.geojson').to_crs(epsg=4326)
    routes = gpd.read_file('route.geojson').to_crs(epsg=4326)
    quartiers = gpd.read_file('quartier.geojson').to_crs(epsg=4326)
    sanitaires = gpd.read_file('structuresanitaire.geojson').to_crs(epsg=4326)
    return limite, routes, quartiers, sanitaires

try:
    gdf_limite, gdf_routes, gdf_quartiers, gdf_sanitaires = load_data()
except Exception as e:
    st.error(f"Erreur lors du chargement des fichiers GeoJSON : {e}")
    st.stop()

# ==============================================================================
# CONTROLE LATÉRAL (SIDEBAR) - FILTRES & STATISTIQUES
# ==============================================================================
with st.sidebar:
    st.markdown('<div class="main-title">Keur Massar Sud</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Système d\'Information Géographique</div>', unsafe_allow_html=True)
    st.write("---")
    
    # Filtre sur les structures sanitaires
    types_disponibles = sorted(list(gdf_sanitaires['Type'].dropna().unique()))
    selected_type = st.selectbox(
        "Type d'infrastructure sanitaire :",
        options=["Toutes"] + types_disponibles
    )
    
    # Filtre sur la vulnérabilité (Inondation)
    filter_inondable = st.radio(
        "Zone Inondable (Infrastructures) :",
        options=["Tous", "Oui", "Non"],
        index=0
    )

# Application des filtres sur le GeoDataFrame des structures sanitaires
gdf_sanitaires_filtered = gdf_sanitaires.copy()
if selected_type != "Toutes":
    gdf_sanitaires_filtered = gdf_sanitaires_filtered[gdf_sanitaires_filtered['Type'] == selected_type]
if filter_inondable != "Tous":
    gdf_sanitaires_filtered = gdf_sanitaires_filtered[gdf_sanitaires_filtered['Inondable'] == filter_inondable]


# ==============================================================================
# DESIGN DE LA CARTE FOLIUM
# ==============================================================================
def create_map(limite, routes, quartiers, sanitaires):
    # Initialisation centrée sur Keur Massar Sud
    m = folium.Map(location=[14.769934, -17.314913], zoom_start=14, tiles=None)
    
    # Ajout des fonds de carte
    folium.TileLayer('CartoDB positron', name="Plan Épuré", control=True).add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri World Imagery',
        name='Vue Satellite',
        control=True
    ).add_to(m)

    # 1. Couche : Limite Communale
    folium.GeoJson(
        limite,
        name="Limite Communale",
        style_function=lambda x: {
            'color': '#e74c3c', 'weight': 3, 'dashArray': '6, 6', 'fillOpacity': 0
        },
        tooltip=folium.GeoJsonTooltip(fields=['Nom_CR'], aliases=['Commune :'])
    ).add_to(m)

    # 2. Couche : Réseau Routier
    folium.GeoJson(
        routes,
        name="Réseau Routier",
        style_function=lambda x: {'color': '#2c3e50', 'weight': 2, 'opacity': 0.7},
        tooltip=folium.GeoJsonTooltip(fields=['fclass', 'name'], aliases=['Classe :', 'Nom :'])
    ).add_to(m)

    # 3. Couche : Quartiers (Démographie)
    folium.GeoJson(
        quartiers,
        name="Démographie des Quartiers",
        style_function=lambda x: {
            'color': '#7f8c8d', 'weight': 1, 'fillColor': '#34495e', 'fillOpacity': 0.15
        },
        highlight_function=lambda x: {'weight': 3, 'fillColor': '#3498db', 'fillOpacity': 0.4},
        popup=folium.GeoJsonPopup(
            fields=['QRT_VLG_HA', 'POPULATION', 'HOMMES', 'FEMMES', 'DENSITE'],
            aliases=['Quartier :', 'Population Total :', 'Hommes :', 'Femmes :', 'Densité (hbts/km²) :']
        ),
        tooltip=folium.GeoJsonTooltip(fields=['QRT_VLG_HA'], aliases=['Quartier :'])
    ).add_to(m)

    # 4. Couche : Structures Sanitaires (Marqueurs dynamiques)
    for _, row in sanitaires.iterrows():
        if row.geometry and not row.geometry.is_empty:
            lon, lat = row.geometry.x, row.geometry.y
            
            # Changement de couleur de l'icône selon l'inondabilité
            color = 'red' if row.get('Inondable') == 'Oui' else 'blue'
            icon_marker = 'triangle-exclamation' if row.get('Inondable') == 'Oui' else 'circle-h'
            
            # Construction propre du HTML de la popup
            popup_html = f"""
            <div style="font-family: 'Arial'; min-width: 200px;">
                <h4 style="margin:0 0 5px 0; color:#2c3e50;">{row.get('Nom', 'N/A')}</h4>
                <p style="margin:0; font-size:12px; color:#7f8c8d;"><b>Type:</b> {row.get('Type', 'N/A')}</p>
                <hr style="margin:5px 0; border:0; border-top:1px solid #eee;">
                <p style="margin:2px 0; font-size:12px;"><b>Quartier:</b> {row.get('Quartier', 'N/A')}</p>
                <p style="margin:2px 0; font-size:12px;"><b>Téléphone:</b> {int(row['Téléphon']) if row.get('Téléphon') and row['Téléphon'] != 0 else 'N/A'}</p>
                <p style="margin:2px 0; font-size:12px; color:{'red' if color=='red' else 'green'};"><b>Inondable:</b> {row.get('Inondable', 'N/A')}</p>
            </div>
            """
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"<b>{row.get('Nom')}</b> ({row.get('Type')})",
                icon=folium.Icon(color=color, icon=icon_marker, prefix='fa')
            ).add_to(m)

    folium.LayerControl(position='topright', collapsed=False).add_to(m)
    return m


# ==============================================================================
# AFFICHAGE DE LA CARTE ET INTERACTION DYNAMIQUE
# ==============================================================================
col_carte, col_infos = st.columns([3, 1])

with col_carte:
    # Génération et rendu de la carte via streamlit-folium
    map_object = create_map(gdf_limite, gdf_routes, gdf_quartiers, gdf_sanitaires_filtered)
    output = st_folium(map_object, width="100%", height=650, returned_objects=["last_active_feature"])

with col_infos:
    st.markdown('<p class="main-title" style="font-size:18px;">📊 Inspection</p>', unsafe_allow_html=True)
    
    # Détection du clic sur l'objet de la carte
    active_feature = output.get("last_active_feature")
    
    if active_feature and active_feature.get("properties"):
        props = active_feature["properties"]
        
        # Cas 1 : Clic sur un Quartier (Contient la clé POPULATION)
        if "POPULATION" in props:
            st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-title">🏡 Quartier Sélectionné</div>
                    <div class="metric-value">{props.get('QRT_VLG_HA')}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">👥 Population</div>
                    <div class="metric-value">{int(props.get('POPULATION', 0)):,} hbts</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">📈 Densité</div>
                    <div class="metric-value">{float(props.get('DENSITE', 0)):.1f} hbts/km²</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">♂️ Hommes / ♀️ Femmes</div>
                    <div class="metric-value">{int(props.get('HOMMES', 0)):,} / {int(props.get('FEMMES', 0)):,}</div>
                </div>
            """, unsafe_allow_html=True)
            
        # Cas 2 : Si clic sur un élément de type Limite ou autre
        elif "Nom_CR" in props:
            st.info(f"Zone d'étude : **{props.get('Nom_CR')}** ({props.get('nom_region')})")
            
    else:
        # Affichage des statistiques globales par défaut si aucun clic
        total_structures = len(gdf_sanitaires_filtered)
        inondables_count = len(gdf_sanitaires_filtered[gdf_sanitaires_filtered['Inondable'] == 'Oui'])
        
        st.markdown(f"""
            <div class="metric-box sanitaire">
                <div class="metric-title">🏥 Structures affichées</div>
                <div class="metric-value">{total_structures}</div>
            </div>
            <div class="metric-box" style="border-left-color:#e67e22;">
                <div class="metric-title">⚠️ Structures En Zone Inondable</div>
                <div class="metric-value">{inondables_count}</div>
            </div>
        """, unsafe_allow_html=True)

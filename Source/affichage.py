import folium
import numpy as np
from datetime import datetime

def create_wind_arrow_svg(direction, speed_kn, max_speed_kn=40):
    """
    Crée SVG d'une flèche de vent.
    
    Args:
        direction: Direction du vent en degrés (d'où vient le vent)
        speed_kn: Vitesse en nœuds
        max_speed_kn: Vitesse max pour normaliser la taille
    
    Returns:
        HTML icon avec flèche SVG
    """
    # Normaliser taille (25-50 pixels selon vitesse)
    size = 25 + (speed_kn / max_speed_kn) * 25
    size = min(max(size, 20), 60)
    
    # Couleur selon vitesse (vert->jaune->orange->rouge)
    if speed_kn < 10:
        color = '#00ff00'  # Vert (faible)
    elif speed_kn < 20:
        color = '#ffff00'  # Jaune (modéré)
    elif speed_kn < 30:
        color = '#ff8800'  # Orange (fort)
    else:
        color = '#ff0000'  # Rouge (très fort)
    
    # Rotation : direction + 180 (flèche pointe vers où VA le vent)
    rotation = (direction + 180) % 360
    
    # SVG flèche
    svg = f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" 
         style="transform: rotate({rotation}deg);">
        <path d="M12 2 L12 18 M12 18 L8 14 M12 18 L16 14" 
              stroke="{color}" stroke-width="3" fill="none" 
              stroke-linecap="round" stroke-linejoin="round"/>
        ircle cx="12" cy="20" r="2" fill="{color}"/>
    </svg>
    """
    
    return folium.DivIcon(html=svg)


def get_wind_compass(direction):
    """Convertit degrés en direction cardinale."""
    directions = [
        "Nord", "NNE", "NE", "ENE",
        "Est", "ESE", "SE", "SSE",
        "Sud", "SSO", "SO", "OSO",
        "Ouest", "ONO", "NO", "NNO"
    ]
    idx = int((direction + 11.25) / 22.5) % 16
    return directions[idx]


def add_grib_wind_vectors(m, lats, lons, u10, v10, 
                          bbox=None, grid_step=3, max_vectors=50):
    """
    Ajoute vecteurs de vent GRIB sur carte Folium.
    
    Args:
        m: Carte Folium
        lats, lons: Grilles GRIB
        u10, v10: Composantes vent
        bbox: (lat_min, lat_max, lon_min, lon_max) ou None pour tout
        grid_step: Espacement entre vecteurs (en indices de grille)
        max_vectors: Nombre max de vecteurs
    """
    # Calculer vent
    speed_ms = np.hypot(u10, v10)
    speed_kn = speed_ms * 1.94384
    direction = (270.0 - np.degrees(np.arctan2(v10, u10))) % 360.0
    
    max_speed_kn = speed_kn.max()
    
    # Filtrer par bbox si fourni
    if bbox:
        lat_min, lat_max, lon_min, lon_max = bbox
        mask = ((lats >= lat_min) & (lats <= lat_max) & 
                (lons >= lon_min) & (lons <= lon_max))
    else:
        mask = np.ones_like(lats, dtype=bool)
    
    # Sous-échantillonner grille
    indices = []
    for i in range(0, lats.shape[0], grid_step):
        for j in range(0, lats.shape[1], grid_step):
            if mask[i, j]:
                indices.append((i, j))
    
    # Limiter nombre de vecteurs
    if len(indices) > max_vectors:
        step = len(indices) // max_vectors
        indices = indices[::step]
    
    print(f"    Ajout de {len(indices)} vecteurs de vent...")
    
    # Ajouter marqueurs
    for i, j in indices:
        lat = lats[i, j]
        lon = lons[i, j]
        wind_speed = speed_kn[i, j]
        wind_dir = direction[i, j]
        
        icon = create_wind_arrow_svg(wind_dir, wind_speed, max_speed_kn)
        
        popup_html = f"""
        <div style="width: 180px;">
            <b>🌬️ Vent GRIB</b><br>
            <hr style="margin: 3px 0;">
            📍 {lat:.2f}°N, {lon:.2f}°W<br>
            💨 <b>{wind_speed:.1f} kn</b> ({wind_speed*1.852:.1f} km/h)<br>
            🧭 <b>{wind_dir:.0f}°</b> (depuis {get_wind_compass(wind_dir)})
        </div>
        """
        
        folium.Marker(
            [lat, lon],
            icon=icon,
            popup=folium.Popup(popup_html, max_width=200)
        ).add_to(m)


def route_to_folium_with_wind(route_waypoints, start, end, 
                               lats, lons, u10, v10,
                               filename="route_avec_vent.html"):
    """
    Crée carte Folium avec route ET vecteurs de vent GRIB.
    """
    print("\n" + "="*70)
    print("  GÉNÉRATION CARTE AVEC VENT")
    print("="*70 + "\n")
    
    # Centre carte
    center_lat = (start[0] + end[0]) / 2
    center_lon = (start[1] + end[1]) / 2
    
    # Créer carte
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=7,
        tiles='OpenStreetMap'
    )
    
    #  1. ROUTE PRINCIPALE
    if route_waypoints:
        coords = [(wp['lat'], wp['lon']) for wp in route_waypoints]
        folium.PolyLine(
            coords, 
            color='blue', 
            weight=4, 
            opacity=0.8,
            popup="Route calculée"
        ).add_to(m)
        
        print(f"  ✓ Route tracée ({len(coords)} waypoints)")
    
    #  2. VECTEURS DE VENT (bbox autour de la route)
    if route_waypoints:
        all_lats = [wp['lat'] for wp in route_waypoints]
        all_lons = [wp['lon'] for wp in route_waypoints]
        
        lat_min = min(all_lats) - 0.5
        lat_max = max(all_lats) + 0.5
        lon_min = min(all_lons) - 0.5
        lon_max = max(all_lons) + 0.5
        
        bbox = (lat_min, lat_max, lon_min, lon_max)
    else:
        lat_min = min(start[0], end[0]) - 1.0
        lat_max = max(start[0], end[0]) + 1.0
        lon_min = min(start[1], end[1]) - 1.0
        lon_max = max(start[1], end[1]) + 1.0
        bbox = (lat_min, lat_max, lon_min, lon_max)
    
    add_grib_wind_vectors(m, lats, lons, u10, v10, 
                          bbox=bbox, grid_step=4, max_vectors=40)
    
    #  3. WAYPOINTS (échantillonnés)
    if route_waypoints:
        step = max(1, len(route_waypoints) // 10)
        
        for i in range(0, len(route_waypoints), step):
            wp = route_waypoints[i]
            
            #  GESTION DES VALEURS None
            wind_speed = wp.get('wind_speed')
            wind_direction = wp.get('wind_direction')
            
            if wind_speed is not None and wind_direction is not None:
                wind_info = f"🌬️ Vent: {wind_speed:.1f} kn @ {wind_direction:.0f}°"
            else:
                wind_info = "🌬️ Vent: N/A"
            
            popup_text = f"""
            <b>Waypoint {i}</b><br>
            <hr style="margin: 3px 0;">
            📍 ({wp['lat']:.2f}°, {wp['lon']:.2f}°)<br>
            ⏰ {wp['timestamp'].strftime('%d/%m %H:%M')}<br>
            🧭 Cap: {wp['heading']:.0f}°<br>
            ⛵ Vitesse: {wp['boat_speed']:.1f} kn<br>
            {wind_info}
            """
            
            folium.CircleMarker(
                [wp['lat'], wp['lon']],
                radius=4,
                popup=folium.Popup(popup_text, max_width=200),
                color='blue',
                fill=True,
                fillColor='cyan',
                fillOpacity=0.8
            ).add_to(m)
        
        print(f"  ✓ {len(range(0, len(route_waypoints), step))} waypoints marqués")
    
    #  4. DÉPART / ARRIVÉE
    folium.Marker(
        start,
        popup='🚢 DÉPART',
        icon=folium.Icon(color='green', icon='play', prefix='fa')
    ).add_to(m)
    
    folium.Marker(
        end,
        popup='🏁 ARRIVÉE',
        icon=folium.Icon(color='red', icon='flag', prefix='fa')
    ).add_to(m)
    
    print(f"  ✓ Départ/Arrivée marqués")
    
    #  5. LÉGENDE
    if route_waypoints:
        duration_h = route_waypoints[-1]['g_cost'] / 3600
        
        #  Statistiques vent (filtrer None)
        wind_speeds = [wp.get('wind_speed') for wp in route_waypoints 
                      if wp.get('wind_speed') is not None]
        
        if wind_speeds:
            avg_wind = np.mean(wind_speeds)
            max_wind = max(wind_speeds)
            wind_stats = f"""
            <b>🌬️ Vent moyen:</b> {avg_wind:.1f} kn<br>
            <b>🌬️ Vent max:</b> {max_wind:.1f} kn<br>
            """
        else:
            wind_stats = "<b>🌬️ Vent:</b> N/A<br>"
        
        eta = route_waypoints[-1]['timestamp'].strftime('%d/%m %H:%M')
        
        legend_html = f"""
        <div style="position: fixed; 
                    top: 10px; right: 10px; 
                    background-color: white; 
                    border: 2px solid blue; 
                    z-index: 9999; 
                    padding: 12px;
                    border-radius: 5px;
                    font-size: 12px;
                    box-shadow: 3px 3px 10px rgba(0,0,0,0.3);">
            <b>🗺️ Route Maritime</b><br>
            <hr style="margin: 5px 0;">
            <b>Waypoints:</b> {len(route_waypoints)}<br>
            <b>Durée:</b> {duration_h:.1f}h ({duration_h/24:.1f}j)<br>
            <b>ETA:</b> {eta}<br>
            <hr style="margin: 5px 0;">
            {wind_stats}
            <hr style="margin: 5px 0;">
            <b>Échelle vent:</b><br>
            <span style="color: #00ff00; font-size: 16px;">●</span> < 10 kn<br>
            <span style="color: #ffff00; font-size: 16px;">●</span> 10-20 kn<br>
            <span style="color: #ff8800; font-size: 16px;">●</span> 20-30 kn<br>
            <span style="color: #ff0000; font-size: 16px;">●</span> > 30 kn
        </div>
        """
    else:
        legend_html = f"""
        <div style="position: fixed; 
                    top: 10px; right: 10px; 
                    background-color: white; 
                    border: 2px solid grey; 
                    z-index: 9999; 
                    padding: 12px;
                    border-radius: 5px;">
            <b>🌬️ Vents GRIB</b><br>
            <hr>
            <span style="color: #00ff00;">●</span> < 10 kn<br>
            <span style="color: #ffff00;">●</span> 10-20 kn<br>
            <span style="color: #ff8800;">●</span> 20-30 kn<br>
            <span style="color: #ff0000;">●</span> > 30 kn
        </div>
        """
    
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Sauvegarder
    m.save(filename)
    
    print(f"\n{'='*70}")
    print(f" Carte sauvegardée: {filename}")
    print(f"{'='*70}\n")
    
    return m


# fonction pas utile encore mais dont on peut s'inspirer pour la suite 


def create_wind_animation_map(lat, lon, time_indices=[0, 12, 24, 36, 48],
                              filename="wind_animation.html"):
    """
    Carte avec slider temporel pour animation du vent.

    Args:
        time_indices: Liste des index temporels à afficher
    """
    print(f" Création animation vent pour ({lat:.2f}, {lon:.2f})...\n")

    wind_data = fetch_wind_data(lat, lon)

    # Créer carte
    m = folium.Map(
        location=[lat, lon],
        zoom_start=7,
        tiles='OpenStreetMap'
    )

    # Créer groupes de features par timestamp
    feature_groups = []

    for idx in time_indices:
        time_str = wind_data['hourly']['time'][idx]

        # Créer groupe pour ce timestamp
        fg = folium.FeatureGroup(name=f"Vent {time_str}")

        # Ajouter vecteurs
        hourly = wind_data['hourly']
        wind_speed = hourly['wind_speed_10m'][idx]
        wind_dir = hourly['wind_direction_10m'][idx]
        max_speed = max(hourly['wind_speed_10m'])

        # Grille 5x5
        grid_size = 5
        offset = 1.0  # ±1° autour du centre

        for i in range(grid_size):
            for j in range(grid_size):
                grid_lat = lat - offset + (i / (grid_size-1)) * 2 * offset
                grid_lon = lon - offset + (j / (grid_size-1)) * 2 * offset

                icon = create_wind_arrow_svg(wind_dir, wind_speed, max_speed)

                popup = f"""
                <b> {time_str}</b><br>
                {wind_speed:.1f} km/h ({wind_speed/1.852:.1f} kn)<br>
                {wind_dir:.0f}° ({get_wind_compass(wind_dir)})
                """

                folium.Marker(
                    [grid_lat, grid_lon],
                    icon=icon,
                    popup=popup
                ).add_to(fg)

        feature_groups.append(fg)
        fg.add_to(m)

    # Ajouter contrôle des couches
    folium.LayerControl().add_to(m)

    m.save(filename)
    print(f" Animation sauvegardée: {filename}")
    print(f"   Utilisez le contrôle des couches pour naviguer entre les heures")

    return m


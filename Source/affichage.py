import folium
import numpy as np


def create_wind_arrow_svg(direction_from_deg, speed_kn, max_speed_kn=40):
    """
    Crée SVG d'une flèche de vent.
    direction_from_deg = d'où vient le vent (météo)
    La flèche affichée pointe vers où VA le vent (= +180).
    """
    size = 25 + (speed_kn / max_speed_kn) * 25
    size = min(max(size, 20), 60)

    if speed_kn < 10:
        color = '#00ff00'
    elif speed_kn < 20:
        color = '#ffff00'
    elif speed_kn < 30:
        color = '#ff8800'
    else:
        color = '#ff0000'

    rotation = (direction_from_deg + 180) % 360

    svg = f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24"
         style="transform: rotate({rotation}deg);">
        <path d="M12 2 L12 18 M12 18 L8 14 M12 18 L16 14"
              stroke="{color}" stroke-width="3" fill="none"
              stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="12" cy="20" r="2" fill="{color}"/>
    </svg>
    """
    return folium.DivIcon(html=svg)


def get_wind_compass(direction):
    directions = [
        "Nord", "NNE", "NE", "ENE",
        "Est", "ESE", "SE", "SSE",
        "Sud", "SSO", "SO", "OSO",
        "Ouest", "ONO", "NO", "NNO"
    ]
    idx = int((direction + 11.25) / 22.5) % 16
    return directions[idx]


def _color_from_twa(twa):
    """
    Couleur par allure (simple):
    - près: bleu
    - reaching: vert
    - portant: orange/rouge
    """
    if twa is None:
        return "blue"
    if twa < 60:
        return "#2b6cb0"
    if twa < 110:
        return "#2f855a"
    if twa < 150:
        return "#dd6b20"
    return "#c53030"


def _segment_route(route_waypoints):
    """
    Segmente la route en tronçons homogènes (même tack approx),
    et garde les points clés (manœuvres).
    """
    if not route_waypoints:
        return []

    segments = []
    current = [route_waypoints[0]]

    for i in range(1, len(route_waypoints)):
        prev = route_waypoints[i - 1]
        wp = route_waypoints[i]

        # changement d'amure => nouvelle section
        if prev.get("tack") is not None and wp.get("tack") is not None and prev.get("tack") != wp.get("tack"):
            current.append(wp)
            segments.append(current)
            current = [wp]
            continue

        # manœuvre explicitement détectée
        if wp.get("maneuver") in ("tack", "gybe"):
            current.append(wp)
            segments.append(current)
            current = [wp]
            continue

        current.append(wp)

    if len(current) >= 2:
        segments.append(current)

    return segments


def route_to_folium_with_wind(route_waypoints, start, end,
                             filename="route_avec_vent.html"):
    """
    Crée carte Folium avec:
    - route segmentée et colorée par TWA
    - waypoints rares + manœuvres marquées
    - vent affiché AU timestamp du waypoint (celui utilisé par le routeur)
    """
    print("\n" + "=" * 70)
    print("GÉNÉRATION CARTE AVEC VENT")
    print("=" * 70 + "\n")

    center_lat = (start[0] + end[0]) / 2
    center_lon = (start[1] + end[1]) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=7,
        tiles='OpenStreetMap'
    )

    # segments route
    if route_waypoints:
        segments = _segment_route(route_waypoints)

        for seg in segments:
            coords = [(wp["lat"], wp["lon"]) for wp in seg]
            # couleur du segment: moyenne TWA
            twas = [wp.get("twa") for wp in seg if wp.get("twa") is not None]
            twa_mean = float(np.mean(twas)) if twas else None
            color = _color_from_twa(twa_mean)

            folium.PolyLine(
                coords,
                color=color,
                weight=4,
                opacity=0.85
            ).add_to(m)

        print(f"✓ Route tracée ({len(route_waypoints)} waypoints, {len(segments)} segments)")

    # waypoints: on en met moins + manœuvres
    if route_waypoints:
        step = max(1, len(route_waypoints) // 12)
        idxs = set(range(0, len(route_waypoints), step))
        for i, wp in enumerate(route_waypoints):
            if i not in idxs and wp.get("maneuver") not in ("tack", "gybe"):
                continue

            wind_speed = wp.get("wind_speed")
            wind_dir = wp.get("wind_direction")
            twa = wp.get("twa")

            wind_info = "🌬️ Vent: N/A"
            if wind_speed is not None and wind_dir is not None:
                wind_info = f"🌬️ Vent: {wind_speed:.1f} kn @ {wind_dir:.0f}° ({get_wind_compass(wind_dir)})"

            man = wp.get("maneuver")
            man_info = ""
            if man == "tack":
                man_info = "<br>🔁 Virement de bord"
            elif man == "gybe":
                man_info = "<br>🔁 Empannage"

            popup_text = f"""
            <b>Waypoint {i}</b><br>
            <hr style="margin: 3px 0;">
            📍 ({wp['lat']:.2f}°, {wp['lon']:.2f}°)<br>
            ⏰ {wp['timestamp'].strftime('%d/%m %H:%M')}<br>
            🧭 Cap: {wp['heading']:.0f}°<br>
            ⛵ Vitesse: {wp['boat_speed']:.1f} kn<br>
            🎯 TWA: {twa:.0f}°<br>
            {wind_info}
            {man_info}
            """

            color = "blue" if man is None else ("purple" if man == "tack" else "orange")
            folium.CircleMarker(
                [wp["lat"], wp["lon"]],
                radius=5 if man else 3,
                popup=folium.Popup(popup_text, max_width=240),
                color=color,
                fill=True,
                fillOpacity=0.85
            ).add_to(m)

        print("✓ Waypoints échantillonnés + manœuvres marquées")

    # départ / arrivée
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

    # légende
    if route_waypoints:
        duration_h = route_waypoints[-1]["g_cost"] / 3600.0
        eta = route_waypoints[-1]["timestamp"].strftime('%d/%m %H:%M')

        wind_speeds = [wp.get("wind_speed") for wp in route_waypoints if wp.get("wind_speed") is not None]
        if wind_speeds:
            avg_wind = float(np.mean(wind_speeds))
            max_wind = float(np.max(wind_speeds))
            wind_stats = f"""
            <b>🌬️ Vent moyen:</b> {avg_wind:.1f} kn<br>
            <b>🌬️ Vent max:</b> {max_wind:.1f} kn<br>
            """
        else:
            wind_stats = "<b>🌬️ Vent:</b> N/A<br>"

        legend_html = f"""
        <div style="position: fixed;
                    top: 10px; right: 10px;
                    background-color: white;
                    border: 2px solid #444;
                    z-index: 9999;
                    padding: 12px;
                    border-radius: 5px;
                    font-size: 12px;
                    box-shadow: 3px 3px 10px rgba(0,0,0,0.3);">
            <b>🗺️ Route Maritime</b><br>
            <hr style="margin: 5px 0;">
            <b>Waypoints:</b> {len(route_waypoints)}<br>
            <b>Durée (coût):</b> {duration_h:.1f}h<br>
            <b>ETA:</b> {eta}<br>
            <hr style="margin: 5px 0;">
            {wind_stats}
            <hr style="margin: 5px 0;">
            <b>Couleur route (TWA):</b><br>
            <span style="color:#2b6cb0;">━</span> près<br>
            <span style="color:#2f855a;">━</span> travers<br>
            <span style="color:#dd6b20;">━</span> largue<br>
            <span style="color:#c53030;">━</span> portant<br>
            <hr style="margin: 5px 0;">
            <b>Manœuvres:</b><br>
            <span style="color:purple;">●</span> virement<br>
            <span style="color:orange;">●</span> empannage
        </div>
        """
    else:
        legend_html = """
        <div style="position: fixed;
                    top: 10px; right: 10px;
                    background-color: white;
                    border: 2px solid grey;
                    z-index: 9999;
                    padding: 12px;
                    border-radius: 5px;">
            <b>🌬️ Vent</b>
        </div>
        """

    m.get_root().html.add_child(folium.Element(legend_html))
    m.save(filename)
    print(f"✓ Carte sauvegardée: {filename}")
    return m

"""
Main script - Routeur météorologique
Adapté à la nouvelle API:
- GRIB temporel (load_grib_wind_fields + interpolation spatio-temporelle)
- Routeur: calculate_route_astar_fixed(..., grib_fields, ...)
- Affichage: route_to_folium_with_wind(route, START, END, filename=...)
"""
import numpy as np
from datetime import datetime

# Imports locaux
from outils import haversine
from polaire import load_polar_diagram
from meteo import load_grib_wind_fields
from routeur import calculate_route_astar_fixed
from affichage import route_to_folium_with_wind
from landmask import LandMask


def main():
    """Point d'entrée principal."""

    print("\n" + "=" * 70)
    print("⛵ ROUTEUR MÉTÉOROLOGIQUE - TDLOG")
    print("=" * 70 + "\n")

    # 1. Charger polaires
    print("\n1) Chargement polaires bateau...")
    twa_arr, tws_arr, speed_mat = load_polar_diagram("docs/Figaro2.csv")

    # 2. Charger GRIB (multi-échéances si présentes dans le fichier)
    print("\n2) Chargement données météo GRIB (spatio-temporel)...")
    grib_fields, meta = load_grib_wind_fields(
        "docs/Atlantic_Coast_12km_WRF_WAM_260105-00.grb",
        normalize_lons=True
    )

    print("✓ GRIB chargé:")
    print(f"  Nb échéances: {meta['n_times']}")
    print(f"  Times: {meta['times'][0]} -> {meta['times'][-1]}")
    print(f"  Shape: {meta['shape']}")
    print(f"  Zone: lat [{meta['lat_range'][0]:.2f}, {meta['lat_range'][1]:.2f}]")
    print(f"        lon [{meta['lon_range'][0]:.2f}, {meta['lon_range'][1]:.2f}]")

    # 3. Charger landmask (optionnel)
    print("\n3) Chargement landmask...")
    try:
        landmask = LandMask("gshhs_land_water_mask_3km_i.tif", verbose=True)
    except Exception as e:
        print(f" Landmask non disponible, continuons sans ({e})")
        landmask = None

    # 4. Configuration route
    print("\n4) Configuration route...")
    START = (46.5, -2.5)  # Large La Rochelle
    END = (43.8, -1.8)    # Large Biarritz

    # IMPORTANT: si la date de départ est hors plage du GRIB, l'interpolation temporelle "clamp"
    # sur la première/dernière échéance.
    # Ici on garde votre date, mais vous pouvez aussi choisir meta['times'][0] pour coller au GRIB.
    DEPARTURE = datetime(2025, 12, 8, 0, 0, 0)

    print(f"  Départ:  {START[0]:.2f}°N, {START[1]:.2f}°")
    print(f"  Arrivée: {END[0]:.2f}°N, {END[1]:.2f}°")
    print(f"  Date: {DEPARTURE.strftime('%d/%m/%Y %H:%M')}")

    # 5. Calcul route
    print("\n5) Calcul route avec A* (VMG + manœuvres + coût composite)...")
    route = calculate_route_astar_fixed(
        START[0], START[1], END[0], END[1], DEPARTURE,
        twa_arr, tws_arr, speed_mat,
        grib_fields,
        time_step=3600,
        landmask=landmask,
        max_iterations=30000,
        arrival_threshold=15000,
        # nouveaux paramètres utiles (laisser par défaut si vous voulez)
        dlat=0.05,
        dlon=0.05,
        beam_width=40
    )

    # 6. Affichage résultats
    if route:
        print("\n" + "=" * 70)
        print(" ROUTE CALCULÉE !")
        print("=" * 70)

        total_dist = sum(
            haversine(route[i]["lat"], route[i]["lon"],
                      route[i + 1]["lat"], route[i + 1]["lon"])
            for i in range(len(route) - 1)
        )

        # Attention: g_cost est maintenant un "coût composite" (temps + pénalités),
        # pas uniquement le temps pur.
        duration_h = route[-1]["g_cost"] / 3600.0
        avg_speed = (total_dist / 1852.0) / duration_h if duration_h > 0 else 0.0

        print("\nSTATISTIQUES:")
        print(f"  Waypoints: {len(route)}")
        print(f"  Distance: {total_dist/1852:.1f} nm")
        print(f"  Durée (coût): {duration_h:.1f}h ({duration_h/24:.1f}j)")
        print(f"  Vitesse moy (approx): {avg_speed:.1f} kn")
        print(f"  ETA: {route[-1]['timestamp'].strftime('%d/%m/%Y %H:%M')}")

        # Conditions vent
        wind_speeds = [wp["wind_speed"] for wp in route if wp.get("wind_speed") is not None]
        if wind_speeds:
            print("\nCONDITIONS VENT:")
            print(f"  Min: {min(wind_speeds):.1f} kn")
            print(f"  Max: {max(wind_speeds):.1f} kn")
            print(f"  Moyenne: {np.mean(wind_speeds):.1f} kn")

        # Manœuvres
        maneuvers = [wp.get("maneuver") for wp in route if wp.get("maneuver") in ("tack", "gybe")]
        if maneuvers:
            n_tack = sum(1 for m in maneuvers if m == "tack")
            n_gybe = sum(1 for m in maneuvers if m == "gybe")
            print("\nMANŒUVRES:")
            print(f"  Virements: {n_tack}")
            print(f"  Empannages: {n_gybe}")

        # 7. Génération carte
        print("\n6) Génération carte...")
        m = route_to_folium_with_wind(
            route, START, END,
            filename="route_finale.html"
        )

        print("\nTERMINÉ !")
        print("  Ouvrez route_finale.html pour voir le résultat")

    else:
        print("\nAucune route trouvée")
        print("💡 Essayez d'augmenter max_iterations ou arrival_threshold, ou beam_width")


if __name__ == "__main__":
    main()

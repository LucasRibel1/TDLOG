"""
Main script - Routeur météorologique
"""
import numpy as np
from datetime import datetime

# Imports locaux
from outils import haversine, bearing, destination_point
from polaire import load_polar_diagram, get_boat_speed, get_max_speed
from meteo import load_grib_wind, get_wind_from_grib
from routeur import calculate_route_astar_fixed
from affichage import route_to_folium_with_wind
from landmask import LandMask

def main():
    """Point d'entrée principal."""
    
    print("\n" + "="*70)
    print("� ROUTEUR MÉTÉOROLOGIQUE - TDLOG")
    print("="*70 + "\n")
    
    # 1. Charger polaires
    print("\n Chargement polaires bateau...")
    twa_arr, tws_arr, speed_mat = load_polar_diagram("docs/Figaro2.csv")
    
    # 2. Charger GRIB
    print("\n2️Chargement données météo GRIB...")
    lats, lons, u10, v10, meta = load_grib_wind(
        "Atlantic_Coast_12km_WRF_WAM_251208-00.grb",
        normalize_lons=True
    )
    
    # 3. Charger landmask (optionnel)
    print("\n3️ Chargement landmask...")
    try:
        landmask = LandMask("gshhs_land_water_mask_3km_i.tif")
    except:
        print(" Landmask non disponible, continuons sans")
        landmask = None
    
    # 4. Configuration route
    print("\n4️ Configuration route...")
    START = (46.5, -2.5)  # Large La Rochelle
    END = (43.8, -1.8)    # Large Biarritz
    DEPARTURE = datetime(2025, 12, 8, 0, 0, 0)
    
    print(f"  Départ:  {START[0]:.2f}°N, {START[1]:.2f}°W")
    print(f"  Arrivée: {END[0]:.2f}°N, {END[1]:.2f}°W")
    print(f"  Date: {DEPARTURE.strftime('%d/%m/%Y %H:%M')}")
    
    # 5. Calcul route
    print("\n5️ Calcul route avec A*...")
    route = calculate_route_astar_fixed(
        START[0], START[1], END[0], END[1], DEPARTURE,
        twa_arr, tws_arr, speed_mat,
        lats, lons, u10, v10,
        n_directions=32,
        time_step=3600,
        landmask=landmask,
        max_iterations=30000,
        arrival_threshold=15000
    )
    
    # 6. Affichage résultats
    if route:
        print("\n" + "="*70)
        print(" ROUTE CALCULÉE !")
        print("="*70)
        
        # Stats
        total_dist = sum(
            haversine(route[i]['lat'], route[i]['lon'],
                     route[i+1]['lat'], route[i+1]['lon'])
            for i in range(len(route)-1)
        )
        
        duration_h = route[-1]['g_cost'] / 3600
        avg_speed = (total_dist/1852) / duration_h if duration_h > 0 else 0
        
        print(f"\n STATISTIQUES:")
        print(f"  Waypoints: {len(route)}")
        print(f"  Distance: {total_dist/1852:.1f} nm")
        print(f"  Durée: {duration_h:.1f}h ({duration_h/24:.1f}j)")
        print(f"  Vitesse moy: {avg_speed:.1f} kn")
        print(f"  ETA: {route[-1]['timestamp'].strftime('%d/%m/%Y %H:%M')}")
        
        # Conditions vent
        wind_speeds = [wp['wind_speed'] for wp in route if wp.get('wind_speed')]
        if wind_speeds:
            print(f"\n CONDITIONS VENT:")
            print(f"  Min: {min(wind_speeds):.1f} kn")
            print(f"  Max: {max(wind_speeds):.1f} kn")
            print(f"  Moyenne: {np.mean(wind_speeds):.1f} kn")
        
        # 7. Génération carte
        print("\n6️ Génération carte...")
        m = route_to_folium_with_wind(
            route, START, END,
            lats, lons, u10, v10,
            filename="route_finale.html"
        )
        
        print("\n TERMINÉ !")
        print("   Ouvrez route_finale.html pour voir le résultat")
        
    else:
        print("\n Aucune route trouvée")
        print("💡 Essayez d'augmenter max_iterations ou n_directions")


if __name__ == "__main__":
    main()

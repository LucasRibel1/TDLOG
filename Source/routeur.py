import heapq
from datetime import timedelta
import numpy as np
from outils import *
from polaire import *
from meteo import *

def compute_heuristic_with_upwind(lat, lon, goal_lat, goal_lon, 
                                   wind_speed, wind_dir, max_speed,
                                   twa_arr, tws_arr, speed_mat):
    """
    Heuristique tenant compte du louvoyage.
    """
    dist = haversine(lat, lon, goal_lat, goal_lon)
    bearing_to_goal = bearing(lat, lon, goal_lat, goal_lon)
    
    # TWA si route directe
    twa_direct = abs((wind_dir - bearing_to_goal + 180) % 360 - 180)
    
    # Vitesse effective
    boat_speed = get_boat_speed(twa_direct, wind_speed, twa_arr, tws_arr, speed_mat)
    
    # Si vent de face (TWA < 50°), simuler louvoyage
    if twa_direct < 50:
        # Trouver meilleur TWA pour remonter au vent (généralement 45-55°)
        best_vmg = 0
        for test_twa in [45, 50, 55, 60]:
            speed_at_twa = get_boat_speed(test_twa, wind_speed, 
                                          twa_arr, tws_arr, speed_mat)
            # VMG = vitesse × cos(TWA)
            vmg = speed_at_twa * np.cos(np.radians(test_twa))
            if vmg > best_vmg:
                best_vmg = vmg
        
        # Distance augmente de ~40% à cause du zigzag
        effective_dist = dist * 1.4
        effective_speed = best_vmg * 0.514444  # kn → m/s
        
        if effective_speed > 0:
            return effective_dist / effective_speed
        else:
            return 999999  # Impossible
    
    # Si allure normale
    else:
        if boat_speed > 0:
            return dist / (boat_speed * 0.514444)
        else:
            return 999999


def expand_waypoint(lat, lon, timestamp, g_cost, 
                   twa_arr, tws_arr, speed_mat,
                   lats, lons, u10, v10,  # ← Paramètres GRIB
                   n_directions=36, time_step=3600,
                   landmask=None):
    """
    Génère waypoints atteignables (avec vent GRIB réel).
    """
    candidates = []
    angle_step = 360.0 / n_directions
    
    # RÉCUPÉRER VENT RÉEL depuis GRIB
    try:
        wind_speed, wind_dir = get_wind_from_grib(lat, lon, timestamp, 
                                                   lats, lons, u10, v10)
    except Exception as e:
        # Si point hors grille GRIB, retourner liste vide
        return candidates
    
    for i in range(n_directions):
        heading = i * angle_step
        
        # Calculer TWA
        twa = abs((wind_dir - heading + 180) % 360 - 180)
        
        # Vitesse bateau
        boat_speed = get_boat_speed(twa, wind_speed, twa_arr, tws_arr, speed_mat)
        
        if boat_speed < 0.5:
            continue
        
        # Distance parcourue (nœuds -> m/s)
        distance = boat_speed * 0.514444 * time_step
        
        # Nouvelle position
        new_lat, new_lon = destination_point(lat, lon, heading, distance)
        
        # Vérifier que nouvelle position est dans zone GRIB
        if (new_lat < lats.min() or new_lat > lats.max() or
            new_lon < lons.min() or new_lon > lons.max()):
            continue  # Hors zone
        
        # Vérifier terre
        if landmask and not landmask.is_path_clear(lat, lon, new_lat, new_lon, n_samples=3):
            continue
        
        # Nouveau waypoint
        candidate = {
            'lat': new_lat,
            'lon': new_lon,
            'timestamp': timestamp + timedelta(seconds=time_step),
            'heading': heading,
            'boat_speed': boat_speed,
            'wind_speed': wind_speed,
            'wind_direction': wind_dir,
            'g_cost': g_cost + time_step,
            'parent': (lat, lon, timestamp)
        }
        
        candidates.append(candidate)
    
    return candidates


def calculate_route_astar_fixed(start_lat, start_lon, goal_lat, goal_lon, departure,
                                twa_arr, tws_arr, speed_mat,
                                lats, lons, u10, v10,  # ← Paramètres GRIB
                                n_directions=12, time_step=3600,
                                landmask=None,
                                max_iterations=50000,
                                arrival_threshold=8000):
    """
    A* avec vent GRIB réel et détection de terre.
    """
    
    print(f"Route: ({start_lat:.2f},{start_lon:.2f}) → ({goal_lat:.2f},{goal_lon:.2f})")
    print(f"Vent: DONNÉES GRIB RÉELLES (Golfe de Gascogne)")
    
    if landmask and landmask.dataset:
        print(f"  Landmask: activé")
    else:
        print(f"  Landmask: désactivé")
    
    print(f"  Paramètres: max_iter={max_iterations}, seuil_arrivée={arrival_threshold/1000:.1f}km\n")
    
    # Vérifier départ et arrivée dans zone GRIB
    if (start_lat < lats.min() or start_lat > lats.max() or
        start_lon < lons.min() or start_lon > lons.max()):
        print(f" Point de départ hors zone GRIB!")
        print(f"   Zone GRIB: lat [{lats.min():.1f}, {lats.max():.1f}], lon [{lons.min():.1f}, {lons.max():.1f}]")
        return None
    
    if (goal_lat < lats.min() or goal_lat > lats.max() or
        goal_lon < lons.min() or goal_lon > lons.max()):
        print(f" Point d'arrivée hors zone GRIB!")
        return None
    
    # Vérifier terre avec landmask
    if landmask:
        if not landmask.is_sea(start_lat, start_lon):
            print(" Point de départ sur terre!")
            return None
        if not landmask.is_sea(goal_lat, goal_lon):
            print(" Point d'arrivée sur terre!")
            return None
    
    max_speed = get_max_speed(speed_mat)
    
    # Point initial
    start = {
        'lat': start_lat, 
        'lon': start_lon,
        'timestamp': departure,
        'heading': 0, 
        'boat_speed': 0,
        'wind_speed': None, 
        'wind_direction': None,
        'g_cost': 0.0, 
        'parent': None
    }
    
    h = haversine(start_lat, start_lon, goal_lat, goal_lon) / (max_speed * 0.514444)
    start['h_cost'] = h
    start['f_cost'] = h
    
    open_set = [(start['f_cost'], 0, start)]
    visited = {}
    all_waypoints = {(start_lat, start_lon, departure): start}
    counter = 1
    
    iteration = 0
    
    while open_set and iteration < max_iterations:
        iteration += 1
        
        _, _, current = heapq.heappop(open_set)
        
        dist = haversine(current['lat'], current['lon'], goal_lat, goal_lon)
        
        if iteration % 50 == 0:
            print(f"  Iter {iteration}: dist={dist/1852:.1f}nm, g={current['g_cost']/3600:.1f}h, queue={len(open_set)}")
        
        # Vérifier arrivée
        if dist < arrival_threshold:
            print(f"\n Arrivée atteinte ! ({iteration} itérations)")
            
            # Reconstruction
            path = []
            c = current
            while c is not None:
                path.append(c)
                
                if c['parent'] is None:
                    break
                
                if isinstance(c['parent'], tuple):
                    c = all_waypoints.get(c['parent'])
                else:
                    c = c['parent']
            
            path.reverse()
            return path
        
        # Clé de visite
        pos_key = (round(current['lat'], 1), round(current['lon'], 1))
        
        if pos_key in visited and visited[pos_key] <= current['g_cost']:
            continue
        
        visited[pos_key] = current['g_cost']
        
        # EXPANSION AVEC GRIB
        candidates = expand_waypoint(
            current['lat'], current['lon'], current['timestamp'], current['g_cost'],
            twa_arr, tws_arr, speed_mat,
            lats, lons, u10, v10,  # ← Données GRIB
            n_directions, time_step,
            landmask=landmask
        )
        
        # Ajouter candidats à open_set
        for cand in candidates:
            new_g = cand['g_cost']
            new_h = compute_heuristic_with_upwind(
                    cand['lat'], cand['lon'], goal_lat, goal_lon,
                    cand['wind_speed'], cand['wind_direction'], max_speed,
                    twa_arr, tws_arr, speed_mat
                )
            
            cand['h_cost'] = new_h
            cand['f_cost'] = new_g + new_h
            
            # Stocker dans all_waypoints
            cand_key = (cand['lat'], cand['lon'], cand['timestamp'])
            all_waypoints[cand_key] = cand
            
            # Parent pointe vers waypoint actuel
            cand['parent'] = (current['lat'], current['lon'], current['timestamp'])
            
            new_key = (round(cand['lat'], 1), round(cand['lon'], 1))
            if new_key not in visited or visited[new_key] > new_g:
                heapq.heappush(open_set, (cand['f_cost'], counter, cand))
                counter += 1
    
    print(f"\n Limite atteinte ({max_iterations} itérations)")
    print(f"   Distance finale: {dist/1852:.1f} nm (seuil: {arrival_threshold/1852:.1f} nm)")
    return None


def reconstruct_route(final_wp, all_waypoints):
    """
    Reconstruit route en remontant parents.
    
    Args:
        final_wp: Waypoint final
        all_waypoints: Dict de tous les waypoints créés
    
    Returns:
        Liste de waypoints du départ à l'arrivée
    """
    route = []
    current = final_wp
    
    while current is not None:
        route.append(current)
        if current['parent'] is None:
            break
        parent_key = current['parent']
        current = all_waypoints.get(parent_key)
    
    route.reverse()
    return route


print("\n Routeur A* avec GRIB prêt")

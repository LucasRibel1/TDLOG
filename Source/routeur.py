import heapq
from datetime import timedelta
import numpy as np

from outils import haversine, bearing, destination_point
from polaire import (
    get_boat_speed, get_max_speed,
    find_optimal_twa_upwind, find_optimal_twa_downwind
)
from meteo import get_wind_from_grib


# ============================================================
# Paramètres "routeur" (faciles à tweaker)
# ============================================================

DEFAULT_MIN_BOAT_SPEED_KN = 0.5

# pénalités (secondes)
PENALTY_TACK = 180.0       # virement de bord
PENALTY_GYBE = 120.0       # empannage
PENALTY_HEADING_CHANGE = 0.0  # si tu veux pénaliser toute rotation

# pénalités coût (secondes "virtuelles")
PENALTY_LOW_WIND = 300.0   # pénaliser zones molles
LOW_WIND_THRESHOLD_KN = 6.0

# beam search: garder les meilleurs n candidats par expansion
DEFAULT_BEAM_WIDTH = 40

# discrétisation d'état
DEFAULT_DLAT = 0.05   # degrés
DEFAULT_DLON = 0.05   # degrés
# DT est implicite: time_step


def _state_key(lat, lon, timestamp, departure, dlat, dlon, dt_seconds):
    """
    Hash robuste: on discretise sur grille spatio-temporelle explicite.
    """
    i = int(np.floor(lat / dlat))
    j = int(np.floor(lon / dlon))
    k = int(np.floor((timestamp - departure).total_seconds() / dt_seconds))
    return (i, j, k)


def _sign_of_tack(heading_deg: float, wind_dir_from_deg: float) -> int:
    """
    Signe d'amure via angle signé (wind - heading) dans [-180,180].
    >0 : vent vient de tribord, <0 : vent vient de bâbord (convention pratique).
    """
    delta = (wind_dir_from_deg - heading_deg + 540.0) % 360.0 - 180.0
    if abs(delta) < 1e-6:
        return 0
    return 1 if delta > 0 else -1


def _maneuver_penalty(prev_heading, new_heading, wind_dir_from, prev_tack, new_tack):
    """
    Détecte virement / empannage grossièrement via changement de signe d'amure.
    - au près: changement de tack => tack
    - au portant: changement de tack => gybe
    """
    if prev_heading is None:
        return 0.0, None

    if prev_tack == 0 or new_tack == 0:
        return 0.0, None

    if prev_tack == new_tack:
        return PENALTY_HEADING_CHANGE, None

    # distinguer près / portant via TWA approx
    # TWA = |wind - heading| dans [0,180]
    prev_twa = abs(((wind_dir_from - prev_heading + 540.0) % 360.0) - 180.0)
    new_twa = abs(((wind_dir_from - new_heading + 540.0) % 360.0) - 180.0)
    twa = 0.5 * (prev_twa + new_twa)

    if twa < 90.0:
        return PENALTY_TACK, "tack"
    return PENALTY_GYBE, "gybe"


def compute_heuristic_admissible(lat, lon, goal_lat, goal_lon, max_speed_kn):
    """
    Heuristique pessimiste/admissible: distance / Vmax théorique (polaires).
    Ne dépend pas d'un vent local, donc évite des surestimations bizarres.
    """
    dist = haversine(lat, lon, goal_lat, goal_lon)
    vmax_ms = max_speed_kn * 0.514444  # conversion locale OK mais on pourrait aussi centraliser
    if vmax_ms <= 1e-9:
        return 1e9
    return dist / vmax_ms


def _generate_candidate_headings(lat, lon, timestamp, goal_lat, goal_lon,
                                 wind_speed_kn, wind_dir_from,
                                 twa_arr, tws_arr, speed_mat,
                                 n_spread=6):
    """
    Remplace l'échantillonnage uniforme.
    On génère des caps autour:
    - du cap vers l'objectif
    - des angles de VMG près/portant optimaux (via polaires)
    """
    bearing_goal = bearing(lat, lon, goal_lat, goal_lon)

    # angles optimums polaires (en TWA)
    twa_up, _ = find_optimal_twa_upwind(wind_speed_kn, twa_arr, tws_arr, speed_mat)
    twa_dn, _ = find_optimal_twa_downwind(wind_speed_kn, twa_arr, tws_arr, speed_mat)

    base_headings = set()

    # 1) head towards goal +/- petit spread
    for d in np.linspace(-25, 25, n_spread):
        base_headings.add((bearing_goal + d) % 360.0)

    # 2) caps de près (deux amures): heading = wind_dir_from ± twa_up + 180? non:
    # TWA = |wind_from - heading| => heading = wind_from ± TWA
    for s in (-1, 1):
        base_headings.add((wind_dir_from + s * twa_up) % 360.0)

    # 3) caps de portant: heading = wind_from ± twa_dn
    for s in (-1, 1):
        base_headings.add((wind_dir_from + s * twa_dn) % 360.0)

    # 4) un peu de spread autour des optima pour laisser respirer
    for base in list(base_headings):
        for d in (-10, 10):
            base_headings.add((base + d) % 360.0)

    return sorted(base_headings)


def expand_waypoint(lat, lon, timestamp, g_cost,
                    twa_arr, tws_arr, speed_mat,
                    grib_fields,
                    goal_lat, goal_lon,
                    time_step=3600,
                    landmask=None,
                    prev_heading=None,
                    prev_tack=None,
                    beam_width=DEFAULT_BEAM_WIDTH):
    """
    Génère des waypoints atteignables avec:
    - vent GRIB spatio-temporel interpolé
    - caps restreints "intéressants" (VMG/polaires + goal)
    - manœuvres (tack/gybe) pénalisées
    - coût composite (temps + pénalités)
    """
    candidates = []

    # vent spatio-temporel au timestamp courant
    wind_speed, wind_dir = meteo_client.get_wind(lat, lon, timestamp)

    headings = _generate_candidate_headings(
        lat, lon, timestamp, goal_lat, goal_lon,
        wind_speed, wind_dir,
        twa_arr, tws_arr, speed_mat
    )

    for heading in headings:
        # TWA
        twa = abs((wind_dir - heading + 180) % 360 - 180)

        # vitesse polaire
        boat_speed = get_boat_speed(twa, wind_speed, twa_arr, tws_arr, speed_mat)
        if boat_speed < DEFAULT_MIN_BOAT_SPEED_KN:
            continue

        # distance parcourue
        distance_m = boat_speed * 0.514444 * time_step

        new_lat, new_lon = destination_point(lat, lon, heading, distance_m)

        # terre
        if landmask and not landmask.is_path_clear(lat, lon, new_lat, new_lon, n_samples=6):
            continue

        # tack/gybe
        new_tack = _sign_of_tack(heading, wind_dir)
        man_pen, man_type = _maneuver_penalty(prev_heading, heading, wind_dir, prev_tack, new_tack)

        # pénalité vent faible
        low_wind_pen = 0.0
        if wind_speed < LOW_WIND_THRESHOLD_KN:
            low_wind_pen = PENALTY_LOW_WIND

        # coût composite (en secondes "A*")
        composite_step = time_step + man_pen + low_wind_pen

        cand = {
            "lat": new_lat,
            "lon": new_lon,
            "timestamp": timestamp + timedelta(seconds=time_step),
            "heading": heading,
            "boat_speed": boat_speed,
            "wind_speed": wind_speed,
            "wind_direction": wind_dir,
            "twa": twa,
            "tack": new_tack,
            "maneuver": man_type,  # None / "tack" / "gybe"
            "g_cost": g_cost + composite_step,
            "g_time": None,  # optionnel si tu veux conserver temps pur
            "parent": (lat, lon, timestamp),
        }
        candidates.append(cand)

    # beam pruning simple: garder ceux qui minimisent un critère local (ex: g_cost + dist/vmax)
    if not candidates:
        return []

    # tri par "promesse" locale: distance restante
    dists = [haversine(c["lat"], c["lon"], goal_lat, goal_lon) for c in candidates]
    for c, d in zip(candidates, dists):
        c["_rank"] = d

    candidates.sort(key=lambda x: (x["_rank"], -x["boat_speed"]))
    candidates = candidates[:beam_width]
    for c in candidates:
        c.pop("_rank", None)

    return candidates


def calculate_route_astar_fixed(start_lat, start_lon, goal_lat, goal_lon, departure,
                               twa_arr, tws_arr, speed_mat,
                               grib_fields,
                               time_step=3600,
                               landmask=None,
                               max_iterations=50000,
                               arrival_threshold=8000,
                               dlat=DEFAULT_DLAT, dlon=DEFAULT_DLON,
                               beam_width=DEFAULT_BEAM_WIDTH):
    """
    A* (version plus robuste) avec:
    - GRIB temporel interpolé
    - état discret spatio-temporel cohérent
    - coût composite
    - beam pruning
    """
    print(f"Route: ({start_lat:.2f},{start_lon:.2f}) → ({goal_lat:.2f},{goal_lon:.2f})")
    print(f"GRIB: {len(grib_fields)} échéances")
    print(f"Landmask: {'activé' if (landmask and landmask.dataset) else 'désactivé'}")
    print(f"Paramètres: time_step={time_step}s, beam={beam_width}, max_iter={max_iterations}\n")

    # sanity time_step vs GRIB
    if len(grib_fields) >= 2:
        grib_dt = (grib_fields[1].valid_date - grib_fields[0].valid_date).total_seconds()
        if grib_dt > 0 and (time_step % grib_dt != 0) and (grib_dt % time_step != 0):
            print(f"⚠️ Attention: time_step ({time_step}s) pas multiple du pas GRIB ({int(grib_dt)}s).")

    if landmask:
        if not landmask.is_sea(start_lat, start_lon):
            print("Point de départ sur terre!")
            return None
        if not landmask.is_sea(goal_lat, goal_lon):
            print("Point d'arrivée sur terre!")
            return None

    max_speed = get_max_speed(speed_mat)

    start = {
        "lat": start_lat,
        "lon": start_lon,
        "timestamp": departure,
        "heading": None,
        "boat_speed": 0.0,
        "wind_speed": None,
        "wind_direction": None,
        "twa": None,
        "tack": None,
        "maneuver": None,
        "g_cost": 0.0,
        "parent": None,
    }

    start["h_cost"] = compute_heuristic_admissible(start_lat, start_lon, goal_lat, goal_lon, max_speed)
    start["f_cost"] = start["g_cost"] + start["h_cost"]

    open_set = [(start["f_cost"], 0, start)]
    counter = 1

    visited_best_g = {}  # state_key -> best g
    all_waypoints = {(start_lat, start_lon, departure): start}

    iteration = 0
    while open_set and iteration < max_iterations:
        iteration += 1
        _, _, current = heapq.heappop(open_set)

        dist = haversine(current["lat"], current["lon"], goal_lat, goal_lon)
        if iteration % 100 == 0:
            print(f"Iter {iteration}: dist={dist/1852:.1f}nm, g={current['g_cost']/3600:.1f}h(eq), queue={len(open_set)}")

        if dist < arrival_threshold:
            print(f"\nArrivée atteinte ! ({iteration} itérations)")
            path = []
            c = current
            while c is not None:
                path.append(c)
                if c["parent"] is None:
                    break
                c = all_waypoints.get(c["parent"])
            path.reverse()
            return path

        skey = _state_key(current["lat"], current["lon"], current["timestamp"],
                          departure, dlat, dlon, time_step)

        best_g = visited_best_g.get(skey)
        if best_g is not None and best_g <= current["g_cost"]:
            continue
        visited_best_g[skey] = current["g_cost"]

        # expansion
        candidates = expand_waypoint(
            current["lat"], current["lon"], current["timestamp"], current["g_cost"],
            twa_arr, tws_arr, speed_mat,
            grib_fields,
            goal_lat, goal_lon,
            time_step=time_step,
            landmask=landmask,
            prev_heading=current["heading"],
            prev_tack=current["tack"],
            beam_width=beam_width
        )

        for cand in candidates:
            cand["h_cost"] = compute_heuristic_admissible(
                cand["lat"], cand["lon"], goal_lat, goal_lon, max_speed
            )
            cand["f_cost"] = cand["g_cost"] + cand["h_cost"]

            cand_key = (cand["lat"], cand["lon"], cand["timestamp"])
            all_waypoints[cand_key] = cand
            cand["parent"] = (current["lat"], current["lon"], current["timestamp"])

            heapq.heappush(open_set, (cand["f_cost"], counter, cand))
            counter += 1

    print(f"\nLimite atteinte ({max_iterations} itérations)")
    if open_set:
        last = current
        dist = haversine(last["lat"], last["lon"], goal_lat, goal_lon)
        print(f"Distance finale: {dist/1852:.1f} nm (seuil: {arrival_threshold/1852:.1f} nm)")
    return None


print("\nRouteur A* (spatio-temporel + VMG + manœuvres) prêt")

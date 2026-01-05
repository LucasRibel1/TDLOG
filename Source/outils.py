import math
from conventions import deg2rad, rad2deg, wrap_360

EARTH_RADIUS_M = 6371000.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance orthodromique en mètres.
    Args: lat/lon en degrés décimaux
    Returns: distance en mètres
    """
    phi1 = deg2rad(lat1)
    phi2 = deg2rad(lat2)
    delta_phi = deg2rad(lat2 - lat1)
    delta_lambda = deg2rad(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2.0) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule le cap initial (en degrés) de point 1 vers point 2.
    Convention: 0°=Nord, sens horaire.
    """
    phi1 = deg2rad(lat1)
    phi2 = deg2rad(lat2)
    delta_lambda = deg2rad(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = (math.cos(phi1) * math.sin(phi2) -
         math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda))
    theta = math.atan2(y, x)
    return wrap_360(rad2deg(theta))


def destination_point(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """
    Calcule le point d'arrivée après avoir parcouru une distance sur un cap.
    Args:
        lat, lon: position départ (degrés)
        bearing_deg: cap en degrés
        distance_m: distance en mètres
    Returns: (lat, lon) destination
    """
    d = distance_m / EARTH_RADIUS_M
    brng = deg2rad(bearing_deg)

    lat1 = deg2rad(lat)
    lon1 = deg2rad(lon)

    lat2 = math.asin(math.sin(lat1) * math.cos(d) +
                     math.cos(lat1) * math.sin(d) * math.cos(brng))
    lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(d) * math.cos(lat1),
                             math.cos(d) - math.sin(lat1) * math.sin(lat2))

    return (rad2deg(lat2), rad2deg(lon2))

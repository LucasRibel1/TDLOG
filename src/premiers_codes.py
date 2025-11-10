# pour savoir si le point est accessibe ou non

import rasterio

with rasterio.open("landmask.tif") as dataset:
    lon, lat = -5.0, 45.0
    row, col = dataset.index(lon, lat)
    value = dataset.read(1)[row, col]  # 0 = terre, 1 = mer

# distance orthodromique 

import math

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance orthodromique en mètres
    Args: lat/lon en degrés décimaux
    Returns: distance en mètres
    """
    R = 6371000  # Rayon terrestre en mètres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2.0) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

#calcul du cap

def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule le cap initial (en degrés) de point 1 vers point 2
    Returns: cap en degrés (0-360)
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = (math.cos(phi1) * math.sin(phi2) -
         math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda))
    theta = math.atan2(y, x)
    
    return (math.degrees(theta) + 360) % 360


# calcul destination avec cap et distance 

def destination_point(lat: float, lon: float, bearing: float, 
                     distance: float) -> tuple[float, float]:
    """
    Calcule le point d'arrivée après avoir parcouru une distance sur un cap
    Args:
        lat, lon: position départ (degrés)
        bearing: cap en degrés
        distance: distance en mètres
    Returns: (lat, lon) destination
    """
    R = 6371000
    d = distance / R  # Distance angulaire
    brng = math.radians(bearing)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    
    lat2 = math.asin(math.sin(lat1) * math.cos(d) +
                     math.cos(lat1) * math.sin(d) * math.cos(brng))
    lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(d) * math.cos(lat1),
                             math.cos(d) - math.sin(lat1) * math.sin(lat2))
    
    return (math.degrees(lat2), math.degrees(lon2))


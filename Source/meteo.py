#penser à !pip install pygrib#

import pygrib
import numpy as np

FILE = "Atlantic_Coast_12km_WRF_WAM_251201-00.grb"

def load_grib_wind(filepath, normalize_lons=True):
    """
    Charge composantes U/V du vent depuis GRIB.
    
    Args:
        filepath: Chemin fichier GRIB
        normalize_lons: Si True, convertit 0-360° → -180 à +180°
    
    Returns:
        lats, lons, u10, v10, metadata
    """
    with pygrib.open(filepath) as grbs:
        # U10
        grb_u10 = grbs.select(
            indicatorOfParameter=33,
            typeOfLevel='heightAboveGround',
            level=10
        )[0]
        
        u10 = grb_u10.values
        lats, lons = grb_u10.latlons()
        
        # V10
        grbs.seek(0)
        grb_v10 = grbs.select(
            indicatorOfParameter=34,
            typeOfLevel='heightAboveGround',
            level=10
        )[0]
        
        v10 = grb_v10.values
    
    # Normaliser longitudes si demandé
    if normalize_lons:
        lons = np.where(lons > 180, lons - 360, lons)
    
    metadata = {
        'validDate': grb_u10.validDate,
        'shape': u10.shape,
        'resolution_km': abs(lats[1,0] - lats[0,0]) * 111,
        'lat_range': (lats.min(), lats.max()),
        'lon_range': (lons.min(), lons.max()),
    }
    
    return lats, lons, u10, v10, metadata


# Utilisation
lats, lons, u10, v10, meta = load_grib_wind(FILE, normalize_lons=True)

print(f"✓ GRIB chargé:")
print(f"  Zone: lat [{meta['lat_range'][0]:.1f}°, {meta['lat_range'][1]:.1f}°]")
print(f"        lon [{meta['lon_range'][0]:.1f}°, {meta['lon_range'][1]:.1f}°]")
print(f"  Date: {meta['validDate']}")
print(f"  Résolution: ~{meta['resolution_km']:.0f} km\n")



def wind_at(lat_target, lon_target, lats, lons, u10, v10):
    """
    Retourne le vent au point de grille le plus proche d'une coordonnée donnée.

    Parameters
    ----------
    lat_target, lon_target : float
        Coordonnées cibles en degrés.
    lats, lons : 2D arrays
        Matrices de latitude / longitude (sorties de grb.latlons()).
    u10, v10 : 2D arrays
        Composantes U/V du vent à 10 m (m/s), même shape que lats/lons.

    Returns
    -------
    speed : float
        Vitesse du vent (m/s).
    direction : float
        Direction du vent en degrés, méteo :
        - 0° = vent de nord
        - 90° = vent d'est
        - 180° = vent de sud
        - 270° = vent d'ouest
    lat_pt, lon_pt : float
        Coordonnées du point de grille utilisé.
    """

    # Distance au carré dans l'espace (lat, lon) pour trouver le point le plus proche
    dist2 = (lats - lat_target)**2 + (lons - lon_target)**2
    i, j = np.unravel_index(np.argmin(dist2), dist2.shape)

    u = u10[i, j]
    v = v10[i, j]

    # Vitesse
    speed = np.hypot(u, v)  # équivalent à sqrt(u**2 + v**2)

    # Direction méteo (d'où vient le vent)
    # atan2(v, u) donne l'angle (vecteur vers lequel souffle le vent)
    # On transforme en "d'où il vient" + convention méteo
    direction = (270.0 - np.degrees(np.arctan2(v, u))) % 360.0

    lat_pt = lats[i, j]
    lon_pt = lons[i, j]

    return speed, direction, lat_pt, lon_pt


def get_wind_from_grib(lat, lon, timestamp, lats, lons, u10, v10):
    """
    Récupère vent réel depuis données GRIB.
    
    Args:
        lat, lon: Position
        timestamp: datetime (non utilisé pour l'instant, une seule échéance)
        lats, lons: Matrices de grille GRIB
        u10, v10: Composantes du vent
    
    Returns:
        wind_speed_kn: Vitesse en nœuds
        wind_direction: Direction en degrés (d'où vient le vent)
    """
    speed_ms, direction, lat_pt, lon_pt = wind_at(lat, lon, lats, lons, u10, v10)
    
    # Convertir m/s en nœuds
    wind_speed_kn = speed_ms * 1.94384
    
    return wind_speed_kn, direction


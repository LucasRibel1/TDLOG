import requests
from datetime import datetime, timezone
from functools import lru_cache
import math

# -----------------------------
# Utils
# -----------------------------

def kmh_to_knots(kmh: float) -> float:
    return kmh * 0.539957


def wind_dir_to_uv(speed_kn: float, direction_from_deg: float):
    """
    Convertit (vitesse, direction FROM) -> (u, v)
    Convention météo (direction FROM).
    """
    speed_ms = speed_kn / 1.94384
    theta = math.radians(direction_from_deg)
    u = -speed_ms * math.sin(theta)
    v = -speed_ms * math.cos(theta)
    return u, v


# -----------------------------
# Client Open-Meteo
# -----------------------------

class OpenMeteoClient:
    """
    Client météo Open-Meteo avec cache.
    """

    def __init__(self, cache_round=2):
        """
        cache_round:
            arrondi lat/lon (2 = ~1 km, 1 = ~10 km)
        """
        self.cache_round = cache_round

    def _round_key(self, lat, lon, timestamp):
        return (
            round(lat, self.cache_round),
            round(lon, self.cache_round),
            timestamp.replace(minute=0, second=0, microsecond=0)
        )

    @lru_cache(maxsize=10_000)
    def _fetch_hourly(self, lat, lon):
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "wind_speed_10m,wind_direction_10m",
            "timezone": "UTC"
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def get_wind(self, lat, lon, timestamp: datetime):
        """
        Renvoie:
            speed_kn, direction_from_deg
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        key = self._round_key(lat, lon, timestamp)

        lat_r, lon_r, ts_r = key
        data = self._fetch_hourly(lat_r, lon_r)

        times = data["hourly"]["time"]
        speeds = data["hourly"]["wind_speed_10m"]
        dirs = data["hourly"]["wind_direction_10m"]

        # Trouver index horaire
        ts_str = ts_r.strftime("%Y-%m-%dT%H:00")
        try:
            idx = times.index(ts_str)
        except ValueError:
            raise ValueError("Timestamp hors plage Open-Meteo")

        speed_kmh = speeds[idx]
        dir_from = dirs[idx]

        return kmh_to_knots(speed_kmh), float(dir_from)

    def get_wind_uv(self, lat, lon, timestamp):
        speed_kn, dir_from = self.get_wind(lat, lon, timestamp)
        return wind_dir_to_uv(speed_kn, dir_from)

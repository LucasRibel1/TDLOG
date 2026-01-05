import pygrib
import numpy as np
from dataclasses import dataclass
from datetime import datetime
from conventions import ms_to_knots, uv_to_wind_dir_from


@dataclass
class GribWindField:
    """
    Représente un champ (u10,v10) sur une grille lat/lon à une date.
    """
    valid_date: datetime
    lats: np.ndarray
    lons: np.ndarray
    u10: np.ndarray  # m/s
    v10: np.ndarray  # m/s


def load_grib_wind_fields(filepath, normalize_lons=True):
    """
    Charge toutes les échéances présentes dans un GRIB (u10/v10 à 10m).
    Retourne une liste triée de GribWindField.
    """
    fields_u = {}
    fields_v = {}

    with pygrib.open(filepath) as grbs:
        for msg in grbs:
            if msg.typeOfLevel != 'heightAboveGround' or msg.level != 10:
                continue
            if msg.indicatorOfParameter == 33:  # U10
                fields_u[msg.validDate] = msg
            elif msg.indicatorOfParameter == 34:  # V10
                fields_v[msg.validDate] = msg

    common_times = sorted(set(fields_u.keys()).intersection(set(fields_v.keys())))
    if not common_times:
        raise ValueError("Aucune échéance commune U10/V10 trouvée dans le GRIB.")

    fields = []
    for t in common_times:
        grb_u = fields_u[t]
        grb_v = fields_v[t]
        u10 = grb_u.values
        v10 = grb_v.values
        lats, lons = grb_u.latlons()

        if normalize_lons:
            lons = np.where(lons > 180, lons - 360, lons)

        fields.append(GribWindField(
            valid_date=grb_u.validDate,
            lats=lats,
            lons=lons,
            u10=u10,
            v10=v10
        ))

    meta = {
        "n_times": len(fields),
        "times": [f.valid_date for f in fields],
        "shape": fields[0].u10.shape,
        "lat_range": (float(fields[0].lats.min()), float(fields[0].lats.max())),
        "lon_range": (float(fields[0].lons.min()), float(fields[0].lons.max())),
    }
    return fields, meta


def _find_bilinear_cell(lat_target, lon_target, lats, lons):
    """
    Trouve (i0,i1,j0,j1) pour interpolation bilinéaire.
    Hypothèse: grille rectiligne type WRF, lats ~ monotone en i, lons ~ monotone en j.
    """
    lat_1d = lats[:, 0]
    lon_1d = lons[0, :]

    # on gère le cas lat décroissante
    if lat_1d[1] < lat_1d[0]:
        lat_1d = lat_1d[::-1]
        lat_flip = True
    else:
        lat_flip = False

    # lon croissante en général après normalisation
    if lon_1d[1] < lon_1d[0]:
        lon_1d = lon_1d[::-1]
        lon_flip = True
    else:
        lon_flip = False

    if lat_target < lat_1d.min() or lat_target > lat_1d.max():
        return None
    if lon_target < lon_1d.min() or lon_target > lon_1d.max():
        return None

    i1 = int(np.searchsorted(lat_1d, lat_target))
    j1 = int(np.searchsorted(lon_1d, lon_target))

    i0 = max(i1 - 1, 0)
    j0 = max(j1 - 1, 0)
    i1 = min(i1, len(lat_1d) - 1)
    j1 = min(j1, len(lon_1d) - 1)

    # remettre indices dans la grille originale si flip
    if lat_flip:
        i0o = (lats.shape[0] - 1) - i0
        i1o = (lats.shape[0] - 1) - i1
        i0, i1 = min(i0o, i1o), max(i0o, i1o)

    if lon_flip:
        j0o = (lons.shape[1] - 1) - j0
        j1o = (lons.shape[1] - 1) - j1
        j0, j1 = min(j0o, j1o), max(j0o, j1o)

    return i0, i1, j0, j1


def _bilinear(lat_target, lon_target, lats, lons, field_2d):
    """
    Interpolation bilinéaire sur une grille lat/lon rectiligne (approx).
    """
    cell = _find_bilinear_cell(lat_target, lon_target, lats, lons)
    if cell is None:
        return None

    i0, i1, j0, j1 = cell

    lat0 = float(lats[i0, 0])
    lat1 = float(lats[i1, 0])
    lon0 = float(lons[0, j0])
    lon1 = float(lons[0, j1])

    # gérer cellules dégénérées
    if abs(lat1 - lat0) < 1e-12 and abs(lon1 - lon0) < 1e-12:
        return float(field_2d[i0, j0])

    if abs(lat1 - lat0) < 1e-12:
        ty = 0.0
    else:
        ty = (lat_target - lat0) / (lat1 - lat0)

    if abs(lon1 - lon0) < 1e-12:
        tx = 0.0
    else:
        tx = (lon_target - lon0) / (lon1 - lon0)

    ty = max(0.0, min(1.0, ty))
    tx = max(0.0, min(1.0, tx))

    f00 = field_2d[i0, j0]
    f01 = field_2d[i0, j1]
    f10 = field_2d[i1, j0]
    f11 = field_2d[i1, j1]

    val = (f00 * (1 - tx) * (1 - ty) +
           f01 * tx * (1 - ty) +
           f10 * (1 - tx) * ty +
           f11 * tx * ty)
    return float(val)


def wind_uv_at(fields, lat, lon, timestamp: datetime):
    """
    Renvoie (u_ms, v_ms) interpolé bilinéairement + linéairement dans le temps.
    """
    times = [f.valid_date for f in fields]
    if timestamp <= times[0]:
        f0 = fields[0]
        u = _bilinear(lat, lon, f0.lats, f0.lons, f0.u10)
        v = _bilinear(lat, lon, f0.lats, f0.lons, f0.v10)
        if u is None or v is None:
            return None
        return u, v

    if timestamp >= times[-1]:
        f1 = fields[-1]
        u = _bilinear(lat, lon, f1.lats, f1.lons, f1.u10)
        v = _bilinear(lat, lon, f1.lats, f1.lons, f1.v10)
        if u is None or v is None:
            return None
        return u, v

    # encadrer
    k1 = int(np.searchsorted(times, timestamp))
    k0 = k1 - 1
    f0 = fields[k0]
    f1 = fields[k1]

    u0 = _bilinear(lat, lon, f0.lats, f0.lons, f0.u10)
    v0 = _bilinear(lat, lon, f0.lats, f0.lons, f0.v10)
    u1 = _bilinear(lat, lon, f1.lats, f1.lons, f1.u10)
    v1 = _bilinear(lat, lon, f1.lats, f1.lons, f1.v10)

    if u0 is None or v0 is None or u1 is None or v1 is None:
        return None

    dt = (f1.valid_date - f0.valid_date).total_seconds()
    if dt <= 0:
        alpha = 0.0
    else:
        alpha = (timestamp - f0.valid_date).total_seconds() / dt

    alpha = max(0.0, min(1.0, alpha))
    u = (1 - alpha) * u0 + alpha * u1
    v = (1 - alpha) * v0 + alpha * v1
    return float(u), float(v)


def get_wind_from_grib(lat, lon, timestamp, grib_fields):
    """
    Renvoie le vent au timestamp demandé, en:
    - interpolation bilinéaire spatiale
    - interpolation linéaire temporelle sur U/V
    Returns:
        wind_speed_kn, wind_dir_from_deg
    """
    uv = wind_uv_at(grib_fields, lat, lon, timestamp)
    if uv is None:
        raise ValueError("Point hors grille GRIB (spatial) ou données invalides.")
    u, v = uv
    speed_ms = float(np.hypot(u, v))
    speed_kn = ms_to_knots(speed_ms)
    direction_from = uv_to_wind_dir_from(u, v)
    return speed_kn, direction_from

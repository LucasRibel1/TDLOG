import math

# ============================================================
# Conventions & unités (centralisées)
# ============================================================
# Convention cap (heading) / navigation :
# - 0° = Nord
# - 90° = Est
# - sens horaire
#
# Convention direction du vent (météo) :
# - direction = "d'où vient le vent"
# - 0° = vent de Nord, 90° = vent d'Est, etc.
#
# True Wind Angle (TWA) :
# - angle entre cap (heading) et direction du vent (d'où vient)
# - ramené dans [0, 180]
# ============================================================

MPS_TO_KNOT = 1.9438444924406048
KNOT_TO_MPS = 1.0 / MPS_TO_KNOT


def deg2rad(deg: float) -> float:
    return math.radians(deg)


def rad2deg(rad: float) -> float:
    return math.degrees(rad)


def wrap_360(angle_deg: float) -> float:
    return angle_deg % 360.0


def wrap_180(angle_deg: float) -> float:
    """Retourne un angle dans [-180, 180]."""
    a = (angle_deg + 180.0) % 360.0 - 180.0
    return a


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def ms_to_knots(v_ms: float) -> float:
    return v_ms * MPS_TO_KNOT


def knots_to_ms(v_kn: float) -> float:
    return v_kn * KNOT_TO_MPS


def uv_to_wind_dir_from(u_ms: float, v_ms: float) -> float:
    """
    Convertit (U,V) géographiques en direction météo "d'où vient le vent".
    U>0 = vent vers l'Est, V>0 = vent vers le Nord.
    Formule standard: Dir = 270 - atan2(V, U) (en degrés) [web:2]
    """
    return wrap_360(270.0 - rad2deg(math.atan2(v_ms, u_ms)))


def wind_dir_from_to_dir_to(dir_from_deg: float) -> float:
    """Direction 'vers où va le vent' = dir_from + 180."""
    return wrap_360(dir_from_deg + 180.0)


def compute_twa(heading_deg: float, wind_dir_from_deg: float) -> float:
    """
    TWA = angle entre le cap (où va le bateau) et le vent (d'où vient),
    ramené dans [0, 180].
    """
    delta = wrap_180(wind_dir_from_deg - heading_deg)
    return abs(delta)

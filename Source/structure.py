from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class Waypoint:
    lat: float
    lon: float
    timestamp: datetime
    heading: float
    boat_speed: float
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    twa: Optional[float] = None
    tack: Optional[int] = None
    maneuver: Optional[str] = None
    parent: Optional['Waypoint'] = None
    g_cost: float = 0.0
    h_cost: float = 0.0

    @property
    def f_cost(self) -> float:
        return self.g_cost + self.h_cost


@dataclass
class Route:
    waypoints: List[Waypoint]
    start: tuple[float, float]
    end: tuple[float, float]
    total_distance: float
    total_time: float

    @property
    def distance_nm(self) -> float:
        return self.total_distance / 1852.0

    @property
    def duration_hours(self) -> float:
        return self.total_time / 3600.0

    @property
    def eta(self) -> datetime:
        return self.waypoints[-1].timestamp if self.waypoints else None

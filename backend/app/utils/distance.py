"""
Utility functions for geographic distance calculations.
"""

from math import radians, sin, cos, atan2, sqrt


# Earth's mean radius in kilometers (WGS-84 standard)
EARTH_RADIUS_KM = 6371


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Uses the Haversine formula, which gives accurate distances for points
    that are not antipodal and accounts for the spherical shape of the Earth.

    Formula reference: https://en.wikipedia.org/wiki/Haversine_formula

    The Haversine formula:
        a = sin²(Δlat/2) + cos(lat1) · cos(lat2) · sin²(Δlng/2)
        c = 2 · atan2(√a, √(1−a))
        d = R · c

    Args:
        lat1: Latitude of the first point in decimal degrees (-90 to 90).
        lng1: Longitude of the first point in decimal degrees (-180 to 180).
        lat2: Latitude of the second point in decimal degrees (-90 to 90).
        lng2: Longitude of the second point in decimal degrees (-180 to 180).

    Returns:
        Distance between the two points in kilometers (float).

    Examples:
        >>> # New York City to Boston (~306 km)
        >>> haversine_distance(40.7128, -74.0060, 42.3601, -71.0589)
        305.87...

        >>> # Same point → 0 km
        >>> haversine_distance(51.5074, -0.1278, 51.5074, -0.1278)
        0.0
    """
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return EARTH_RADIUS_KM * c

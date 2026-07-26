from typing import Literal

from pydantic import BaseModel


class TravelEstimate(BaseModel):
    """How far away a place is, and — when we can tell — how long it takes.

    `source` is part of the contract rather than an implementation detail: the
    UI phrases a straight-line number differently ("4.2 km away") from a routed
    one ("4.2 km · ~15 min drive"), and presenting a crow-flies distance as a
    drive would be a lie on any route with a river in it.
    """

    distance_km: float
    duration_minutes: int | None = None
    source: Literal["ola", "straight_line"]

from typing import Literal

from pydantic import BaseModel

PlaceKind = Literal["dog_park", "park", "vet"]


class NearbyPlace(BaseModel):
    name: str
    kind: PlaceKind
    latitude: float
    longitude: float
    distance_m: int


class NearbyPlaceList(BaseModel):
    items: list[NearbyPlace]
    total: int

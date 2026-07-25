from pydantic import BaseModel


class GeocodeResult(BaseModel):
    address: str
    pincode: str | None = None
    lat: float
    lng: float

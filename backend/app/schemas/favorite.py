from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.pet import PetPublicResponse


class CreateFavoriteRequest(BaseModel):
    pet_id: UUID
    target_pet_id: UUID


class FavoriteResponse(BaseModel):
    id: UUID
    pet_id: UUID
    target_pet_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteWithPetResponse(BaseModel):
    id: UUID
    # Was a bare `dict` — nothing validated/coerced its contents, so
    # list_favorites's raw ORM `owner` assignment sailed through untyped and
    # blew up at serialization time (pydantic doesn't know how to encode a
    # SQLAlchemy User). A real nested model actually validates it.
    target_pet: PetPublicResponse
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteListResponse(BaseModel):
    items: list[FavoriteWithPetResponse]
    total: int
    limit: int
    offset: int

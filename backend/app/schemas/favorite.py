from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
    target_pet: dict  # holds PetPublicResponse data
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteListResponse(BaseModel):
    items: list[FavoriteWithPetResponse]
    total: int
    limit: int
    offset: int

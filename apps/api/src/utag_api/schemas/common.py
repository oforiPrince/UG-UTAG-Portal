from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PageSize = Annotated[int, Field(ge=1, le=100)]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class Page[T](ApiModel):
    items: list[T]
    page: int
    page_size: int
    total: int
    pages: int


class MessageResponse(ApiModel):
    message: str


class DeliveryCapabilities(ApiModel):
    email_delivery: bool
    sms_delivery: bool


class ResourceRef(ApiModel):
    id: UUID
    type: str


class ActivityItem(ApiModel):
    id: UUID
    action: str
    resource_type: str
    resource_id: UUID | None
    created_at: datetime
    actor_name: str | None = None

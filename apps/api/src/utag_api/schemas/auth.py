from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from utag_api.schemas.common import ApiModel
from utag_api.services.content import validate_social_links


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class UserSummary(ApiModel):
    id: UUID
    email: EmailStr
    full_name: str
    title: str
    other_name: str
    surname: str
    staff_id: str | None
    gender: str | None
    academic_rank: str | None
    phone_number: str | None
    profile_media_id: UUID | None
    school_id: UUID | None
    college_id: UUID | None
    department_id: UUID | None
    must_change_password: bool
    roles: list[str]
    permissions: list[str]


class AuthResponse(ApiModel):
    user: UserSummary
    csrf_token: str
    expires_at: datetime


class SessionSummary(ApiModel):
    id: UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str
    current: bool


class ChangePasswordRequest(ApiModel):
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class ProfileUpdate(ApiModel):
    title: str | None = Field(default=None, max_length=30)
    other_name: str | None = Field(default=None, min_length=1, max_length=120)
    surname: str | None = Field(default=None, min_length=1, max_length=120)
    gender: str | None = Field(default=None, max_length=30)
    academic_rank: str | None = Field(default=None, max_length=120)
    phone_number: str | None = Field(default=None, max_length=40)
    profile_media_id: UUID | None = None
    school_id: UUID | None = None
    college_id: UUID | None = None
    department_id: UUID | None = None


class ExecutiveProfileSummary(ApiModel):
    id: UUID
    position: str
    biography_html: str
    social_links: dict[str, str]


class ExecutiveProfileUpdate(ApiModel):
    biography_html: str = Field(default="", max_length=50_000)
    social_links: dict[str, str] = Field(default_factory=dict)

    @field_validator("social_links")
    @classmethod
    def validate_links(cls, value: dict[str, str]) -> dict[str, str]:
        return validate_social_links(value)


class ForgotPasswordRequest(ApiModel):
    email: EmailStr


class ResetPasswordRequest(ApiModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=8, max_length=256)


class AcceptInvitationRequest(ApiModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=8, max_length=256)

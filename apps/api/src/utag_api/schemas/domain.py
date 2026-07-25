from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import EmailStr, Field, HttpUrl, field_validator, model_validator

from utag_api.schemas.auth import ExecutiveProfileSummary
from utag_api.schemas.common import ApiModel
from utag_api.services.content import sanitize_html, validate_social_links


class MemberBase(ApiModel):
    email: EmailStr
    staff_id: str | None = Field(default=None, max_length=40)
    title: str = Field(default="", max_length=30)
    other_name: str = Field(min_length=1, max_length=120)
    surname: str = Field(min_length=1, max_length=120)
    gender: str | None = Field(default=None, max_length=30)
    academic_rank: str | None = Field(default=None, max_length=120)
    phone_number: str | None = Field(default=None, max_length=40)
    school_id: UUID | None = None
    college_id: UUID | None = None
    department_id: UUID | None = None


class MemberCreate(MemberBase):
    profile_media_id: UUID | None = None
    roles: list[str] = Field(default_factory=lambda: ["member"], max_length=10)
    send_invitation: bool = True


class MemberUpdate(ApiModel):
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
    status: Literal["invited", "active", "suspended", "archived"] | None = None
    roles: list[str] | None = Field(default=None, max_length=10)


class MemberLifecycleRequest(ApiModel):
    reason: str = Field(min_length=3, max_length=500)


class MemberPermissionUpdate(ApiModel):
    permissions: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("permissions")
    @classmethod
    def unique_permissions(cls, value: list[str]) -> list[str]:
        return sorted(set(value))


class PermissionOption(ApiModel):
    key: str
    description: str


class MemberView(MemberBase):
    id: UUID
    full_name: str
    status: str
    email_verified: bool
    must_change_password: bool
    profile_media_id: UUID | None
    roles: list[str] = Field(default_factory=list)
    role_permissions: list[str] = Field(default_factory=list)
    extra_permissions: list[str] = Field(default_factory=list)
    effective_permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    last_login_at: datetime | None
    school_name: str | None = None
    college_name: str | None = None
    department_name: str | None = None


class MemberImportIssue(ApiModel):
    row: int
    field: str | None = None
    message: str


class MemberImportResult(ApiModel):
    dry_run: bool
    total_rows: int
    valid_rows: int
    invalid_rows: int
    imported_rows: int
    duplicate_rows: int
    issues: list[MemberImportIssue] = Field(default_factory=list)
    preview: list[dict[str, Any]] = Field(default_factory=list)
    preview_truncated: bool = False


class OrganizationUnitView(ApiModel):
    id: UUID
    unit_type: str
    name: str
    slug: str
    parent_id: UUID | None
    parent_name: str | None = None
    is_active: bool


class OrganizationUnitUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    parent_id: UUID | None = None
    is_active: bool | None = None


class ExecutiveBase(ApiModel):
    user_id: UUID
    position: str = Field(min_length=2, max_length=120)
    portfolio: str | None = Field(default=None, max_length=180)
    summary: str | None = Field(default=None, max_length=500)
    biography_html: str | None = None
    social_links: dict[str, str] = Field(default_factory=dict)
    appointed_on: date | None = None
    ended_on: date | None = None
    term_number: int = Field(default=1, ge=1, le=20)
    is_acting: bool = False
    is_active: bool = True
    is_public: bool = True

    @field_validator("social_links")
    @classmethod
    def validate_links(cls, value: dict[str, str]) -> dict[str, str]:
        return validate_social_links(value)


class ExecutiveCreate(ExecutiveBase):
    profile_media_id: UUID


class ExecutiveView(ExecutiveBase):
    id: UUID
    full_name: str
    title: str
    academic_rank: str | None
    profile_media_id: UUID | None


class PublicExecutiveView(ExecutiveView):
    email: EmailStr
    phone_number: str | None
    school_name: str | None = None
    college_name: str | None = None
    department_name: str | None = None


class MediaReference(ApiModel):
    media_asset_id: UUID
    filename: str
    content_type: str
    byte_size: int
    content_url: str


class EditorialBase(ApiModel):
    title: str = Field(min_length=3, max_length=300)
    excerpt: str = Field(default="", max_length=2_000)
    content_json: dict[str, Any] = Field(default_factory=dict)
    content_html: str = ""
    featured_media_id: UUID | None = None
    is_featured: bool = False
    tags: list[str] = Field(default_factory=list, max_length=30)
    citations: list[dict[str, str]] = Field(default_factory=list, max_length=50)
    attachment_media_ids: list[UUID] = Field(default_factory=list, max_length=25)


class ArticleCreate(EditorialBase):
    slug: str | None = Field(default=None, max_length=260)
    status: Literal["draft", "review", "scheduled", "published"] = "draft"
    published_at: datetime | None = None


class ArticleUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    excerpt: str | None = Field(default=None, max_length=2_000)
    content_json: dict[str, Any] | None = None
    content_html: str | None = None
    featured_media_id: UUID | None = None
    is_featured: bool | None = None
    tags: list[str] | None = Field(default=None, max_length=30)
    citations: list[dict[str, str]] | None = Field(default=None, max_length=50)
    attachment_media_ids: list[UUID] | None = Field(default=None, max_length=25)
    status: Literal["draft", "review", "scheduled", "published", "archived", "withdrawn"] | None = (
        None
    )
    published_at: datetime | None = None


class ArticleView(EditorialBase):
    id: UUID
    slug: str
    status: str
    author_id: UUID | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int
    author_name: str | None = None
    featured_media_name: str | None = None
    attachments: list["MediaReference"] = Field(default_factory=list)


class AnnouncementCreate(ApiModel):
    title: str = Field(min_length=3, max_length=250)
    content_json: dict[str, Any] = Field(default_factory=dict)
    content_html: str = ""
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    audiences: list[dict[str, str]] = Field(default_factory=list)
    status: Literal["draft", "review", "scheduled", "published"] = "draft"
    published_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("audiences")
    @classmethod
    def validate_audiences(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        allowed_roles = {
            "member",
            "executive",
            "editor",
            "publisher",
            "secretary",
            "administrator",
        }
        if not value or any(item.get("type") in {"everyone", "all_members"} for item in value):
            return [{"type": "everyone", "value": "all"}]

        roles = {
            item.get("value")
            for item in value
            if item.get("type") == "role" and item.get("value") in allowed_roles
        }
        if len(roles) != len(value):
            raise ValueError("Choose Everyone or one or more valid member roles")
        return [{"type": "role", "value": role} for role in sorted(roles)]


class AnnouncementView(AnnouncementCreate):
    id: UUID
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    version: int


class EventCreate(ApiModel):
    title: str = Field(min_length=3, max_length=300)
    slug: str | None = Field(default=None, max_length=260)
    short_description: str = Field(default="", max_length=2_000)
    description_json: dict[str, Any] = Field(default_factory=dict)
    description_html: str = ""
    featured_media_id: UUID | None = None
    start_date: date
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    timezone: str = Field(default="Africa/Accra", max_length=80)
    event_type: str = Field(default="meeting", max_length=40)
    status: Literal["upcoming", "ongoing", "completed", "cancelled", "postponed"] = "upcoming"
    publication_status: Literal["draft", "review", "scheduled", "published"] = "draft"
    published_at: datetime | None = None
    venue: str | None = Field(default=None, max_length=250)
    address: str | None = Field(default=None, max_length=500)
    location_url: HttpUrl | None = None
    photos_url: HttpUrl | None = None
    is_online: bool = False
    online_platform: str | None = Field(default=None, max_length=120)
    online_link: str | None = Field(default=None, max_length=2_000)
    access_code: str | None = Field(default=None, max_length=200)
    registration_required: bool = False
    registration_url: HttpUrl | None = None
    registration_deadline: datetime | None = None
    max_participants: int | None = Field(default=None, ge=1, le=100_000)
    expected_participants: int | None = Field(default=None, ge=0, le=100_000)
    cpd_credits: Decimal = Field(default=Decimal("0"), ge=0, le=999)
    organizer: dict[str, str] = Field(default_factory=dict)
    speakers: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    schedule: list[dict[str, Any]] = Field(default_factory=list, max_length=300)
    supplementary_media_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_dates(self) -> "EventCreate":
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        if self.registration_deadline and self.registration_deadline.date() > self.start_date:
            raise ValueError("Registration deadline cannot be after the event starts")
        if self.publication_status == "scheduled" and self.published_at is None:
            raise ValueError("Scheduled events require a publication time")
        return self


class EventView(ApiModel):
    id: UUID
    slug: str
    title: str
    short_description: str
    description_html: str
    featured_media_id: UUID | None
    start_date: date
    end_date: date | None
    start_time: time | None
    end_time: time | None
    timezone: str
    event_type: str
    status: str
    publication_status: str
    published_at: datetime | None
    venue: str | None
    address: str | None
    location_url: str | None
    photos_url: str | None
    is_online: bool
    online_platform: str | None
    registration_required: bool
    registration_url: str | None
    registration_deadline: datetime | None
    max_participants: int | None
    cpd_credits: Decimal
    organizer: dict[str, str]
    speakers: list[dict[str, Any]]
    schedule: list[dict[str, Any]]
    registrations: int = 0
    registered: bool = False
    created_at: datetime
    updated_at: datetime
    version: int
    featured_media_name: str | None = None
    supplementary_media_ids: list[UUID] = Field(default_factory=list)
    attachments: list["MediaReference"] = Field(default_factory=list)


class DocumentCreate(ApiModel):
    title: str = Field(min_length=3, max_length=300)
    category: str = Field(default="internal", max_length=50)
    sender: str | None = Field(default=None, max_length=250)
    receiver: str | None = Field(default=None, max_length=250)
    description_html: str = ""
    document_date: date | None = None
    audiences: list[dict[str, str]] = Field(default_factory=list)
    retention_class: str | None = Field(default=None, max_length=80)
    legal_hold: bool = False
    status: Literal["draft", "review", "published"] = "draft"
    media_asset_id: UUID | None = None
    media_asset_ids: list[UUID] = Field(default_factory=list, max_length=50)
    change_note: str | None = None

    @model_validator(mode="after")
    def require_files(self) -> "DocumentCreate":
        asset_ids = list(dict.fromkeys(self.media_asset_ids))
        if self.media_asset_id and self.media_asset_id not in asset_ids:
            asset_ids.insert(0, self.media_asset_id)
        if not asset_ids:
            raise ValueError("Select at least one uploaded file")
        self.media_asset_ids = asset_ids
        return self


class DocumentView(ApiModel):
    id: UUID
    public_id: str
    title: str
    category: str
    sender: str | None
    receiver: str | None
    description_html: str
    document_date: date | None
    status: str
    audiences: list[dict[str, str]]
    retention_class: str | None
    legal_hold: bool
    version: int
    latest_media_asset_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    latest_filename: str | None = None
    files: list[MediaReference] = Field(default_factory=list)


class DocumentUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    category: str | None = Field(default=None, max_length=50)
    sender: str | None = Field(default=None, max_length=250)
    receiver: str | None = Field(default=None, max_length=250)
    description_html: str | None = None
    document_date: date | None = None
    audiences: list[dict[str, str]] | None = None
    retention_class: str | None = Field(default=None, max_length=80)
    legal_hold: bool | None = None
    status: Literal["draft", "review", "published", "archived"] | None = None


class PresignUploadRequest(ApiModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=150)
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    is_private: bool = True
    alt_text: str | None = Field(default=None, max_length=500)


class PresignUploadResponse(ApiModel):
    asset_id: UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    expires_in: int


class CompleteUploadRequest(ApiModel):
    asset_id: UUID


class DocumentVersionCreate(ApiModel):
    asset_id: UUID | None = None
    asset_ids: list[UUID] = Field(default_factory=list, max_length=50)
    change_note: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def require_files(self) -> "DocumentVersionCreate":
        asset_ids = list(dict.fromkeys(self.asset_ids))
        if self.asset_id and self.asset_id not in asset_ids:
            asset_ids.insert(0, self.asset_id)
        if not asset_ids:
            raise ValueError("Select at least one uploaded file")
        self.asset_ids = asset_ids
        return self


class MediaView(ApiModel):
    id: UUID
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    status: str
    is_private: bool
    alt_text: str | None
    caption: str | None
    credit: str | None
    created_at: datetime


class MediaUpdate(ApiModel):
    alt_text: str | None = Field(default=None, max_length=500)
    caption: str | None = Field(default=None, max_length=5_000)
    credit: str | None = Field(default=None, max_length=250)
    is_private: bool | None = None


class NotificationView(ApiModel):
    id: UUID
    category: str
    priority: str
    title: str
    body: str
    resource_type: str | None
    resource_id: UUID | None
    deep_link: str | None
    read_at: datetime | None
    created_at: datetime

    @field_validator("body")
    @classmethod
    def sanitize_body(cls, value: str) -> str:
        return sanitize_html(value)


class NotificationCreate(ApiModel):
    user_ids: list[UUID] = Field(min_length=1, max_length=5_000)
    category: str = Field(default="general", max_length=80)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    title: str = Field(min_length=2, max_length=300)
    body: str = Field(default="", max_length=5_000)
    resource_type: str | None = Field(default=None, max_length=80)
    resource_id: UUID | None = None
    deep_link: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def reserve_announcement_delivery(self) -> "NotificationCreate":
        if self.category == "announcement" or self.resource_type == "announcement":
            raise ValueError("Publish official communications from Announcements")
        return self


class ConversationCreate(ApiModel):
    kind: Literal["direct", "group"] = "direct"
    title: str | None = Field(default=None, max_length=180)
    member_ids: list[UUID] = Field(min_length=1, max_length=250)


class ConversationUpdate(ApiModel):
    title: str = Field(min_length=2, max_length=180)


class ConversationMembersUpdate(ApiModel):
    member_ids: list[UUID] = Field(min_length=1, max_length=250)


class ConversationMemberRoleUpdate(ApiModel):
    role: Literal["member", "admin"]


class ConversationView(ApiModel):
    id: UUID
    kind: str
    title: str | None
    created_by_id: UUID | None
    last_message_at: datetime | None = None
    member_count: int
    unread_count: int = 0
    created_at: datetime


class MessageCreateRequest(ApiModel):
    client_message_id: str = Field(min_length=8, max_length=100)
    text: str = Field(default="", max_length=20_000)
    reply_to_id: UUID | None = None
    attachment_media_ids: list[UUID] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def require_message_content(self) -> "MessageCreateRequest":
        if not self.text.strip() and not self.attachment_media_ids:
            raise ValueError("Write a message or attach a file")
        self.attachment_media_ids = list(dict.fromkeys(self.attachment_media_ids))
        return self


class MessageAttachmentView(ApiModel):
    id: UUID
    filename: str
    content_type: str | None
    byte_size: int
    content_url: str
    thumbnail_url: str | None = None


class MessageView(ApiModel):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    sender_name: str
    client_message_id: str
    text: str
    reply_to_id: UUID | None
    created_at: datetime
    read_by: int = 0
    attachments: list[MessageAttachmentView] = Field(default_factory=list)


class ConversationInviteCreate(ApiModel):
    expires_in_hours: int = Field(default=72, ge=1, le=720)
    max_uses: int | None = Field(default=None, ge=1, le=1_000)


class ConversationInviteView(ApiModel):
    id: UUID
    conversation_id: UUID
    conversation_title: str
    join_url: str
    expires_at: datetime
    max_uses: int | None
    use_count: int


class AdSlotView(ApiModel):
    id: UUID
    key: str
    name: str
    width: int | None
    height: int | None
    description: str
    is_active: bool


class AdSlotCreate(ApiModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,98}$")
    name: str = Field(min_length=2, max_length=180)
    width: int | None = Field(default=None, ge=1, le=10_000)
    height: int | None = Field(default=None, ge=1, le=10_000)
    description: str = Field(default="", max_length=2_000)
    is_active: bool = True


class AdCampaignCreate(ApiModel):
    slot_id: UUID
    title: str = Field(min_length=2, max_length=200)
    media_asset_id: UUID | None = None
    target_url: HttpUrl | None = None
    status: Literal["draft", "scheduled", "active", "paused", "completed"] = "draft"
    priority: int = Field(default=0, ge=-100, le=100)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class AdCampaignUpdate(ApiModel):
    slot_id: UUID | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    media_asset_id: UUID | None = None
    target_url: HttpUrl | None = None
    status: Literal["draft", "scheduled", "active", "paused", "completed"] | None = None
    priority: int | None = Field(default=None, ge=-100, le=100)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class AdCampaignView(ApiModel):
    id: UUID
    slot_id: UUID
    title: str
    media_asset_id: UUID | None
    target_url: str | None
    status: str
    priority: int
    starts_at: datetime | None
    ends_at: datetime | None
    impressions: int
    clicks: int
    created_at: datetime
    placement_name: str | None = None
    media_name: str | None = None


class AdPlanCreate(ApiModel):
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=2_000)
    price: Decimal = Field(default=Decimal("0"), ge=0)
    duration_days: int = Field(default=30, ge=1, le=3_650)
    is_active: bool = True


class AdPlanUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=2_000)
    price: Decimal | None = Field(default=None, ge=0)
    duration_days: int | None = Field(default=None, ge=1, le=3_650)
    is_active: bool | None = None


class AdPlanView(AdPlanCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class AdOrderCreate(ApiModel):
    user_id: UUID
    plan_id: UUID
    campaign_id: UUID | None = None
    status: Literal["pending", "approved", "active", "completed", "cancelled"] = "pending"
    payment_status: Literal["unpaid", "pending", "paid", "refunded"] = "unpaid"
    starts_on: date | None = None
    ends_on: date | None = None
    notes: str = Field(default="", max_length=5_000)

    @model_validator(mode="after")
    def validate_order_dates(self) -> "AdOrderCreate":
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("Order end date cannot be before its start date")
        return self


class AdOrderUpdate(ApiModel):
    campaign_id: UUID | None = None
    status: Literal["pending", "approved", "active", "completed", "cancelled"] | None = None
    payment_status: Literal["unpaid", "pending", "paid", "refunded"] | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    notes: str | None = Field(default=None, max_length=5_000)


class AdOrderView(ApiModel):
    id: UUID
    user_id: UUID
    plan_id: UUID
    campaign_id: UUID | None
    status: str
    payment_status: str
    starts_on: date | None
    ends_on: date | None
    notes: str
    created_at: datetime
    updated_at: datetime
    advertiser_name: str | None = None
    plan_name: str | None = None
    campaign_name: str | None = None


class DashboardMetric(ApiModel):
    key: str
    label: str
    value: int | float | str
    change: float | None = None
    trend: Literal["up", "down", "flat"] = "flat"


class PulsePoint(ApiModel):
    at: date
    engagement: int
    events: int
    publications: int


class DashboardOverview(ApiModel):
    generated_at: datetime
    metrics: list[DashboardMetric]
    pulse: list[PulsePoint]
    upcoming_events: list[EventView]
    recent_notifications: list[NotificationView]
    recent_activity: list[dict[str, Any]]
    live_topic: str = "dashboard"
    # Names the blocks this principal may see, so an empty block means "no data"
    # rather than "not authorized".
    sections: list[str] = Field(default_factory=list)
    executive_appointment: ExecutiveProfileSummary | None = None


class SiteSettingUpdate(ApiModel):
    value: dict[str, Any]
    is_public: bool = False


class FeatureFlagUpdate(ApiModel):
    description: str = ""
    enabled: bool = False
    rules: dict[str, Any] = Field(default_factory=dict)


class CarouselSlideCreate(ApiModel):
    title: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=2_000)
    media_asset_id: UUID
    link_url: HttpUrl | None = None
    order: int = Field(default=0, ge=0, le=10_000)
    is_published: bool = False


class CarouselSlideUpdate(ApiModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2_000)
    media_asset_id: UUID | None = None
    link_url: HttpUrl | None = None
    order: int | None = Field(default=None, ge=0, le=10_000)
    is_published: bool | None = None


class CarouselSlideView(ApiModel):
    id: UUID
    title: str
    description: str
    media_asset_id: UUID
    link_url: str | None
    order: int
    is_published: bool
    archived: bool = False
    media_name: str | None = None


class OrganizationUnitCreate(ApiModel):
    unit_type: Literal["school", "college", "department", "committee"]
    name: str = Field(min_length=2, max_length=180)
    parent_id: UUID | None = None
    is_active: bool = True


class GalleryCreate(ApiModel):
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(default="", max_length=5_000)
    status: Literal["draft", "review", "published", "archived"] = "draft"
    media_asset_ids: list[UUID] = Field(default_factory=list, max_length=500)
    # Asset IDs visitors may not download from the public gallery. All other
    # selected images remain downloadable. Defaults to fully open downloads.
    blocked_download_media_ids: list[UUID] = Field(default_factory=list, max_length=500)
    external_album_url: HttpUrl | None = None

    @model_validator(mode="after")
    def require_images_or_external_album(self) -> "GalleryCreate":
        if not self.media_asset_ids and self.external_album_url is None:
            raise ValueError(
                "Add at least one gallery image or an external album link "
                "(Google Drive, OneDrive, or similar)"
            )
        blocked = set(self.blocked_download_media_ids)
        selected = set(self.media_asset_ids)
        if blocked - selected:
            raise ValueError(
                "blocked_download_media_ids must only include selected gallery images"
            )
        return self


class ContactRequest(ApiModel):
    name: str = Field(min_length=2, max_length=180)
    email: EmailStr
    subject: str = Field(min_length=3, max_length=250)
    message: str = Field(min_length=10, max_length=10_000)
    website: str = ""


class SearchResult(ApiModel):
    id: UUID
    kind: Literal["article", "event", "document", "executive"]
    title: str
    excerpt: str
    url: str
    published_at: datetime | date | None

    @field_validator("excerpt")
    @classmethod
    def normalize_excerpt(cls, value: str) -> str:
        return " ".join(value.split())[:320]

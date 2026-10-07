from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from utag_api.schemas.common import ApiModel

AudienceType = Literal[
    "all_members", "college", "school", "department", "role", "chat_group", "member"
]
PollState = Literal["draft", "scheduled", "open", "closed"]


class PollAudience(ApiModel):
    type: AudienceType
    value: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_value(self) -> "PollAudience":
        if self.type == "all_members":
            self.value = "all"
        elif not self.value:
            raise ValueError("Choose a target group or member")
        elif self.type != "role":
            UUID(self.value)
        return self


class AudienceOption(PollAudience):
    label: str


class AudiencePreview(ApiModel):
    audiences: list[PollAudience] = Field(min_length=1, max_length=100)


class PollCreate(ApiModel):
    title: str = Field(min_length=3, max_length=250)
    question: str = Field(min_length=3, max_length=3000)
    description: str = Field(default="", max_length=10000)
    kind: Literal["single", "multiple"] = "single"
    privacy: Literal["confidential", "named"] = "confidential"
    results_visibility: Literal["live", "after_vote", "after_close"] = "after_close"
    allow_vote_changes: bool = False
    max_choices: int = Field(default=1, ge=1, le=20)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    audiences: list[PollAudience] = Field(min_length=1, max_length=100)
    options: list[str] = Field(min_length=2, max_length=20)

    @field_validator("opens_at", "closes_at")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Include a timezone in the poll schedule")
        return value

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        labels = [label.strip() for label in value]
        if any(not label or len(label) > 500 for label in labels):
            raise ValueError("Each option must have between 1 and 500 characters")
        if len({label.casefold() for label in labels}) != len(labels):
            raise ValueError("Poll options must be distinct")
        return labels

    @model_validator(mode="after")
    def validate_configuration(self) -> "PollCreate":
        if self.kind == "single":
            self.max_choices = 1
        if self.max_choices > len(self.options):
            raise ValueError("Maximum choices cannot exceed the number of options")
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValueError("The poll must close after it opens")
        return self


class PollUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=3, max_length=250)
    question: str | None = Field(default=None, min_length=3, max_length=3000)
    description: str | None = Field(default=None, max_length=10000)
    kind: Literal["single", "multiple"] | None = None
    privacy: Literal["confidential", "named"] | None = None
    results_visibility: Literal["live", "after_vote", "after_close"] | None = None
    allow_vote_changes: bool | None = None
    max_choices: int | None = Field(default=None, ge=1, le=20)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    audiences: list[PollAudience] | None = Field(default=None, min_length=1, max_length=100)
    options: list[str] | None = Field(default=None, min_length=2, max_length=20)


class PollOptionView(ApiModel):
    id: UUID
    label: str
    position: int


class PollView(ApiModel):
    id: UUID
    title: str
    question: str
    description: str
    kind: str
    privacy: str
    results_visibility: str
    allow_vote_changes: bool
    max_choices: int
    opens_at: datetime | None
    closes_at: datetime | None
    closed_at: datetime | None
    audiences: list[PollAudience]
    options: list[PollOptionView]
    status: PollState
    published_at: datetime | None
    eligible_count: int
    has_voted: bool
    my_vote: list[UUID] | None
    can_vote: bool
    can_manage: bool
    can_view_results: bool
    can_export: bool
    created_at: datetime
    version: int
    server_now: datetime


class PollVoteRequest(ApiModel):
    option_ids: list[UUID] = Field(min_length=1, max_length=20)

    @field_validator("option_ids")
    @classmethod
    def distinct_options(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Each option can be selected only once")
        return value


class PollCloseRequest(ApiModel):
    reason: str = Field(min_length=3, max_length=1000)


class PollExtendRequest(PollCloseRequest):
    closes_at: datetime

    @field_validator("closes_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Include a timezone in the poll schedule")
        return value


class PollResultOption(PollOptionView):
    votes: int
    percent: float


class PollTimelinePoint(ApiModel):
    at: datetime
    responses: int


class NamedPollVoter(ApiModel):
    member_name: str
    option_labels: list[str]


class PollResults(ApiModel):
    response_count: int
    eligible_count: int
    turnout_percent: float
    options: list[PollResultOption]
    timeline: list[PollTimelinePoint]
    generated_at: datetime
    named_voters: list[NamedPollVoter] | None


class PollAudienceCount(ApiModel):
    eligible_count: int


class PollReminderCount(ApiModel):
    recipient_count: int

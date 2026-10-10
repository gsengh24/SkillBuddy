"""Request and response models for teams (ADR 0016)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import (
    MAX_TEAM_MEMBERS,
    MAX_TEAMS_OWNED,
    MAX_TEAMS_PER_PERSON,
    TEAM_DESCRIPTION_MAX_LENGTH,
    TEAM_LOOKING_FOR_MAX_LENGTH,
    TEAM_NAME_MAX_LENGTH,
    TEAM_REQUEST_NOTE_MAX_LENGTH,
)
from app.services.teams import InviteView, MemberView, TeamSummary, TeamView

Purpose = Literal["hackathon", "project", "study", "other"]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TEAM_NAME_MAX_LENGTH)
]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=TEAM_DESCRIPTION_MAX_LENGTH)
]

LookingFor = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=TEAM_LOOKING_FOR_MAX_LENGTH)
]


class TeamIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    purpose: Purpose
    description: Description = ""


class TeamPatch(BaseModel):
    """Send only what changes."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    purpose: Purpose | None = None
    description: Description | None = None
    listed: bool | None = Field(
        default=None,
        description="Listed teams can be found by any signed-in person, who may ask to join.",
    )
    looking_for: LookingFor | None = Field(
        default=None, description="Who the team is looking for; shown with a listed team."
    )


class TeamInviteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID | None = Field(
        default=None, description="Someone you have an open connection with."
    )
    match_id: uuid.UUID | None = Field(
        default=None,
        description="Or a match from your request for a teammate for this team: that person "
        "is invited, and sees why they were suggested.",
    )

    @model_validator(mode="after")
    def _one_of(self) -> Self:
        if (self.user_id is None) == (self.match_id is None):
            raise ValueError("send user_id or match_id, not both")
        return self


class TeamRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=TEAM_REQUEST_NOTE_MAX_LENGTH)
    ] = Field(default="", description="A short hello, shown to the team's owner.")


class TeamInviteResponseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept: bool


class TeamSummaryOut(BaseModel):
    id: uuid.UUID
    name: str
    purpose: Purpose
    description: str
    owner_id: uuid.UUID | None = Field(
        description="Empty only for a moment after the owner's account was deleted."
    )
    member_count: int
    max_members: int
    created_at: datetime
    listed: bool = False
    looking_for: str = Field(default="", description="Shown with a listed team.")
    unread: int = Field(
        default=0,
        description="Team chat messages from others not yet read. Filled in the list of teams.",
    )
    last_message_at: datetime | None = Field(
        default=None, description="Filled in the list of your teams."
    )

    @classmethod
    def build(cls, summary: TeamSummary) -> TeamSummaryOut:
        team = summary.team
        return cls(
            id=team.id,
            name=team.name,
            purpose=team.purpose,  # type: ignore[arg-type]  # CHECK-constrained column
            description=team.description,
            owner_id=team.owner_id,
            member_count=summary.member_count,
            max_members=MAX_TEAM_MEMBERS,
            created_at=team.created_at,
            listed=team.listed,
            looking_for=team.looking_for,
        )


class TeamMateOut(BaseModel):
    """Teammates see each other's display name, connected or not."""

    user_id: uuid.UUID
    display_name: str
    joined_at: datetime

    @classmethod
    def build(cls, member: MemberView) -> TeamMateOut:
        return cls(
            user_id=member.user_id, display_name=member.display_name, joined_at=member.joined_at
        )


class TeamInviteOut(BaseModel):
    id: uuid.UUID
    kind: Literal["invite", "request", "suggested"]
    status: Literal["pending", "accepted", "declined"] = Field(
        description="The owner sees `pending` for a declined invite until it expires."
    )
    team: TeamSummaryOut
    user_id: uuid.UUID = Field(description="The invited person, or the person asking.")
    note: str = Field(
        default="",
        description="What a person asking to join wrote; for `suggested`, why the matcher "
        "suggested them.",
    )
    display_name: str = Field(description="Their name, in the owner's list; otherwise empty.")
    expires_at: datetime
    created_at: datetime

    @classmethod
    def build(cls, view: InviteView) -> TeamInviteOut:
        invite = view.invite
        return cls(
            id=invite.id,
            kind=invite.kind,  # type: ignore[arg-type]  # CHECK-constrained column
            status=view.status.value,  # type: ignore[arg-type]  # only these three are returned
            team=TeamSummaryOut.build(view.summary),
            user_id=invite.user_id,
            note=invite.note,
            display_name=view.display_name,
            expires_at=invite.expires_at,
            created_at=invite.created_at,
        )


class TeamDetailOut(TeamSummaryOut):
    members: list[TeamMateOut] = Field(description="Longest-standing first.")
    invites: list[TeamInviteOut] = Field(description="Open invites; filled for the owner only.")
    invite_link_expires_at: datetime | None = Field(
        default=None,
        description="When the invite link stops working; for the owner only, and empty "
        "without a live link. The link itself is shown only when it is made.",
    )

    @classmethod
    def build_full(cls, view: TeamView) -> TeamDetailOut:
        return cls(
            **TeamSummaryOut.build(view.summary).model_dump(),
            members=[TeamMateOut.build(member) for member in view.members],
            invites=[TeamInviteOut.build(invite) for invite in view.invites],
            invite_link_expires_at=view.link_expires_at,
        )


class TeamLinkOut(BaseModel):
    """A new invite link. The code is shown this once; only its hash is kept."""

    code: str = Field(description="Put it in a link to the join page; anyone signed in can use it.")
    expires_at: datetime


class TeamList(BaseModel):
    items: list[TeamSummaryOut] = Field(description="Most recently joined first.")
    max_teams: int = MAX_TEAMS_PER_PERSON
    max_owned: int = MAX_TEAMS_OWNED


class ListedTeamPage(BaseModel):
    items: list[TeamSummaryOut] = Field(description="Listed teams, newest first.")
    next_cursor: str | None = Field(description="Pass as `cursor` for older teams.")


class TeamInviteList(BaseModel):
    items: list[TeamInviteOut] = Field(description="Open invites to you, newest first.")

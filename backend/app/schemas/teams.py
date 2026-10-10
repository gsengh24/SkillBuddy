"""Request and response models for teams (ADR 0016)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import (
    MAX_TEAM_MEMBERS,
    MAX_TEAMS_OWNED,
    MAX_TEAMS_PER_PERSON,
    TEAM_DESCRIPTION_MAX_LENGTH,
    TEAM_NAME_MAX_LENGTH,
)
from app.services.teams import InviteView, MemberView, TeamSummary, TeamView

Purpose = Literal["hackathon", "project", "study", "other"]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TEAM_NAME_MAX_LENGTH)
]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=TEAM_DESCRIPTION_MAX_LENGTH)
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


class TeamInviteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID = Field(description="Someone you have an open connection with.")


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
    user_id: uuid.UUID = Field(description="The invited person.")
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
            display_name=view.display_name,
            expires_at=invite.expires_at,
            created_at=invite.created_at,
        )


class TeamDetailOut(TeamSummaryOut):
    members: list[TeamMateOut] = Field(description="Longest-standing first.")
    invites: list[TeamInviteOut] = Field(description="Open invites; filled for the owner only.")

    @classmethod
    def build_full(cls, view: TeamView) -> TeamDetailOut:
        return cls(
            **TeamSummaryOut.build(view.summary).model_dump(),
            members=[TeamMateOut.build(member) for member in view.members],
            invites=[TeamInviteOut.build(invite) for invite in view.invites],
        )


class TeamList(BaseModel):
    items: list[TeamSummaryOut] = Field(description="Most recently joined first.")
    max_teams: int = MAX_TEAMS_PER_PERSON
    max_owned: int = MAX_TEAMS_OWNED


class TeamInviteList(BaseModel):
    items: list[TeamInviteOut] = Field(description="Open invites to you, newest first.")

"""Requests and responses for the admin Settings page (A6) and the public feature list."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models import SignupMode
from app.schemas.admin_portal import Reason
from app.services.app_settings import Feature, Limit

_REQUEST = ConfigDict(extra="forbid")


class ServerSettingsOut(BaseModel):
    """Set on the server (environment variables); read only here."""

    app_name: str
    terms_version: str
    environment: str


class FeatureStateOut(BaseModel):
    key: Feature
    on: bool


class LimitStateOut(BaseModel):
    key: Limit
    value: int
    default: int = Field(description="Today's value from the server settings.")
    minimum: int
    maximum: int


class SettingsOut(BaseModel):
    server: ServerSettingsOut
    signup_mode: SignupMode = Field(description="Set on the Signup and access page.")
    features: list[FeatureStateOut]
    limits: list[LimitStateOut]
    intents: list[str] = Field(description="The intent types, read only for now.")


class FeatureIn(BaseModel):
    model_config = _REQUEST

    on: bool
    reason: Reason


class LimitIn(BaseModel):
    model_config = _REQUEST

    value: int = Field(ge=1, le=100_000, description="Within the limit's own minimum and maximum.")
    reason: Reason


class FeaturesOut(BaseModel):
    """What's switched on right now, so clients hide what's off. Cached up to 60 seconds."""

    features: dict[Feature, bool]
    message_max_length: int

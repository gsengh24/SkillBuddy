"""What each admin role may do (ADR 0015). The table in docs/design/reference-admin.html
(Team and audit page) is the contract; code checks a permission, never a role name."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from app.models import AdminRole


class Permission(StrEnum):
    VIEW_DASHBOARDS = "view_dashboards"
    VIEW_USERS = "view_users"
    SUSPEND_USERS = "suspend_users"
    HANDLE_REPORTS = "handle_reports"
    READ_REPORTED_MESSAGES = "read_reported_messages"
    MANAGE_SIGNUP = "manage_signup"
    MANAGE_SETTINGS = "manage_settings"
    MANAGE_AI = "manage_ai"
    MANAGE_ADMINS = "manage_admins"
    DELETE_DATA = "delete_data"


# In the reference's order, with its wording.
LABELS: Final[dict[Permission, str]] = {
    Permission.VIEW_DASHBOARDS: "View dashboards",
    Permission.VIEW_USERS: "View users",
    Permission.SUSPEND_USERS: "Suspend / ban users",
    Permission.HANDLE_REPORTS: "Handle reports",
    Permission.READ_REPORTED_MESSAGES: "Read messages attached to reports",
    Permission.MANAGE_SIGNUP: "Signup and invites",
    Permission.MANAGE_SETTINGS: "Settings and switches",
    Permission.MANAGE_AI: "AI and matching",
    Permission.MANAGE_ADMINS: "Manage admins",
    Permission.DELETE_DATA: "Delete users and data",
}

_EVERYONE = frozenset({Permission.VIEW_DASHBOARDS, Permission.VIEW_USERS})
_SAFETY = frozenset(
    {Permission.SUSPEND_USERS, Permission.HANDLE_REPORTS, Permission.READ_REPORTED_MESSAGES}
)
_PLATFORM = frozenset(
    {
        Permission.MANAGE_SIGNUP,
        Permission.MANAGE_SETTINGS,
        Permission.MANAGE_AI,
        Permission.DELETE_DATA,
    }
)

ROLE_PERMISSIONS: Final[dict[AdminRole, frozenset[Permission]]] = {
    AdminRole.OWNER: _EVERYONE | _SAFETY | _PLATFORM | {Permission.MANAGE_ADMINS},
    AdminRole.ADMIN: _EVERYONE | _SAFETY | _PLATFORM,
    AdminRole.MODERATOR: _EVERYONE | _SAFETY,
    AdminRole.READONLY: _EVERYONE,
}


def allows(role: AdminRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]


def permissions_of(role: AdminRole) -> list[Permission]:
    """In the table's order."""
    return [permission for permission in LABELS if allows(role, permission)]

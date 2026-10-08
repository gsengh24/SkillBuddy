"""A short "Chrome on Windows" summary of a session's user agent, for the devices list.

Deliberately coarse: the browser family and the system, never versions or the IP address.
No user-agent library: a few ordered checks cover the browsers people actually use.
"""

from __future__ import annotations

from typing import Final

# Order matters: Edge and Opera also say "Chrome", Chrome also says "Safari".
_BROWSERS: Final = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("SamsungBrowser/", "Samsung Internet"),
    ("Firefox/", "Firefox"),
    ("FxiOS/", "Firefox"),
    ("CriOS/", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)
_SYSTEMS: Final = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("CrOS", "ChromeOS"),
    ("Windows", "Windows"),
    ("Mac OS X", "macOS"),
    ("Macintosh", "macOS"),
    ("Linux", "Linux"),
)


def describe_device(user_agent: str | None) -> str:
    """e.g. "Chrome on Windows"; "Unknown device" when there is nothing to go on."""
    agent = user_agent or ""
    browser = next((name for marker, name in _BROWSERS if marker in agent), None)
    system = next((name for marker, name in _SYSTEMS if marker in agent), None)
    if browser and system:
        return f"{browser} on {system}"
    if browser or system:
        return browser or system or ""
    # API clients (curl, a future mobile app) send their own name; keep it short.
    first = agent.split(" ", 1)[0].split("/", 1)[0][:40]
    return first or "Unknown device"

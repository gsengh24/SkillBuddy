"""Authentication module: passwordless email codes and server-side sessions (ADR 0006).

Other modules use it only through ``app.api.deps`` (``get_current_user`` and friends) and
``AuthService``; they never read the auth tables directly.
"""

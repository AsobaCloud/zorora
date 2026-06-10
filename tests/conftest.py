"""Shared pytest fixtures for the Zorora test suite.

The web API endpoints are auth-gated (``@require_auth`` / ``@require_research_quota``
in ``ui/web/auth.py``). The functional endpoint test suites predate that gating and
do not send credentials, so without help they get 401/403.

The autouse fixture below injects a fake authenticated user by patching the
authentication seam in ``ui.web.auth`` itself — the decorator wrappers are defined
there and resolve ``get_current_user`` in that module's globals, and request
handlers lazily ``from ui.web.auth import get_accessible_user_ids`` at call time, so
patching the source module is what actually takes effect. Production auth code is
untouched; this only affects the in-process test client.
"""

import pytest


@pytest.fixture(autouse=True)
def _authenticated_test_user(monkeypatch, request):
    """Make gated Flask endpoints see an authenticated user, without DynamoDB.

    No-op when ``ui.web.auth`` cannot be imported (e.g. a minimal environment
    without the web app's dependencies), so unrelated tests are unaffected.
    """
    try:
        import ui.web.auth as auth
    except Exception:
        return

    # user_id=None routes every gated handler (which does
    # `get_accessible_user_ids(user_id) if user_id else None`) to the legacy
    # NULL-owned bucket, matching how the inherited endpoint tests seed data via
    # the store without a user_id. require_auth only rejects a None *payload*, so a
    # dict with user_id=None still authenticates.
    fake_user = {"user_id": None, "team_id": None}

    # Covers @require_auth and @require_research_quota (both call get_current_user
    # and set request.user). Signature mirrors the real (payload, error) tuple.
    monkeypatch.setattr(
        auth, "get_current_user", lambda: (fake_user, None), raising=False
    )
    # Avoid the DynamoDB team-membership scan; team access = just this user.
    monkeypatch.setattr(
        auth, "get_accessible_user_ids", lambda user_id: [user_id], raising=False
    )
    # Unlimited tier so require_research_quota neither blocks nor touches DynamoDB.
    # Set to enterprise to satisfy Scouting requirements in SEP-044.
    # Skip this mock if we are explicitly testing the auth module (unit tests).
    if "test_auth_unit" not in request.node.nodeid:
        monkeypatch.setattr(
            auth, "_get_user_subscription", lambda user_id: ("enterprise", {}, "regular"), raising=False
        )

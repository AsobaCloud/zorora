"""Tests for SEP-050: Containerize Zorora Flask application for deployment.

These tests verify the four success criteria from the user's perspective:

1. Flask /health endpoint returns HTTP 200 with JSON {"status": "ok"}
2. gunicorn.conf.py exists with expected configuration
3. Dockerfile exists at the project root
4. .dockerignore exists at the project root
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Lazy-load the Flask app the same way other test modules do, so that missing
# optional dependencies don't block the static-file tests.
# ---------------------------------------------------------------------------

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

WEB_APP_IMPORT_ERROR = None
web_app = None

try:
    _APP_PATH = PROJECT_ROOT / "ui" / "web" / "app.py"
    _SPEC = importlib.util.spec_from_file_location("web_app_under_test_sep050", _APP_PATH)
    web_app = importlib.util.module_from_spec(_SPEC)
    sys.modules["web_app_under_test_sep050"] = web_app
    _SPEC.loader.exec_module(web_app)
except ModuleNotFoundError as exc:
    WEB_APP_IMPORT_ERROR = exc


# ---------------------------------------------------------------------------
# Criterion 1: /health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """The /health route must exist and return {"status": "ok"} with HTTP 200.

    This is required so container orchestrators (Docker health-check, ECS,
    Kubernetes liveness probes) can verify the process is alive without
    triggering any expensive database or LLM initialisation.
    """

    def setup_method(self):
        if WEB_APP_IMPORT_ERROR is not None:
            pytest.skip(f"web app dependencies unavailable: {WEB_APP_IMPORT_ERROR}")

    def test_health_endpoint_returns_200(self):
        """GET /health must respond with HTTP 200."""
        client = web_app.app.test_client()
        response = client.get("/health")
        assert response.status_code == 200, (
            f"/health returned {response.status_code}, expected 200"
        )

    def test_health_endpoint_returns_json_status_ok(self):
        """GET /health must return JSON body {"status": "ok"}."""
        client = web_app.app.test_client()
        response = client.get("/health")
        payload = response.get_json()
        assert payload is not None, (
            "/health response is not valid JSON"
        )
        assert "status" in payload, (
            f'/health JSON must contain a "status" key, got: {payload}'
        )
        assert payload["status"] == "ok", (
            f'/health "status" must be "ok", got: {payload["status"]!r}'
        )

    def test_health_endpoint_content_type_is_json(self):
        """GET /health must set Content-Type: application/json."""
        client = web_app.app.test_client()
        response = client.get("/health")
        assert "application/json" in response.content_type, (
            f"/health Content-Type must be application/json, got: {response.content_type}"
        )

    def test_health_endpoint_is_registered_on_app(self):
        """The /health URL rule must be registered on the Flask app object."""
        if WEB_APP_IMPORT_ERROR is not None:
            pytest.skip(f"web app dependencies unavailable: {WEB_APP_IMPORT_ERROR}")

        url_map = {rule.rule for rule in web_app.app.url_map.iter_rules()}
        assert "/health" in url_map, (
            f"/health route is not registered. Registered routes: {sorted(url_map)}"
        )

    def test_health_endpoint_accepts_get_method(self):
        """The /health endpoint must accept GET (the standard probe method)."""
        if WEB_APP_IMPORT_ERROR is not None:
            pytest.skip(f"web app dependencies unavailable: {WEB_APP_IMPORT_ERROR}")

        for rule in web_app.app.url_map.iter_rules():
            if rule.rule == "/health":
                assert "GET" in rule.methods, (
                    f"/health must accept GET, allowed methods: {rule.methods}"
                )
                return

        pytest.fail("/health route not found in URL map")

    def test_health_endpoint_does_not_require_database(self):
        """GET /health must succeed even when all data stores are unavailable.

        A health endpoint that touches the database defeats its purpose: if the
        database is corrupt or slow, the health-check fails and the container
        is killed in a restart loop. The endpoint must be side-effect-free.
        """
        if WEB_APP_IMPORT_ERROR is not None:
            pytest.skip(f"web app dependencies unavailable: {WEB_APP_IMPORT_ERROR}")

        client = web_app.app.test_client()

        # Simulate all store methods blowing up — health must still return 200.
        with patch("tools.market.store.MarketDataStore.get_latest_point",
                   side_effect=Exception("DB unavailable")):
            response = client.get("/health")

        assert response.status_code == 200, (
            "/health must return 200 even when data stores are unavailable"
        )


# ---------------------------------------------------------------------------
# Criterion 2: gunicorn.conf.py configuration
# ---------------------------------------------------------------------------

class TestGunicornConfig:
    """gunicorn.conf.py must exist at the project root and contain the
    production-ready configuration expected by Docker deployments."""

    CONF_PATH = PROJECT_ROOT / "gunicorn.conf.py"

    def test_gunicorn_conf_exists(self):
        """gunicorn.conf.py must exist at the project root."""
        assert self.CONF_PATH.exists(), (
            f"gunicorn.conf.py not found at {self.CONF_PATH}"
        )

    def test_gunicorn_conf_binds_to_all_interfaces(self):
        """gunicorn.conf.py must bind to 0.0.0.0 so the container exposes the port."""
        assert self.CONF_PATH.exists(), pytest.skip("gunicorn.conf.py not yet created")

        source = self.CONF_PATH.read_text()
        assert "0.0.0.0" in source, (
            "gunicorn.conf.py must bind to 0.0.0.0 (all interfaces) for container networking. "
            f"Content: {source[:500]}"
        )

    def test_gunicorn_conf_binds_to_port_5000(self):
        """gunicorn.conf.py must bind to port 5000 to match the Docker EXPOSE directive."""
        assert self.CONF_PATH.exists(), pytest.skip("gunicorn.conf.py not yet created")

        source = self.CONF_PATH.read_text()
        assert "5000" in source, (
            "gunicorn.conf.py must specify port 5000. "
            f"Content: {source[:500]}"
        )

    def test_gunicorn_conf_has_workers_set_to_one(self):
        """gunicorn.conf.py must set workers=1 because background threads use
        module-level state; multiple workers would each have separate state."""
        assert self.CONF_PATH.exists(), pytest.skip("gunicorn.conf.py not yet created")

        source = self.CONF_PATH.read_text()
        assert "workers" in source, (
            "gunicorn.conf.py must define a 'workers' setting"
        )
        # Parse the value — allow `workers = 1` or `workers=1`
        import re
        match = re.search(r"workers\s*=\s*(\d+)", source)
        assert match is not None, (
            "gunicorn.conf.py must assign an integer value to 'workers'"
        )
        workers_val = int(match.group(1))
        assert workers_val == 1, (
            f"gunicorn.conf.py workers must be 1 (got {workers_val}). "
            "Multiple workers break module-level state (background threads, in-memory caches)."
        )

    def test_gunicorn_conf_has_timeout_at_least_60(self):
        """gunicorn.conf.py must set timeout >= 60 seconds.

        Deep research and synthesis requests can take longer than the default
        30-second gunicorn timeout, causing spurious 504s.
        """
        assert self.CONF_PATH.exists(), pytest.skip("gunicorn.conf.py not yet created")

        source = self.CONF_PATH.read_text()
        assert "timeout" in source, (
            "gunicorn.conf.py must define a 'timeout' setting (deep research takes > 30s)"
        )
        import re
        match = re.search(r"timeout\s*=\s*(\d+)", source)
        assert match is not None, (
            "gunicorn.conf.py must assign an integer value to 'timeout'"
        )
        timeout_val = int(match.group(1))
        assert timeout_val >= 60, (
            f"gunicorn.conf.py timeout must be >= 60s (got {timeout_val}). "
            "Deep research requests routinely exceed 30s."
        )

    def test_gunicorn_conf_is_importable_as_python(self):
        """gunicorn.conf.py must be valid Python (no syntax errors)."""
        assert self.CONF_PATH.exists(), pytest.skip("gunicorn.conf.py not yet created")

        import importlib.util as ilu
        spec = ilu.spec_from_file_location("_gunicorn_conf_test", self.CONF_PATH)
        mod = ilu.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except SyntaxError as exc:
            pytest.fail(f"gunicorn.conf.py has a syntax error: {exc}")
        except Exception:
            # Ignore runtime errors (e.g., import of gunicorn internals) —
            # we only care that the file parses correctly as Python.
            pass


# ---------------------------------------------------------------------------
# Criterion 3: Dockerfile exists at project root
# ---------------------------------------------------------------------------

class TestDockerfile:
    """A Dockerfile must exist at the project root so `docker build` works."""

    DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile"

    def test_dockerfile_exists(self):
        """Dockerfile must exist at the project root."""
        assert self.DOCKERFILE_PATH.exists(), (
            f"Dockerfile not found at {self.DOCKERFILE_PATH}"
        )

    def test_dockerfile_not_empty(self):
        """Dockerfile must contain at least a FROM instruction."""
        assert self.DOCKERFILE_PATH.exists(), pytest.skip("Dockerfile not yet created")

        content = self.DOCKERFILE_PATH.read_text().strip()
        assert len(content) > 0, "Dockerfile must not be empty"

    def test_dockerfile_has_from_instruction(self):
        """Dockerfile must start with a FROM instruction."""
        assert self.DOCKERFILE_PATH.exists(), pytest.skip("Dockerfile not yet created")

        lines = [
            line.strip()
            for line in self.DOCKERFILE_PATH.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 0, "Dockerfile has no non-comment lines"
        assert lines[0].upper().startswith("FROM"), (
            f"First non-comment Dockerfile instruction must be FROM, got: {lines[0]!r}"
        )

    def test_dockerfile_exposes_port_5000(self):
        """Dockerfile must EXPOSE 5000 to document the container port."""
        assert self.DOCKERFILE_PATH.exists(), pytest.skip("Dockerfile not yet created")

        content = self.DOCKERFILE_PATH.read_text()
        assert "EXPOSE" in content.upper(), (
            "Dockerfile must include an EXPOSE instruction"
        )
        assert "5000" in content, (
            "Dockerfile must EXPOSE port 5000"
        )

    def test_dockerfile_copies_application_source(self):
        """Dockerfile must include a COPY instruction to include source code."""
        assert self.DOCKERFILE_PATH.exists(), pytest.skip("Dockerfile not yet created")

        content = self.DOCKERFILE_PATH.read_text().upper()
        assert "COPY" in content or "ADD" in content, (
            "Dockerfile must include a COPY (or ADD) instruction to include source code"
        )

    def test_dockerfile_installs_python_dependencies(self):
        """Dockerfile must install Python dependencies (pip install or similar)."""
        assert self.DOCKERFILE_PATH.exists(), pytest.skip("Dockerfile not yet created")

        content = self.DOCKERFILE_PATH.read_text()
        has_pip = "pip install" in content or "pip3 install" in content
        has_requirements = "requirements" in content.lower()
        assert has_pip or has_requirements, (
            "Dockerfile must install Python dependencies "
            "(e.g., RUN pip install -r requirements.txt)"
        )

    def test_dockerfile_has_cmd_or_entrypoint(self):
        """Dockerfile must specify how to start the application (CMD or ENTRYPOINT)."""
        assert self.DOCKERFILE_PATH.exists(), pytest.skip("Dockerfile not yet created")

        content = self.DOCKERFILE_PATH.read_text().upper()
        assert "CMD" in content or "ENTRYPOINT" in content, (
            "Dockerfile must include a CMD or ENTRYPOINT instruction to start the app"
        )

    def test_dockerfile_uses_gunicorn_not_flask_dev_server(self):
        """Dockerfile CMD/ENTRYPOINT must use gunicorn, not the Flask dev server.

        The Flask dev server (`flask run` or `app.run()`) is single-threaded and
        not safe for production. gunicorn must be used instead.
        """
        assert self.DOCKERFILE_PATH.exists(), pytest.skip("Dockerfile not yet created")

        content = self.DOCKERFILE_PATH.read_text()
        assert "gunicorn" in content.lower(), (
            "Dockerfile must use gunicorn to serve the app, not the Flask dev server"
        )

    def test_dockerfile_does_not_run_as_root(self):
        """Dockerfile should create and use a non-root user for security.

        Running containers as root is a security anti-pattern and is blocked
        in some container runtime environments.
        """
        assert self.DOCKERFILE_PATH.exists(), pytest.skip("Dockerfile not yet created")

        content = self.DOCKERFILE_PATH.read_text()
        has_user = "USER" in content.upper()
        assert has_user, (
            "Dockerfile must include a USER instruction to run as a non-root user"
        )


# ---------------------------------------------------------------------------
# Criterion 4: .dockerignore exists at project root
# ---------------------------------------------------------------------------

class TestDockerignore:
    """.dockerignore must exist so large data files are excluded from the
    build context, keeping image size reasonable."""

    DOCKERIGNORE_PATH = PROJECT_ROOT / ".dockerignore"

    def test_dockerignore_exists(self):
        """.dockerignore must exist at the project root."""
        assert self.DOCKERIGNORE_PATH.exists(), (
            f".dockerignore not found at {self.DOCKERIGNORE_PATH}"
        )

    def test_dockerignore_includes_data_directory(self):
        """.dockerignore must NOT exclude the data/ directory.

        The data/ directory contains static GIS shapefiles, SAPP DAM prices,
        and Eskom operational CSVs that the Discovery map and Global View tabs
        need at runtime. Excluding them breaks those features.
        """
        assert self.DOCKERIGNORE_PATH.exists(), pytest.skip(".dockerignore not yet created")

        content = self.DOCKERIGNORE_PATH.read_text()
        lines = [line.strip() for line in content.splitlines()]
        has_data_exclusion = any(
            line in ("data/", "data", "/data", "/data/")
            for line in lines
        )
        assert not has_data_exclusion, (
            ".dockerignore must NOT exclude data/ — it contains static GIS/market files "
            "needed by Discovery map and Global View tabs at runtime."
        )

    def test_dockerignore_excludes_dot_zorora_state(self):
        """.dockerignore must exclude ~/.zorora runtime state.

        The ~/.zorora directory holds SQLite databases that are rebuilt at
        runtime. Including them in the image would bake stale developer-local
        state into the container.
        """
        assert self.DOCKERIGNORE_PATH.exists(), pytest.skip(".dockerignore not yet created")

        content = self.DOCKERIGNORE_PATH.read_text()
        lines = [line.strip() for line in content.splitlines()]
        # .zorora is at $HOME, not in the project root — it should never be
        # included, but we can verify the image doesn't try to bake in any
        # *.db files from the working directory either.
        has_db_exclusion = any(
            "*.db" in line or ".zorora" in line
            for line in lines
        )
        assert has_db_exclusion, (
            ".dockerignore must exclude *.db files or .zorora state directories. "
            f"Current entries: {lines[:20]}"
        )

    def test_dockerignore_excludes_git_directory(self):
        """.dockerignore must exclude the .git directory to avoid leaking
        git history and credentials into the image."""
        assert self.DOCKERIGNORE_PATH.exists(), pytest.skip(".dockerignore not yet created")

        content = self.DOCKERIGNORE_PATH.read_text()
        lines = [line.strip() for line in content.splitlines()]
        has_git = any(
            line in (".git", ".git/", "/.git", "/.git/")
            for line in lines
        )
        assert has_git, (
            ".dockerignore must exclude .git to prevent git history leaking into the image. "
            f"Current entries: {lines[:20]}"
        )

    def test_dockerignore_is_not_empty(self):
        """.dockerignore must not be empty — an empty file provides no exclusions."""
        assert self.DOCKERIGNORE_PATH.exists(), pytest.skip(".dockerignore not yet created")

        content = self.DOCKERIGNORE_PATH.read_text().strip()
        assert len(content) > 0, ".dockerignore must not be empty"

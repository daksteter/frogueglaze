"""Launch-readiness contract tests for Docker, CI, and docs."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_compose():
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_default_compose_is_single_service_sqlite_on_named_volumes():
    compose = load_compose()
    app = compose["services"]["openglaze"]

    assert "8768:8768" in app["ports"]
    assert "openglaze_data:/data" in app["volumes"]
    assert "openglaze_uploads:/app/frontend/uploads" in app["volumes"]
    assert set(compose["volumes"]) == {"openglaze_data", "openglaze_uploads"}
    # The Ory Kratos + PostgreSQL cloud-auth stack was removed from the fork.
    for removed in ("postgres", "kratos", "kratos-migrate", "mailhog"):
        assert removed not in compose["services"]
    env = " ".join(app.get("environment", []))
    assert "DATABASE_URL" not in env and "KRATOS" not in env


def test_compose_environment_interpolations_all_have_defaults():
    """Every ${VAR} interpolation in compose environment entries carries an
    inline default, so `cp .env.example .env && docker compose up -d` boots on
    a pristine clone instead of crashing on a blank required variable."""
    import re

    compose = load_compose()
    offenders = []
    for name, service in compose["services"].items():
        for item in service.get("environment", []):
            for match in re.findall(r"\$\{([^}]*)\}", item):
                if ":-" not in match:
                    offenders.append(f"{name}: {item}")
    assert not offenders, f"compose vars without defaults: {offenders}"


def test_reverse_proxy_profiles_reference_existing_configs():
    compose = load_compose()

    nginx = compose["services"]["nginx"]
    assert "80:80" in nginx["ports"]
    assert "443:443" in nginx["ports"]

    mounted_files = [
        v.split(":", 1)[0].removeprefix("./") for v in nginx.get("volumes", [])
    ]
    for relative in mounted_files:
        if relative and not relative.startswith(("certs", "openglaze_")):
            assert (ROOT / relative).exists(), f"compose references missing {relative}"


def test_tls_reverse_proxy_documents_expected_certificate_files():
    tls_config = (ROOT / "nginx.tls.conf").read_text(encoding="utf-8")
    docs = (ROOT / "docs/self-hosting.md").read_text(encoding="utf-8")

    assert "/etc/nginx/certs/fullchain.pem" in tls_config
    assert "/etc/nginx/certs/privkey.pem" in tls_config
    assert "certs/fullchain.pem" in docs
    assert "certs/privkey.pem" in docs


def test_ci_starts_container_and_checks_health_endpoint():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "docker run" in ci
    assert "/health" in ci
    assert "curl" in ci
    assert "import flask" not in ci


def test_api_docs_match_current_public_routes():
    api = (ROOT / "docs/API.md").read_text(encoding="utf-8")
    stale_paths = [
        "POST /api/auth/login",
        "POST /api/auth/register",
        "POST /api/uploads",
        "GET /api/gamification/stats",
        "GET /api/gamification/leaderboard",
        "GET /api/stats",
        "GET /api/progress",
        "/api/predictions",
    ]
    for path in stale_paths:
        assert path not in api

    current_paths = [
        "POST /api/auth/simple-login",
        "GET /api/auth/me",
        "POST /api/upload",
    ]
    for path in current_paths:
        assert path in api


def test_runtime_ports_and_cors_defaults_match_documented_docker_port():
    app_factory = (ROOT / "webapp" / "app_factory.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "http://localhost:8768" in readme
    assert "Open http://localhost:8768" in readme
    assert "localhost:8767" not in app_factory
    assert "FLASK_PORT" in app_factory
    assert "configured_port" in app_factory


def test_env_example_has_no_cloud_auth_settings():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "OPENGLAZE_MODE=personal" in env
    for removed in ("POSTGRES_PASSWORD", "KRATOS", "OPENGLAZE_MODE=cloud"):
        assert removed not in env


def test_codecov_action_uses_v6_input_name():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "codecov/codecov-action@e79a6962e0d4c0c17b229090214935d2e33f8354 # v6" in ci
    assert "files: ./coverage.xml" in ci
    assert "file: ./coverage.xml" not in ci


def test_app_no_longer_serves_seo_discovery_assets():
    """The fork dropped upstream's SEO landing pages and discovery files."""
    static_docs = (ROOT / "webapp" / "routes" / "static_docs.py").read_text(
        encoding="utf-8"
    )
    assert 'REPO_ROOT / "docs"' not in static_docs
    for name in ("sitemap.xml", "llms.txt", "robots.txt", "index.html"):
        assert not (ROOT / "docs" / name).exists(), name

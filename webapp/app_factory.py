"""Application factory for the OpenGlaze Flask app."""

import logging
import os
import secrets

from flask import Flask, g, jsonify
from flask_cors import CORS

from config import load_config, ConfigurationError
from core.errors import error_payload
from core.glazes import GlazeManager
from core.combinations import CombinationManager
from core.experiments import ExperimentManager
from core.ai.context import ContextRetriever
from core.security import init_security
from core.studio_materials import sync_engine
from webapp.db import get_db_connection, init_db
from webapp.helpers import get_current_user_id
from webapp.routes import ALL_BLUEPRINTS

try:
    from core.studios import StudioManager

    STUDIOS_AVAILABLE = True
except ImportError:
    STUDIOS_AVAILABLE = False

logger = logging.getLogger(__name__)


def create_app(config: dict = None) -> Flask:
    """Create and configure the OpenGlaze Flask application."""
    from webapp import REPO_ROOT

    app = Flask(__name__, static_folder=str(REPO_ROOT / "frontend"))

    # Load configuration if not provided
    if config is None:
        try:
            config = load_config()
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            raise

    mode = config.get("mode")
    app.config["MODE"] = mode

    # Secret key for sessions
    secret_key = getattr(mode, "security", None)
    if secret_key:
        secret_key = secret_key.secret_key
    if not secret_key:
        secret_key = secrets.token_hex(32)
    app.config["SECRET_KEY"] = secret_key

    # Feature flags
    features = {
        "auth_enabled": getattr(mode, "AUTH_ENABLED", False),
        "multi_tenant": getattr(mode, "MULTI_TENANT", False),
        "api_access": getattr(mode, "API_ACCESS", False),
        "analytics": getattr(mode, "ANALYTICS", False),
    }
    app.config["FEATURES"] = features

    # Database path (routes read this via current_app.config)
    db_path = config.get("database", {}).get("path", "glaze.db")
    app.config["DATABASE_PATH"] = db_path

    _configure_cors(app)

    # Initialize security
    init_security(app)

    # Initialize database schema
    init_db(db_path)

    app.before_request(_make_request_setup(db_path))
    app.teardown_appcontext(_close_request_db)

    _register_error_handlers(app)

    # Register route blueprints; the static/docs blueprint owns a catch-all
    # route and must be registered last.
    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app


def _make_request_setup(db_path: str):
    """Build the per-request manager setup closure bound to a database path."""

    def setup_managers():
        """Set up managers for each request."""
        # Studio materials and current lots feed every calculation
        sync_engine(db_path)
        # Personal mode: glazes, combinations and experiments are not per-user
        g.glaze_manager = GlazeManager(db_path)
        g.combo_manager = CombinationManager(db_path)
        g.exp_manager = ExperimentManager(db_path)
        g.context_retriever = ContextRetriever(db_path)
        # Shared DB connection for routes that take a connection, not db_path
        g.db_conn = get_db_connection(db_path)
        if STUDIOS_AVAILABLE:
            # Studio endpoints identify the caller by simple-auth token
            g.studio_manager = StudioManager(db_path, user_id=get_current_user_id())

    return setup_managers


def _close_request_db(exc=None) -> None:
    """Close the shared per-request connection opened by setup_managers.

    Leaving it to garbage collection keeps the SQLite file open, which on
    Windows blocks deleting or moving it (WinError 32).
    """
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


def _configure_cors(app: Flask) -> None:
    """Allow localhost dev origins plus any operator-provided extras."""
    configured_port = os.environ.get("FLASK_PORT", "8767")
    cors_origins = [
        f"http://localhost:{configured_port}",
        f"http://127.0.0.1:{configured_port}",
    ]
    extra_cors_origins = [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    cors_origins.extend(extra_cors_origins)
    CORS(app, origins=cors_origins, supports_credentials=True)


def _register_error_handlers(app: Flask) -> None:
    """Attach JSON error handlers with concrete retry invocations."""

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error_payload("Not found", "not_found")), 404

    @app.errorhandler(415)
    def unsupported_media_type(e):
        return (
            jsonify(
                error_payload(
                    "Unsupported Media Type: send JSON request bodies with Content-Type: application/json.",
                    "unsupported_media_type",
                )
            ),
            415,
        )

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {e}")
        return jsonify(error_payload("Internal server error", "server_error")), 500

    # No 429 handler here: rate-limit denials are built inside the
    # @rate_limit decorator (core/security), which returns the response
    # directly with the measured retry_after and a request-specific retry
    # invocation. A generic handler would only substitute fixed values.

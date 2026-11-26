"""
OpenGlaze Configuration Loader
Provides the personal-mode runtime configuration.
Security-hardened as of March 2026.
"""

import os
import re
import yaml
import secrets
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing required values."""

    pass


@dataclass
class SecurityConfig:
    """Security-related configuration."""

    rate_limiting_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_storage_url: str = "memory://"
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:8767"])
    cookie_secure: bool = True
    cookie_httponly: bool = True
    cookie_samesite: str = "Lax"
    https_enforce: bool = False
    hsts_max_age: int = 31536000
    secret_key: str = ""


@dataclass
class ModeConfig:
    """Base configuration for any mode."""

    AUTH_ENABLED: bool = False
    MULTI_TENANT: bool = False
    API_ACCESS: bool = False
    ANALYTICS: bool = False
    DEFAULT_THEME: str = "dark"
    DB_TYPE: str = "sqlite"
    DB_PATH: str = "glaze.db"
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8767
    security: SecurityConfig = field(default_factory=SecurityConfig)

    def __post_init__(self):
        self.name = "base"


@dataclass
class PersonalMode(ModeConfig):
    """Personal mode: Single-user, local SQLite, no auth/billing."""

    def __post_init__(self):
        self.name = "personal"
        self.AUTH_ENABLED = False
        self.MULTI_TENANT = False
        self.API_ACCESS = False
        self.ANALYTICS = False
        self.DEFAULT_THEME = "dark"
        self.DB_TYPE = "sqlite"
        self.DB_PATH = os.environ.get("DATABASE_PATH", "glaze.db")
        self.DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
        self.HOST = os.environ.get("FLASK_HOST", "127.0.0.1")
        self.PORT = int(os.environ.get("FLASK_PORT", "8767"))

        # Security defaults for personal mode
        self.security = SecurityConfig(
            rate_limiting_enabled=True,
            rate_limit_per_minute=int(os.environ.get("RATELIMIT_PER_MINUTE", "60")),
            cookie_secure=False,  # Personal mode typically runs locally
            https_enforce=False,
            secret_key=self._get_or_create_secret_key(),
        )

    def _get_or_create_secret_key(self) -> str:
        """Get secret key from environment or generate one for this session."""
        key = os.environ.get("SECRET_KEY")
        if not key:
            # Generate a random key for this session (won't persist across restarts)
            key = secrets.token_hex(32)
            logger.info(
                "Generated session secret key (set SECRET_KEY env var for persistence)"
            )
        return key


def detect_mode() -> ModeConfig:
    """Return the runtime mode. This fork supports personal mode only.

    Raises:
        ConfigurationError: If OPENGLAZE_MODE asks for any other mode.
    """
    mode_env = os.environ.get("OPENGLAZE_MODE", "").lower()
    if mode_env not in ("", "personal"):
        raise ConfigurationError(
            f"Unsupported OPENGLAZE_MODE={mode_env!r}: only 'personal' is supported "
            "(cloud mode and its Ory Kratos auth were removed from this fork)."
        )
    return PersonalMode()


def load_config(mode: Optional[ModeConfig] = None) -> dict:
    """
    Load configuration from YAML file based on mode.

    Args:
        mode: ModeConfig instance. If None, auto-detects.

    Returns:
        Dictionary with configuration values.
    """
    if mode is None:
        mode = detect_mode()

    config_dir = Path(__file__).parent
    config_file = config_dir / f"{mode.name}.yaml"

    config = {}

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                raw_content = f.read()

            # Substitute environment variables
            content = _substitute_env_vars(raw_content)

            config = yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            logger.warning(f"Error loading config file {config_file}: {e}")

    # Add mode info
    config["mode"] = mode

    return config


def _substitute_env_vars(content: str) -> str:
    """
    Substitute environment variables in YAML content.
    Supports ${VAR_NAME} and ${VAR_NAME:default} syntax.

    Security: Only allows specific patterns to prevent injection.
    """
    # Pattern: ${VAR_NAME} or ${VAR_NAME:default}
    pattern = r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}"

    def replacer(match):
        var_name = match.group(1)
        default = match.group(2)

        # Only allow specific characters in default values
        if default and not re.match(r"^[a-zA-Z0-9_:/\.\-\+]*$", default):
            logger.warning(f"Invalid default value for {var_name}, using empty string")
            default = ""

        value = os.environ.get(var_name, default if default is not None else "")

        # For sensitive values, don't log the actual value
        if any(
            sensitive in var_name.upper()
            for sensitive in ["PASSWORD", "SECRET", "KEY", "TOKEN", "CREDENTIAL"]
        ):
            log_value = "***REDACTED***"
        else:
            log_value = value[:50] + "..." if len(value) > 50 else value

        logger.debug(f"Substituted ${{{var_name}}} -> {log_value}")
        return value

    return re.sub(pattern, replacer, content)


# Convenience exports
__all__ = [
    "detect_mode",
    "load_config",
    "PersonalMode",
    "ModeConfig",
    "SecurityConfig",
    "ConfigurationError",
]

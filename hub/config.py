"""Hub settings loaded from environment / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


# Android app allowlist — constant; never user-supplied.
ANDROID_APP_ALLOWLIST: dict[str, str] = {
    "chrome": "com.android.chrome",
    "youtube": "com.google.android.youtube",
    "settings": "com.android.settings",
}


class Settings(BaseSettings):
    """All configuration comes from environment variables (or .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    hub_api_token: str = "CHANGE_ME_long_random_string"
    database_url: str = "sqlite://"
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_username: str = "orb_hub"
    mqtt_password: str = "CHANGE_ME"
    command_timeout_seconds: float = 10.0
    pairing_code_ttl_seconds: int = 300
    adb_path: str = "adb"
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS origins as a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset cached settings (used in tests)."""
    global _settings
    _settings = None

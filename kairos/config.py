from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings, read from the environment / .env.

    Everything defaults to empty so that importing this module never needs
    secrets; each component checks the values it actually uses.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    redis_url: str = ""

    wa_access_token: str = ""
    wa_phone_number_id: str = ""
    wa_app_secret: str = ""
    wa_verify_token: str = ""

    llm_provider: str = "anthropic"
    llm_model: str = ""
    llm_api_key: str = ""

    google_service_account_json: str = ""
    sheet_id: str = ""

    owner_phones: str = ""

    @property
    def owner_phone_list(self) -> list[str]:
        return [p for p in (normalize_phone(x) for x in self.owner_phones.split(",")) if p]


def normalize_phone(phone: str) -> str:
    """Digits only, the format WhatsApp uses for wa_id (e.g. 923001234567)."""
    return "".join(ch for ch in phone if ch.isdigit())


@lru_cache
def get_settings() -> Settings:
    return Settings()

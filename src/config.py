from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Allowlist — stored as a set for O(1) lookup
    ALLOWED_PHONE_NUMBERS: list[str]

    # AI
    ANTHROPIC_API_KEY: str
    TAVILY_API_KEY: str

    # Database
    DATABASE_URL: str

    # Baileys sidecar
    SIDECAR_URL: str = "http://localhost:3000"

    @field_validator("ALLOWED_PHONE_NUMBERS", mode="before")
    @classmethod
    def parse_phone_list(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v  # type: ignore[return-value]

    @property
    def allowed_set(self) -> set[str]:
        return set(self.ALLOWED_PHONE_NUMBERS)

    @property
    def phone_to_user_id(self) -> dict[str, str]:
        return {phone: f"user_{phone.lstrip('+')}" for phone in self.ALLOWED_PHONE_NUMBERS}


settings = Settings()  # type: ignore[call-arg]

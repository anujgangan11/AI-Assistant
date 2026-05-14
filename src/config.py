from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Meta / WhatsApp
    META_APP_SECRET: str
    META_ACCESS_TOKEN: str
    META_PHONE_NUMBER_ID: str
    META_VERIFY_TOKEN: str

    # Allowlist — stored as a set for O(1) lookup
    ALLOWED_PHONE_NUMBERS: list[str]

    # AI
    ANTHROPIC_API_KEY: str
    TAVILY_API_KEY: str

    # Database
    DATABASE_URL: str

    # Dev tunnel
    NGROK_URL: str = ""

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
        # v0: derive a stable user_id from the phone number
        return {phone: f"user_{phone.lstrip('+')}" for phone in self.ALLOWED_PHONE_NUMBERS}


settings = Settings()  # type: ignore[call-arg]

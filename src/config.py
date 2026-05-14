from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Stored as a raw comma-separated string to avoid pydantic-settings JSON parsing
    ALLOWED_PHONE_NUMBERS: str

    # AI
    ANTHROPIC_API_KEY: str
    TAVILY_API_KEY: str

    # Database
    DATABASE_URL: str

    # Baileys sidecar
    SIDECAR_URL: str = "http://localhost:3000"

    @property
    def allowed_list(self) -> list[str]:
        return [p.strip() for p in self.ALLOWED_PHONE_NUMBERS.split(",") if p.strip()]

    @property
    def allowed_set(self) -> set[str]:
        return set(self.allowed_list)

    @property
    def phone_to_user_id(self) -> dict[str, str]:
        return {phone: f"user_{phone.lstrip('+')}" for phone in self.allowed_list}


settings = Settings()  # type: ignore[call-arg]

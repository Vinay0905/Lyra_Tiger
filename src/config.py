import os
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """
    Validates and stores system environment configuration parameters.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # API Keys
    groq_api_key: str = Field("", validation_alias="GROQ_API_KEY")
    openai_api_key: str = Field("", validation_alias="OPENAI_API_KEY")
    gemini_api_key: str = Field("", validation_alias="GEMINI_API_KEY")
    openrouter_api_key: str = Field("", validation_alias="OPENROUTER_API_KEY")

    # LLM Configurations
    llm_fallback_chain: str = Field("groq", validation_alias="LLM_FALLBACK_CHAIN")
    groq_model: str = Field("llama3-70b-8192", validation_alias="GROQ_MODEL")
    groq_vision_model: str = Field("llama-3.2-11b-vision-preview", validation_alias="GROQ_VISION_MODEL")
    openai_model: str = Field("gpt-4o-mini", validation_alias="OPENAI_MODEL")
    gemini_model: str = Field("gemini-1.5-flash", validation_alias="GEMINI_MODEL")
    openrouter_model: str = Field("meta-llama/llama-3-70b-instruct", validation_alias="OPENROUTER_MODEL")

    # Local Server settings
    host: str = Field("127.0.0.1", validation_alias="HOST")
    port: int = Field(8000, validation_alias="PORT")
    debug: bool = Field(True, validation_alias="LYRA_DEBUG")

    # Developer settings
    approved_workspace_dirs: str = Field("", validation_alias="APPROVED_WORKSPACE_DIRS")

    # Kimi WebBridge settings
    webbridge_host: str = Field("127.0.0.1", validation_alias="WEBBRIDGE_HOST")
    webbridge_port: int = Field(10086, validation_alias="WEBBRIDGE_PORT")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "no", "f", "off"}:
                return False
            if normalized in {"debug", "dev", "development", "true", "1", "yes", "t", "on"}:
                return True
        return value

    @field_validator("llm_fallback_chain")
    @classmethod
    def normalize_fallback_chain(cls, value: str) -> str:
        providers = [v.strip().lower() for v in value.split(",") if v.strip()]
        return ",".join(providers) or "groq"

    @field_validator("approved_workspace_dirs")
    @classmethod
    def normalize_workspace_dirs(cls, value: str) -> str:
        paths = [p.strip() for p in value.split(",") if p.strip()]
        absolute_paths = [os.path.abspath(os.path.expanduser(p)) for p in paths]
        return ",".join(absolute_paths)

    @property
    def llm_fallback_providers(self) -> list[str]:
        return [v.strip().lower() for v in self.llm_fallback_chain.split(",") if v.strip()]

    @property
    def approved_workspace_paths(self) -> list[str]:
        return [p.strip() for p in self.approved_workspace_dirs.split(",") if p.strip()]

settings = Settings()

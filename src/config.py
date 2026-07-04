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
    # Large / primary reasoning model (accepts GROQ_MODEL or GROQ_CHAT_MODEL)
    groq_model: str = Field("llama-3.3-70b-versatile", validation_alias="GROQ_MODEL")
    groq_chat_model: str = Field("", validation_alias="GROQ_CHAT_MODEL")
    # Small / fast tier used by the intent router (A4 tiered routing)
    groq_small_model: str = Field("llama-3.1-8b-instant", validation_alias="GROQ_SMALL_MODEL")
    groq_vision_model: str = Field("llama-3.2-11b-vision-preview", validation_alias="GROQ_VISION_MODEL")
    groq_stt_model: str = Field("whisper-large-v3", validation_alias="GROQ_STT_MODEL")
    openai_model: str = Field("gpt-4o-mini", validation_alias="OPENAI_MODEL")
    gemini_model: str = Field("gemini-1.5-flash", validation_alias="GEMINI_MODEL")
    openrouter_model: str = Field("meta-llama/llama-3-70b-instruct", validation_alias="OPENROUTER_MODEL")

    # Local Server settings
    host: str = Field("127.0.0.1", validation_alias="HOST")
    port: int = Field(8000, validation_alias="PORT")
    debug: bool = Field(True, validation_alias="LYRA_DEBUG")

    # Persistence (A3: unified SQLite conversation + audit store)
    db_path: str = Field("lyra_store.db", validation_alias="LYRA_DB_PATH")
    history_turns: int = Field(8, validation_alias="LYRA_HISTORY_TURNS")

    # Caching (A4: classification + TTS caches)
    classify_cache_ttl: int = Field(600, validation_alias="LYRA_CLASSIFY_CACHE_TTL")
    tts_cache_size: int = Field(64, validation_alias="LYRA_TTS_CACHE_SIZE")

    # Voice
    tts_voice: str = Field("af_sarah", validation_alias="TTS_VOICE")

    # Developer settings
    approved_workspace_dirs: str = Field("", validation_alias="APPROVED_WORKSPACE_DIRS")

    # Web engine (L1: owned Playwright engine, replaces Kimi WebBridge)
    # Mode: "cdp" attaches to the user's real Chrome; "bundled" launches Playwright Chromium.
    browser_mode: str = Field("cdp", validation_alias="BROWSER_MODE")
    chrome_cdp_url: str = Field("http://127.0.0.1:9222", validation_alias="CHROME_CDP_URL")
    browser_headless: bool = Field(False, validation_alias="BROWSER_HEADLESS")
    browser_user_data_dir: str = Field("", validation_alias="BROWSER_USER_DATA_DIR")
    # Comma-separated host allow/deny lists. Empty allowlist = allow all (except denied/internal).
    browser_allowlist: str = Field("", validation_alias="BROWSER_ALLOWLIST")
    browser_denylist: str = Field("", validation_alias="BROWSER_DENYLIST")
    browser_nav_timeout_ms: int = Field(30000, validation_alias="BROWSER_NAV_TIMEOUT_MS")
    browser_action_budget_s: float = Field(45.0, validation_alias="BROWSER_ACTION_BUDGET_S")
    browser_idle_teardown_s: float = Field(300.0, validation_alias="BROWSER_IDLE_TEARDOWN_S")

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

    @property
    def primary_chat_model(self) -> str:
        """Prefer GROQ_CHAT_MODEL when supplied, else fall back to GROQ_MODEL."""
        return (self.groq_chat_model or self.groq_model).strip()

    @property
    def browser_allow_hosts(self) -> list[str]:
        return [h.strip().lower() for h in self.browser_allowlist.split(",") if h.strip()]

    @property
    def browser_deny_hosts(self) -> list[str]:
        return [h.strip().lower() for h in self.browser_denylist.split(",") if h.strip()]

settings = Settings()

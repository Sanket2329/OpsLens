from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "OpsLens"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS — comma-separated list of allowed origins
    # Set to "*" only for local development.
    cors_origins: str = "*"

    # Database
    database_url: str

    # Qdrant
    qdrant_url: str
    qdrant_collection: str = "documents"
    qdrant_vector_size: int = 3072

    # Google AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Document upload
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20
    allowed_extensions: str = ".pdf,.txt,.md"

    # RAG
    rag_retrieval_limit: int = 10
    rag_chat_retrieval_limit: int = 6
    rag_conversation_history_turns: int = 6

    # Slack notifications (optional)
    slack_webhook_url: str = ""
    slack_enabled: bool = False

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )


settings = Settings()

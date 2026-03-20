from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FactorAI Server"
    app_env: str = "dev"
    sqlite_path: str = "factorai.db"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    python_node_timeout: int = 6
    python_node_memory_mb: int = 256
    artifact_dir: str = "server_artifacts"
    auth_enabled: bool = True
    auth_allow_unauthenticated_health: bool = True
    auth_tokens: str = (
        "dev-admin-token:admin:admin,"
        "dev-editor-token:editor:editor,"
        "dev-viewer-token:viewer:viewer"
    )

    model_config = SettingsConfigDict(env_prefix="FACTORAI_", extra="ignore")


settings = Settings()

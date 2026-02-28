from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/workshop"
    gemini_api_key: str
    gemini_image_model: str = "gemini-3.1-flash-image-preview"
    gemini_analysis_model: str = "gemini-2.5-flash"
    outputs_dir: Path = Path("data/outputs")
    uploads_dir: Path = Path("data/uploads")
    cors_origins: str = "http://localhost:3000"

    model_config = {"env_file": ".env"}


settings = Settings()
settings.outputs_dir.mkdir(parents=True, exist_ok=True)
settings.uploads_dir.mkdir(parents=True, exist_ok=True)

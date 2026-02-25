from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    gemini_api_key: str
    gemini_image_model: str = "gemini-2.5-flash-image"
    outputs_dir: Path = Path("data/outputs")
    uploads_dir: Path = Path("data/uploads")
    cors_origins: str = "http://localhost:3000"

    model_config = {"env_file": ".env"}


settings = Settings()
settings.outputs_dir.mkdir(parents=True, exist_ok=True)
settings.uploads_dir.mkdir(parents=True, exist_ok=True)

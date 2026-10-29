from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://manas:manas@localhost:5432/manas_inference"
    test_database_url: str = "sqlite:///./test.db"  # override with TEST_DATABASE_URL env
    jwt_secret: str = "aman"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    artifacts_dir: Path = Path(__file__).resolve().parents[1] / "models" / "artifacts"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    clinician_password: str = "clinician123"
    mlops_password: str = "mlops123"
    preprocessing_version: str = "scaler-v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()

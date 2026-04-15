from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/linkedin_automation"
    encryption_key: str = ""
    secret_key: str = "changeme"
    headless: bool = True
    daily_limit_max: int = 30
    min_delay: int = 20
    max_delay: int = 60

    class Config:
        env_file = ".env"

    def get_fernet(self) -> Fernet:
        if not self.encryption_key:
            self.encryption_key = Fernet.generate_key().decode()
        return Fernet(self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key)


settings = Settings()

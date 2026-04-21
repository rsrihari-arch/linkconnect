import base64
import hashlib
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@db:5432/linkedin_automation"
    encryption_key: str = "default-key-change-me"
    secret_key: str = "changeme"
    headless: bool = True
    daily_limit_max: int = 30
    min_delay: int = 30
    max_delay: int = 90
    warmup_days: int = 7
    warmup_start_limit: int = 5

    class Config:
        env_file = ".env"

    def encrypt(self, plaintext: str) -> str:
        key = hashlib.sha256(self.encryption_key.strip().encode()).digest()
        encoded = base64.b64encode(plaintext.encode()).decode()
        # Simple XOR obfuscation with key
        result = []
        for i, ch in enumerate(encoded):
            result.append(chr(ord(ch) ^ key[i % len(key)]))
        return base64.b64encode("".join(result).encode("latin-1")).decode()

    def decrypt(self, ciphertext: str) -> str:
        key = hashlib.sha256(self.encryption_key.strip().encode()).digest()
        decoded = base64.b64decode(ciphertext.encode()).decode("latin-1")
        result = []
        for i, ch in enumerate(decoded):
            result.append(chr(ord(ch) ^ key[i % len(key)]))
        return base64.b64decode("".join(result)).decode()


settings = Settings()

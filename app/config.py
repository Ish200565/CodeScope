from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    github_webhook_secret: str = ""
    github_app_id: str = ""
    github_private_key_path: str = ""
    fail_mode:str =""

settings = Settings()
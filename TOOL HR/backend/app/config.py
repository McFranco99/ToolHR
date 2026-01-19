from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://toolhr:toolhr@localhost:5432/toolhr"

settings = Settings()

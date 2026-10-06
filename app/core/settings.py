from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # DB
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"

    # TOKENS
    # Short, so a closed account or changed password stops working soon: the
    # frontend renews the token with the refresh token (revoked on closing,
    # password change and logout).
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_HOURS: int = 168

    GATEWAY_AUTH_CLIENT_ID: str = "api_gateway"
    GATEWAY_AUTH_CLIENT_SECRET: str

    PHYSICAL_AUTH_CLIENT_ID: str = "api_physical"
    PHYSICAL_AUTH_CLIENT_SECRET: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

settings = Settings()

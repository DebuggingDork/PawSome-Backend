from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config= SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development" #typehint vairable_name : data_type = default value
    database_url: str 
    redis_url: str = Field(..., description="Redis URL") # ... means required (ellipses)

    jwt_secret: str = Field(...,description="JWT Secret")
    jwt_algorithm: str = Field("HS256",description="JWT Algorithm") # Field will expect its first argument toi be default  whne we keep as .... it is required and if we dont use it then we need to prvide a default values for it and then the second argument is the description of the field 
    access_token_expire_minutes: int = Field(30,description="Acces toke expire minutes")
    refresh_token_expire_days: int = Field(7,description ="refresh token expired days")

    cors_origins: str = Field("http://localhost:5173",description="CORS Origins")


settings  = Settings()
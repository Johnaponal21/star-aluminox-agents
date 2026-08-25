"""Configuración central del sistema Star Aluminox Agents."""
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "staraluminox-verify"
    
    database_url: str = "postgresql://user:pass@localhost:5432/staraluminox"
    redis_url: str = "redis://localhost:6379/0"
    
    business_name: str = "Star Aluminox"
    business_country: str = "Colombia"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

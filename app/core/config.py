import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "NIA Content Studio"
    VERSION: str = "1.0.0"
    
    # Google Cloud Config
    GOOGLE_CLOUD_PROJECT: str
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = "service_account.json"
    GOOGLE_CLOUD_API_KEY: str

    # Pub/Sub Config
    PUBSUB_TOPIC_NAME: str = "ImageGenerationRequests"
    
    # Storage Config
    GCS_BUCKET_NAME: str
    
    # Supabase Config
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    # Model Config
    #IMAGE_MODEL_ID: str = "gemini-3-pro-image-preview"
    IMAGE_MODEL_ID: str = "gemini-3-pro-image-preview"
    VIDEO_MODEL_ID: str = "gemini-2.5-flash-image"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
import uuid
from google.cloud import storage
from app.core.config import get_settings

settings = get_settings()

class StorageService:
    def __init__(self):
        try:
            self.client = storage.Client()
            self.bucket_name = settings.GCS_BUCKET_NAME
            print(f"✅ GCS Client initialized for bucket: {self.bucket_name}")
        except Exception as e:
            print(f"❌ Failed to initialize GCS: {e}")
            self.client = None

    def upload_bytes(self, data: bytes, prefix: str, ext: str, content_type: str) -> str:
        """
        Uploads bytes to GCS and returns the public URL.
        """
        if not self.client:
            raise Exception("Storage client not available")

        try:
            filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            
            # Note: This is a blocking call. In high-scale async apps, 
            # consider running this in a threadpool.
            blob.upload_from_string(data, content_type=content_type)
            
            # Assuming bucket is public or you want the storage URL
            return f"https://storage.googleapis.com/{self.bucket_name}/{filename}"
        except Exception as e:
            print(f"❌ GCS Upload Error: {e}")
            raise e
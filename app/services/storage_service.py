import uuid
import base64  # <--- Add this import
from google.cloud import storage
from app.core.config import get_settings

settings = get_settings()

class StorageService:
    # ... existing __init__ ...
    def __init__(self):
        try:
            self.client = storage.Client()
            self.bucket_name = settings.GCS_BUCKET_NAME
            print(f"✅ GCS Client initialized for bucket: {self.bucket_name}")
        except Exception as e:
            print(f"❌ Failed to initialize GCS: {e}")
            self.client = None

    # ... existing upload_bytes ...
    def upload_bytes(self, data: bytes, prefix: str, ext: str, content_type: str) -> str:
        # (Existing implementation)
        if not self.client:
            raise Exception("Storage client not available")

        try:
            filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            blob.upload_from_string(data, content_type=content_type)
            return f"https://storage.googleapis.com/{self.bucket_name}/{filename}"
        except Exception as e:
            print(f"❌ GCS Upload Error: {e}")
            raise e

    # --- NEW METHOD ---
    def download_image_as_base64(self, image_url: str) -> str:
        """
        Downloads image from GCS URL and returns base64 string.
        """
        if not self.client:
            print("❌ Storage client not available")
            return None
        
        try:
            # Extract blob name from the public URL
            # URL structure: https://storage.googleapis.com/{bucket_name}/{blob_name}
            url_prefix = f"https://storage.googleapis.com/{self.bucket_name}/"
            
            if not image_url.startswith(url_prefix):
                print(f"⚠️ URL {image_url} does not match expected bucket prefix.")
                return None
            
            blob_name = image_url.replace(url_prefix, "")
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            
            # Download as bytes
            image_bytes = blob.download_as_bytes()
            
            # Convert to base64
            return base64.b64encode(image_bytes).decode("utf-8")
        except Exception as e:
            print(f"❌ GCS Download Error for {image_url}: {e}")
            return None

    def generate_signed_url(self, blob_name):
        blob = self.client.bucket(self.bucket_name).blob(blob_name)
        return blob.generate_signed_url(version="v4", expiration=3600)    
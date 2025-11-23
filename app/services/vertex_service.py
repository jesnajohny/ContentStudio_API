import os
import base64
import io
from PIL import Image
from google import genai
from google.genai import types
from app.core.config import get_settings
from app.services.storage_service import StorageService
from app.services.supabase_service import SupabaseService
from urllib.parse import urlparse

settings = get_settings()

class VertexGenerator:
    def __init__(self):
        # Ensure auth env var is set for the SDK
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS
        
        try:
            self.client = genai.Client(
                vertexai=True,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION
            )
            self.storage = StorageService()
            self.supabase = SupabaseService()
            print(f"✅ Vertex AI Client initialized.")
        except Exception as e:
            print(f"❌ Failed to initialize Vertex AI: {e}")
            self.client = None

    def _save_asset(self, data: bytes, user_id: str, asset_type: str, source: str, prefix: str, ext: str, mime: str) -> str:
        """
        Helper to upload file to GCS, extract metadata, and save info to Supabase.
        """
        # 1. Upload to GCS
        try:
            url = self.storage.upload_bytes(data, prefix, ext, mime)
        except Exception as e:
            print(f"❌ Failed to upload asset to storage: {e}")
            raise e

        # 2. Extract Metadata
        metadata = {"size_bytes": len(data), "format": ext, "mime": mime}
        if asset_type == "image":
            try:
                with Image.open(io.BytesIO(data)) as img:
                    metadata["width"] = img.width
                    metadata["height"] = img.height
            except Exception as e:
                print(f"⚠️ Failed to extract image metadata: {e}")

        # 3. Insert into Supabase
        self.supabase.insert_asset(
            user_id=user_id,
            asset_type=asset_type,
            source=source,
            storage_path=url,
            metadata=metadata
        )
        
        return url

    def _process_media(self, data: bytes, prefix: str, ext: str, mime: str, user: str, asset_type: str) -> dict:
        try:
            # Save the GENERATED asset to GCS and Supabase
            url = self._save_asset(data, user, asset_type, "generated", prefix, ext, mime)
            
            

            parsed = urlparse(url)
            
            response = {"status": "completed", "base_url": url, "signed_url": self.storage.generate_signed_url(parsed.path.lstrip("/").split("/", 1)[1])}

            return response
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def generate_text_to_image(self, prompt: str, aspect_ratio: str, user: str) -> dict:
        if not self.client: return {"status": "failed", "error": "Client unavailable"}
        
        try:
            config = types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio)
            )
            response = self.client.models.generate_content(
                model=settings.IMAGE_MODEL_ID,
                contents=[prompt],
                config=config
            )
            
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        # Pass user and asset_type="image"
                        return self._process_media(
                            part.inline_data.data, f"{user}/t2i", "png", "image/png", user, "image"
                        )
            return {"status": "failed", "error": "No image generated"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def generate_image_to_image(self, image_bytes: bytes, prompt: str, user: str) -> dict:
        if not self.client: return {"status": "failed", "error": "Client unavailable"}

        try:
            # 1. Save Input Asset (Uploaded)
            self._save_asset(image_bytes, user, "image", "uploaded", f"{user}/inputs", "png", "image/png")

            # 2. Generate Content
            image_part = types.Part(
                inline_data=types.Blob(mime_type="image/png", data=image_bytes)
            )
            text_part = types.Part(text=prompt)

            response = self.client.models.generate_content(
                model=settings.IMAGE_MODEL_ID,
                contents=[image_part, text_part],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"])
            )

            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        return self._process_media(
                            part.inline_data.data, f"{user}/i2i", "png", "image/png", user, "image"
                        )
            return {"status": "failed", "error": "No image generated"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def generate_image_to_video(self, image_bytes: bytes, prompt: str, user: str) -> dict:
        if not self.client: return {"status": "failed", "error": "Client unavailable"}
        
        try:
            # 1. Save Input Asset (Uploaded)
            self._save_asset(image_bytes, user, "image", "uploaded", f"{user}/inputs", "png", "image/png")

            # 2. Generate Content
            operation = self.client.models.generate_videos(
                model=settings.VIDEO_MODEL_ID,
                prompt=prompt,
                image=types.Image(image_bytes=image_bytes, mime_type="image/png"),
                config=types.GenerateVideosConfig(aspect_ratio="16:9", fps=24)
            )
            
            result = operation.result() if hasattr(operation, 'result') else operation

            if hasattr(result, 'generated_videos'):
                video_bytes = result.generated_videos[0].video.video_bytes
                return self._process_media(
                    video_bytes, f"{user}/vi", "mp4", "video/mp4", user, "video"
                )
            
            return {"status": "failed", "error": "No video generated"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
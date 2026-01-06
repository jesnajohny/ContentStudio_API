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
                api_key=os.environ.get("GOOGLE_CLOUD_API_KEY"),
            )

            self.storage = StorageService()
            self.supabase = SupabaseService()
            print(f"✅ Vertex AI Client initialized.")
        except Exception as e:
            print(f"❌ Failed to initialize Vertex AI: {e}")
            self.client = None

    def _save_asset(self, data: bytes, user_id: str, asset_type: str, source: str, prefix: str, ext: str, mime: str, prompt: str = None, product_id: str = None) -> tuple[str, str]:
        """
        Helper to upload file to GCS, extract metadata, and save info to Supabase.
        Returns a tuple of (url, asset_id).
        """
        # 1. Upload to GCS
        try:
            url = self.storage.upload_bytes(data, prefix, ext, mime)
        except Exception as e:
            print(f"❌ Failed to upload asset to storage: {e}")
            raise e

        # 2. Extract Metadata
        metadata = {"size_bytes": len(data), "format": ext, "mime": mime}
        if prompt:
            metadata["prompt"] = prompt
        # Add product_id to metadata if provided
        if product_id:
            metadata["product_id"] = product_id

        if asset_type == "image":
            try:
                with Image.open(io.BytesIO(data)) as img:
                    metadata["width"] = img.width
                    metadata["height"] = img.height
            except Exception as e:
                print(f"⚠️ Failed to extract image metadata: {e}")
        print(metadata)
        
        # 3. Insert into Supabase
        result = self.supabase.insert_asset(
            user_id=user_id,
            asset_type=asset_type,
            source=source,
            storage_path=url,
            metadata=metadata
        )
        
        # Extract asset_id from the result
        asset_id = None
        if result and isinstance(result, list) and len(result) > 0:
            asset_id = result[0].get('asset_id')
        
        return url, asset_id

    def _process_media(self, data: bytes, prefix: str, ext: str, mime: str, user: str, asset_type: str, prompt: str, product_id: str = None) -> dict:
        try:
            # Save the GENERATED asset to GCS and Supabase
            # Pass product_id to be stored in metadata
            url, _ = self._save_asset(data, user, asset_type, "generated", prefix, ext, mime, prompt, product_id=product_id)           
            
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
                        # Added explicit prompt argument which was missing in original code
                        return self._process_media(
                            part.inline_data.data, f"{user}/t2i", "png", "image/png", user, "image", prompt
                        )
            return {"status": "failed", "error": "No image generated"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def generate_image_to_image(self, image_bytes: bytes, prompt: str, user: str, image_url: str = None, product_id: str = None) -> dict:
        if not self.client: return {"status": "failed", "error": "Client unavailable"}

        # Determine which ID to associate with the output
        current_product_id = product_id

        try:
            # 1. Save Input Asset (Uploaded)
            if not image_url:
                # Capture the asset_id of the uploaded input
                _, asset_id = self._save_asset(image_bytes, user, "image", "uploaded", f"{user}/inputs", "png", "image/png")
                # If no product_id was provided in request, use the uploaded asset's ID
                if not current_product_id:
                    current_product_id = asset_id
            else:
                print(f"⬇️ Fetching input image from: {image_url}")
                fetched_bytes = self.storage.download_image_as_bytes(image_url)
                if fetched_bytes:
                    image_bytes = fetched_bytes
                else:
                    return {"status": "failed", "error": "Failed to download image from provided URL"}

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
                        # Pass current_product_id to be saved in generated image metadata
                        return self._process_media(
                            part.inline_data.data, f"{user}/i2i", "png", "image/png", user, "image", prompt, product_id=current_product_id
                        )
            return {"status": "failed", "error": "No image generated"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
        
    def generate_image_variations(self, prompt: str, user: str, image_url: str, product_id: str) -> dict:
        if not self.client: return {"status": "failed", "error": "Client unavailable"}

        # Determine which ID to associate with the output
        current_product_id = product_id

        try:

            print(f"⬇️ Fetching input image from: {image_url}")
            fetched_bytes = self.storage.download_image_as_bytes(image_url)
            if fetched_bytes:
                image_bytes = fetched_bytes
            else:
                return {"status": "failed", "error": "Failed to download image from provided URL"}

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
                        # Pass current_product_id to be saved in generated image metadata
                        return self._process_media(
                            part.inline_data.data, f"{user}/i2i", "png", "image/png", user, "image", prompt, product_id=current_product_id
                        )
            return {"status": "failed", "error": "No image generated"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def generate_image_to_video(self, image_bytes: bytes, prompt: str, user: str, image_url: str = None, product_id: str = None) -> dict:
        if not self.client: return {"status": "failed", "error": "Client unavailable"}
        
        # Determine which ID to associate with the output
        current_product_id = product_id
        
        try:
            # 1. Save Input Asset (Uploaded)
            if not image_url:
                # Capture the asset_id of the uploaded input
                _, asset_id = self._save_asset(image_bytes, user, "image", "uploaded", f"{user}/inputs", "png", "image/png")
                
                # If no product_id was provided in request, use the uploaded asset's ID
                if not current_product_id:
                    current_product_id = asset_id
            else:
                print(f"⬇️ Fetching input image from: {image_url}")
                fetched_bytes = self.storage.download_image_as_bytes(image_url)
                if fetched_bytes:
                    image_bytes = fetched_bytes
                else:
                    return {"status": "failed", "error": "Failed to download image from provided URL"}

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
                # Pass current_product_id to be saved in generated video metadata
                return self._process_media(
                    video_bytes, f"{user}/vi", "mp4", "video/mp4", user, "video", prompt, product_id=current_product_id
                )
            
            return {"status": "failed", "error": "No video generated"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
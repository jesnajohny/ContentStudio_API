import os
from google import genai
from google.genai import types
from app.core.config import get_settings
from app.services.storage_service import StorageService

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
            print(f"✅ Vertex AI Client initialized.")
        except Exception as e:
            print(f"❌ Failed to initialize Vertex AI: {e}")
            self.client = None

    def _process_media(self, data: bytes, prefix: str, ext: str, mime: str) -> dict:
        try:
            url = self.storage.upload_bytes(data, prefix, ext, mime)
            return {"status": "completed", "url": url}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def generate_text_to_image(self, prompt: str, aspect_ratio: str) -> dict:
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
                        return self._process_media(
                            part.inline_data.data, "t2i", "png", "image/png"
                        )
            return {"status": "failed", "error": "No image generated"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def generate_image_to_image(self, image_bytes: bytes, prompt: str) -> dict:
        if not self.client: return {"status": "failed", "error": "Client unavailable"}

        try:
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
                            part.inline_data.data, "i2i", "png", "image/png"
                        )
            return {"status": "failed", "error": "No image generated"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def generate_image_to_video(self, image_bytes: bytes, prompt: str) -> dict:
        if not self.client: return {"status": "failed", "error": "Client unavailable"}
        
        try:
            operation = self.client.models.generate_videos(
                model=settings.VIDEO_MODEL_ID,
                prompt=prompt,
                image=types.Image(image_bytes=image_bytes, mime_type="image/png"),
                config=types.GenerateVideosConfig(aspect_ratio="16:9", fps=24)
            )
            
            # Handle polling/result
            result = operation.result() if hasattr(operation, 'result') else operation

            if hasattr(result, 'generated_videos'):
                video_bytes = result.generated_videos[0].video.video_bytes
                return self._process_media(video_bytes, "veo", "mp4", "video/mp4")
            
            return {"status": "failed", "error": "No video generated"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
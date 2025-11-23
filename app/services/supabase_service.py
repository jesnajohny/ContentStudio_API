from datetime import datetime, timezone
from supabase import create_client, Client
from app.core.config import get_settings

settings = get_settings()

class SupabaseService:
    def __init__(self):
        try:
            self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            print("✅ Supabase Client initialized.")
        except Exception as e:
            print(f"❌ Failed to initialize Supabase: {e}")
            self.client = None

    def upsert_template(self, template_name: str, category: str, product_type: str, image_url: str, prompt: str):
        """
        Upserts data into the 'template' table.
        """
        if not self.client:
            return {"error": "Supabase client not available"}

        data = {
            "template_name": template_name,
            "category": category,
            "product_type": product_type,
            "image_url": image_url,
            "prompt": prompt,
            "updated_date": datetime.now(timezone.utc).isoformat()
        }

        print(f'update data : {data}')

        try:
            # .upsert() will insert or update based on the primary key (likely template_name or an id)
            response = self.client.table("templates").upsert(data, on_conflict="template_name, category, product_type").execute()
            return response.data
        except Exception as e:
            print(f"❌ Supabase Upsert Error: {e}")
            return {"error": str(e)}
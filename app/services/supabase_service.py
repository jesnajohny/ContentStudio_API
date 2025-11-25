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

        try:
            # .upsert() will insert or update based on the primary key (likely template_name or an id)
            response = self.client.table("templates").upsert(data, on_conflict="template_name, category, product_type").execute()
            return response.data
        except Exception as e:
            print(f"❌ Supabase Upsert Error: {e}")
            return {"error": str(e)}

    def get_template_filters(self):
        """
        Fetches data from 'templates' and returns a dictionary mapping 
        categories to a list of their associated product types.
        """
        if not self.client:
            return {"error": "Supabase client not available"}

        try:
            # Fetch both columns
            response = self.client.table("templates").select("category, product_type").execute()
            data = response.data
            
            # Dictionary to hold distinct sets of product types for each category
            category_map = {}

            for item in data:
                cat = item.get("category")
                prod = item.get("product_type")

                # Ensure both fields exist before processing
                if cat and prod:
                    if cat not in category_map:
                        category_map[cat] = set()
                    category_map[cat].add(prod)
            
            # Convert sets to sorted lists for the final JSON response
            result = {cat: sorted(list(prods)) for cat, prods in category_map.items()}
            
            return result

        except Exception as e:
            print(f"❌ Supabase Fetch Error: {e}")
            return {"error": str(e)}

    def get_templates(self, category: str, product_type: str):
        """
        Fetches templates filtering by category and product_type.
        """
        if not self.client:
            return {"error": "Supabase client not available"}
        
        try:
            # Query: Select * from templates where category = X and product_type = Y
            response = self.client.table("templates")\
                .select("*")\
                .eq("category", category)\
                .eq("product_type", product_type)\
                .execute()
            
            return response.data
        except Exception as e:
            print(f"❌ Supabase Fetch Error: {e}")
            return {"error": str(e)}
        
    def insert_asset(self, user_id: str, asset_type: str, source: str, storage_path: str, metadata: dict = None):
        """
        Inserts a record into the 'assets' table.
        """
        if not self.client:
            print("❌ Supabase client not available for asset insertion")
            return None

        data = {
            "user_id": user_id,
            "type": asset_type,
            "source": source,
            "storage_path": storage_path,
            "metadata": metadata or {}
        }

        try:
            response = self.client.table("assets").insert(data).execute()
            print(f"✅ Asset inserted: {source} {asset_type}")
            return response.data
        except Exception as e:
            print(f"❌ Supabase Insert Asset Error: {e}")
            return {"error": str(e)}

    def get_user_assets(self, user_id: str):
        """
        Fetches assets for a specific user from the 'assets' table.
        """
        if not self.client:
            return {"error": "Supabase client not available"}

        try:
            # Select all columns for the given user_id
            # You might want to add .order("created_at", desc=True) if that column exists
            response = self.client.table("assets").select("*").eq("user_id", user_id).execute()
            return response.data
        except Exception as e:
            print(f"❌ Supabase Fetch Assets Error: {e}")
            return {"error": str(e)}    
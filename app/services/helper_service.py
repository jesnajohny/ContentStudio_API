from typing import List
from fastapi import UploadFile
from app.services.storage_service import StorageService
from app.services.supabase_service import SupabaseService

class HelperService:
    def __init__(self):
        # Initialize dependencies internally to keep the route clean
        self.storage = StorageService()
        self.supabase = SupabaseService()

    async def process_uploads(self, files: List[UploadFile], user: str, product_id: str = None) -> List[str]:
        """
        Uploads files to GCS, records them in Supabase, and returns a list of their GCS URLs.
        """
        urls = []
        if not files:
            return urls
            
        for file in files:
            try:
                # Read file content
                file_bytes = await file.read()
                
                # Determine extension and mime type
                ext = file.filename.split(".")[-1] if "." in file.filename else "png"
                mime = file.content_type or "image/png"
                
                # GCS path structure: {user}/inputs/{uuid}.{ext}
                gcs_prefix = f"{user}/inputs"
                
                # 1. Upload to GCS
                url = self.storage.upload_bytes(file_bytes, gcs_prefix, ext, mime)
                
                # 2. Add to result list
                urls.append(url)
                
                # 3. Insert into Supabase Assets
                metadata = {"size_bytes": len(file_bytes), "format": ext, "mime": mime}
                self.supabase.insert_asset(
                    user_id=user,
                    asset_type="image",
                    source="uploaded",
                    storage_path=url,
                    metadata=metadata,
                    product_id = product_id
                )
            except Exception as e:
                print(f"❌ Error processing upload {file.filename}: {e}")
                # Continue processing other files even if one fails
                continue
        
        return urls
    
    def insert_product_details(self, product_name: str, category: str, product_type: str, product_hash: str) -> str:
        """
        Inserts product details into the database and returns the new product_id.
        """
        return self.supabase.insert_product(product_name, category, product_type, product_hash)
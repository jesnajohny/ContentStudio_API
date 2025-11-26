from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from app.services.vertex_service import VertexGenerator
from app.services.supabase_service import SupabaseService
from app.services.storage_service import StorageService
from functools import lru_cache
from urllib.parse import urlparse
from typing import Optional

router = APIRouter()

# Dependency to get the generator instance
@lru_cache()
def get_generator():
    return VertexGenerator()

# Dependency to get the supabase service instance
@lru_cache()
def get_supabase_service():
    return SupabaseService()

# Dependency to get the storage service instance
@lru_cache()
def get_storage_service():
    return StorageService()

# --- Existing Routes (Text/Image Generation) ---
@router.post("/text-to-image")
async def text_to_image(
    prompt: str = Form(...), 
    user: str = Form(...),
    aspect_ratio: str = Form("1:1"),
    service: VertexGenerator = Depends(get_generator)
):
    result = service.generate_text_to_image(prompt, aspect_ratio, user)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@router.post("/image-to-image")
async def image_to_image(
    prompt: str = Form(...), 
    user: str = Form(...),
    image_url: Optional[str] = Form(None),
    product_id: Optional[str] = Form(None), # Added optional product_id
    file: Optional[UploadFile] = File(None),
    service: VertexGenerator = Depends(get_generator)
):
    if file:
        file_bytes = await file.read()
    else:
        file_bytes = None
    # Pass product_id to the service
    result = service.generate_image_to_image(file_bytes, prompt, user, image_url, product_id=product_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@router.post("/image-to-video")
async def image_to_video(
    prompt: str = Form(...), 
    user: str = Form(...),
    image_url: Optional[str] = Form(None),
    product_id: Optional[str] = Form(None), # Added optional product_id
    file: UploadFile = File(...),
    service: VertexGenerator = Depends(get_generator)
):
    if file:
        file_bytes = await file.read()
    else:
        file_bytes = None
    # Pass product_id to the service
    result = service.generate_image_to_video(file_bytes, prompt, user, image_url, product_id=product_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

# --- Modified Supabase Route ---
@router.post("/templates/upsert")
async def upsert_template(
    template_name: str = Form(...),
    category: str = Form(...),
    product_type: str = Form(...),
    prompt: str = Form(...),
    file: UploadFile = File(...),  # Changed to accept file upload
    supabase: SupabaseService = Depends(get_supabase_service),
    service: VertexGenerator = Depends(get_generator),
    storage: StorageService = Depends(get_storage_service)
):
    # 1. Read the file content
    file_bytes = await file.read()
    
    # 2. Determine file extension and content type
    # Default to 'png' if extension is missing
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    content_type = file.content_type or "image/png"

    # 3. Upload to GCS
    # The storage service appends _{uuid}.{ext} to the prefix.
    # We set prefix to 'templates/{category}/img' to ensure it goes into the correct folder.
    # Example result: templates/shoes/img_a1b2c3d4.png
    gcs_prefix = f"templates/{category}/img"
    
    try:
        # Uses StorageService.upload_bytes defined in storage_service.py
        image_url = storage.upload_bytes(file_bytes, gcs_prefix, ext, content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload image to GCS: {str(e)}")

    # 4. Upsert to Supabase with the new GCS URL
    result = supabase.upsert_template(
        template_name=template_name,
        category=category,
        product_type=product_type,
        image_url=image_url,
        prompt=prompt
    )
    
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return {"status": "success", "data": result}

@router.get("/templates/filters")
def get_template_filters(
    supabase: SupabaseService = Depends(get_supabase_service)
):
    # This now returns the dictionary structure: {"Category": ["Product1", "Product2"]}
    result = supabase.get_template_filters()
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result

@router.get("/templates/list")
async def list_templates(
    category: str,
    product_type: str,
    supabase: SupabaseService = Depends(get_supabase_service),
    service: VertexGenerator = Depends(get_generator),
    storage: StorageService = Depends(get_storage_service)
):
    # 1. Fetch metadata from Supabase
    templates = supabase.get_templates(category, product_type)
    
    if isinstance(templates, dict) and "error" in templates:
         raise HTTPException(status_code=500, detail=templates["error"])

    # 2. Process each template to fetch and encode the image
    results = []
    for template in templates:
        
        # # Copy template to avoid mutating the original if cached somewhere (good practice)
        temp_data = template.copy()
        
        image_url = temp_data.get("image_url")
        parsed = urlparse(image_url)
        temp_data["image_url"] = storage.generate_signed_url(parsed.path.lstrip("/").split("/", 1)[1])        
        results.append(temp_data)
        
    return results

@router.get("/assets")
async def get_user_assets(
    user_id: str,
    supabase: SupabaseService = Depends(get_supabase_service),
    service: VertexGenerator = Depends(get_generator),
    storage: StorageService = Depends(get_storage_service)
):
    # 1. Fetch assets from Supabase
    assets = supabase.get_user_assets(user_id)
    
    if isinstance(assets, dict) and "error" in assets:
        raise HTTPException(status_code=500, detail=assets["error"])
    
    # 2. Process assets to generate signed URLs (Access control)
    results = []
    for asset in assets:
        asset_data = asset.copy()
        storage_path = asset_data.get("storage_path")
        
        # specific logic to handle GCS URLs
        if storage_path and "storage.googleapis.com" in storage_path:
            try:
                parsed = urlparse(storage_path)
                # URL format: https://storage.googleapis.com/{bucket_name}/{blob_name}
                # We need to extract {blob_name}
                path_parts = parsed.path.lstrip("/").split("/", 1)
                if len(path_parts) > 1:
                    blob_name = path_parts[1]
                    asset_data["signed_url"] = storage.generate_signed_url(blob_name)
            except Exception as e:
                print(f"⚠️ Failed to generate signed URL for asset {asset.get('id', 'unknown')}: {e}")
        
        results.append(asset_data)
        
    return results
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from app.services.vertex_service import VertexGenerator
from app.services.supabase_service import SupabaseService
from app.services.storage_service import StorageService
from app.services.pubsub_service import PubSubService
from app.services.helper_service import HelperService
from functools import lru_cache
from urllib.parse import urlparse
from typing import Optional, List
import random

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

@lru_cache()
def get_pubsub_service():
    return PubSubService()

@lru_cache()
def get_helper_service():
    return HelperService()

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

@router.post("/image-variations")
async def image_to_image(
    prompt: str = Form(...), 
    user: str = Form(...),
    image_url: Optional[str] = Form(None),
    product_id: Optional[str] = Form(None), # Added optional product_id
    service: VertexGenerator = Depends(get_generator)
):

    result = service.generate_image_variations(prompt, user, image_url, product_id)
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

@router.post("/generate")
async def generate(
    prompt: str = Form(...),
    user: str = Form(...),
    category: str = Form(...),
    product_type: str = Form(...),
    generation_type: str = Form(...),
    product_name: Optional[str] = Form(None),
    product_images: Optional[List[UploadFile]] = File(None),
    reference_images: Optional[List[UploadFile]] = File(None),
    product_urls: Optional[List[str]] = Form(None),
    referance_urls: Optional[List[str]] = Form(None),
    supabase: SupabaseService = Depends(get_supabase_service),
    pubsub: PubSubService = Depends(get_pubsub_service),
    helper: HelperService = Depends(get_helper_service)
):
    """
    Endpoint to handle generation requests.
    - Uploads files to GCS via HelperService.
    - Saves asset metadata to Supabase via HelperService.
    - Aggregates all URLs.
    - Publishes job to Pub/Sub.
    """

    print(f"inserting product name : {product_name}")
    product_id = ""
    if not product_name:        
        product_name = f"{category}_{product_type}_{random.randint(10000, 99999)}"
        print(f"inserting product name : {product_name}")
    if product_images:
        print(f"inserting product")
        product_id = supabase.insert_product(product_name, category, product_type)
        print(f"product id : {product_id}")
    
    # 1. Process Uploaded Files
    uploaded_product_urls =  await helper.process_uploads(product_images, user, product_id) if product_images else product_urls
    uploaded_reference_urls = await helper.process_uploads(reference_images, user) if  reference_images  else referance_urls if referance_urls else []

    print(f"uploaded_product_urls : {uploaded_product_urls}")
    print(f"uploaded_reference_urls : {uploaded_reference_urls}")
    
    # 2. Combine with provided URLs (handle None types)
    final_product_urls =  uploaded_product_urls
    final_reference_urls =  uploaded_reference_urls
    
    # 3. Construct Pub/Sub Payload
    payload = {
        "product_urls": final_product_urls,
        "reference_urls": final_reference_urls, 
        "prompt": prompt,
        "user": user,
        "generation_type": generation_type
    }
    
    # 4. Publish to Pub/Sub
    try:
        message_id = pubsub.publish_message(payload)
        
        if not message_id:
             raise HTTPException(status_code=500, detail="Failed to publish to Pub/Sub (Client unavailable)")
             
        return {
            "status": "queued",
            "message_id": message_id,
            "data": payload
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pub/Sub Error: {str(e)}")
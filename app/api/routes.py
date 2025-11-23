from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from app.services.vertex_service import VertexGenerator
from app.services.supabase_service import SupabaseService
from app.services.storage_service import StorageService
from functools import lru_cache

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
    file: UploadFile = File(...),
    service: VertexGenerator = Depends(get_generator)
):
    file_bytes = await file.read()
    result = service.generate_image_to_image(file_bytes, prompt, user)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@router.post("/image-to-video")
async def image_to_video(
    prompt: str = Form(...), 
    user: str = Form(...),
    file: UploadFile = File(...),
    service: VertexGenerator = Depends(get_generator)
):
    file_bytes = await file.read()
    result = service.generate_image_to_video(file_bytes, prompt, user)
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
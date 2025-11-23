from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from app.services.vertex_service import VertexGenerator

router = APIRouter()

# Dependency to get the generator instance
def get_generator():
    return VertexGenerator()

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
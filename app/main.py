from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.routes import router as gen_router

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME, 
    version=settings.VERSION,
    description="Production ready API for Gemini 2.5 & Veo"
)

# CORS Middleware (Essential for frontend integration)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routes
app.include_router(gen_router, prefix="/generate", tags=["Generation"])

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.GOOGLE_CLOUD_PROJECT}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
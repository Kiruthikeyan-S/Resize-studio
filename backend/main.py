"""Ratio Studio - Backend Main FastAPI Application."""

import os
from contextlib import asynccontextmanager

try:
    import dotenv
    this_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv.load_dotenv(os.path.join(this_dir, ".env"))
    dotenv.load_dotenv()
except Exception:
    pass
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.upload import router as upload_router
from routes.convert import router as convert_router
from routes.download import router as download_router
from services.image_processor import cleanup_old_sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: clean up any stale sessions
    try:
        cleanup_old_sessions(max_age_seconds=3600)
    except Exception:
        pass
    yield
    # Shutdown


app = FastAPI(
    title="Ratio Studio API",
    description="Professional Image Aspect Ratio Conversion Platform with Non-AI Processing",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://resizeap.web.app",
        "https://resizeap.firebaseapp.com",
        "https://resize-studio.onrender.com",
    ],
    allow_origin_regex=r"https://.*\.web\.app|https://.*\.firebaseapp\.com|https://.*\.onrender\.com|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Register routes
app.include_router(upload_router)
app.include_router(convert_router)
app.include_router(download_router)


@app.get("/")
async def root():
    return {
        "app": "Ratio Studio",
        "status": "online",
        "version": "1.0.0",
        "endpoints": [
            "/api/upload",
            "/api/convert",
            "/api/replace/{ratio}",
            "/api/adjust-crop",
            "/api/download/{image_id}/{ratio}",
            "/api/download-all/{image_id}",
            "/api/preview/{image_id}/{ratio}",
            "/api/original/{image_id}",
        ]
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

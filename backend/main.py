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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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
        "http://localhost:8000",
        "http://127.0.0.1:8000",
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

# Register API routes
app.include_router(upload_router)
app.include_router(convert_router)
app.include_router(download_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Mount frontend static distribution for unified single-port hosting
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    index_html = os.path.join(frontend_dist, "index.html")

    @app.get("/")
    async def serve_index():
        return FileResponse(index_html)

    @app.get("/{full_path:path}")
    async def serve_spa_or_static(full_path: str):
        # Exclude backend API and docs endpoints
        if full_path.startswith("api/") or full_path == "api" or full_path in ["docs", "redoc", "openapi.json"]:
            raise HTTPException(status_code=404, detail="Not Found")

        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # SPA client-side routing fallback
        return FileResponse(index_html)
else:
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

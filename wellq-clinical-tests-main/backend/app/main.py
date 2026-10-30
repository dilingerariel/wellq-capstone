from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.routes import clinical_tests, extractions, scoring
from app.database import connect_to_mongo, close_mongo_connection

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="API para carga y gestión de exámenes médicos",
    version="1.0.0",
)

@app.on_event("startup")
def startup_db_client():
    connect_to_mongo()

@app.on_event("shutdown")
def shutdown_db_client():
    close_mongo_connection()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restringir en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas
app.include_router(
    clinical_tests.router,
    prefix="/api/v1",
    tags=["clinical-tests"],
)

app.include_router(
    extractions.router,
    prefix="/api/v1",
    tags=["extractions"],
)

app.include_router(
    scoring.router,
    prefix="/api/v1",
    tags=["scoring"],
)

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}

# Dashboard Frontend UI
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/dashboard", StaticFiles(directory=static_dir, html=True), name="dashboard")

exports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "exports"))
if os.path.exists(exports_dir):
    app.mount("/exports", StaticFiles(directory=exports_dir), name="exports")

@app.get("/demo")
async def demo():
    return RedirectResponse(url="/dashboard/")

# Root
@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "dashboard": "/dashboard/"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
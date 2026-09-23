from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.routes import clinical_tests
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

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}

# Root
@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
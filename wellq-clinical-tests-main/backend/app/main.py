from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError, DuplicateKeyError
from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection, mongodb
from app.dependencies.auth import current_identity
from app.routes import clinical_tests, extractions, scoring, demo, auth
from contextlib import asynccontextmanager
from app.models.errors import ErrorResponse

@asynccontextmanager
async def lifespan(app):
    if settings.DEMO_AUTH_ENABLED and settings.ENVIRONMENT != "production":
        demo.prepare_demo_identity()
    settings.validate_clinical_services()
    connect_to_mongo()
    try:
        yield
    finally:
        close_mongo_connection()

app = FastAPI(title=settings.APP_NAME, version="1.1.0",
              description="Clinical API. External trusted identity and tenant schema required.", lifespan=lifespan,
              responses={code: {"model": ErrorResponse, "description": description,
                  "headers": ({"WWW-Authenticate": {"schema": {"type": "string"}}} if code == 401 else
                              {"Retry-After": {"schema": {"type": "string"}}} if code in (429, 503) else {})}
                  for code, description in {
                  401: "Authentication required (WWW-Authenticate: Bearer)",
                  403: "Role, relationship, permission or capability denied",
                  404: "Resource or publishable score unavailable",
                  409: "State, idempotency, source or retryable write conflict",
                  422: "Invalid request; detail is an object with code and optional errors",
                  429: "Rate limit (Retry-After where applicable)",
                  503: "Dependency unavailable (Retry-After for database failures)",
              }.items()})
cors_origins = settings.CORS_ORIGINS
if not cors_origins and settings.ENVIRONMENT != "production":
    cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5178", "http://127.0.0.1:5178"]
app.add_middleware(CORSMiddleware, allow_origins=cors_origins,
                   allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-WellQ-Local",
                                  "X-WellQ-Upload-Token", "X-WellQ-If-Absent"])

@app.middleware("http")
async def identity_scope(request: Request, call_next):
    token = current_identity.set(None)
    try:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    finally:
        current_identity.reset(token)

@app.exception_handler(PyMongoError)
async def database_error(request, exc):
    conflict = isinstance(exc, DuplicateKeyError) or exc.has_error_label("TransientTransactionError")
    return JSONResponse(status_code=409 if conflict else 503,
        content={"detail": {"code": "RETRYABLE_CONFLICT", "message": "Retry with the same idempotency key"}},
        headers={"Retry-After": "2"})

for router in (clinical_tests.router, extractions.router, scoring.router, demo.router, auth.router):
    app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/ready")
async def ready():
    try:
        settings.validate_identity()
        settings.validate_clinical_services()
        if mongodb.client is None:
            raise RuntimeError()
        mongodb.client.admin.command("ping")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready"}

@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "version": "1.1.0", "status": "running"}

from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def input_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": {"code": "INVALID_INPUT", "message": "Invalid request",
        "errors": [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]}})

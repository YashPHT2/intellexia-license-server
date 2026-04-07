"""
Intellexia License Server – FastAPI entry point.

Startup: creates DB tables (use Alembic migrations in production).
Routes:
  /                          – health check
  /api/v1/activate           – client activation
  /api/v1/deactivate         – client deactivation
  /api/v1/validate           – client validation
  /admin/licenses            – admin CRUD
  /admin/licenses/{id}/...   – revoke, reissue, activations, audit
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import engine, Base
from app.activation import router as activation_router
from app.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables on startup (safe: create_all is idempotent)
    Base.metadata.create_all(bind=engine)
    yield


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# CORS – wide open for now; tighten for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(activation_router)
app.include_router(admin_router)


@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": "1.0.0",
    }

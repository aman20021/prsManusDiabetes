from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from app.api import auth, models, monitoring, predict, predictions, uploads
from app.config import get_settings
from app.db.base import Base
from app.db.seed import seed_model_versions, seed_roles_and_users
from app.db.session import get_engine, init_engine
from app.exceptions import AppError, app_error_handler, validation_exception_handler
from app.services.registry import bootstrap_artifacts, registry
from app.services.validation import ValidationException

app = FastAPI(
    title="MANAS Diabetes Inference API",
    version="1.0.0",
    description="Production-style inference service for diabetes health indicators.",
)

settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ValidationException, validation_exception_handler)
app.add_exception_handler(AppError, app_error_handler)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(predict.router, prefix="/api/v1")
app.include_router(uploads.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(monitoring.router, prefix="/api/v1")


@app.on_event("startup")
def on_startup() -> None:
    testing = os.getenv("TESTING") == "1"
    init_engine(testing=testing)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    bootstrap_artifacts()
    from app.db.session import get_session_factory

    db = get_session_factory()()
    try:
        seed_roles_and_users(db)
        seed_model_versions(db)
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def root():
    return """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>MANAS API</title></head>
<body>
  <h1>MANAS Diabetes Inference API</h1>
  <p>This port serves the API only. Open the web app at
    <a href="http://localhost:8080">http://localhost:8080</a>.</p>
  <ul>
    <li><a href="/docs">API docs</a></li>
    <li><a href="/health">Health</a></li>
    <li><a href="/ready">Readiness</a></li>
  </ul>
</body>
</html>
"""


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    from app.db.session import get_session_factory
    from app.db.seed import get_active_model_version

    db = get_session_factory()()
    try:
        active = get_active_model_version(db)
        if not active:
            raise AppError(503, "NOT_READY", "No production model", [])
        registry.get_scaler()
        registry.get_adapter(active.version)
    except AppError:
        raise
    except Exception as e:
        raise AppError(503, "NOT_READY", "Service not ready", [{"message": str(e)}]) from e
    finally:
        db.close()
    return {"status": "ready", "active_model": active.version}

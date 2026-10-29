from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import DbDep, get_current_user, require_role
from app.db.models import ModelVersion, PromotionEvent, User
from app.db.seed import get_active_model_version
from app.exceptions import AppError

router = APIRouter(prefix="/models", tags=["models"])


class PromoteRequest(BaseModel):
    reason: str = Field(min_length=3)


class RollbackRequest(BaseModel):
    reason: str = Field(min_length=3)


class RegisterRequest(BaseModel):
    version: str
    framework: str
    artifact_path: str
    artifact_sha256: str
    offline_metrics: dict | None = None


def _model_dict(mv: ModelVersion) -> dict:
    return {
        "version": mv.version,
        "framework": mv.framework,
        "artifact_sha256": mv.artifact_sha256,
        "status": mv.status,
        "preprocessing_version": mv.preprocessing_version,
        "offline_metrics": mv.offline_metrics,
        "created_at": mv.created_at.isoformat() if mv.created_at else None,
    }


@router.get("")
def list_models(db: DbDep, user: Annotated[User, Depends(get_current_user)]):
    models = db.query(ModelVersion).order_by(ModelVersion.created_at).all()
    return {"models": [_model_dict(m) for m in models]}


@router.get("/active")
def active_model(db: DbDep, user: Annotated[User, Depends(get_current_user)]):
    active = get_active_model_version(db)
    if not active:
        raise AppError(503, "MODEL_UNAVAILABLE", "No production model configured", [])
    return _model_dict(active)


@router.post("/{version}/promote")
def promote_model(
    version: str,
    body: PromoteRequest,
    db: DbDep,
    user: Annotated[User, Depends(require_role("mlops"))],
):
    candidate = db.query(ModelVersion).filter_by(version=version).first()
    if not candidate:
        raise AppError(404, "MODEL_NOT_FOUND", f"Version {version} not found", [])
    if candidate.status == "production":
        return _model_dict(candidate)

    metrics = candidate.offline_metrics or {}
    if not metrics.get("eval_completed"):
        raise AppError(
            422,
            "EVAL_REQUIRED",
            "Candidate must complete offline evaluation before promotion",
            [{"message": "Set offline_metrics.eval_completed via evaluate_candidate.py"}],
        )

    current = get_active_model_version(db)
    from_version = current.version if current else None
    if current:
        current.status = "retired"
    candidate.status = "production"
    db.add(
        PromotionEvent(
            action="promote",
            from_version=from_version,
            to_version=version,
            actor_user_id=user.id,
            reason=body.reason,
        )
    )
    db.commit()
    db.refresh(candidate)
    return _model_dict(candidate)


@router.post("/rollback")
def rollback_model(
    body: RollbackRequest,
    db: DbDep,
    user: Annotated[User, Depends(require_role("mlops"))],
):
    current = get_active_model_version(db)
    if not current:
        raise AppError(503, "MODEL_UNAVAILABLE", "No production model to rollback", [])

    last = (
        db.query(PromotionEvent)
        .filter_by(action="promote")
        .order_by(PromotionEvent.created_at.desc())
        .first()
    )
    if not last or not last.from_version:
        raise AppError(422, "ROLLBACK_UNAVAILABLE", "No previous production version in history", [])

    previous = db.query(ModelVersion).filter_by(version=last.from_version).first()
    if not previous:
        raise AppError(404, "MODEL_NOT_FOUND", f"Previous version {last.from_version} not found", [])

    from_version = current.version
    current.status = "retired"
    previous.status = "production"
    db.add(
        PromotionEvent(
            action="rollback",
            from_version=from_version,
            to_version=previous.version,
            actor_user_id=user.id,
            reason=body.reason,
        )
    )
    db.commit()
    db.refresh(previous)
    return _model_dict(previous)


@router.post("/register")
def register_model(
    body: RegisterRequest,
    db: DbDep,
    user: Annotated[User, Depends(require_role("mlops"))],
):
    if db.query(ModelVersion).filter_by(version=body.version).first():
        raise AppError(409, "CONFLICT", f"Version {body.version} already exists", [])
    from app.config import get_settings

    settings = get_settings()
    mv = ModelVersion(
        version=body.version,
        framework=body.framework,
        artifact_path=body.artifact_path,
        artifact_sha256=body.artifact_sha256,
        status="candidate",
        preprocessing_version=settings.preprocessing_version,
        offline_metrics=body.offline_metrics,
    )
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return _model_dict(mv)

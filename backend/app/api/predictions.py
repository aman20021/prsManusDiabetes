from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbDep, get_current_user
from app.db.models import InferenceLog, User

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("")
def list_predictions(
    db: DbDep,
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=50, le=200),
):
    q = db.query(InferenceLog).filter_by(success=True).order_by(InferenceLog.created_at.desc())
    if user.role.name == "clinician":
        q = q.filter(InferenceLog.user_id == user.id)
    logs = q.limit(limit).all()
    return {
        "predictions": [
            {
                "request_id": log.request_id,
                "upload_id": log.upload_id,
                "row_index": log.row_index,
                "model_version": log.model_version,
                "label": log.prediction,
                "probability_positive": log.probability_positive,
                "confidence": log.confidence,
                "latency_ms": log.latency_ms,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    }

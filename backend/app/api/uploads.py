from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbDep, get_current_user, require_role
from app.db.models import InferenceLog, Upload, User
from app.exceptions import AppError

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _upload_to_dict(u: Upload) -> dict:
    return {
        "id": u.id,
        "filename": u.filename,
        "content_sha256": u.content_sha256,
        "row_count": u.row_count,
        "upload_type": u.upload_type,
        "status": u.status,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.get("")
def list_uploads(
    db: DbDep,
    user: Annotated[User, Depends(get_current_user)],
):
    q = db.query(Upload).order_by(Upload.created_at.desc())
    if user.role.name == "clinician":
        q = q.filter(Upload.user_id == user.id)
    uploads = q.limit(100).all()
    return {"uploads": [_upload_to_dict(u) for u in uploads]}


@router.get("/{upload_id}")
def get_upload(
    upload_id: int,
    db: DbDep,
    user: Annotated[User, Depends(get_current_user)],
):
    upload = db.query(Upload).filter_by(id=upload_id).first()
    if not upload:
        raise AppError(404, "NOT_FOUND", "Upload not found", [])
    if user.role.name == "clinician" and upload.user_id != user.id:
        raise AppError(403, "FORBIDDEN", "Cannot access this upload", [])

    logs = (
        db.query(InferenceLog)
        .filter_by(upload_id=upload_id, success=True)
        .order_by(InferenceLog.row_index)
        .all()
    )
    predictions = [
        {
            "row_index": log.row_index,
            "label": log.prediction,
            "probability_positive": log.probability_positive,
            "confidence": log.confidence,
            "input_hash": log.input_hash,
            "input_echo": log.input_json,
            "model_version": log.model_version,
        }
        for log in logs
    ]
    return {**_upload_to_dict(upload), "predictions": predictions}

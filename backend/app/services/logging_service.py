from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import InferenceLog, Upload


def _log_request_id(batch_request_id: str, row_index: int | None) -> str:
    """Per-row id for inference_logs.request_id (varchar(36), unique)."""
    if row_index is None or row_index == 0:
        return batch_request_id
    return str(uuid.uuid5(uuid.UUID(batch_request_id), str(row_index)))


def create_upload(
    db: Session,
    user_id: int,
    upload_type: str,
    row_count: int,
    filename: str | None = None,
    content_sha256: str | None = None,
    status: str = "completed",
) -> Upload:
    upload = Upload(
        user_id=user_id,
        filename=filename,
        content_sha256=content_sha256,
        row_count=row_count,
        upload_type=upload_type,
        status=status,
    )
    db.add(upload)
    db.flush()
    return upload


def log_inference_success(
    db: Session,
    *,
    request_id: str,
    user_id: int | None,
    upload_id: int | None,
    model_version: str,
    preprocessing_version: str,
    artifact_sha256: str | None,
    scaler_sha256: str | None,
    upload_type: str,
    results: list[dict],
    latency_ms: float,
) -> None:
    for r in results:
        db.add(
            InferenceLog(
                request_id=_log_request_id(request_id, r.get("row_index")),
                user_id=user_id,
                upload_id=upload_id,
                model_version=model_version,
                preprocessing_version=preprocessing_version,
                artifact_sha256=artifact_sha256,
                scaler_sha256=scaler_sha256,
                upload_type=upload_type,
                row_index=r.get("row_index"),
                input_json=r.get("input_echo"),
                input_hash=r.get("input_hash"),
                prediction=r.get("label"),
                probability_positive=r.get("probability_positive"),
                confidence=r.get("confidence"),
                latency_ms=latency_ms if r.get("row_index", 0) == 0 else None,
                success=True,
            )
        )
    db.commit()


def log_inference_error(
    db: Session,
    *,
    request_id: str,
    user_id: int | None,
    upload_id: int | None,
    upload_type: str,
    error_code: str,
    error_message: str,
    model_version: str | None = None,
) -> None:
    db.add(
        InferenceLog(
            request_id=request_id,
            user_id=user_id,
            upload_id=upload_id,
            model_version=model_version,
            upload_type=upload_type,
            success=False,
            error_code=error_code,
            error_message=error_message,
        )
    )
    db.commit()


def log_validation_error(
    db: Session,
    *,
    request_id: str,
    user_id: int | None,
    upload_type: str,
    error_code: str,
    error_message: str,
) -> None:
    log_inference_error(
        db,
        request_id=request_id,
        user_id=user_id,
        upload_id=None,
        upload_type=upload_type,
        error_code=error_code,
        error_message=error_message,
    )

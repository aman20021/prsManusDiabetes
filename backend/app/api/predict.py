from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.api.deps import DbDep, get_current_user
from app.db.models import ModelVersion, User
from app.db.seed import get_active_model_version
from app.exceptions import AppError
from app.services.hashing import hash_bytes
from app.services.inference import run_inference
from app.services.logging_service import (
    create_upload,
    log_inference_error,
    log_inference_success,
    log_validation_error,
)
from app.services.registry import registry
from app.services.validation import (
    ValidationException,
    validate_batch_csv,
    validate_batch_json,
    validate_single_payload,
)

router = APIRouter(prefix="/predict", tags=["predict"])


def _resolve_model(db: DbDep, version: str | None) -> ModelVersion:
    """Pick one model and prove its weights are loaded before any prediction is stored.

    An explicit model_version must already be registered. With no version, the
    production row is used. The in-memory adapter for that same version is what
    will run, so the response cannot name a different artifact than the one scored.
    """
    if version:
        mv = db.query(ModelVersion).filter_by(version=version).first()
        if not mv:
            raise AppError(404, "MODEL_NOT_FOUND", f"Model version {version} is not registered", [])
    else:
        mv = get_active_model_version(db)
        if not mv:
            raise AppError(503, "MODEL_UNAVAILABLE", "No production model is configured", [])
    registry.ensure_ready(mv.version)
    return mv


def _persist_failure(
    db: DbDep,
    *,
    request_id: str,
    user_id: int,
    upload_type: str,
    row_count: int,
    filename: str | None,
    content_hash: str | None,
    model_version: str | None,
    error_code: str,
    error_message: str,
) -> None:
    upload = create_upload(
        db,
        user_id,
        upload_type,
        row_count,
        filename=filename,
        content_sha256=content_hash,
        status="failed",
    )
    db.commit()
    log_inference_error(
        db,
        request_id=request_id,
        user_id=user_id,
        upload_id=upload.id,
        upload_type=upload_type,
        error_code=error_code,
        error_message=error_message,
        model_version=model_version,
    )


def _run(
    db: DbDep,
    user: User,
    records: list[dict],
    upload_type: str,
    model_version: str | None,
    filename: str | None = None,
    content_hash: str | None = None,
) -> tuple[list[dict], dict, int]:
    request_id = str(uuid.uuid4())
    try:
        mv = _resolve_model(db, model_version)
    except AppError as e:
        if e.status_code != 404:
            _persist_failure(
                db,
                request_id=request_id,
                user_id=user.id,
                upload_type=upload_type,
                row_count=len(records),
                filename=filename,
                content_hash=content_hash,
                model_version=model_version,
                error_code=e.code,
                error_message=e.message,
            )
        raise

    try:
        results, meta, latency_ms = run_inference(
            records,
            mv.version,
            request_id=request_id,
            preprocessing_version=mv.preprocessing_version,
            artifact_sha256=mv.artifact_sha256,
        )
    except AppError as e:
        _persist_failure(
            db,
            request_id=request_id,
            user_id=user.id,
            upload_type=upload_type,
            row_count=len(records),
            filename=filename,
            content_hash=content_hash,
            model_version=mv.version,
            error_code=e.code,
            error_message=e.message,
        )
        raise
    except RuntimeError as e:
        _persist_failure(
            db,
            request_id=request_id,
            user_id=user.id,
            upload_type=upload_type,
            row_count=len(records),
            filename=filename,
            content_hash=content_hash,
            model_version=mv.version,
            error_code="INFERENCE_FAILED",
            error_message=str(e),
        )
        raise AppError(
            503,
            "INFERENCE_FAILED",
            "Model inference failed",
            [{"message": str(e)}],
        ) from e

    upload = create_upload(
        db,
        user.id,
        upload_type,
        len(results),
        filename=filename,
        content_sha256=content_hash,
        status="completed",
    )
    db.commit()
    log_inference_success(
        db,
        request_id=request_id,
        user_id=user.id,
        upload_id=upload.id,
        model_version=mv.version,
        preprocessing_version=mv.preprocessing_version,
        artifact_sha256=mv.artifact_sha256,
        scaler_sha256=registry.scaler_sha256,
        upload_type=upload_type,
        results=results,
        latency_ms=latency_ms,
    )
    return results, meta, upload.id


def _prediction_body(meta: dict, row: dict, upload_id: int) -> dict:
    return {
        **meta,
        "prediction": {
            "label": row["label"],
            "label_name": row["label_name"],
            "probability_positive": row["probability_positive"],
            "probability_negative": row["probability_negative"],
            "confidence": row["confidence"],
            "input_hash": row["input_hash"],
            "input_echo": row["input_echo"],
        },
        "upload_id": upload_id,
    }


@router.post("")
def predict_single(
    db: DbDep,
    user: Annotated[User, Depends(get_current_user)],
    body: dict[str, Any],
    model_version: str | None = Query(default=None),
):
    request_id = str(uuid.uuid4())
    try:
        record = validate_single_payload(body)
    except ValidationException as e:
        log_validation_error(
            db,
            request_id=request_id,
            user_id=user.id,
            upload_type="single",
            error_code=e.code,
            error_message=e.message,
        )
        raise

    results, meta, upload_id = _run(db, user, [record], "single", model_version)
    return _prediction_body(meta, results[0], upload_id)


@router.post("/csv")
async def predict_single_csv(
    db: DbDep,
    user: Annotated[User, Depends(get_current_user)],
    model_version: str | None = Query(default=None),
    file: UploadFile = File(...),
):
    """One CSV row. Same response as JSON single prediction, scored by the same resolved model."""
    request_id = str(uuid.uuid4())
    try:
        raw = await file.read()
        records = validate_batch_csv(raw)
        if len(records) != 1:
            raise ValidationException(
                "VALIDATION_ERROR",
                "Single CSV must contain exactly one data row",
                [{"message": f"row count {len(records)}"}],
            )
    except ValidationException as e:
        log_validation_error(
            db,
            request_id=request_id,
            user_id=user.id,
            upload_type="single",
            error_code=e.code,
            error_message=e.message,
        )
        raise

    results, meta, upload_id = _run(
        db,
        user,
        records,
        "single",
        model_version,
        filename=file.filename,
        content_hash=hash_bytes(raw),
    )
    return _prediction_body(meta, results[0], upload_id)


@router.post("/batch")
async def predict_batch(
    db: DbDep,
    user: Annotated[User, Depends(get_current_user)],
    model_version: str | None = Query(default=None),
    file: UploadFile = File(...),
):
    request_id = str(uuid.uuid4())
    filename: str | None = None
    content_hash: str | None = None

    try:
        raw = await file.read()
        content_hash = hash_bytes(raw)
        filename = file.filename
        records = validate_batch_csv(raw)
    except ValidationException as e:
        log_validation_error(
            db,
            request_id=request_id,
            user_id=user.id,
            upload_type="batch",
            error_code=e.code,
            error_message=e.message,
        )
        raise

    results, meta, upload_id = _run(
        db,
        user,
        records,
        "batch",
        model_version,
        filename=filename,
        content_hash=content_hash,
    )
    return {
        **meta,
        "upload_id": upload_id,
        "row_count": len(results),
        "predictions": results,
    }


@router.post("/batch/json")
def predict_batch_json(
    db: DbDep,
    user: Annotated[User, Depends(get_current_user)],
    payload: list[dict[str, Any]],
    model_version: str | None = Query(default=None),
):
    request_id = str(uuid.uuid4())
    try:
        records = validate_batch_json(payload)
    except ValidationException as e:
        log_validation_error(
            db,
            request_id=request_id,
            user_id=user.id,
            upload_type="batch",
            error_code=e.code,
            error_message=e.message,
        )
        raise

    results, meta, upload_id = _run(db, user, records, "batch", model_version)
    return {
        **meta,
        "upload_id": upload_id,
        "row_count": len(results),
        "predictions": results,
    }

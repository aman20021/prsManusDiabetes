from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import DbDep, get_current_user
from app.db.models import InferenceLog, ModelVersion, User
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
    parse_json_body,
    validate_batch_csv,
    validate_batch_json,
    validate_single_payload,
)

router = APIRouter(prefix="/predict", tags=["predict"])


class PredictQuery(BaseModel):
    model_version: str | None = None


def _resolve_model_version(db: DbDep, version: str | None) -> tuple[str, ModelVersion]:
    if version:
        mv = db.query(ModelVersion).filter_by(version=version).first()
        if not mv:
            raise AppError(404, "MODEL_NOT_FOUND", f"Model version {version} is not registered", [])
        return version, mv
    active = get_active_model_version(db)
    if not active:
        raise AppError(503, "MODEL_UNAVAILABLE", "No production model is configured", [])
    return active.version, active


def _artifact_sha(db: DbDep, version: str) -> str | None:
    mv = db.query(ModelVersion).filter_by(version=version).first()
    return mv.artifact_sha256 if mv else None


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

    version, mv = _resolve_model_version(db, model_version)
    upload = create_upload(db, user.id, "single", 1, status="completed")
    db.commit()

    try:
        results, meta, latency_ms = run_inference([record], version)
    except RuntimeError as e:
        log_inference_error(
            db,
            request_id=request_id,
            user_id=user.id,
            upload_id=upload.id,
            upload_type="single",
            error_code="INFERENCE_FAILED",
            error_message=str(e),
            model_version=version,
        )
        raise AppError(
            503,
            "INFERENCE_FAILED",
            "Model inference failed",
            [{"message": str(e)}],
        ) from e

    meta["request_id"] = request_id
    meta["artifact_sha256"] = mv.artifact_sha256
    log_inference_success(
        db,
        request_id=request_id,
        user_id=user.id,
        upload_id=upload.id,
        model_version=version,
        preprocessing_version=mv.preprocessing_version,
        artifact_sha256=mv.artifact_sha256,
        scaler_sha256=registry.scaler_sha256,
        upload_type="single",
        results=results,
        latency_ms=latency_ms,
    )

    r = results[0]
    return {
        **meta,
        "prediction": {
            "label": r["label"],
            "label_name": r["label_name"],
            "probability_positive": r["probability_positive"],
            "probability_negative": r["probability_negative"],
            "confidence": r["confidence"],
            "input_hash": r["input_hash"],
            "input_echo": r["input_echo"],
        },
        "upload_id": upload.id,
    }


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

    version, mv = _resolve_model_version(db, model_version)
    upload = create_upload(
        db,
        user.id,
        "batch",
        len(records),
        filename=filename,
        content_sha256=content_hash,
    )
    db.commit()

    try:
        results, meta, latency_ms = run_inference(records, version)
    except RuntimeError as e:
        log_inference_error(
            db,
            request_id=request_id,
            user_id=user.id,
            upload_id=upload.id,
            upload_type="batch",
            error_code="INFERENCE_FAILED",
            error_message=str(e),
            model_version=version,
        )
        raise AppError(
            503,
            "INFERENCE_FAILED",
            "Model inference failed",
            [{"message": str(e)}],
        ) from e

    meta["request_id"] = request_id
    meta["artifact_sha256"] = mv.artifact_sha256
    log_inference_success(
        db,
        request_id=request_id,
        user_id=user.id,
        upload_id=upload.id,
        model_version=version,
        preprocessing_version=mv.preprocessing_version,
        artifact_sha256=mv.artifact_sha256,
        scaler_sha256=registry.scaler_sha256,
        upload_type="batch",
        results=results,
        latency_ms=latency_ms,
    )

    return {
        **meta,
        "upload_id": upload.id,
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

    version, mv = _resolve_model_version(db, model_version)
    upload = create_upload(db, user.id, "batch", len(records))
    db.commit()

    try:
        results, meta, latency_ms = run_inference(records, version)
    except RuntimeError as e:
        log_inference_error(
            db,
            request_id=request_id,
            user_id=user.id,
            upload_id=upload.id,
            upload_type="batch",
            error_code="INFERENCE_FAILED",
            error_message=str(e),
            model_version=version,
        )
        raise AppError(
            503,
            "INFERENCE_FAILED",
            "Model inference failed",
            [{"message": str(e)}],
        ) from e

    meta["request_id"] = request_id
    meta["artifact_sha256"] = mv.artifact_sha256
    log_inference_success(
        db,
        request_id=request_id,
        user_id=user.id,
        upload_id=upload.id,
        model_version=version,
        preprocessing_version=mv.preprocessing_version,
        artifact_sha256=mv.artifact_sha256,
        scaler_sha256=registry.scaler_sha256,
        upload_type="batch",
        results=results,
        latency_ms=latency_ms,
    )

    return {
        **meta,
        "upload_id": upload.id,
        "row_count": len(results),
        "predictions": results,
    }

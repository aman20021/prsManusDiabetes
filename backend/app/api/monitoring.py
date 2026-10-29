from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.deps import DbDep, get_current_user, require_role
from app.db.models import InferenceLog, User
from app.db.seed import get_active_model_version

router = APIRouter(tags=["monitoring"])


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_v) - 1)
    if f == c:
        return round(sorted_v[f], 2)
    return round(sorted_v[f] + (sorted_v[c] - sorted_v[f]) * (k - f), 2)


def _build_summary(db: DbDep, window_hours: int = 24) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    logs = db.query(InferenceLog).filter(InferenceLog.created_at >= since).all()
    total = len(logs)
    errors = sum(1 for l in logs if not l.success)
    successes = [l for l in logs if l.success and l.prediction is not None]
    latencies = [l.latency_ms for l in logs if l.latency_ms is not None]
    positive_rate = None
    if successes:
        positive_rate = round(
            sum(1 for l in successes if l.prediction == 1) / len(successes), 4
        )
    active = get_active_model_version(db)
    return {
        "window_hours": window_hours,
        "request_count": total,
        "error_count": errors,
        "error_rate": round(errors / total, 4) if total else 0.0,
        "latency_ms_p50": _percentile(latencies, 0.5),
        "latency_ms_p95": _percentile(latencies, 0.95),
        "positive_prediction_rate": positive_rate,
        "active_model_version": active.version if active else None,
    }


@router.get("/monitoring/summary")
def monitoring_summary(
    db: DbDep,
    user: Annotated[User, Depends(get_current_user)],
    window_hours: int = 24,
):
    return _build_summary(db, window_hours)


@router.get("/metrics")
def prometheus_metrics(db: DbDep, user: Annotated[User, Depends(require_role("mlops"))]):
    summary = _build_summary(db)
    lines = [
        "# HELP manas_inference_requests Total inference log entries in window",
        "# TYPE manas_inference_requests gauge",
        f'manas_inference_requests{{window_hours="{summary["window_hours"]}"}} {summary["request_count"]}',
        "# HELP manas_inference_error_rate Error rate in window",
        "# TYPE manas_inference_error_rate gauge",
        f'manas_inference_error_rate{{window_hours="{summary["window_hours"]}"}} {summary["error_rate"]}',
    ]
    if summary["latency_ms_p95"] is not None:
        lines.append(f"manas_inference_latency_ms_p95 {summary['latency_ms_p95']}")
    if summary["positive_prediction_rate"] is not None:
        lines.append(
            f"manas_inference_positive_rate {summary['positive_prediction_rate']}"
        )
    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type="text/plain; version=0.0.4")

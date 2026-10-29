from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.config import get_settings
from app.domain.features import LABEL_NAMES
from app.services.hashing import canonical_input_hash
from app.services.registry import registry


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_inference(
    records: list[dict[str, int]],
    model_version: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], float]:
    settings = get_settings()
    scaler = registry.get_scaler()
    adapter = registry.get_adapter(model_version)

    start = time.perf_counter()
    try:
        X = scaler.transform(records)
        proba = adapter.predict_proba(X)
    except Exception as e:
        raise RuntimeError(str(e)) from e
    latency_ms = (time.perf_counter() - start) * 1000

    results: list[dict[str, Any]] = []
    for i, record in enumerate(records):
        p = proba[i]
        if len(p) < 2:
            p1 = float(p[0])
            p0, p1 = 1 - p1, p1
        else:
            p0, p1 = float(p[0]), float(p[1])
        label = 1 if p1 >= p0 else 0
        confidence = max(p0, p1)
        results.append(
            {
                "row_index": i,
                "label": label,
                "label_name": LABEL_NAMES[label],
                "probability_positive": round(p1, 6),
                "probability_negative": round(p0, 6),
                "confidence": round(confidence, 6),
                "input_hash": canonical_input_hash(record),
                "input_echo": record,
            }
        )

    meta = {
        "request_id": str(uuid.uuid4()),
        "timestamp": _utc_now().isoformat(),
        "model_version": model_version,
        "preprocessing_version": settings.preprocessing_version,
        "scaler_sha256": registry.scaler_sha256,
        "disclaimer": "Assistive screening tool only; not a clinical diagnosis.",
    }
    return results, meta, latency_ms

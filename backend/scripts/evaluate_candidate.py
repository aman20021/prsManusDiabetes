#!/usr/bin/env python3
"""Offline challenger evaluation — does not promote models."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import ModelVersion
from app.db.seed import get_active_model_version
from app.db.session import init_engine, get_session_factory
from app.domain.features import normalize_record
from app.services.inference import run_inference
from app.services.registry import bootstrap_artifacts


def load_labelled_csv(path: Path) -> tuple[list[dict], list[int]]:
    records: list[dict] = []
    labels: list[int] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            label_raw = row.pop("Diabetes_binary", None) or row.pop("diabetes_binary", None)
            if label_raw is None:
                raise ValueError(f"Row {i}: missing Diabetes_binary label")
            parsed = {}
            for k, v in row.items():
                if v is None or str(v).strip() == "":
                    parsed[k] = None
                else:
                    s = str(v).strip()
                    parsed[k] = int(s) if "." not in s else float(s)
            rec, errs = normalize_record(parsed, row_index=i)
            if errs:
                raise ValueError(f"Row {i} validation: {errs}")
            records.append(rec)
            labels.append(int(label_raw))
    return records, labels


def metrics(y_true: list[int], y_pred: list[int]) -> dict:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    n = len(y_true)
    acc = (tp + tn) / n if n else 0
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    return {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "eval_completed": True,
        "sample_count": n,
    }


def evaluate(db: Session, candidate_version: str, csv_path: Path) -> dict:
    bootstrap_artifacts()
    prod = get_active_model_version(db)
    records, labels = load_labelled_csv(csv_path)

    cand_results, _, _ = run_inference(records, candidate_version)
    cand_pred = [r["label"] for r in cand_results]
    cand_metrics = metrics(labels, cand_pred)
    cand_metrics["role"] = "candidate"
    cand_metrics["version"] = candidate_version

    comparison = {"candidate": cand_metrics}
    if prod:
        prod_results, _, _ = run_inference(records, prod.version)
        prod_pred = [r["label"] for r in prod_results]
        pm = metrics(labels, prod_pred)
        pm["role"] = "production"
        pm["version"] = prod.version
        comparison["production"] = pm

    mv = db.query(ModelVersion).filter_by(version=candidate_version).first()
    if mv:
        existing = mv.offline_metrics or {}
        existing.update(cand_metrics)
        existing["comparison"] = comparison
        mv.offline_metrics = existing
        db.commit()
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, help="Model version e.g. v1.1.0")
    parser.add_argument("--csv", required=True, type=Path, help="Labelled eval CSV")
    args = parser.parse_args()

    init_engine()
    Base.metadata.create_all(bind=init_engine())
    db = get_session_factory()()
    try:
        result = evaluate(db, args.candidate, args.csv)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ModelVersion, Role, User
from app.services.auth import hash_password
from app.services.hashing import sha256_file
from app.services.registry import bootstrap_artifacts, registry


def seed_roles_and_users(db: Session) -> None:
    settings = get_settings()
    for name in ("clinician", "mlops"):
        if not db.query(Role).filter_by(name=name).first():
            db.add(Role(name=name))
    db.flush()

    clinician_role = db.query(Role).filter_by(name="clinician").one()
    mlops_role = db.query(Role).filter_by(name="mlops").one()

    users = [
        ("clinician", settings.clinician_password, clinician_role.id),
        ("mlops", settings.mlops_password, mlops_role.id),
    ]
    for username, password, role_id in users:
        if not db.query(User).filter_by(username=username).first():
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    role_id=role_id,
                )
            )
    db.commit()


def seed_model_versions(db: Session) -> None:
    settings = get_settings()
    art = settings.artifacts_dir
    bootstrap_artifacts()

    specs = [
        {
            "version": "v1.0.0",
            "framework": "sklearn",
            "file": "diabetes_random_forest_tuned.joblib",
            "status": "production",
            "offline_metrics": {
                "accuracy": 0.7488,
                "precision": 0.7281,
                "recall": 0.7942,
                "f1": 0.7597,
            },
        },
        {
            "version": "v1.1.0",
            "framework": "keras",
            "file": "diabetes_mlp_tuned.keras",
            "status": "candidate",
            "offline_metrics": {
                "accuracy": 0.7512,
                "precision": 0.7264,
                "recall": 0.8059,
                "f1": 0.7641,
            },
        },
    ]

    for spec in specs:
        path = art / spec["file"]
        if not path.exists():
            continue
        existing = db.query(ModelVersion).filter_by(version=spec["version"]).first()
        sha = sha256_file(path)
        if existing:
            continue
        db.add(
            ModelVersion(
                version=spec["version"],
                framework=spec["framework"],
                artifact_path=str(path),
                artifact_sha256=sha,
                status=spec["status"],
                preprocessing_version=settings.preprocessing_version,
                offline_metrics=spec["offline_metrics"],
            )
        )
    db.commit()

    # Ensure single production
    prod = db.query(ModelVersion).filter_by(status="production").all()
    if len(prod) > 1:
        for mv in prod[1:]:
            mv.status = "candidate"
        db.commit()
    elif len(prod) == 0:
        first = db.query(ModelVersion).filter_by(version="v1.0.0").first()
        if first:
            first.status = "production"
            db.commit()


def get_active_model_version(db: Session) -> ModelVersion | None:
    return db.query(ModelVersion).filter_by(status="production").first()

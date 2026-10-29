from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.preprocessing import StandardScaler

os.environ["TESTING"] = "1"

from app.db.base import Base
from app.db.models import ModelVersion
from app.db.seed import seed_roles_and_users
from app.db.session import get_engine, get_session_factory, init_engine
from app.main import app
from app.services.registry import ScalerWrapper, registry


class FakeAdapter:
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        out = []
        for row in X:
            score = 1 / (1 + np.exp(-row[3])) if len(row) > 3 else 0.5
            out.append([1 - score, score])
        return np.array(out)


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("TEST_DATABASE_URL", f"sqlite:///{db_path}")

    from app.config import get_settings

    get_settings.cache_clear()

    init_engine(testing=True)
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    scaler = StandardScaler()
    from app.domain.features import FEATURE_ORDER

    dummy = np.array([[0, 0, 0, 25, 0, 0, 0, 1, 1, 1, 0, 1, 0, 3, 0, 0, 0, 0, 5, 4, 5]], dtype=float)
    scaler.fit(dummy)
    registry._adapters.clear()
    registry._load_failures.clear()
    registry.set_scaler_fake(ScalerWrapper(scaler, list(FEATURE_ORDER)), sha="test-scaler-sha")
    registry.register_fake("v1.0.0", FakeAdapter())
    registry.register_fake("v1.1.0", FakeAdapter())

    db = get_session_factory()()
    try:
        seed_roles_and_users(db)
        for spec in [
            ("v1.0.0", "sklearn", "production"),
            ("v1.1.0", "keras", "candidate"),
        ]:
            if not db.query(ModelVersion).filter_by(version=spec[0]).first():
                db.add(
                    ModelVersion(
                        version=spec[0],
                        framework=spec[1],
                        artifact_path=f"/fake/{spec[0]}",
                        artifact_sha256=f"sha-{spec[0]}",
                        status=spec[2],
                        preprocessing_version="scaler-v1",
                        offline_metrics={"accuracy": 0.75},
                    )
                )
        db.commit()
    finally:
        db.close()

    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinician_token(client):
    r = client.post("/api/v1/auth/login", json={"username": "clinician", "password": "clinician123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def mlops_token(client):
    r = client.post("/api/v1/auth/login", json={"username": "mlops", "password": "mlops123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def sample_record() -> dict:
    return {
        "HighBP": 1,
        "HighChol": 1,
        "CholCheck": 1,
        "BMI": 30,
        "Smoker": 0,
        "Stroke": 0,
        "HeartDiseaseorAttack": 0,
        "PhysActivity": 1,
        "Fruits": 1,
        "Veggies": 1,
        "HvyAlcoholConsump": 0,
        "AnyHealthcare": 1,
        "NoDocbcCost": 0,
        "GenHlth": 3,
        "MentHlth": 0,
        "PhysHlth": 0,
        "DiffWalk": 0,
        "Sex": 0,
        "Age": 5,
        "Education": 4,
        "Income": 5,
    }

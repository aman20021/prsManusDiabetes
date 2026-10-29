from io import BytesIO

from app.db.models import InferenceLog, ModelVersion
from app.db.session import get_session_factory
from tests.conftest import sample_record


def test_health(client):
    assert client.get("/health").status_code == 200


def test_ready(client):
    assert client.get("/ready").status_code == 200


def test_predict_single(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    r = client.post("/api/v1/predict", json=sample_record(), headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "prediction" in body
    assert body["model_version"] == "v1.0.0"
    assert "request_id" in body
    assert "input_hash" in body["prediction"]


def test_predict_invalid(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    bad = sample_record()
    bad["Age"] = 99
    r = client.post("/api/v1/predict", json=bad, headers=headers)
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"


def test_predict_unauthorized(client):
    r = client.post("/api/v1/predict", json=sample_record())
    assert r.status_code == 401


def test_batch_json(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    r = client.post(
        "/api/v1/predict/batch/json",
        json=[sample_record(), sample_record()],
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["row_count"] == 2


def test_batch_csv(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    header = ",".join(sample_record().keys())
    row = ",".join(str(v) for v in sample_record().values())
    files = {"file": ("batch.csv", BytesIO(f"{header}\n{row}\n".encode()), "text/csv")}
    r = client.post("/api/v1/predict/batch", headers=headers, files=files)
    assert r.status_code == 200


def test_model_version_selection(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    r = client.post(
        "/api/v1/predict?model_version=v1.1.0",
        json=sample_record(),
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["model_version"] == "v1.1.0"


def test_unknown_model(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    r = client.post(
        "/api/v1/predict?model_version=v9.9.9",
        json=sample_record(),
        headers=headers,
    )
    assert r.status_code == 404


def test_persistence(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    client.post("/api/v1/predict", json=sample_record(), headers=headers)
    db = get_session_factory()()
    try:
        count = db.query(InferenceLog).filter_by(success=True).count()
        assert count >= 1
    finally:
        db.close()


def test_uploads_list(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    client.post("/api/v1/predict", json=sample_record(), headers=headers)
    r = client.get("/api/v1/uploads", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["uploads"]) >= 1


def test_monitoring_empty(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    r = client.get("/api/v1/monitoring/summary", headers=headers)
    assert r.status_code == 200
    assert r.json()["error_rate"] == 0.0


def test_promote_requires_eval(client, mlops_token):
    headers = {"Authorization": f"Bearer {mlops_token}"}
    r = client.post("/api/v1/models/v1.1.0/promote", json={"reason": "test promote"}, headers=headers)
    assert r.status_code == 422


def test_promote_and_rollback(client, mlops_token):
    headers = {"Authorization": f"Bearer {mlops_token}"}
    db = get_session_factory()()
    try:
        mv = db.query(ModelVersion).filter_by(version="v1.1.0").one()
        mv.offline_metrics = {"eval_completed": True, "f1": 0.77}
        db.commit()
    finally:
        db.close()

    r = client.post("/api/v1/models/v1.1.0/promote", json={"reason": "better recall"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "production"

    r2 = client.get("/api/v1/models/active", headers=headers)
    assert r2.json()["version"] == "v1.1.0"

    r3 = client.post("/api/v1/models/rollback", json={"reason": "regression"}, headers=headers)
    assert r3.status_code == 200
    assert r3.json()["version"] == "v1.0.0"


def test_clinician_forbidden_promote(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    r = client.post("/api/v1/models/v1.1.0/promote", json={"reason": "nope"}, headers=headers)
    assert r.status_code == 403


def test_model_load_failure(client, clinician_token, monkeypatch):
    from app.exceptions import AppError
    from app.services import registry as reg_mod

    def boom(_version):
        raise AppError(503, "MODEL_UNAVAILABLE", "broken", [])

    monkeypatch.setattr(reg_mod.registry, "get_adapter", boom)
    headers = {"Authorization": f"Bearer {clinician_token}"}
    r = client.post("/api/v1/predict", json=sample_record(), headers=headers)
    assert r.status_code == 503

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


def test_create_user_and_assign_role(client, mlops_token, clinician_token):
    mlops = {"Authorization": f"Bearer {mlops_token}"}
    clinician = {"Authorization": f"Bearer {clinician_token}"}

    denied = client.post(
        "/api/v1/users",
        json={"username": "nia", "password": "screening1", "role": "clinician"},
        headers=clinician,
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/v1/users",
        json={"username": "nia", "password": "screening1", "role": "clinician"},
        headers=mlops,
    )
    assert created.status_code == 201
    assert created.json()["role"] == "clinician"
    user_id = created.json()["id"]

    login = client.post("/api/v1/auth/login", json={"username": "nia", "password": "screening1"})
    assert login.status_code == 200
    assert login.json()["role"] == "clinician"

    duplicate = client.post(
        "/api/v1/users",
        json={"username": "nia", "password": "screening1", "role": "clinician"},
        headers=mlops,
    )
    assert duplicate.status_code == 409

    weak = client.post(
        "/api/v1/users",
        json={"username": "sam", "password": "short", "role": "clinician"},
        headers=mlops,
    )
    assert weak.status_code == 422

    assigned = client.patch(f"/api/v1/users/{user_id}", json={"role": "mlops"}, headers=mlops)
    assert assigned.status_code == 200
    assert assigned.json()["role"] == "mlops"

    listed = client.get("/api/v1/users", headers=mlops)
    assert listed.status_code == 200
    mlops_row = next(u for u in listed.json()["users"] if u["username"] == "mlops")
    self_change = client.patch(
        f"/api/v1/users/{mlops_row['id']}",
        json={"role": "clinician"},
        headers=mlops,
    )
    assert self_change.status_code == 422


def test_default_model_is_production(client, clinician_token, mlops_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    mlops = {"Authorization": f"Bearer {mlops_token}"}
    before = client.post("/api/v1/predict", json=sample_record(), headers=headers)
    assert before.status_code == 200
    assert before.json()["model_version"] == "v1.0.0"
    assert before.json()["artifact_sha256"] == "sha-v1.0.0"
    assert before.json()["preprocessing_version"] == "scaler-v1"

    db = get_session_factory()()
    try:
        mv = db.query(ModelVersion).filter_by(version="v1.1.0").one()
        mv.offline_metrics = {"eval_completed": True}
        db.commit()
    finally:
        db.close()
    promoted = client.post(
        "/api/v1/models/v1.1.0/promote",
        json={"reason": "use the challenger"},
        headers=mlops,
    )
    assert promoted.status_code == 200

    after = client.post("/api/v1/predict", json=sample_record(), headers=headers)
    assert after.status_code == 200
    body = after.json()
    assert body["model_version"] == "v1.1.0"
    assert body["artifact_sha256"] == "sha-v1.1.0"
    assert body["preprocessing_version"] == "scaler-v1"


def test_registered_model_must_be_loaded(client, clinician_token):
    from app.services.registry import registry

    registry._adapters.pop("v1.1.0", None)
    headers = {"Authorization": f"Bearer {clinician_token}"}
    r = client.post("/api/v1/predict?model_version=v1.1.0", json=sample_record(), headers=headers)
    assert r.status_code == 503
    assert r.json()["code"] == "MODEL_UNAVAILABLE"

    db = get_session_factory()()
    try:
        from app.db.models import Upload

        failed = db.query(Upload).filter_by(status="failed").count()
        completed = db.query(Upload).filter_by(status="completed").count()
        assert failed == 1
        assert completed == 0
    finally:
        db.close()


def test_inference_failure_marks_upload_failed(client, clinician_token, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("score failed")

    monkeypatch.setattr("app.api.predict.run_inference", boom)
    headers = {"Authorization": f"Bearer {clinician_token}"}
    r = client.post("/api/v1/predict", json=sample_record(), headers=headers)
    assert r.status_code == 503
    assert r.json()["code"] == "INFERENCE_FAILED"

    db = get_session_factory()()
    try:
        from app.db.models import Upload

        upload = db.query(Upload).one()
        assert upload.status == "failed"
        log = db.query(InferenceLog).one()
        assert log.success is False
        assert log.model_version == "v1.0.0"
    finally:
        db.close()


def test_single_csv(client, clinician_token):
    headers = {"Authorization": f"Bearer {clinician_token}"}
    header = ",".join(sample_record().keys())
    row = ",".join(str(v) for v in sample_record().values())
    files = {"file": ("one.csv", BytesIO(f"{header}\n{row}\n".encode()), "text/csv")}
    r = client.post("/api/v1/predict/csv", headers=headers, files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == "v1.0.0"
    assert "prediction" in body

    two = {"file": ("two.csv", BytesIO(f"{header}\n{row}\n{row}\n".encode()), "text/csv")}
    bad = client.post("/api/v1/predict/csv", headers=headers, files=two)
    assert bad.status_code == 422


def test_model_load_failure(client, clinician_token, monkeypatch):
    from app.exceptions import AppError
    from app.services import registry as reg_mod

    def boom(_version):
        raise AppError(503, "MODEL_UNAVAILABLE", "broken", [])

    monkeypatch.setattr(reg_mod.registry, "get_adapter", boom)
    headers = {"Authorization": f"Bearer {clinician_token}"}
    r = client.post("/api/v1/predict", json=sample_record(), headers=headers)
    assert r.status_code == 503

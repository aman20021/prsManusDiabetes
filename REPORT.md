# MANAS Take-Home Report

## Approach summary

The solution wraps the Hugging Face study models in a small three-tier app: FastAPI inference API, React client, and PostgreSQL for users, model registry, uploads, and inference logs. Two supplied artifacts are treated as coexisting **versions** (Random Forest `v1.0.0` in production, MLP `v1.1.0` as candidate). A shared `StandardScaler` (`scaler-v1`) is loaded once; feature order was verified against `scaler.feature_names_in_` (21 BRFSS indicators, matching Kaggle schema without `Diabetes_binary`).

## 1. Inference service

- **Validation:** Strict pydantic-free validation in `app/services/validation.py` rejects missing/extra fields (including target column), wrong types, booleans, non-integer floats on coded fields, and out-of-range values. Batch validation is all-or-nothing.
- **Single:** `POST /api/v1/predict` with JSON body.
- **Batch:** `POST /api/v1/predict/batch` (multipart CSV) or `POST /api/v1/predict/batch/json`.
- **Responses** include label, probabilities, confidence, model version, preprocessing version, artifact/scaler hashes, timestamp, request ID, and input echo/hash for reproducibility.
- **Errors** return structured JSON `{ code, message, details }` with HTTP 422 (validation), 401/403 (auth), 404 (unknown model), 503 (load/inference failure)—covered by pytest.

### Example single response (abbreviated)

```json
{
  "request_id": "…",
  "timestamp": "2026-10-28T12:00:00+00:00",
  "model_version": "v1.0.0",
  "preprocessing_version": "scaler-v1",
  "artifact_sha256": "…",
  "scaler_sha256": "…",
  "prediction": {
    "label": 1,
    "label_name": "diabetes_or_prediabetes",
    "probability_positive": 0.812345,
    "confidence": 0.812345,
    "input_hash": "…",
    "input_echo": { "HighBP": 1, "BMI": 30, "…": "…" }
  },
  "upload_id": 42
}
```

### Example batch response (shape)

```json
{
  "request_id": "…",
  "model_version": "v1.0.0",
  "row_count": 2,
  "upload_id": 43,
  "predictions": [
    { "row_index": 0, "label": 0, "probability_positive": 0.31, "…": "…" },
    { "row_index": 1, "label": 1, "probability_positive": 0.67, "…": "…" }
  ]
}
```

## 2. Frontend

React (Vite + TypeScript) provides login, single form + CSV row upload, batch CSV upload, upload history/detail, dashboard (active model + recent predictions + monitoring summary), and an MLOps-only models page for promote/rollback. Loading and validation errors from the API are surfaced via `ErrorBox`.

## 3. Containerization

Root `docker-compose.yml` starts PostgreSQL, backend (downloads artifacts at image build, initializes DB on entry), and nginx-served frontend proxying `/api` to the backend. One command: `docker compose up --build`.

## 4. Versioning and logging

- **Registry:** `model_versions` table stores artifact path, SHA-256, framework, status (`candidate` | `production` | `retired`), offline metrics.
- **Logging:** Every success and validation/inference failure creates `inference_logs` rows linked to optional `uploads`.
- **Promotion:** MLOps promotes only after `evaluate_candidate.py` sets `eval_completed`; `promotion_events` records promote/rollback with actor and reason.
- **Rollback:** Restores previous production version from the latest promote event’s `from_version`.

Production is **not** silently replaced when a new artifact appears on disk—only the promote endpoint changes the active pointer.

## 5. Testing

`pytest` (23 tests) covers validation unit tests and API integration: auth, single/batch, persistence, monitoring on empty logs, model selection, 404/403/503 paths, promote/rollback. Tests use SQLite and fake adapters to stay fast and avoid requiring TensorFlow in CI.

Run: `cd backend && TESTING=1 pytest -q`

## 6. Bonus features

- **RBAC:** JWT login; roles `clinician` (own uploads/logs) and `mlops` (global logs, metrics, promote/rollback).
- **Monitoring:** `/api/v1/monitoring/summary` (counts, error rate, latency p50/p95, positive prediction rate) and Prometheus-style `/api/v1/metrics`.
- **OpenAPI:** Auto-generated at `/docs`.

## Assumptions and tradeoffs

| Choice | Rationale |
|--------|-----------|
| RF as initial production | Faster cold start, smaller dependency surface; MLP remains challenger with higher published recall. |
| Shared scaler for both versions | Matches upstream training notebook; both models expect scaled inputs. |
| `create_all` vs Alembic migrations | Faster take-home setup; schema is small and created on startup. Production would use Alembic. |
| SQLite in tests | Meets “run pytest without Docker” while compose uses PostgreSQL. |
| Positive-rate monitoring | Training data is 50/50 balanced; drift metric is operational, not epidemiological prevalence. |

## Limitations

- Labels and features are self-reported BRFSS survey data; positive class merges diabetes and prediabetes.
- Keras/TensorFlow increases image size and startup time; candidate MLP loads only when selected or when artifacts are present at bootstrap.
- Offline evaluation script expects a labelled CSV with `Diabetes_binary`; operators must supply held-out data from Kaggle responsibly.

## Promotion / rollback (operational)

1. The new artifact file is stored under `backend/models/artifacts/` and registered with status `candidate` (the production row is unchanged).
2. Run `python scripts/evaluate_candidate.py --candidate vX --csv eval.csv`.
3. MLOps reviews metrics comparison in DB/UI.
4. `POST …/promote` with reason → old production `retired`, candidate `production`.
5. If production misbehaves, `POST …/rollback` → previous version restored, event logged.

See [DESIGN.md](DESIGN.md) for the required answer on 1,000 new labelled samples (no automatic retraining).

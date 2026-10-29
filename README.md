# MANAS Diabetes Inference Service

Production-style inference web app for the [Neperl/diabetes-health-indicators-study](https://huggingface.co/Neperl/diabetes-health-indicators-study) models (Random Forest v1.0.0 production, MLP v1.1.0 candidate) on BRFSS health indicators.

## Quick start (Docker)

```bash
docker compose up --build
```

- Frontend: http://localhost:8080  
- API docs: http://localhost:8000/docs (also proxied at http://localhost:8080/docs)  
- Health: http://localhost:8000/health  

### Demo accounts

| User       | Password       | Role      |
|------------|----------------|-----------|
| clinician  | clinician123   | Submit predictions, view own uploads |
| mlops      | mlops123       | All logs, promote/rollback models |

## Local development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_models.py
export DATABASE_URL=postgresql://manas:manas@localhost:5432/manas_inference
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 (API proxied to port 8000).

### Tests

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
TESTING=1 pytest -q
```

Tests use SQLite (`TEST_DATABASE_URL`) and in-memory fake model adapters so they do not require PostgreSQL or TensorFlow at runtime.

## Example API calls

### Login

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"clinician","password":"clinician123"}' | jq -r .access_token)
```

### Single prediction (JSON)

```bash
curl -s -X POST http://localhost:8000/api/v1/predict \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "HighBP":1,"HighChol":1,"CholCheck":1,"BMI":30,"Smoker":0,"Stroke":0,
    "HeartDiseaseorAttack":0,"PhysActivity":1,"Fruits":1,"Veggies":1,
    "HvyAlcoholConsump":0,"AnyHealthcare":1,"NoDocbcCost":0,"GenHlth":3,
    "MentHlth":0,"PhysHlth":0,"DiffWalk":0,"Sex":0,"Age":5,"Education":4,"Income":5
  }' | jq
```

### Batch (JSON array)

```bash
curl -s -X POST http://localhost:8000/api/v1/predict/batch/json \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '[{ ... same fields ... }]' | jq
```

### Batch (CSV upload)

```bash
curl -s -X POST http://localhost:8000/api/v1/predict/batch \
  -H "Authorization: Bearer $TOKEN" \
  -F file=@sample.csv | jq
```

## Model promotion (offline eval required)

1. Run offline challenger evaluation (does **not** promote):

```bash
cd backend
python scripts/evaluate_candidate.py --candidate v1.1.0 --csv /path/to/labelled_eval.csv
```

2. Promote as MLOps (requires `offline_metrics.eval_completed`):

```bash
curl -X POST http://localhost:8000/api/v1/models/v1.1.0/promote \
  -H "Authorization: Bearer $MLOPS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Higher recall on held-out eval"}'
```

3. Rollback:

```bash
curl -X POST http://localhost:8000/api/v1/models/rollback \
  -H "Authorization: Bearer $MLOPS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Production regression"}'
```

## Repository layout

```
backend/     FastAPI service, models, tests, Dockerfile
frontend/    React (Vite) client, Dockerfile
docker-compose.yml
README.md
REPORT.md
DESIGN.md
```

See [REPORT.md](REPORT.md) for design choices and [DESIGN.md](DESIGN.md) for the retraining / 1,000-sample update process.

erDiagram
  roles ||--o{ users : has
  users ||--o{ uploads : creates
  users ||--o{ inference_logs : triggers
  uploads ||--o{ inference_logs : contains
  users ||--o{ promotion_events : actor
  model_versions ||--o{ inference_logs : version string


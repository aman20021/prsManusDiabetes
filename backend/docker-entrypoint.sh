#!/bin/sh
set -e
python - <<'PY'
from app.db.base import Base
from app.db.seed import seed_model_versions, seed_roles_and_users
from app.db.session import get_engine, get_session_factory, init_engine
from app.services.registry import bootstrap_artifacts

init_engine()
Base.metadata.create_all(bind=get_engine())
bootstrap_artifacts()
db = get_session_factory()()
try:
    seed_roles_and_users(db)
    seed_model_versions(db)
finally:
    db.close()
print("Database initialized")
PY
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

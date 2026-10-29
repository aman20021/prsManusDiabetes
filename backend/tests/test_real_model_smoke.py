import os
from pathlib import Path

import pytest

ART = Path(__file__).resolve().parents[1] / "models" / "artifacts" / "diabetes_random_forest_tuned.joblib"


@pytest.mark.skipif(not ART.exists(), reason="Real artifacts not downloaded")
def test_load_real_random_forest():
    import joblib

    model = joblib.load(ART)
    assert hasattr(model, "predict_proba")

#!/usr/bin/env python3
"""Download model artifacts from Hugging Face."""
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO = "Neperl/diabetes-health-indicators-study"
FILES = [
    "diabetes_random_forest_tuned.joblib",
    "diabetes_mlp_tuned.keras",
    "scaler.joblib",
]   


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "models" / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        path = hf_hub_download(repo_id=REPO, filename=name, local_dir=str(out))
        print(f"Downloaded {name} -> {path}")


if __name__ == "__main__":
    main()

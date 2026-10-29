from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.config import get_settings
from app.domain.features import FEATURE_ORDER
from app.exceptions import AppError
from app.services.hashing import sha256_file

logger = logging.getLogger(__name__)


class ModelAdapter(ABC):
    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        ...


class SklearnAdapter(ModelAdapter):
    def __init__(self, model: Any):
        self._model = model

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict_proba(X)


class KerasAdapter(ModelAdapter):
    def __init__(self, model: Any):
        self._model = model

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        proba = self._model.predict(X, verbose=0)
        if proba.ndim == 1:
            p1 = proba
            return np.column_stack([1 - p1, p1])
        if proba.shape[1] == 1:
            p1 = proba[:, 0]
            return np.column_stack([1 - p1, p1])
        return proba


class ScalerWrapper:
    def __init__(self, scaler: Any, feature_order: list[str]):
        self.scaler = scaler
        self.feature_order = feature_order

    def transform(self, records: list[dict[str, int]]) -> np.ndarray:
        rows = [[float(r[c]) for c in self.feature_order] for r in records]
        return self.scaler.transform(np.array(rows, dtype=np.float64))


class ModelRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}
        self._scaler: ScalerWrapper | None = None
        self._scaler_sha: str | None = None
        self._feature_order: list[str] = list(FEATURE_ORDER)
        self._load_failures: dict[str, str] = {}

    @property
    def feature_order(self) -> list[str]:
        return self._feature_order

    @property
    def scaler_sha256(self) -> str | None:
        return self._scaler_sha

    def load_scaler(self, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"Scaler not found: {path}")
        scaler = joblib.load(path)
        order = list(FEATURE_ORDER)
        names = getattr(scaler, "feature_names_in_", None)
        if names is not None:
            order = [str(n) for n in names]
            if order != FEATURE_ORDER:
                logger.warning("Scaler feature order differs from default; using scaler order")
        self._feature_order = order
        self._scaler = ScalerWrapper(scaler, order)
        self._scaler_sha = sha256_file(path)

    def get_scaler(self) -> ScalerWrapper:
        if self._scaler is None:
            raise AppError(503, "MODEL_UNAVAILABLE", "Preprocessing scaler is not loaded", [])
        return self._scaler

    def load_sklearn(self, version: str, path: Path) -> str:
        try:
            if not path.is_file():
                raise FileNotFoundError(str(path))
            model = joblib.load(path)
            self._adapters[version] = SklearnAdapter(model)
            self._load_failures.pop(version, None)
            return sha256_file(path)
        except Exception as e:
            self._load_failures[version] = str(e)
            logger.exception("Failed to load sklearn model %s", version)
            raise AppError(
                503,
                "MODEL_UNAVAILABLE",
                f"Failed to load model version {version}",
                [{"message": str(e)}],
            ) from e

    def load_keras(self, version: str, path: Path) -> str:
        try:
            if not path.is_file():
                raise FileNotFoundError(str(path))
            from tensorflow import keras

            model = keras.models.load_model(path)
            self._adapters[version] = KerasAdapter(model)
            self._load_failures.pop(version, None)
            return sha256_file(path)
        except Exception as e:
            self._load_failures[version] = str(e)
            logger.exception("Failed to load keras model %s", version)
            raise AppError(
                503,
                "MODEL_UNAVAILABLE",
                f"Failed to load model version {version}",
                [{"message": str(e)}],
            ) from e

    def get_adapter(self, version: str) -> ModelAdapter:
        if version in self._load_failures:
            raise AppError(
                503,
                "MODEL_UNAVAILABLE",
                f"Model version {version} failed to load",
                [{"message": self._load_failures[version]}],
            )
        if version not in self._adapters:
            raise AppError(404, "MODEL_NOT_FOUND", f"Model version {version} is not registered", [])
        return self._adapters[version]

    def register_fake(self, version: str, adapter: ModelAdapter) -> None:
        """For tests only."""
        self._adapters[version] = adapter

    def set_scaler_fake(self, scaler: ScalerWrapper, sha: str = "test-scaler") -> None:
        self._scaler = scaler
        self._scaler_sha = sha


registry = ModelRegistry()


def bootstrap_artifacts() -> None:
    settings = get_settings()
    art = settings.artifacts_dir
    scaler_path = art / "scaler.joblib"
    if scaler_path.exists():
        registry.load_scaler(scaler_path)
    rf_path = art / "diabetes_random_forest_tuned.joblib"
    if rf_path.exists():
        try:
            registry.load_sklearn("v1.0.0", rf_path)
        except AppError:
            pass
    mlp_path = art / "diabetes_mlp_tuned.keras"
    if mlp_path.exists():
        try:
            registry.load_keras("v1.1.0", mlp_path)
        except AppError:
            pass

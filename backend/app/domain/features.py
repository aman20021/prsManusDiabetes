"""BRFSS diabetes health indicators feature contract (21 inputs, no target)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Order used when scaler has no feature_names_in_
FEATURE_ORDER: list[str] = [
    "HighBP",
    "HighChol",
    "CholCheck",
    "BMI",
    "Smoker",
    "Stroke",
    "HeartDiseaseorAttack",
    "PhysActivity",
    "Fruits",
    "Veggies",
    "HvyAlcoholConsump",
    "AnyHealthcare",
    "NoDocbcCost",
    "GenHlth",
    "MentHlth",
    "PhysHlth",
    "DiffWalk",
    "Sex",
    "Age",
    "Education",
    "Income",
]

BINARY_FEATURES = {
    "HighBP",
    "HighChol",
    "CholCheck",
    "Smoker",
    "Stroke",
    "HeartDiseaseorAttack",
    "PhysActivity",
    "Fruits",
    "Veggies",
    "HvyAlcoholConsump",
    "AnyHealthcare",
    "NoDocbcCost",
    "DiffWalk",
    "Sex",
}

INTEGER_RANGES: dict[str, tuple[int, int]] = {
    "BMI": (12, 98),
    "GenHlth": (1, 5),
    "MentHlth": (0, 30),
    "PhysHlth": (0, 30),
    "Age": (1, 13),
    "Education": (1, 6),
    "Income": (1, 8),
}

FORBIDDEN_FIELDS = {"Diabetes_binary", "diabetes_binary"}

LABEL_POSITIVE = 1
LABEL_NEGATIVE = 0
LABEL_NAMES = {0: "no_diabetes", 1: "diabetes_or_prediabetes"}


@dataclass
class ValidationErrorDetail:
    field: str | None
    message: str
    row_index: int | None = None


def is_valid_feature_set(keys: set[str]) -> list[ValidationErrorDetail]:
    errors: list[ValidationErrorDetail] = []
    required = set(FEATURE_ORDER)
    missing = required - keys
    extra = keys - required
    for f in sorted(missing):
        errors.append(ValidationErrorDetail(field=f, message="missing required field"))
    for f in sorted(extra):
        if f in FORBIDDEN_FIELDS:
            errors.append(
                ValidationErrorDetail(
                    field=f,
                    message="target column must not be included in inference input",
                )
            )
        else:
            errors.append(ValidationErrorDetail(field=f, message="unexpected field"))
    return errors


def validate_value(name: str, value: Any, row_index: int | None = None) -> list[ValidationErrorDetail]:
    errors: list[ValidationErrorDetail] = []

    if value is None:
        errors.append(
            ValidationErrorDetail(field=name, message="value must not be null", row_index=row_index)
        )
        return errors

    if isinstance(value, bool):
        errors.append(
            ValidationErrorDetail(
                field=name, message="boolean not allowed; use 0 or 1", row_index=row_index
            )
        )
        return errors

    if name in BINARY_FEATURES:
        if isinstance(value, float) and not value.is_integer():
            errors.append(
                ValidationErrorDetail(
                    field=name, message="must be integer 0 or 1", row_index=row_index
                )
            )
            return errors
        if not isinstance(value, (int, float)):
            errors.append(
                ValidationErrorDetail(
                    field=name, message="must be integer 0 or 1", row_index=row_index
                )
            )
            return errors
        iv = int(value)
        if iv not in (0, 1):
            errors.append(
                ValidationErrorDetail(
                    field=name, message="must be 0 or 1", row_index=row_index
                )
            )
        elif isinstance(value, float) and float(value) != float(iv):
            errors.append(
                ValidationErrorDetail(
                    field=name, message="must be integer 0 or 1", row_index=row_index
                )
            )
        return errors

    if name in INTEGER_RANGES:
        lo, hi = INTEGER_RANGES[name]
        if isinstance(value, bool):
            errors.append(
                ValidationErrorDetail(
                    field=name, message=f"must be integer in [{lo}, {hi}]", row_index=row_index
                )
            )
            return errors
        if isinstance(value, float):
            if not value.is_integer():
                errors.append(
                    ValidationErrorDetail(
                        field=name,
                        message=f"must be integer in [{lo}, {hi}]",
                        row_index=row_index,
                    )
                )
                return errors
            value = int(value)
        if not isinstance(value, int):
            errors.append(
                ValidationErrorDetail(
                    field=name, message=f"must be integer in [{lo}, {hi}]", row_index=row_index
                )
            )
            return errors
        if value < lo or value > hi:
            errors.append(
                ValidationErrorDetail(
                    field=name,
                    message=f"out of range; expected [{lo}, {hi}]",
                    row_index=row_index,
                )
            )
        return errors

    errors.append(
        ValidationErrorDetail(field=name, message="unknown feature", row_index=row_index)
    )
    return errors


def normalize_record(raw: dict[str, Any], row_index: int | None = None) -> tuple[dict[str, int], list[ValidationErrorDetail]]:
    errors: list[ValidationErrorDetail] = []
    errors.extend(is_valid_feature_set(set(raw.keys())))
    if errors:
        return {}, errors

    normalized: dict[str, int] = {}
    for name in FEATURE_ORDER:
        field_errors = validate_value(name, raw[name], row_index=row_index)
        errors.extend(field_errors)
        if not field_errors:
            v = raw[name]
            normalized[name] = int(v) if name in BINARY_FEATURES or name in INTEGER_RANGES else int(v)

    return normalized, errors


def record_to_vector(record: dict[str, int], order: list[str] | None = None) -> list[float]:
    cols = order or FEATURE_ORDER
    return [float(record[c]) for c in cols]

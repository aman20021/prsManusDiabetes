"""Strict JSON and CSV validation for inference inputs."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.domain.features import ValidationErrorDetail, normalize_record

MAX_BATCH_ROWS = 1000
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class ValidationException(Exception):
    def __init__(self, code: str, message: str, details: list[dict[str, Any]]):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _details_to_dict(details: list[ValidationErrorDetail]) -> list[dict[str, Any]]:
    out = []
    for d in details:
        item: dict[str, Any] = {"message": d.message}
        if d.field is not None:
            item["field"] = d.field
        if d.row_index is not None:
            item["row_index"] = d.row_index
        out.append(item)
    return out


def validate_single_payload(data: Any) -> dict[str, int]:
    if not isinstance(data, dict):
        raise ValidationException(
            "INVALID_INPUT",
            "Request body must be a JSON object with feature fields",
            [{"message": "expected object"}],
        )
    record, errors = normalize_record(data)
    if errors:
        raise ValidationException(
            "VALIDATION_ERROR",
            "Input validation failed",
            _details_to_dict(errors),
        )
    return record


def validate_batch_json(data: Any) -> list[dict[str, int]]:
    if not isinstance(data, list):
        raise ValidationException(
            "INVALID_INPUT",
            "Batch body must be a JSON array of records",
            [{"message": "expected array"}],
        )
    if len(data) == 0:
        raise ValidationException(
            "VALIDATION_ERROR",
            "Batch must contain at least one record",
            [{"message": "empty batch"}],
        )
    if len(data) > MAX_BATCH_ROWS:
        raise ValidationException(
            "VALIDATION_ERROR",
            f"Batch exceeds maximum of {MAX_BATCH_ROWS} rows",
            [{"message": f"row count {len(data)}"}],
        )

    all_errors: list[ValidationErrorDetail] = []
    records: list[dict[str, int]] = []
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            all_errors.append(
                ValidationErrorDetail(field=None, message="each row must be an object", row_index=i)
            )
            continue
        record, errors = normalize_record(row, row_index=i)
        all_errors.extend(errors)
        records.append(record)

    if all_errors:
        raise ValidationException(
            "VALIDATION_ERROR",
            "Batch validation failed; no rows were scored",
            _details_to_dict(all_errors),
        )
    return records


def parse_csv_text(text: str) -> list[dict[str, Any]]:
    if not text or not text.strip():
        raise ValidationException(
            "INVALID_INPUT",
            "CSV file is empty",
            [{"message": "empty file"}],
        )

    try:
        reader = csv.DictReader(io.StringIO(text))
    except csv.Error as e:
        raise ValidationException(
            "INVALID_INPUT",
            "Malformed CSV",
            [{"message": str(e)}],
        ) from e

    if reader.fieldnames is None:
        raise ValidationException(
            "INVALID_INPUT",
            "CSV has no header row",
            [{"message": "missing header"}],
        )

    # Duplicate headers
    seen: set[str] = set()
    for h in reader.fieldnames:
        if h in seen:
            raise ValidationException(
                "INVALID_INPUT",
                "Duplicate CSV column names",
                [{"field": h, "message": "duplicate column"}],
            )
        seen.add(h)

    rows: list[dict[str, Any]] = []
    for line_num, row in enumerate(reader, start=1):
        if len(rows) >= MAX_BATCH_ROWS:
            raise ValidationException(
                "VALIDATION_ERROR",
                f"Batch exceeds maximum of {MAX_BATCH_ROWS} rows",
                [{"message": f"row count > {MAX_BATCH_ROWS}"}],
            )
        parsed: dict[str, Any] = {}
        for key, val in row.items():
            if key is None:
                continue
            stripped = (val or "").strip()
            if stripped == "":
                parsed[key] = None
                continue
            # Strict: no silent string coercion for numeric fields
            if stripped.lower() in ("true", "false", "yes", "no"):
                parsed[key] = stripped
            else:
                try:
                    if "." in stripped:
                        parsed[key] = float(stripped)
                    else:
                        parsed[key] = int(stripped)
                except ValueError:
                    parsed[key] = stripped
        rows.append(parsed)

    if not rows:
        raise ValidationException(
            "VALIDATION_ERROR",
            "CSV contains no data rows",
            [{"message": "no data rows"}],
        )
    return rows


def validate_batch_csv(content: bytes) -> list[dict[str, int]]:
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValidationException(
            "VALIDATION_ERROR",
            f"Upload exceeds maximum size of {MAX_UPLOAD_BYTES} bytes",
            [{"message": f"size {len(content)}"}],
        )
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValidationException(
            "INVALID_INPUT",
            "CSV must be UTF-8 encoded",
            [{"message": str(e)}],
        ) from e

    raw_rows = parse_csv_text(text)
    return validate_batch_json(raw_rows)


def parse_json_body(raw: bytes) -> Any:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValidationException(
            "VALIDATION_ERROR",
            f"Body exceeds maximum size of {MAX_UPLOAD_BYTES} bytes",
            [{"message": f"size {len(raw)}"}],
        )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationException(
            "INVALID_INPUT",
            "Malformed JSON",
            [{"message": str(e)}],
        ) from e

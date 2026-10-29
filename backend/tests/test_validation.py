import pytest

from app.services.validation import ValidationException, validate_batch_csv, validate_single_payload
from tests.conftest import sample_record


def test_valid_single():
    rec = validate_single_payload(sample_record())
    assert rec["BMI"] == 30


def test_missing_field():
    bad = sample_record()
    del bad["BMI"]
    with pytest.raises(ValidationException) as exc:
        validate_single_payload(bad)
    assert exc.value.code == "VALIDATION_ERROR"


def test_extra_field():
    bad = {**sample_record(), "Diabetes_binary": 1}
    with pytest.raises(ValidationException):
        validate_single_payload(bad)


def test_range_failure():
    bad = sample_record()
    bad["BMI"] = 5
    with pytest.raises(ValidationException):
        validate_single_payload(bad)


def test_boolean_rejected():
    bad = sample_record()
    bad["HighBP"] = True
    with pytest.raises(ValidationException):
        validate_single_payload(bad)


def test_batch_csv_valid():
    header = ",".join(sample_record().keys())
    row = ",".join(str(v) for v in sample_record().values())
    csv_bytes = f"{header}\n{row}\n".encode()
    records = validate_batch_csv(csv_bytes)
    assert len(records) == 1


def test_batch_csv_malformed():
    with pytest.raises(ValidationException) as exc:
        validate_batch_csv(b"not,a,valid\n1,2")
    assert exc.value.code in ("INVALID_INPUT", "VALIDATION_ERROR")

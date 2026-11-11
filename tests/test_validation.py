import pandas as pd
import pytest
from src.validation import validate_frame

def test_valid_and_missing_required():
    df = pd.DataFrame([
        {"source_system":"CRM","source_id":"1","event_id":"e1","event_ts":"2026-01-01T00:00:00Z"},
        {"source_system":"crm","source_id":"","event_id":"e2","event_ts":"2026-01-01T00:00:00Z"}
    ])
    valid, rejects = validate_frame(df)
    assert len(valid) == 1
    assert len(rejects) == 1
    assert rejects[0]["reason"] == "missing_required_field:source_id"

def test_empty_batch():
    df = pd.DataFrame(columns=["source_system","source_id","event_id","event_ts"])
    valid, rejects = validate_frame(df)
    assert valid.empty and rejects == []

def test_schema_change_fails():
    with pytest.raises(ValueError):
        validate_frame(pd.DataFrame([{"source_system":"crm"}]))

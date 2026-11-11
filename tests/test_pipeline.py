
import pandas as pd
from src.pipeline import run_pipeline
from src.database import connect


def test_pipeline_and_rerun(tmp_path):
    input_file = tmp_path / "input.csv"

    pd.DataFrame([
        {
            "source_system": "crm",
            "source_id": "c1",
            "event_id": "e1",
            "event_ts": "2026-01-01T00:00:00Z",
            "email": "a@test.test",
            "phone": "9876543210",
            "name": "A"
        },
        {
            "source_system": "billing",
            "source_id": "b1",
            "event_id": "e2",
            "event_ts": "2026-01-02T00:00:00Z",
            "email": "a@test.test",
            "phone": "9876543210",
            "name": "A"
        }
    ]).to_csv(input_file, index=False)

    config = tmp_path / "config.yaml"

    config.write_text(f'''paths:
  database: {tmp_path / "db.duckdb"}
  input: {input_file}
  output_dir: {tmp_path / "out"}
  quarantine_dir: {tmp_path / "q"}
  reports_dir: {tmp_path / "reports"}
matching:
  exact_fields: [source_system, source_id]
  rule_fields: [email, phone]
  minimum_rule_agreement: 1
''')

    first = run_pipeline(input_file, config, "run-1")
    assert first["mapped_count"] == 2

    second = run_pipeline(input_file, config, "run-2")
    assert second["duplicate_count"] == 2
    assert second["mapped_count"] == 0


def test_failed_run_is_recorded(tmp_path):
    input_file = tmp_path / "missing.csv"
    config = tmp_path / "config.yaml"

    config.write_text(f'''paths:
  database: {tmp_path / "recovery.duckdb"}
  input: {input_file}
  output_dir: {tmp_path / "out"}
  quarantine_dir: {tmp_path / "q"}
  reports_dir: {tmp_path / "reports"}
matching:
  exact_fields: [source_system, source_id]
  rule_fields: [email, phone]
  minimum_rule_agreement: 1
''')

    try:
        run_pipeline(input_file, config, "failed-run-1")
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass

    con = connect(tmp_path / "recovery.duckdb")

    result = con.execute(
        "SELECT status, error_message FROM pipeline_runs WHERE run_id=?",
        ["failed-run-1"]
    ).fetchone()

    con.close()

    assert result is not None
    assert result[0] == "FAILED"
    assert "Input file not found" in result[1]

import duckdb
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id VARCHAR PRIMARY KEY,
    source_file VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status VARCHAR NOT NULL,
    input_count BIGINT DEFAULT 0,
    mapped_count BIGINT DEFAULT 0,
    unresolved_count BIGINT DEFAULT 0,
    rejected_count BIGINT DEFAULT 0,
    duplicate_count BIGINT DEFAULT 0,
    error_message VARCHAR
);
CREATE TABLE IF NOT EXISTS canonical_entities (
    canonical_id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS mapping_history (
    mapping_event_id VARCHAR PRIMARY KEY,
    source_system VARCHAR NOT NULL,
    source_id VARCHAR NOT NULL,
    canonical_id VARCHAR NOT NULL,
    match_type VARCHAR NOT NULL,
    confidence DOUBLE NOT NULL,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP,
    is_current BOOLEAN NOT NULL,
    run_id VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    FOREIGN KEY(canonical_id) REFERENCES canonical_entities(canonical_id)
);
CREATE TABLE IF NOT EXISTS mapping_conflicts (
    conflict_id VARCHAR PRIMARY KEY,
    source_system VARCHAR NOT NULL,
    source_id VARCHAR NOT NULL,
    candidate_canonical_ids VARCHAR NOT NULL,
    reason VARCHAR NOT NULL,
    run_id VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS unresolved_records (
    unresolved_id VARCHAR PRIMARY KEY,
    source_system VARCHAR,
    source_id VARCHAR,
    reason VARCHAR NOT NULL,
    raw_record VARCHAR NOT NULL,
    run_id VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS rejected_records (
    reject_id VARCHAR PRIMARY KEY,
    source_system VARCHAR,
    source_id VARCHAR,
    reason VARCHAR NOT NULL,
    raw_record VARCHAR NOT NULL,
    run_id VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS processed_events (
    event_key VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    processed_at TIMESTAMP NOT NULL
);
"""

def connect(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(DDL)
    return con

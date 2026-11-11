# Entity Resolution & Canonical ID Mapping Pipeline

A local, reproducible Data Engineering project that maps source-system identifiers to stable canonical IDs, detects ambiguous matches, preserves mapping history, quarantines invalid/unresolved records, and records operational metrics.

## Stack

- Python 3.11+
- Pandas for CSV ingestion and row-level transformation
- DuckDB for persistent analytical tables and mapping history
- Pytest for automated tests

## Architecture

CSV source → Schema validation → Exact/rule-based matching → Conflict detection → DuckDB mapping/history tables → CSV outputs and JSON run report.

## Data Model and Grain

- `source_records.csv`: One row per source event. `event_id` is unique within a source system; `source_system + source_id` identifies a source entity.
- `canonical_entities`: One row per canonical entity.
- `mapping_history`: One row per mapping event/version. `is_current=true` identifies the current mapping for a source key.
- `entity_attribute_index`: Normalized email/phone values linked to canonical IDs for deterministic rule matching.
- `mapping_conflicts`: One row per ambiguous source entity and run.
- `unresolved_records`: Traceable records requiring manual review.
- `rejected_records`: Invalid rows with raw payload and reason.
- `pipeline_runs`: One row per execution.

## Matching Rules

1. Exact source key match (`source_system + source_id`) reuses its current canonical ID.
2. Otherwise, normalize email (trim/lowercase) and phone (digits, last 10 digits).
3. If attributes point to exactly one canonical ID, map by rule.
4. If attributes point to multiple canonical IDs, record a conflict and unresolved row; do not guess.
5. If there is no match, create a deterministic canonical ID from source system and source ID.
6. A mapping change closes the prior current history row and inserts a new version.

This is intentionally conservative: one matching normalized attribute is sufficient for a rule match in this demo. Production systems should define authoritative fields, thresholds, survivorship, and manual approval policy with business owners.

## Setup

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Generate Data and Run

Generate a small dataset:

```bash
python scripts/generate_data.py --rows 100 --seed 42
python -m src.pipeline
```

Scale to 100,000 rows:

```bash
python scripts/generate_data.py --rows 100000 --seed 42
python -m src.pipeline
```

Use a different input file:

```bash
python -m src.pipeline --input data/input/source_records.csv
```

## Outputs

- `data/canonical_mapping.duckdb`: Persistent target database.
- `data/output/mapped_<run_id>.csv`: Mapped records for that run.
- `data/quarantine/rejected_<run_id>.csv`: Schema/business validation rejects.
- `data/quarantine/unresolved_<run_id>.csv`: Ambiguous mapping cases.
- `reports/run_<run_id>.json`: Counts and reconciliation report.

## Tests

Run the automated test suite:

```bash
pytest -v
```

The current test suite contains 8 automated tests covering matching, stable ID generation, pipeline reruns, failed-run recording, validation, empty batches, and schema changes.

## Useful SQL

Open the database using Python:

```python
import duckdb

con = duckdb.connect(
    "data/canonical_mapping.duckdb",
    read_only=True
)

print(con.execute("SELECT * FROM pipeline_runs").df())
print(con.execute(
    "SELECT * FROM mapping_history WHERE is_current"
).df())
print(con.execute("SELECT * FROM mapping_conflicts").df())
```

See `src/queries.sql` for additional checks.

## Idempotency, Retries, and Backfills

`processed_events` uses a deterministic hash of `source_system + event_id`. Re-running the same input skips already processed events. A retry can process events that have not yet been recorded. The run ledger records each attempt.

For a backfill, use a new event ID for a genuinely new event; do not mutate event IDs for already processed events.

## Observability and Reconciliation

Every run stores start/end timestamps, status, input count, mapped/unresolved/rejected/duplicate counts, and failure reason.

JSON reports include a reconciliation assertion:

```text
input_count = mapped + unresolved + rejected + duplicates
```

## Performance

The sample generator supports 100k+ rows. The matching engine builds in-memory indexes so lookups are approximately O(1) average per row after index construction.

A reasonable next optimization is bulk-loading and vectorizing normalization/index construction for very large datasets, plus partitioning by source/date.

## Known Limitations and Trade-offs

- This is a local vertical slice, not a distributed orchestration platform.
- Rule matching uses email OR phone; real deployments should define field trust and conflict precedence.
- The source file's `event_id` is treated as immutable and unique within source system.
- The pipeline is designed for append-only event ingestion. Manual mapping overrides and a UI are future extensions.
- Partial failures can leave already processed records in the database; the run ledger records failures, but full transactional rollback is not implemented.
- For production, add transactional batch boundaries, schema versioning, access control, monitoring/alerting, and data retention policies.

## Naming Conventions

All database tables and columns use `snake_case`; timestamps are UTC and stored as timestamp values; IDs are stable SHA-256-derived strings; each output is traceable through `run_id` and `source_file`.
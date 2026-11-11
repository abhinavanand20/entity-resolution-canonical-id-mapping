**# Entity Resolution & Canonical ID Mapping Pipeline**

A local, reproducible Data Engineering project that maps source-system identifiers to stable canonical IDs, detects ambiguous matches, preserves mapping history, quarantines invalid/unresolved records, and records operational metrics.

**## Stack**
\- Python 3.12+
\- Pandas for CSV ingestion and row-level transformation
\- DuckDB for persistent analytical tables and mapping history
\- Pytest for automated tests

**## Architecture**
CSV source -> schema validation -> exact/rule-based matching -> conflict detection -> DuckDB mapping/history tables -> CSV outputs and JSON run report.

**## Data model and grain**
\- \`source_records.csv\`: one row per source event. \`event_id\` is unique within a source system; \`source_system + source_id\` identifies a source entity.
\- \`canonical_entities\`: one row per canonical entity.
\- \`mapping_history\`: one row per mapping event/version. \`is_current=true\` identifies the current mapping for a source key.
\- \`entity_attribute_index\`: normalized email/phone values linked to canonical IDs for deterministic rule matching.
\- \`mapping_conflicts\`: one row per ambiguous source entity and run.
\- \`unresolved_records\`: traceable records requiring manual review.
\- \`rejected_records\`: invalid rows with raw payload and reason.
\- \`pipeline_runs\`: one row per execution.

**## Matching rules**
1\. Exact source key match (\`source_system + source_id\`) reuses its current canonical ID.
2\. Otherwise normalize email (trim/lowercase) and phone (digits, last 10 digits).
3\. If attributes point to exactly one canonical ID, map by rule.
4\. If attributes point to multiple canonical IDs, record a conflict and unresolved row; do not guess.
5\. If there is no match, create a deterministic canonical ID from source system and source ID.
6\. A mapping change closes the prior current history row and inserts a new version.

This is intentionally conservative: one matching normalized attribute is sufficient for a rule match in this demo. Production systems should define authoritative fields, thresholds, survivorship, and manual approval policy with business owners.

**## Setup**
\`\`\`bash
python -m venv .venv
\# Windows:
.venv\\\Scripts\\\activate
\# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
\`\`\`

**## Generate data and run**
\`\`\`bash
python scripts/generate_data.py --rows 100 --seed 42
python -m src.pipeline
\`\`\`
Scale to 100,000 rows:
\`\`\`bash
python scripts/generate_data.py --rows 100000 --seed 42
python -m src.pipeline
\`\`\`
Use a different file:
\`\`\`bash
python -m src.pipeline --input data/input/source_records.csv
\`\`\`

Outputs:
\- \`data/canonical_mapping.duckdb\`: persistent target database
\- \`data/output/mapped\_\<run_id>.csv\`: mapped records for that run
\- \`data/quarantine/rejected\_\<run_id>.csv\`: schema/business validation rejects
\- \`data/quarantine/unresolved\_\<run_id>.csv\`: ambiguous mapping cases
\- \`reports/run\_\<run_id>.json\`: counts and reconciliation

**## Tests**
\`\`\`bash
pytest -q
\`\`\`

**## Useful SQL**
Open the database using Python:
\`\`\`python
import duckdb
con = duckdb.connect("data/canonical_mapping.duckdb", read_only=True)
print(con.execute("SELECT \* FROM pipeline_runs").df())
print(con.execute("SELECT \* FROM mapping_history WHERE is_current").df())
print(con.execute("SELECT \* FROM mapping_conflicts").df())
\`\`\`
See \`src/queries.sql\` for additional checks.

**## Idempotency, retries, and backfills**
\`processed_events\` uses a deterministic hash of \`source_system + event_id\`. Re-running the same input skips already processed events. A retry after a successful partial batch can safely process events not yet recorded. For a backfill, use a new event ID for a genuinely new event; do not mutate event IDs for already processed events. The run ledger records each attempt.

**## Observability and reconciliation**
Every run stores start/end timestamps, status, input count, mapped/unresolved/rejected/duplicate counts, and failure reason. JSON reports include a reconciliation assertion:
\`input_count = mapped + unresolved + rejected + duplicates\`.

**## Performance**
The sample generator supports 100k+ rows. The matching engine builds in-memory indexes so lookups are approximately O(1) average per row after index construction. A reasonable next optimization is bulk-loading and vectorizing normalization/index construction for very large datasets, plus partitioning by source/date.

**## Known limitations and trade-offs**
\- This is a local vertical slice, not a distributed orchestration platform.
\- Rule matching uses email OR phone; real deployments should define field trust and conflict precedence.
\- The source file's \`event_id\` is treated as immutable and unique within source system.
\- The pipeline is designed for append-only event ingestion. Manual mapping overrides and a UI are future extensions.
\- For production, add transactional batch boundaries, schema versioning, access control, monitoring/alerting, and data retention policies.

**## Naming conventions**
All database tables and columns use \`snake_case\`; timestamps are UTC and stored as timestamp values; IDs are stable SHA-256-derived strings; each output is traceable through \`run_id\` and \`source_file\`.
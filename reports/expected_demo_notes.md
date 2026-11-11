# Demo validation checklist

Run `python -m src.pipeline`, then inspect the JSON report.
Expected properties:
- Generator creates 20 ordinary records plus one deliberately invalid record and one repeated event (22 total).
- Invalid row is quarantined with `missing_required_field:source_id`.
- The repeated event is counted as a duplicate if its first occurrence was processed in the same run.
- Cross-source records with shared email/phone are rule-matched when a unique canonical candidate exists.
- Re-running the same input produces zero newly mapped records and counts previously processed events as duplicates.

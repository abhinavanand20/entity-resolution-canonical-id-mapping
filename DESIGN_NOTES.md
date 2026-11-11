# Design Notes — Entity Resolution and Canonical ID Mapping

## 1. Objective

The objective is to build a reproducible data engineering pipeline that processes records from multiple source systems and maps them to canonical entity IDs.

The pipeline supports validation, matching, duplicate detection, conflict handling, mapping history, quarantine, and run-level reconciliation.

## 2. Technology Stack

- Python 3.11
- DuckDB
- Pandas
- Pytest
- SQL
- YAML configuration

## 3. Pipeline Architecture

The pipeline follows these stages:

1. **Ingestion:** Read source records from CSV files.
2. **Validation:** Check required fields and record validity.
3. **Quarantine:** Separate invalid records and capture rejection reasons.
4. **Matching:** Apply exact source-key matching and email/phone-based matching.
5. **Conflict Detection:** Identify cases where multiple canonical candidates exist.
6. **Mapping:** Assign or reuse canonical IDs.
7. **Persistence:** Store mappings, processing history, and run information in DuckDB.
8. **Outputs:** Generate mapped records, rejected records, and JSON run reports.

## 4. Matching Strategy

The implementation uses the following matching approach:

- Normalize email addresses using lowercase conversion and whitespace trimming.
- Normalize phone numbers by retaining digits and using the last 10 digits when at least 10 digits are available.
- Check an exact source-key match first.
- If no exact match exists, identify candidates using normalized email and phone information.
- If exactly one canonical candidate exists, apply a rule-based match.
- If multiple candidates exist, mark the record as a conflict.
- If no candidate exists, generate a new stable canonical ID.

Rule-based matches use a confidence value of 0.95 in the current implementation.

## 5. Duplicate and Idempotency Handling

Processed event keys are checked to identify previously processed events.

When the same input is processed again, previously processed events are counted as duplicates instead of creating new mappings.

This behaviour was verified through sample reruns.

## 6. Data Quality and Reconciliation

The pipeline records input, valid, mapped, unresolved, rejected, and duplicate counts.

The reconciliation condition is:

Input Count = Mapped Count + Unresolved Count + Rejected Count + Duplicate Count

The JSON report records whether this condition is satisfied.

## 7. Testing

The automated test suite contains 8 tests covering:

- Email-based rule matching.
- Multiple-candidate conflict detection.
- Stable canonical ID generation.
- Pipeline execution and rerun behaviour.
- Failed-run recording.
- Required-field validation.
- Empty batch handling.
- Schema validation.

Latest recorded result: 8 tests passed.

## 8. Performance Benchmark

A generated dataset containing 100,002 input rows was processed successfully.

Recorded benchmark:
- Input records: 100,002
- Valid records: 100,001
- Mapped records: 99,980
- Unresolved records: 0
- Rejected records: 1
- Duplicate records: 21
- Reconciliation: Passed
- Elapsed time: 34 minutes 48 seconds

The benchmark was executed in a local development environment. Execution time may vary depending on hardware and system conditions.

## 9. Design Trade-offs and Limitations

- The current implementation uses row-by-row database operations, which can increase processing time for large datasets.
- Full transaction rollback for partially processed runs is not implemented.
- An interruption during processing may leave partial records in the database.
- Matching is based on deterministic exact-key and normalized email/phone rules; it does not implement probabilistic or machine-learning-based entity matching.
- The current confidence values are rule-based indicators, not statistically calibrated probabilities.

## 10. Future Improvements

- Optimize database operations using batch inserts and bulk processing.
- Introduce transaction management and rollback for safer recovery.
- Add more comprehensive recovery and partial-failure tests.
- Improve observability with structured logs and detailed run metrics.
- Add configurable matching rules and thresholds.
- Explore scalable matching strategies for larger datasets.

## 11. Reproducibility

The project includes a sample input dataset, generated output examples, a JSON run report, and a data generator for larger datasets.

Refer to README.md for setup and execution instructions.
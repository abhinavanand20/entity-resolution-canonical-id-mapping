-- Current source-to-canonical mappings
SELECT source_system, source_id, canonical_id, match_type, confidence, valid_from
FROM mapping_history WHERE is_current = TRUE;

-- Conflicts and unresolved mappings
SELECT * FROM mapping_conflicts ORDER BY created_at DESC;
SELECT * FROM unresolved_records ORDER BY created_at DESC;

-- Operational run summary
SELECT run_id, status, input_count, mapped_count, unresolved_count,
       rejected_count, duplicate_count, error_message
FROM pipeline_runs ORDER BY started_at DESC;

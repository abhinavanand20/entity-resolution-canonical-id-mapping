import hashlib
import re
from collections import defaultdict

def normalize_email(value):
    return str(value).strip().lower() if value else None

def normalize_phone(value):
    digits = re.sub(r"\D", "", str(value)) if value else ""
    return digits[-10:] if len(digits) >= 10 else None

def stable_id(namespace, value):
    digest = hashlib.sha256(f"{namespace}|{value}".encode()).hexdigest()[:20]
    return f"{namespace}_{digest}"

def build_existing_indexes(con):
    """Build deterministic indexes from current mapping history and entity attributes."""
    rows = con.execute("""
        SELECT h.source_system, h.source_id, h.canonical_id
        FROM mapping_history h WHERE h.is_current = TRUE
    """).fetchall()
    source_map = {(s, sid): cid for s, sid, cid in rows}
    # A canonical ID is also inferred from normalized attributes of source records
    # retained in the mapping ledger via entity_attribute_index.
    attr_rows = con.execute("""
        SELECT normalized_value, canonical_id, field_name
        FROM entity_attribute_index
    """).fetchall() if con.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name='entity_attribute_index'
    """).fetchone()[0] else []
    attr_index = defaultdict(set)
    for value, cid, field in attr_rows:
        attr_index[(field, value)].add(cid)
    return source_map, attr_index

def ensure_attribute_table(con):
    con.execute("""
    CREATE TABLE IF NOT EXISTS entity_attribute_index (
        field_name VARCHAR NOT NULL,
        normalized_value VARCHAR NOT NULL,
        canonical_id VARCHAR NOT NULL,
        PRIMARY KEY(field_name, normalized_value, canonical_id)
    )
    """)

def match_record(record, source_map, attr_index):
    key = (record["source_system"], record["source_id"])
    if key in source_map:
        return source_map[key], "exact", 1.0, []
    candidates = set()
    email = normalize_email(record.get("email"))
    phone = normalize_phone(record.get("phone"))
    if email:
        candidates |= attr_index.get(("email", email), set())
    if phone:
        candidates |= attr_index.get(("phone", phone), set())
    if len(candidates) == 1:
        return next(iter(candidates)), "rule", 0.95, []
    if len(candidates) > 1:
        return None, "conflict", 0.0, sorted(candidates)
    # No match: deterministic new entity ID based on source identity.
    canonical_id = stable_id("can", f'{record["source_system"]}|{record["source_id"]}')
    return canonical_id, "new", 1.0, []

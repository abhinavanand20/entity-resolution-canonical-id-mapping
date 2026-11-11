import json
import pandas as pd

REQUIRED = ["source_system", "source_id", "event_id", "event_ts"]
OPTIONAL = ["email", "phone", "name"]

def validate_frame(df):
    """Return (valid dataframe, rejects dataframe); no invalid row is silently dropped."""
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Unexpected schema: missing required columns {missing}")
    for col in OPTIONAL:
        if col not in df.columns:
            df[col] = None
    valid_rows, rejects = [], []
    for _, row in df.iterrows():
        record = row.to_dict()
        reason = None
        for col in REQUIRED:
            value = record.get(col)
            if pd.isna(value) or str(value).strip() == "":
                reason = f"missing_required_field:{col}"
                break
        if reason is None:
            try:
                pd.to_datetime(record["event_ts"], utc=True, errors="raise")
            except Exception:
                reason = "invalid_event_ts"
        if reason:
            rejects.append({"record": record, "reason": reason})
        else:
            record["source_system"] = str(record["source_system"]).strip().lower()
            record["source_id"] = str(record["source_id"]).strip()
            record["event_id"] = str(record["event_id"]).strip()
            record["event_ts"] = pd.to_datetime(record["event_ts"], utc=True).tz_convert(None)
            for c in OPTIONAL:
                if pd.isna(record.get(c)):
                    record[c] = None
                elif isinstance(record.get(c), str):
                    record[c] = record[c].strip() or None
            valid_rows.append(record)
    return pd.DataFrame(valid_rows), rejects

def raw_json(record):
    return json.dumps(record, default=str, sort_keys=True)

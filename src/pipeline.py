import argparse, hashlib, json, logging, time, uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from .config import load_config
from .database import connect
from .validation import validate_frame, raw_json
from .matching import (build_existing_indexes, ensure_attribute_table,
                       match_record, normalize_email, normalize_phone, stable_id)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("canonical_mapping")

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def run_pipeline(input_path=None, config_path=None, run_id=None):
    cfg = load_config(config_path)
    input_path = Path(input_path) if input_path else cfg["paths"]["input"]
    db_path = cfg["paths"]["database"]
    for key in ("output_dir", "quarantine_dir", "reports_dir"):
        cfg["paths"][key].mkdir(parents=True, exist_ok=True)
    run_id = run_id or str(uuid.uuid4())
    started = _now()
    con = connect(db_path)
    source_file = str(input_path.name)
    con.execute("""INSERT INTO pipeline_runs(run_id,source_file,started_at,status)
                   VALUES (?, ?, ?, 'RUNNING')""", [run_id, source_file, started])
    try:
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
        input_count = len(df)
        valid, rejects = validate_frame(df)
        ensure_attribute_table(con)
        source_map, attr_index = build_existing_indexes(con)
        mapped_rows, unresolved, conflicts = [], [], []
        duplicate_count = 0
        for record in valid.to_dict("records"):
            event_key = stable_id("evt", f'{record["source_system"]}|{record["event_id"]}')
            if con.execute("SELECT 1 FROM processed_events WHERE event_key=?", [event_key]).fetchone():
                duplicate_count += 1
                continue
            cid, match_type, confidence, candidates = match_record(record, source_map, attr_index)
            if match_type == "conflict":
                conflicts.append((record, candidates))
                unresolved.append((record, "one_to_many_candidate_conflict"))
                # Record event as processed to make the same batch retry idempotent.
                con.execute("INSERT INTO processed_events VALUES (?, ?, ?)", [event_key, run_id, _now()])
                continue
            if match_type == "new":
                con.execute("INSERT INTO canonical_entities VALUES (?, ?) ON CONFLICT DO NOTHING", [cid, _now()])
            # If source key has a current mapping to a different ID, close it before inserting history.
            old = con.execute("""SELECT canonical_id FROM mapping_history
                                 WHERE source_system=? AND source_id=? AND is_current=TRUE
                                 ORDER BY valid_from DESC LIMIT 1""",
                              [record["source_system"], record["source_id"]]).fetchone()
            if old and old[0] != cid:
                con.execute("""UPDATE mapping_history SET is_current=FALSE, valid_to=?
                               WHERE source_system=? AND source_id=? AND is_current=TRUE""",
                            [_now(), record["source_system"], record["source_id"]])
            existing_same_event = con.execute("SELECT 1 FROM processed_events WHERE event_key=?", [event_key]).fetchone()
            if not existing_same_event:
                mapping_event_id = stable_id("map", f'{event_key}|{cid}')
                # Keep event history; only one current row per source key.
                con.execute("""INSERT INTO mapping_history VALUES (?, ?, ?, ?, ?, ?, ?, NULL, TRUE, ?, ?)
                               ON CONFLICT DO NOTHING""",
                            [mapping_event_id, record["source_system"], record["source_id"], cid,
                             match_type, confidence, record["event_ts"], run_id, source_file])
                for field, value in (("email", normalize_email(record.get("email"))),
                                     ("phone", normalize_phone(record.get("phone")))):
                    if value:
                        con.execute("""INSERT INTO entity_attribute_index VALUES (?, ?, ?)
                                       ON CONFLICT DO NOTHING""", [field, value, cid])
                con.execute("INSERT INTO processed_events VALUES (?, ?, ?)", [event_key, run_id, _now()])
            source_map[(record["source_system"], record["source_id"])] = cid
            for field, value in (("email", normalize_email(record.get("email"))),
                                 ("phone", normalize_phone(record.get("phone")))):
                if value:
                    attr_index[(field, value)].add(cid)
            mapped_rows.append({**record, "canonical_id": cid, "match_type": match_type,
                                "confidence": confidence, "run_id": run_id, "source_file": source_file})
        for record, candidates in conflicts:
            con.execute("INSERT INTO mapping_conflicts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        [stable_id("conf", run_id + "|" + record["source_system"] + "|" + record["source_id"]),
                         record["source_system"], record["source_id"], json.dumps(candidates),
                         "multiple canonical candidates matched", run_id, source_file, _now()])
        for record, reason in unresolved:
            con.execute("INSERT INTO unresolved_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        [stable_id("unres", run_id + "|" + record["source_system"] + "|" + record["source_id"]),
                         record["source_system"], record["source_id"], reason, raw_json(record),
                         run_id, source_file, _now()])
        for item in rejects:
            record = item["record"]
            con.execute("INSERT INTO rejected_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        [stable_id("rej", run_id + "|" + raw_json(record)),
                         record.get("source_system"), record.get("source_id"), item["reason"],
                         raw_json(record), run_id, source_file, _now()])
        mapped_df = pd.DataFrame(mapped_rows)
        if not mapped_df.empty:
            mapped_df.to_csv(cfg["paths"]["output_dir"] / f"mapped_{run_id}.csv", index=False)
        if rejects:
            pd.DataFrame([{"reason": x["reason"], **x["record"]} for x in rejects]).to_csv(
                cfg["paths"]["quarantine_dir"] / f"rejected_{run_id}.csv", index=False)
        if unresolved:
            pd.DataFrame([{"reason": reason, **record} for record, reason in unresolved]).to_csv(
                cfg["paths"]["quarantine_dir"] / f"unresolved_{run_id}.csv", index=False)
        mapped_count = len(mapped_rows)
        unresolved_count = len(unresolved)
        rejected_count = len(rejects)
        finished = _now()
        con.execute("""UPDATE pipeline_runs SET finished_at=?,status='SUCCESS',input_count=?,
                       mapped_count=?,unresolved_count=?,rejected_count=?,duplicate_count=?
                       WHERE run_id=?""",
                    [finished, input_count, mapped_count, unresolved_count, rejected_count, duplicate_count, run_id])
        report = {
            "run_id": run_id, "status": "SUCCESS", "source_file": source_file,
            "started_at": started.isoformat() + "Z", "finished_at": finished.isoformat() + "Z",
            "input_count": input_count, "valid_count": len(valid), "mapped_count": mapped_count,
            "unresolved_count": unresolved_count, "rejected_count": rejected_count,
            "duplicate_count": duplicate_count,
            "reconciliation": {"input_equals_mapped_plus_unresolved_plus_rejected_plus_duplicates":
                input_count == mapped_count + unresolved_count + rejected_count + duplicate_count}
        }
        report_path = cfg["paths"]["reports_dir"] / f"run_{run_id}.json"
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        log.info("Run %s complete: %s", run_id, report)
        return report
    except Exception as exc:
        con.execute("""UPDATE pipeline_runs SET finished_at=?,status='FAILED',error_message=?
                       WHERE run_id=?""", [_now(), str(exc), run_id])
        log.exception("Pipeline run %s failed", run_id)
        raise
    finally:
        con.close()

def main():
    parser = argparse.ArgumentParser(description="Canonical ID mapping pipeline")
    parser.add_argument("--input", help="Input CSV path")
    parser.add_argument("--config", help="YAML config path")
    parser.add_argument("--run-id", help="Optional stable run ID")
    args = parser.parse_args()
    print(json.dumps(run_pipeline(args.input, args.config, args.run_id), indent=2))

if __name__ == "__main__":
    main()

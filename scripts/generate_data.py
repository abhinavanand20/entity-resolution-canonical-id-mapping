import argparse, csv, random
from pathlib import Path
from datetime import datetime, timedelta, timezone

def generate(path, rows=100, seed=42):
    random.seed(seed)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    first = ["Asha", "Ravi", "Neha", "Arjun", "Meera", "Kabir", "Isha", "Dev"]
    last = ["Sharma", "Kumar", "Singh", "Patel", "Rao", "Das"]
    records = []
    for i in range(rows):
        n = i + 1
        name = f"{random.choice(first)} {random.choice(last)}"
        email = f"person{n}@example.test"
        phone = f"+91-98{n % 100000000:08d}"
        source = "crm" if i % 2 == 0 else "billing"
        source_id = f"{source.upper()}-{n:07d}"
        # Rule-based cross-system duplicates: billing rows share email with preceding CRM entity.
        if source == "billing":
            email = f"person{n-1}@example.test"
            phone = f"+91-98{(n-1) % 100000000:08d}"
        records.append({
            "source_system": source, "source_id": source_id, "event_id": f"event-{n:08d}",
            "event_ts": (datetime.now(timezone.utc)-timedelta(minutes=n)).isoformat(),
            "email": email, "phone": phone, "name": name
        })
    # Deliberate invalid row and duplicate event for edge-case coverage.
    if rows >= 10:
        bad = dict(records[0]); bad["source_id"] = ""; bad["event_id"] = "event-invalid"
        records.append(bad)
        records.append(dict(records[1]))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source_system","source_id","event_id","event_ts","email","phone","name"])
        writer.writeheader(); writer.writerows(records)
    print(f"Generated {len(records)} rows at {path}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="data/input/source_records.csv")
    a = p.parse_args(); generate(a.output, a.rows, a.seed)

from src.matching import match_record, stable_id

def test_rule_match_email():
    record = {"source_system":"billing","source_id":"b1","email":"X@EXAMPLE.COM","phone":None}
    cid, kind, confidence, conflicts = match_record(record, {}, {("email","x@example.com"):{"can_1"}})
    assert (cid, kind, confidence, conflicts) == ("can_1","rule",0.95,[])

def test_conflict_two_candidates():
    record = {"source_system":"billing","source_id":"b1","email":"x@example.com","phone":None}
    cid, kind, _, candidates = match_record(record, {}, {("email","x@example.com"):{"can_1","can_2"}})
    assert cid is None and kind == "conflict" and len(candidates) == 2

def test_stable_id():
    assert stable_id("can","crm|1") == stable_id("can","crm|1")

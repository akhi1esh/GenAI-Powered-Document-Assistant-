import json

from docassist.llm import MockProvider
from docassist.pipeline import extract_record, parse_json, validate_output

DOC = """SERVICE REPORT #SR-1001
Date of visit: 14 March 2025
Customer: Northwind Cold Storage
Unit: Compressor CMP-220 (Asset ID A-4471)
Tech: R. Patel
Notes:
Customer reported loud rattling and intermittent shutdown. Replaced drive belt (P/N BLT-88, qty 1) and capacitor (P/N CAP-12, qty 2). Cleaned condenser coils. Labor 3.5 hrs. Total cost $412.50. Severity: high. Recommend follow-up inspection by 14 June 2025."""


def test_parse_json_handles_fences_and_prose():
    assert parse_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}


def test_clean_extraction_valid():
    res = extract_record(DOC, MockProvider(flaky=0))
    assert res.ok and res.attempts == 1
    assert res.record.total_cost == 412.50 and len(res.record.parts_replaced) == 2


def test_bad_enum_and_date_rejected():
    good = json.loads(MockProvider().complete("", "TASK: extract\n<<<" + DOC + ">>>"))
    good["severity"], good["service_date"] = "urgent", "14/03/2025"
    rec, errs = validate_output(json.dumps(good), DOC)
    assert rec is None and any("severity" in e for e in errs) and any("service_date" in e for e in errs)


def test_hallucinated_part_number_caught():
    good = json.loads(MockProvider().complete("", "TASK: extract\n<<<" + DOC + ">>>"))
    good["parts_replaced"].append({"name": "Gasket", "part_number": "GSK-999", "quantity": 1})
    rec, errs = validate_output(json.dumps(good), DOC)
    assert rec is None and any("GSK-999" in e for e in errs)


def test_repair_loop_recovers():
    res = extract_record(DOC, MockProvider(flaky=1.0, seed=3))  # always wrong on 1st try
    assert res.ok and res.attempts >= 2 and res.error_history

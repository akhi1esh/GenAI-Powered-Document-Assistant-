"""Measure extraction quality: baseline (single pass, no validation) vs. validated pipeline.

Usage:
  python scripts/evaluate.py --provider mock --flaky 0.35      # offline simulation
  python scripts/evaluate.py --provider anthropic              # real LLM numbers for your resume
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docassist import prompts  # noqa: E402
from docassist.llm import get_provider  # noqa: E402
from docassist.pdf_extract import extract_pdf_text  # noqa: E402
from docassist.pipeline import extract_record, parse_json  # noqa: E402

FIELDS = ["report_id", "service_date", "customer_name", "asset_id", "asset_type", "technician",
          "issue_description", "parts_replaced", "labor_hours", "total_cost", "severity",
          "follow_up_required", "follow_up_date"]


def norm(v):
    return json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else str(v).strip().lower()


def field_errors(pred: dict | None, truth: dict) -> int:
    if pred is None:
        return len(FIELDS)
    errs = 0
    for f in FIELDS:
        a, b = pred.get(f), truth.get(f)
        if f == "parts_replaced":
            a = sorted((p.get("part_number"), p.get("quantity")) for p in (a or []))
            b = sorted((p["part_number"], p["quantity"]) for p in b)
        if f in ("labor_hours", "total_cost"):
            try:
                a, b = round(float(a), 2), round(float(b), 2)
            except (TypeError, ValueError):
                errs += 1
                continue
        errs += norm(a) != norm(b)
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/samples")
    ap.add_argument("--provider", default="mock")
    ap.add_argument("--flaky", type=float, default=0.35, help="mock only: first-pass error rate")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    kw = {"flaky": a.flaky} if a.provider == "mock" else {}
    pdfs = sorted(Path(a.dir).glob("*.pdf"))[: a.limit or None]
    base_p, val_p = get_provider(a.provider, **kw), get_provider(a.provider, **kw)
    if a.provider == "mock":  # same seed -> identical first-pass mistakes for a fair comparison
        base_p.rng.seed(1); val_p.rng.seed(1)

    b_doc_err = v_doc_err = b_fld = v_fld = retries = 0
    t_b = t_v = 0.0
    for pdf in pdfs:
        truth = json.loads(pdf.with_suffix(".truth.json").read_text())
        text = extract_pdf_text(pdf).text

        t0 = time.time()
        raw = base_p.complete(prompts.SYSTEM, prompts.extraction_prompt(text))
        t_b += time.time() - t0
        try:
            pred = parse_json(raw)
        except Exception:
            pred = None
        e = field_errors(pred, truth); b_fld += e; b_doc_err += e > 0

        t0 = time.time()
        res = extract_record(text, val_p)
        t_v += time.time() - t0
        pred2 = json.loads(res.record.model_dump_json()) if res.record else None
        e = field_errors(pred2, truth); v_fld += e; v_doc_err += e > 0
        retries += res.attempts - 1

    n, nf = len(pdfs), len(pdfs) * len(FIELDS)
    red = lambda b, v: (100 * (b - v) / b) if b else 0.0
    print(f"\nDocuments evaluated: {n}   provider: {a.provider}")
    print(f"{'':28}{'Baseline':>12}{'Validated':>12}")
    print(f"{'Docs with >=1 field error':28}{b_doc_err:>12}{v_doc_err:>12}")
    print(f"{'Field-level error rate':28}{100*b_fld/nf:>11.1f}%{100*v_fld/nf:>11.1f}%")
    print(f"{'Repair retries used':28}{'-':>12}{retries:>12}")
    print(f"\nError reduction (docs):   {red(b_doc_err, v_doc_err):.0f}%")
    print(f"Error reduction (fields): {red(b_fld, v_fld):.0f}%")
    if a.provider == "mock":
        print("\nNOTE: mock + injected faults is a simulation. Run with --provider anthropic for real figures.")


if __name__ == "__main__":
    main()

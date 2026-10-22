"""CLI:  python -m docassist.cli extract <pdf|dir> [--provider mock|anthropic] [--out out.json] [--generate]"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .generate import customer_email, summarize
from .llm import get_provider
from .pipeline import extract_from_pdf


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="docassist", description="GenAI document assistant")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract", help="extract structured JSON from PDF(s)")
    ex.add_argument("path", help="a PDF file or a directory of PDFs")
    ex.add_argument("--provider", default="mock", choices=["mock", "anthropic"])
    ex.add_argument("--out", help="write results JSON here (default: stdout)")
    ex.add_argument("--retries", type=int, default=2)
    ex.add_argument("--workers", type=int, default=4)
    ex.add_argument("--generate", action="store_true", help="also create a summary + customer email")
    ex.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO if a.verbose else logging.ERROR, format="%(message)s")
    provider = get_provider(a.provider)
    p = Path(a.path)
    files = sorted(p.glob("*.pdf")) if p.is_dir() else [p]
    if not files:
        print("no PDFs found", file=sys.stderr)
        return 1

    def work(f: Path) -> dict:
        try:
            r = extract_from_pdf(f, provider, a.retries)
        except Exception as e:  # unreadable PDF etc.
            return {"source": f.name, "ok": False, "errors": [str(e)]}
        out = {"source": f.name, "ok": r.ok, "attempts": r.attempts,
               "data": json.loads(r.record.model_dump_json()) if r.record else None,
               "errors": r.error_history}
        if r.record and a.generate:
            out["summary"] = summarize(r.record, provider)
            out["customer_email"] = customer_email(r.record, provider)
        return out

    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        results = list(pool.map(work, files))

    text = json.dumps(results if len(results) > 1 else results[0], indent=2)
    if a.out:
        Path(a.out).write_text(text)
    else:
        print(text)
    ok = sum(r["ok"] for r in results)
    print(f"\n{ok}/{len(results)} documents extracted and validated", file=sys.stderr)
    return 0 if ok == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())

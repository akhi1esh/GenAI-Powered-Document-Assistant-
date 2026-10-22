"""LLM provider abstraction: real Anthropic API + deterministic offline mock."""
from __future__ import annotations

import json
import os
import random
import re
from typing import Protocol


class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class AnthropicProvider:
    """Thin wrapper over the Anthropic Messages API (needs ANTHROPIC_API_KEY)."""

    def __init__(self, model: str | None = None, max_tokens: int = 2000):
        import anthropic  # imported lazily so the mock works without the SDK/key

        self.client = anthropic.Anthropic()
        self.model = model or os.getenv("DOCASSIST_MODEL", "claude-sonnet-4-6")
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        resp = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, temperature=0,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")


# --------------------------------------------------------------------------- #
# Offline mock: regex "LLM" so the whole pipeline runs without an API key.
# flaky=True simulates typical LLM mistakes on the FIRST attempt only, so the
# validation/repair loop has something to fix. It is a simulation, not a result.
# --------------------------------------------------------------------------- #
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}


def _iso(day: str, month: str, year: str) -> str:
    return f"{int(year):04d}-{_MONTHS[month.lower()]:02d}-{int(day):02d}"


def _mock_extract(raw_doc: str) -> dict:
    doc = raw_doc                                  # header fields are line-based
    flat = re.sub(r"\s+", " ", raw_doc)            # body is wrapped text
    g = lambda pat, text=doc: (re.search(pat, text) or [None, None])[1]
    d = re.search(r"Date of visit:\s*(\d{1,2}) (\w+) (\d{4})", flat)
    fu = re.search(r"follow-?up (?:inspection )?by (\d{1,2}) (\w+) (\d{4})", flat, re.I)
    rep = re.search(r"Replaced (.*?\(P/N[^.]*)\.", flat)
    parts = [
        {"name": n.strip(), "part_number": pn, "quantity": int(q)}
        for n, pn, q in re.findall(r"([A-Za-z ]+?) \(P/N ([\w-]+), qty (\d+)\)", re.sub(r" and ", "  ", rep.group(1) + ".")) 
    ] if rep else []
    other = re.findall(r"((?:Cleaned|Tightened|Recalibrated|Flushed|Lubricated) [^.]+)\.", flat)
    actions = [f"Replaced {p['name']}" for p in parts] + [a.strip() for a in other]
    return {
        "report_id": g(r"SERVICE REPORT #([\w-]+)"),
        "service_date": _iso(*d.groups()) if d else None,
        "customer_name": g(r"Customer:\s*(.+)"),
        "asset_id": g(r"Asset ID ([\w-]+)"),
        "asset_type": g(r"Unit:\s*([A-Za-z ]+?) [A-Z]{2,4}-\d+"),
        "technician": g(r"Tech:\s*(.+)"),
        "issue_description": g(r"Customer reported (.+?)\.", flat),
        "actions_taken": actions or None,
        "parts_replaced": parts,
        "labor_hours": float(g(r"Labor ([\d.]+) hrs", flat) or 0),
        "total_cost": float((g(r"Total cost \$([\d,]+\.\d{2})", flat) or "0").replace(",", "")),
        "severity": (g(r"Severity:\s*(\w+)", flat) or "").lower(),
        "follow_up_required": fu is not None,
        "follow_up_date": _iso(*fu.groups()) if fu else None,
    }


def _corrupt(rec: dict, rng: random.Random) -> dict:
    """Inject one realistic LLM mistake."""
    rec = json.loads(json.dumps(rec))
    kind = rng.choice(["date_format", "severity", "cost_symbol", "bad_followup", "fake_part"])
    if kind == "date_format" and rec.get("service_date"):
        y, m, d = rec["service_date"].split("-")
        rec["service_date"] = f"{d}/{m}/{y}"
    elif kind == "severity":
        rec["severity"] = rng.choice(["urgent", "moderate", "severe"])
    elif kind == "cost_symbol":
        rec["total_cost"] = f"${rec['total_cost']}"
    elif kind == "bad_followup" and rec.get("follow_up_date"):
        rec["follow_up_date"] = "2020-01-01"
    else:  # hallucinated part number (caught by the grounding check)
        rec["parts_replaced"] = rec["parts_replaced"] + [
            {"name": "Gasket", "part_number": "GSK-999", "quantity": 1}]
    return rec


class MockProvider:
    def __init__(self, flaky: float = 0.0, seed: int = 0):
        self.flaky = flaky
        self.rng = random.Random(seed)

    def complete(self, system: str, user: str) -> str:
        task = user.split("\n", 1)[0].replace("TASK:", "").strip()
        if task in ("extract", "repair"):
            doc = user.split("<<<", 1)[1].rsplit(">>>", 1)[0]
            rec = _mock_extract(doc)
            if task == "extract" and self.rng.random() < self.flaky:
                rec = _corrupt(rec, self.rng)
            return json.dumps(rec)
        rec = json.loads(user.split("RECORD:", 1)[1])
        if task == "summary":
            return (f"On {rec['service_date']}, {rec['technician']} serviced {rec['asset_type']} "
                    f"{rec['asset_id']} for {rec['customer_name']} after a report of {rec['issue_description']}. "
                    f"Actions: {'; '.join(rec['actions_taken'])}. "
                    f"{'Follow-up due ' + rec['follow_up_date'] + '.' if rec['follow_up_date'] else 'No follow-up needed.'}")
        return (f"Subject: Service report {rec['report_id']}\n\nHi {rec['customer_name']} team,\n\n"
                f"We serviced {rec['asset_id']} on {rec['service_date']}. Issue: {rec['issue_description']}. "
                f"Work done: {'; '.join(rec['actions_taken'])}. Total: ${rec['total_cost']:.2f}.\n\nRegards,\n{rec['technician']}")


def get_provider(name: str, **kw) -> LLMProvider:
    if name == "anthropic":
        return AnthropicProvider(**kw)
    if name == "mock":
        return MockProvider(**kw)
    raise ValueError(f"unknown provider: {name}")

"""Extraction pipeline: PDF -> prompt -> LLM -> parse -> validate -> (repair loop)."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from . import prompts
from .llm import LLMProvider
from .pdf_extract import extract_pdf_text
from .schemas import ServiceRecord

log = logging.getLogger("docassist")


@dataclass
class ExtractionResult:
    source: str
    record: Optional[ServiceRecord]
    attempts: int
    error_history: list[list[str]] = field(default_factory=list)
    raw_output: str = ""

    @property
    def ok(self) -> bool:
        return self.record is not None


def parse_json(text: str) -> dict:
    """Tolerant JSON parsing: strips code fences / stray prose around the object."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in model output")
    return json.loads(text[start : end + 1])


def grounding_errors(rec: ServiceRecord, source_text: str) -> list[str]:
    """Anti-hallucination check: identifiers must literally appear in the source."""
    hay = source_text.lower()
    errs = []
    if rec.asset_id.lower() not in hay:
        errs.append(f"asset_id '{rec.asset_id}' not found in document")
    if rec.report_id.lower() not in hay:
        errs.append(f"report_id '{rec.report_id}' not found in document")
    for p in rec.parts_replaced:
        if p.part_number and p.part_number.lower() not in hay:
            errs.append(f"part_number '{p.part_number}' not found in document")
    return errs


def validate_output(raw: str, source_text: str) -> tuple[Optional[ServiceRecord], list[str]]:
    """Return (record, errors). record is None when any error exists."""
    try:
        data = parse_json(raw)
    except (ValueError, json.JSONDecodeError) as e:
        return None, [f"output is not valid JSON: {e}"]
    try:
        rec = ServiceRecord.model_validate(data)
    except ValidationError as e:
        return None, [f"{'.'.join(map(str, x['loc'])) or 'record'}: {x['msg']}" for x in e.errors()]
    errs = grounding_errors(rec, source_text)
    return (None, errs) if errs else (rec, [])


def extract_record(text: str, provider: LLMProvider, max_retries: int = 2,
                   source: str = "<text>") -> ExtractionResult:
    """Extract + validate; on failure, feed the errors back to the LLM for repair."""
    raw = provider.complete(prompts.SYSTEM, prompts.extraction_prompt(text))
    history: list[list[str]] = []
    for attempt in range(1, max_retries + 2):
        rec, errs = validate_output(raw, text)
        if rec:
            return ExtractionResult(source, rec, attempt, history, raw)
        history.append(errs)
        log.warning("%s attempt %d failed validation: %s", source, attempt, errs)
        if attempt > max_retries:
            break
        raw = provider.complete(prompts.SYSTEM, prompts.repair_prompt(text, raw, errs))
    return ExtractionResult(source, None, max_retries + 1, history, raw)


def extract_from_pdf(path: str | Path, provider: LLMProvider, max_retries: int = 2) -> ExtractionResult:
    doc = extract_pdf_text(path)
    return extract_record(doc.text, provider, max_retries, source=str(path))

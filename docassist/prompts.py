"""Prompt templates. The TASK marker on line 1 also lets the offline mock route requests."""
import json

from .schemas import ServiceRecord

SYSTEM = (
    "You are a precise data-extraction engine for service and maintenance reports. "
    "Return ONLY a single JSON object. No prose, no markdown fences. "
    "Never invent values: if a required value is absent from the document, use null."
)

_SCHEMA = json.dumps(ServiceRecord.model_json_schema(), indent=1)

EXTRACT = """TASK: extract
Extract the service record from the document below into JSON matching this JSON Schema.

RULES
- Dates must be ISO-8601 (YYYY-MM-DD).
- severity must be one of: low, medium, high, critical.
- Numbers must be plain numbers (no currency symbols or units).
- Copy identifiers and part numbers exactly as written.

SCHEMA
{schema}

DOCUMENT
<<<
{document}
>>>
"""

REPAIR = """TASK: repair
Your previous JSON output failed validation. Fix ONLY the problems listed and return the corrected JSON object.

VALIDATION ERRORS
{errors}

PREVIOUS OUTPUT
{previous}

SCHEMA
{schema}

DOCUMENT
<<<
{document}
>>>
"""

SUMMARY = """TASK: summary
Write a 2-3 sentence plain-English summary of this service record for an operations manager.
Mention the problem, the fix, and any follow-up. Do not add facts not in the record.

RECORD:
{record}
"""

EMAIL = """TASK: email
Draft a short, professional email to the customer summarising the completed service visit.
Include: what was found, what was done, cost, and next steps. Use only facts from the record.

RECORD:
{record}
"""


def extraction_prompt(document: str) -> str:
    return EXTRACT.format(schema=_SCHEMA, document=document)


def repair_prompt(document: str, previous: str, errors: list[str]) -> str:
    return REPAIR.format(
        schema=_SCHEMA, document=document, previous=previous,
        errors="\n".join(f"- {e}" for e in errors),
    )

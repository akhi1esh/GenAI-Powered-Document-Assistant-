"""Content generation from validated records."""
from . import prompts
from .llm import LLMProvider
from .schemas import ServiceRecord


def summarize(rec: ServiceRecord, provider: LLMProvider) -> str:
    return provider.complete("You write concise operational summaries.",
                             prompts.SUMMARY.format(record=rec.model_dump_json(indent=1))).strip()


def customer_email(rec: ServiceRecord, provider: LLMProvider) -> str:
    return provider.complete("You write professional customer emails.",
                             prompts.EMAIL.format(record=rec.model_dump_json(indent=1))).strip()

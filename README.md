# GenAI-Powered Document Assistant

Turns unstructured **service & maintenance PDFs** into **validated, structured JSON** using LLM APIs,
then generates summaries and customer emails from the extracted data.

```
PDF ──► text extraction ──► prompt ──► LLM ──► JSON parse ──► schema validation ──► grounding check
                                         ▲                                              │
                                         └────────── repair prompt (errors fed back) ◄──┘ (fail, ≤ N retries)
                                                                                         │ pass
                                                                         summary / customer email generation
```

## Why it's built this way
| Problem with raw LLM extraction | What this project does |
|---|---|
| Wrong formats (`14/03/2025`, `"$412.50"`) | Pydantic schema with typed fields, enums, ranges |
| Inconsistent fields (follow-up date before service date) | Cross-field validators |
| Hallucinated IDs / part numbers | **Grounding check**: identifiers must appear verbatim in the source text |
| One bad output = lost record | **Repair loop**: validation errors are sent back to the LLM for a targeted fix |
| Can't prove it works | `scripts/evaluate.py` measures baseline vs. validated error rates against ground truth |

## Quick start
```bash
pip install -r requirements.txt
python scripts/make_sample_pdfs.py 30          # synthetic PDFs + ground truth in data/samples
python -m pytest -q                            # unit tests

# Offline demo (no API key):
python -m docassist.cli extract data/samples/service_001.pdf --generate

# Real LLM:
export ANTHROPIC_API_KEY=sk-ant-...            # optional: DOCASSIST_MODEL=<model name>
python -m docassist.cli extract data/samples --provider anthropic --out results.json --workers 4
```

## Evaluate (get real numbers for your resume)
```bash
python scripts/evaluate.py --provider anthropic        # real model, your measured numbers
python scripts/evaluate.py --provider mock --flaky 0.35  # offline simulation of LLM mistakes
```
The script compares a **baseline** (single pass, no validation) against the **validated pipeline** and prints
document-level and field-level error rates plus the % reduction.


## Project layout
```
docassist/
  pdf_extract.py   PDF → clean text (pypdf), detects scanned PDFs
  schemas.py       Pydantic models + cross-field rules
  prompts.py       extraction / repair / summary / email prompts
  llm.py           Anthropic provider + offline mock provider
  pipeline.py      extract → validate → ground → repair loop
  generate.py      summaries and customer emails
  cli.py           batch CLI with thread pool
scripts/           sample data generator, evaluation harness
tests/             pytest suite
```

## Ideas to extend
OCR fallback (pytesseract) for scanned PDFs · FastAPI / Streamlit upload UI · SQLite/Postgres sink ·
confidence scores · caching by document hash · additional document types (invoices, work orders).


- Built a Python document-intelligence pipeline using LLM APIs, prompt engineering, and PDF parsing to convert unstructured service notes into structured JSON; automated batch processing with a CLI and thread pool.
- Added Pydantic schema validation, source-grounding checks, and an LLM self-repair loop, reducing extraction errors by **X%** on a **N**-document labeled evaluation set.

# Course Match

## What this is
Help incoming exchange students compare a home-university course with Bocconi courses. Return possible equivalences with evidence from both syllabi. Universities decide approval.
Current milestone: local keyword comparison, local Qwen through Ollama and optional OpenAI analysis of two syllabus texts, with verified source quotes and advisor review for every result. PDF uploads extract text and ruled tables for user review. No equivalence validation. OCR and retrieval remain future work.

## How to run
- Python 3.10 or later.
- python -m venv .venv
- Activate: source .venv/bin/activate (Windows PowerShell: .venv\Scripts\Activate.ps1)
- python -m pip install -r requirements.txt
- python -m uvicorn backend.main:app --reload --port 8000
- python -m pytest

## Where things live
- backend/main.py: FastAPI routes and frontend serving.
- backend/llm.py: the only module allowed to call a model or import its SDK; owns prompts, structured output schema and provider requests.
- backend/extract.py: text evidence helpers; judge.py: keyword and AI comparison; retrieve.py: future retrieval.
- backend/checks.py: quote verification and numerical calculations.
- frontend/: plain HTML, CSS and JavaScript; no build step.
- data/bocconi/: source of truth for Bocconi course information.
- data/approved/: verified equivalences, used only by tests.
- tests/: automated verification.
- NOTES.md: decisions and status.

## How to work
- Explain assumptions and a short plan before editing. Ask when requirements are unclear.
- Make the smallest change that meets the task.
- For new behavior, write a meaningful failing test before implementation.
- Cite passages from both syllabi for each proposed match; never guess missing evidence.
- Put counts, percentages, dates and credit conversions in code. Use a verified conversion rule.
- Record decisions in NOTES.md and report the verification command and result.
- Keep model-facing prompts in the application: this file guides development and is not automatically sent to the model.

## Boundaries
- No new frameworks, database, authentication or unrelated features.
- Do not weaken tests merely to make broken code pass.
- Never read, print, log, commit or hardcode API keys or .env contents.
- Never invent course data or treat a suggestion as an official approval.
- Discuss additions outside this structure before making them.

## Mistakes we have seen
- None recorded yet. Add a brief lesson after an actual mistake.

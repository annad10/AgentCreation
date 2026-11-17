# Decisions and current status

- Added POST /match and connected a two-syllabus form to it.
- Keyword mode stays local. OpenAI mode requires text-sharing consent and a key. Ollama mode runs local Qwen without a key.
- Shows verbatim source excerpts with exact offsets, verified in code.
- Every result routes to an advisor; no equivalence claims, scores or credit conversions.
- Texts are processed in memory and not saved by the application.
- Generic French/English syllabus words are excluded; different wording or
  languages may hide similarities. Common words can also create false positives.
- Limits: 30,000 characters per syllabus and excerpts for 20 shared terms.
- Removed the unused credits input because no verified conversion rule exists.
- Added PDF uploads for each syllabus via POST /extract-pdf (raw bytes).
- PDF dependency: pdfplumber. Optional AI adds OpenAI API usage through the existing HTTPX dependency; no new framework.
- Detects ruled tables, removes duplicated cells from narrative text and shows
  rows/columns for review. Borderless and merged layouts may need correction.
- Limits: 10 MB / 30 pages / 30,000 extracted characters. No silent truncation.
- Uploaded PDFs stay in memory; no files or document contents are logged by the app.
- Image-only PDFs are rejected with OCR guidance. Mixed documents flag textless pages;
  embedded images on otherwise text-readable pages may still be missed.
- Results include PDF page labels when present in the reviewed extracted text.
- AI gateway added in backend/llm.py using OpenAI Responses API structured output.
- Model: OPENAI_MODEL, default gpt-4.1-mini. Key loaded from project .env server-side;
  no key is returned to the browser. Existing process environment takes precedence.
- Requests use store=false, fixed official endpoint, 90-second timeout, no retries,
  4,000 output tokens maximum. Provider data policies still apply.
- AI source excerpts checked verbatim in code. Unsupported findings hidden and
  result marked incomplete; semantic interpretation still requires human review.
- AI similarities/differences have quotes from both sources. Possible gaps have a
  quote from the source that mentions the topic and are explicitly uncertain.
- GET /config exposes only key-presence status. It does not test account access.
- Added Local AI mode using Ollama's local /api/chat endpoint. Fixed loopback URL,
  proxy use disabled, no credential headers, no cloud fallback or auto-download.
- Same source-quote verification and structured output schema for both providers.
- Local input cap 6,000 combined characters, 16,384 context setting, 2,048 output
  tokens, 240-second timeout, no retries. Qwen3 thinking disabled for JSON output.
- Default qwen3:0.6b; local 1.7b, 4b and 8b tags also allowed when installed.
- UI labels local model results experimental and reports provider used.
- Verification: 28 API/test functions passed via direct Python runner (pytest
  unavailable in this runtime). Includes consent, local-mode isolation, quote
  rejection, HTTP request structure, source page labels, timeouts, refusal,
  incomplete/invalid responses, missing keys and provider access/usage failures.
- node --check frontend/app.js passed. Browser visual testing unavailable because
  Playwright Chromium is absent. No live API request or real credential was used;
  model quality and real account access remain unverified. Local provider tests also use mock HTTP responses; no live Qwen comparison was run here.

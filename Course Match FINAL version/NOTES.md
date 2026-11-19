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

## Bocconi course data (2026-11-17)
- data/bocconi/courses.json: 557 course rows (Fall 2026: 292, Spring 2027: 265) parsed from the official
  "Educational Offer" PDFs (course lists for exchange students, English-taught). Fields: code, term, level,
  title, credits, class_group, teaching_year, department, notes, source_page.
- Parsed by word position (pdfplumber), not copied by hand. Counts per department match the totals printed in the PDFs.
- The PDFs contain titles only, no syllabi or learning outcomes. Bocconi credits are ECTS equivalent (25 h each).
- Source text-layer glitch: "MA-EMENT" and "ALTERNA-E" repaired to MANAGEMENT and ALTERNATIVE; nothing else edited.
- A course can appear in both terms and in several class groups; "*" in class_group is explained in notes (exchange/CEMS reserved).
- Verification: python -m pytest, 32 passed (tests/test_bocconi_data.py added).

## Course recommendations from a CV and site redesign (2026-11-19)
- The page has two tabs: "Syllabus comparison" (first) and "CV course recommendations". Steps are numbered on both, each with one instruction line.
- POST /recommend takes cv_text, job, optional interests, terms (fall/spring), level (undergraduate/graduate), mode
  (keyword, ollama, ai) and ai_consent. CV text can come from the existing PDF upload.
- Candidates come only from data/bocconi/courses.json (542 unique codes; Fall 2026 and Spring 2027), deduplicated by code
  with credits stored per term (codes 30065 and 30066 differ between terms). Undergraduates see undergraduate courses only.
- Titles, credits, terms, levels and links are filled in by code. A model may only return course codes from the supplied
  list plus a reason and an exact quote from the student's own text; unknown codes and unverifiable quotes are dropped.
- The data has titles and departments only, so suggestions rest on titles; the page says so. Keyword mode scores title
  words found in the job (weight 3), interests (2) and CV (1). Local Qwen sees only the 60 best title matches.
- Course link: https://didattica.unibocconi.eu/ts/tsn_anteprima.php?cod_ins=<code>&anno=2027 (anno 2027 = academic year 2026-27).
  Checked on 15 sampled codes; each page showed the matching course. Some pages say their content still refers to 2025-26.
- The earlier "CV vs one syllabus" idea was removed; /match is unchanged. llm.py now shares OpenAI and Ollama request
  helpers between syllabus comparison and recommendations.
- The "B" in the header is a placeholder monogram in Georgia, not Bocconi's logo or typeface.
- Verification: python -m pytest, 42 passed (tests/test_recommend.py added). Headless Chrome filled the CV form in keyword
  mode and rendered the course cards. No live OpenAI or Ollama call was made; model quality is unverified.
- CV tab is upload-only: the CV text comes from /extract-pdf and sits in a collapsed, editable "Check the text read from your CV" box.
  Its step 4 is fixed keyword matching (works on any computer, sends nothing out); the UI has no method menu there. /recommend still
  accepts mode ai/ollama, covered by tests, but the page does not offer them. Syllabus tab keeps all three methods.
- Static files are linked with ?v=4 so browsers fetch updated CSS and JavaScript; bump it when they change.
- Verification: python -m pytest, 42 passed. Headless Chrome rendered both tabs and a CV-tab keyword run (CV text set in the box; a real PDF upload was not clicked).

## Link to a course or degree page (2026-11-19)
- Syllabus tab, step 1: choose "Upload a PDF or paste the syllabus" or "Paste a link to my course or degree page". The link
  option fills the same editable text box, so the student reviews the text before comparing. Home-university side only.
- POST /extract-url {url} -> {source html|pdf, url, title, text, warnings}, in backend/web_page.py (standard-library
  html.parser plus the existing httpx and pdfplumber; no new dependency).
- Safety rules: http/https on ports 80/443 only; no user:password in the address; every address (also each redirect, up to 3)
  must resolve only to public IPs, so localhost, private networks, link-local and cloud-metadata addresses are refused;
  no proxies, cookies or credentials; 10 MB and 20 s limits; only web pages, plain text and PDFs; PDFs use the existing reader.
  Errors never echo the site's response. Known limit: the check runs just before each request, so a hostile DNS server could
  still change its answer in between; use the tool locally, as the README advises.
- The page text drops scripts, styles, nav, footer and aside only. Some header menu text can remain (seen on a Bocconi page),
  so the interface asks the student to check the text. Pages built with JavaScript or behind a login return a "paste instead" message.
- Verification: python -m pytest, 52 passed (tests/test_web_page.py added, offline with mock HTTP). One real Bocconi course page
  (code 20161) was read through the running server: 6,988 characters with title, credits and mission text; localhost,
  127.0.0.1 and 169.254.169.254 were refused. Browser flow checked in headless Chrome.

## Syllabus tab uses the Bocconi offer, no Bocconi upload (2026-11-19)
- The offer PDFs hold titles, credits, departments and terms only, not syllabi. So the syllabus tab now takes only the home
  course (PDF, text or link), term and level and a method, and POST /match-offer (backend/offer_match.py) does the rest.
- Shortlist: up to 5 courses whose title words appear in the student's text (same ranking as the CV tab), filtered by term/level.
  A good match with a different title can be missed; if nothing matches the result says so and points to the CV tab.
- For each shortlisted course the server reads the public Bocconi page (anno=2027 link) with backend/web_page.py, starts the text
  at the "<code> - " heading to drop menus, and runs the existing keyword (or OpenAI/Ollama) comparison, so quotes from both
  sides are verified in code. Keyword evidence shows at most 5 items per course.
- If the page says its content refers to another academic year (seen: 2025-2026 on tested pages), the result shows that.
  If a page cannot be read, or Local AI's 6,000-character cap is exceeded, the course still appears with credits, link and a note.
  Other AI errors (missing key, rate limit) stop the whole request with the usual message.
- OpenAI mode sends the home text and the Bocconi page texts, one request per shortlisted course (up to 5), after consent.
- Added generic syllabus words (assessment, exam, written, grade, lecture, learn, teaching, group...) to STOPWORDS so keyword
  evidence is about content.
- Verification: python -m pytest, 60 passed (tests/test_offer_match.py added). Live run on real Bocconi pages: a corporate
  finance course text returned Corporate Finance 30017 and 20127 plus related finance courses with credits in about 3 seconds;
  the browser flow was checked in headless Chrome. No live OpenAI or Ollama request was made.

## Syllabus tab simplified (2026-11-19)
- Step 1 takes a PDF or a link only; the extracted text sits in a collapsed, editable "Check the text read from your course" box.
  Link and page errors now suggest saving the page as a PDF instead of pasting text.
- Step 3 is a fixed explanation of keyword comparison; the method menu and OpenAI consent box are gone from both tabs.
  /match-offer, /recommend and /match still accept ai and ollama in the backend (tests cover them) but the website does not offer them.
- Verification: python -m pytest, 60 passed; headless Chrome read a link, filled the hidden text box and ran the full flow without errors.

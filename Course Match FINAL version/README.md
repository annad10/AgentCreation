# Course Match

Helps incoming exchange students find Bocconi courses that fit their degree and interests.
Results are suggestions to discuss with an advisor; the home university makes the final decision.

The website has two tabs, each with numbered steps:

1. **Syllabus comparison**: upload a syllabus PDF from your home university, or paste a link to your course or
   degree page. Choose term (Fall 2026 and/or Spring 2027) and level. The app shortlists up to 5 courses from the
   official Bocconi exchange offer, reads each course's public Bocconi page and shows its credits, a link, and
   quotes from both your course and the Bocconi page.
2. **CV course recommendations**: upload your CV as a PDF, enter the job you want (and optional interests), choose
   term and level. The app suggests courses from the Fall 2026 and Spring 2027 offer, with credits per term, a quote
   from your own text and a link to the Bocconi course description.

Both tabs use one method that works on any computer: keyword matching. No account, API key or AI service is needed.

## Run it on your computer

You need Python 3.10 or newer and an internet connection (the syllabus tab reads Bocconi's public course pages).
Open a terminal in this folder.

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

**Windows (PowerShell)**
```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Then open http://127.0.0.1:8000. Keep the terminal open while you use the site; stop it with Ctrl+C.
The address works only on the computer running the server. Each team member runs their own copy.

## What to know

- **Titles only.** The official offer lists course titles, departments, credits and terms, not syllabi. Shortlists and
  recommendations are based on titles, so a good match with a different title can be missed. Always read the course page.
- **Bocconi pages can be out of date.** Some pages still describe the previous academic year; results say so when a page does.
- **Credits** are Bocconi credits (ECTS equivalent, 25 hours each) exactly as listed. They are never converted.
- **PDFs:** up to 10 MB and 30 pages. Scanned PDFs need OCR first. Check the extracted text before comparing.
- **Links:** only public web pages work. Pages that need a login or load their text with JavaScript cannot be read;
  save the page as a PDF and upload that instead. The server never opens local or private network addresses.
- **Privacy:** nothing you enter is saved. Do not put API keys or a `.env` file on GitHub.
- **Local use only.** A public website would need a separate security review first.
- The "B" in the page header is a placeholder, not the official Bocconi logo.

## Check the code

```bash
python -m pytest
```

All tests run offline with mock web pages and mock AI responses.

## Where things live

- `backend/main.py`: web routes. `backend/offer_match.py`, `backend/recommend.py`: matching.
  `backend/web_page.py`: reads a public page. `backend/pdf_upload.py`: reads PDFs. `backend/judge.py`: keyword comparison.
- `backend/llm.py`: the only file that may talk to an AI model (not used by the website).
- `frontend/`: plain HTML, CSS and JavaScript, no build step.
- `data/bocconi/courses.json`: the course offer (542 courses), parsed from the two "Educational Offer" PDFs in this folder.
- `tests/`: automated checks. `NOTES.md`: decisions and status. `CLAUDE.md`: project rules.

## For developers: API

| Route | Purpose |
|---|---|
| `POST /match-offer` | home course text, `terms`, `level` -> up to 5 Bocconi matches with credits, link and quotes |
| `POST /recommend` | `cv_text`, `job`, `interests`, `terms`, `level` -> suggested courses with credits, link and evidence quote |
| `POST /extract-url` | `{"url": "https://..."}` -> text of one public page or PDF |
| `POST /extract-pdf` | raw PDF bytes (`Content-Type: application/pdf`) -> text, pages, tables |
| `POST /match` | two pasted texts -> keyword comparison (not used by the website) |
| `GET /health`, `GET /config` | status; whether an OpenAI key is configured |

Quotes carry zero-based `start`/`end` offsets into the text they came from, and are verified in code.

## Optional AI (not shown on the website)

The backend can also use OpenAI or a local Qwen model through Ollama (`mode` = `ai` or `ollama` on the routes above).
The website does not offer these, and no live AI request has been made during development; tests use mock responses.
To try OpenAI, put `OPENAI_API_KEY=...` (and optionally `OPENAI_MODEL`) in a `.env` file next to `requirements.txt`.
For local Qwen, install Ollama and run `ollama run qwen3:0.6b`. Never share or commit `.env`.
AI output can be wrong; every quote is checked against the source, but interpretations are not.

## Still to do

OCR for scanned PDFs, smarter course retrieval than title matching, validated credit-conversion rules, and
evaluation against approved equivalences. Universities decide approval.

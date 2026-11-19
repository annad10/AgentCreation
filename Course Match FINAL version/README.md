# Course Match

Helps incoming exchange students find Bocconi courses that fit their degree and interests, by comparing a
course syllabus with a Bocconi course or by suggesting courses from their CV. The website has two tabs, each with numbered steps:

1. **Syllabus comparison** (first tab): add one home-university course (a PDF or a link to the course or
   degree page) and choose term and level. There is one method for everyone: keyword comparison. The app shortlists up to 5 courses by title from the Fall 2026 and
   Spring 2027 offer, reads each official Bocconi course page itself and shows credits, a link and quotes from both sides.
   No Bocconi syllabus has to be uploaded.
2. **CV course recommendations**: upload your CV as a PDF, enter the job you want (and optional interests),
   choose Fall 2026 and/or Spring 2027 and your level, and get suggested courses from the official exchange offer
   in data/bocconi/courses.json. Each suggestion shows its credits per term, a quote from your own text and a link
   to the Bocconi course description (https://didattica.unibocconi.eu/ts/tsn_anteprima.php?cod_ins=CODE&anno=2027).
   Suggestions use course titles and departments only (the offer lists no syllabi), run as keyword matching on any
   computer, and always need advisor review. The header "B" is a placeholder, not the official Bocconi logo.

## macOS / Linux quick start
Needs Python 3.10 or newer. From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Open http://127.0.0.1:8000. If the page looks old after an update, press Cmd+Shift+R.

Compare a home-university syllabus with a Bocconi syllabus uploaded as a PDF or pasted by the user.
Choose keyword comparison, local Qwen AI or optional OpenAI analysis of similarities,
differences and possible coverage gaps. Source excerpts are checked in code.
Every result requests advisor review. Quote presence does not prove the model's
interpretation, course equivalence or official recognition.
No similarity percentages or credit conversions are supplied.

## Windows quick start
Open this project folder in VS Code, then open a PowerShell terminal:

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Open http://127.0.0.1:8000. Keep the terminal running; stop with Ctrl+C.
For each syllabus, choose a PDF file or paste the text. After a PDF upload,
review the extracted text and use **View extracted tables** to check row and
column alignment against your original document. Correct the text if necessary,
then click **Compare syllabi**. Prefer documents in the same language.

PDF limits: 10 MB and 30 pages per file. Text-based PDFs are supported using
pdfplumber (https://github.com/jsvine/pdfplumber). Ruled tables are detected
and represented as rows and columns; other text is extracted with layout spacing.
Tables appear after other text on each page. Merged cells, borderless tables
and complex layouts may need manual corrections. Scanned PDFs require OCR
(text recognition) first. Mixed documents report pages with no selectable text;
images on otherwise readable pages may still contain unextracted information.
Password-protected or unreadable PDFs are rejected with a message.
PDF page references in results point to the extracted page labels; excerpts are
verified against the reviewed extracted text, not against the visual PDF.
Each text is limited to
30,000 characters. Evidence is displayed for up to 20 shared terms.
Keyword mode needs no API key and makes no model request. PDF extraction runs
on the local server. The app does not save uploads or results.
In OpenAI mode, both reviewed syllabus texts are sent to OpenAI after consent;
the raw PDF files are not sent. OpenAI provider data policies still apply.
Use this locally; public deployment requires separate security review.

## Checks

```powershell
python -m pytest
```

GET /health returns {"ok":true}. POST /match accepts JSON fields
home_syllabus and bocconi_syllabus, plus mode (keyword by default or ai) and
ai_consent (must be true for ai mode). mode=ollama selects local Qwen without a key; its two texts may total at most 6,000 characters. GET /config reports only whether an API
key is configured, not whether billing or provider access is working. Quotes include zero-based start and end
character offsets into each original text (the end is exclusive).

## Offer matching API
POST /match-offer accepts JSON: home_syllabus, terms ("fall"/"spring"), level ("graduate"/"undergraduate"), mode
("keyword" by default, "ai" with ai_consent=true, or "ollama"). It returns up to 5 matches with code, title,
offerings (term, credits), url, profile_year (when the Bocconi page states one), note and a comparison with verified
quotes from both texts. POST /match (two pasted texts) still exists but the website no longer uses it.

## Link to a course page API
POST /extract-url accepts JSON {"url": "https://..."} and returns editable text from one public web page or PDF
(fields source, url, title, text, warnings). Only http/https on standard ports are fetched, never local or private
addresses, and nothing is stored. Pages that need a login or JavaScript cannot be read; paste the text instead.

## CV recommendations API
POST /recommend accepts JSON: cv_text, job (up to 500 characters), optional interests, terms (a list of
"fall" and/or "spring"), level ("graduate" or "undergraduate"), mode ("keyword" by default, "ai" with
ai_consent=true, or "ollama") and returns courses with code, title, department, level, offerings (term and
credits), url, category (background, interest or gap), reason and a verified evidence quote. The website only
uses keyword mode. In ai and ollama modes a model may only choose course codes from the offer; credits, terms
and links always come from the data file, and unknown codes or unverifiable quotes are dropped.

## Remaining work
OCR, course retrieval from data/bocconi, validated
credit conversion rules and evaluation using approved equivalences remain
unimplemented. No real syllabus data is included. Universities decide approval.
Do not upload .env, API keys or .venv to GitHub.

## PDF extraction API
POST /extract-pdf accepts raw PDF bytes with Content-Type: application/pdf.
It returns editable text, page numbers, detected table cell arrays and warnings.
The browser checks file size; the server enforces the size while reading bytes.
Test PDFs in tests/fixtures are synthetic fixtures, not official course data.

## Use local Qwen with Ollama on Windows (no paid API key)

1. Install Ollama from https://ollama.com/download/windows and open it.
2. In a terminal run: ollama run qwen3:0.6b
3. Once the download completes, ask a short question to confirm it answers.
   Type /bye to exit the chat. Keep the Ollama application running in the background.
4. Start Course Match with the Windows quick-start commands above.
5. Refresh the website with Ctrl+F5. Upload your PDFs and review the text/tables.
6. Select **Local AI - Qwen (Ollama), no API key** under Comparison method.
7. Keep short relevant text excerpts in the boxes, no more than 6,000 characters
   across both, then click Compare syllabi. No application-side truncation occurs:
   oversized inputs are rejected before a model request.

Local mode sends reviewed text only to the fixed loopback Ollama endpoint
http://127.0.0.1:11434/api/chat. It sends no API key and makes no OpenAI request.
No automatic cloud fallback or model download happens. It uses a JSON schema,
think=false, temperature=0, a 16,384-token context setting and at most 2,048
output tokens. The request timeout is 240 seconds with no automatic retries.

The default qwen3:0.6b is a tiny experimental model, not a validated academic
comparison system. A fluent answer does not establish accuracy or instruction
following. Check every observation; quote checks do not validate interpretations.
If replies are incomplete or fail schema validation, use shorter excerpts.
Local model quality, memory use and speed need testing on your computer.

No .env change is needed for the default local model. To test a larger local
Qwen3 later, set OLLAMA_MODEL in .env to qwen3:1.7b, qwen3:4b or qwen3:8b and
install that exact model with ollama run. Check hardware capacity first.
Only these local Qwen3 tags are accepted; cloud model tags are rejected.

Official Ollama references:
- https://docs.ollama.com/api/chat
- https://docs.ollama.com/capabilities/structured-outputs
- https://ollama.com/library/qwen3:0.6b

## Enable OpenAI on Windows

1. Stop the server with Ctrl+C.
2. Create an API key at https://platform.openai.com/api-keys. Check your API
   billing and model access before running a comparison; API usage may incur charges.
3. In VS Code, right-click the project folder in the Explorer and choose New File.
   Name it .env, next to requirements.txt. If .env already exists, edit that file.
   Put the following in it, replacing YOUR_API_KEY_HERE only on your own computer:

```dotenv
OPENAI_API_KEY=YOUR_API_KEY_HERE
OPENAI_MODEL=gpt-4.1-mini
```

4. Save with Ctrl+S. Never share the key, commit .env or include it in screenshots.
   The app loads this exact project .env; existing process environment variables
   take precedence. Restart after changing the key or model.
5. In the activated terminal, run python -m pip install -r requirements.txt,
   then python -m uvicorn backend.main:app --reload --port 8000.
6. Open http://127.0.0.1:8000 and press Ctrl+F5. Upload and review both syllabi.
   Choose AI analysis - OpenAI, check the text-sharing checkbox and click Compare.

The application requests structured output from the OpenAI Responses API using
HTTPX, with a fixed official endpoint, a 90-second timeout, no automatic retries,
store=false and at most 4,000 output tokens. All model-facing instructions and
network requests are in backend/llm.py. OPENAI_MODEL can select a model supporting
the Responses API and structured outputs; the supplied default is gpt-4.1-mini.
Official OpenAI documentation:
- https://developers.openai.com/api/docs/quickstart
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/models/gpt-4.1-mini

Up to six similarities/differences need exact informative quotes from both texts.
Up to four possible gaps cite the side where the topic is mentioned; lack of
coverage in the other supplied syllabus is uncertain, not proof of absence.
Findings with unverifiable quotes are hidden with a warning. This checks quotes,
not semantic correctness. Empty/refused/incomplete/invalid provider output is
reported as an error; it is never silently presented as successful AI analysis.
Missing keys, rejected access, timeouts and usage limits give actionable messages.

No live AI call was made during development. Tests use synthetic syllabi and
mock HTTP provider responses, with no real key or paid requests. The local
Ollama integration was also verified with mock responses; no live Qwen model
was available in the development environment. Evaluate real
outputs with an advisor before relying on the tool for recognition requests.

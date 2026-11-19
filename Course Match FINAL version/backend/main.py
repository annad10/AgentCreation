"""Syllabus comparison server with optional, explicit AI requests."""
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Request, HTTPException
from starlette.concurrency import run_in_threadpool
from .pdf_upload import extract_pdf, MAX_BYTES
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, StrictBool
from .judge import compare, compare_ai
from .web_page import read_page
from .recommend import recommend_keyword, recommend_ai
from .offer_match import match_offer
from . import llm

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
app = FastAPI(title="Course Match", version="0.1.0")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

@app.middleware("http")
async def always_revalidate(request: Request, call_next):
    # Browsers must check for updates, so students never see an old copy of the site.
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/health")
def health():
    return {"ok": True}

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND / "index.html")


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    home_syllabus: str = Field(min_length=1, max_length=30000)
    bocconi_syllabus: str = Field(min_length=1, max_length=30000)
    mode: Literal["keyword", "ai", "ollama"] = "keyword"
    ai_consent: StrictBool = False

    @field_validator("home_syllabus", "bocconi_syllabus")
    @classmethod
    def reject_blank(cls, value):
        if not value.strip():
            raise ValueError("Paste syllabus text, not only spaces.")
        return value


@app.post("/match")
def match(payload: ComparisonRequest):
    if payload.mode in ("ai", "ollama"):
        if payload.mode == "ai" and not payload.ai_consent:
            raise HTTPException(422, "Confirm sending both syllabus texts to OpenAI before using AI analysis.")
        try:
            return compare_ai(payload.home_syllabus, payload.bocconi_syllabus,
                              provider="ollama" if payload.mode == "ollama" else "openai")
        except llm.AIError as error:
            raise HTTPException(error.status, error.message) from None
    return compare(payload.home_syllabus, payload.bocconi_syllabus)


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cv_text: str = Field(min_length=1, max_length=30000)
    job: str = Field(min_length=1, max_length=500)
    interests: str = Field(default="", max_length=1000)
    terms: list[Literal["fall", "spring"]] = Field(min_length=1, max_length=2)
    level: Literal["undergraduate", "graduate"] = "graduate"
    mode: Literal["keyword", "ai", "ollama"] = "keyword"
    ai_consent: StrictBool = False

    @field_validator("cv_text", "job")
    @classmethod
    def reject_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter text, not only spaces.")
        return value


@app.post("/recommend")
def recommend(payload: RecommendRequest):
    args = (payload.cv_text, payload.job, payload.interests, payload.terms, payload.level)
    if payload.mode == "keyword":
        return recommend_keyword(*args)
    if payload.mode == "ai" and not payload.ai_consent:
        raise HTTPException(422, "Confirm sending your CV, job and interests to OpenAI before using AI suggestions.")
    try:
        return recommend_ai(*args, provider="ollama" if payload.mode == "ollama" else "openai")
    except llm.AIError as error:
        raise HTTPException(error.status, error.message) from None


class PageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2000)


class OfferMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    home_syllabus: str = Field(min_length=1, max_length=30000)
    terms: list[Literal["fall", "spring"]] = Field(min_length=1, max_length=2)
    level: Literal["undergraduate", "graduate"] = "graduate"
    mode: Literal["keyword", "ai", "ollama"] = "keyword"
    ai_consent: StrictBool = False

    @field_validator("home_syllabus")
    @classmethod
    def reject_blank(cls, value):
        if not value.strip():
            raise ValueError("Add your course text, not only spaces.")
        return value


@app.post("/match-offer")
def match_offer_route(payload: OfferMatchRequest):
    if payload.mode == "ai" and not payload.ai_consent:
        raise HTTPException(422, "Confirm sending your course text and the Bocconi page texts to OpenAI before using AI analysis.")
    try:
        return match_offer(payload.home_syllabus, payload.terms, payload.level, payload.mode)
    except llm.AIError as error:
        raise HTTPException(error.status, error.message) from None


@app.post("/extract-url")
def extract_url(payload: PageRequest):
    return read_page(payload.url)


@app.post("/extract-pdf")
async def extract_uploaded_pdf(request: Request):
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/pdf":
        raise HTTPException(415, "Upload a PDF file.")
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "PDF must be 10 MB or smaller.")
        content.extend(chunk)
    return await run_in_threadpool(extract_pdf, bytes(content))


@app.get("/config")
def configuration():
    # Configuration presence only; no credential or provider diagnostics exposed.
    return {"ai_available": llm.available()}

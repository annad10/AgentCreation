# Serve the Course Match placeholder page, static files and health endpoint.
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
load_dotenv(ROOT / ".env")

app = FastAPI(title="Course Match")
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/", response_class=FileResponse)
def home():
    return FileResponse(FRONTEND / "index.html")

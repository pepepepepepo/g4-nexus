# gemma4_tribe/api.py
# FastAPI server — wraps tribe.py for WebUI

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from tribe import run_tribe, _load_memory, SESSIONS_DIR

BASE_DIR = Path(__file__).parent.resolve()

# ─── App ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="gemma4_tribe", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─── Schemas ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ExportRequest(BaseModel):
    filename: str       # e.g. "article_draft.md" — relative to BASE_DIR
    content: str
    confirmed: bool = False  # False = preview only, True = actually write


# ─── Routes ───────────────────────────────────────────────

@app.get("/")
async def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"status": "gemma4_tribe api running", "ui": "PUT index.html in static/"}


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message is empty")
    result = await run_tribe(req.message, verbose=False)
    return result


@app.get("/memory/{name}")
async def get_memory(name: str):
    if name not in ("koyomi", "mochi", "jun", "uruu"):
        raise HTTPException(status_code=404, detail="unknown persona")
    return _load_memory(name)


@app.get("/sessions")
async def list_sessions():
    files = sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:20]
    return [f.name for f in files]


@app.get("/sessions/{filename}")
async def get_session(filename: str):
    import json, re
    if not re.fullmatch(r"[\w\-]+\.json", filename):
        raise HTTPException(status_code=400, detail="invalid filename")
    path = SESSIONS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Export (file write with confirmation) ────────────────

@app.post("/export")
async def export_file(req: ExportRequest):
    import re
    # Allow only filenames in BASE_DIR — no path traversal
    if not re.fullmatch(r"[\w\-][\w\-. ]*\.(md|txt|json|html|py)", req.filename):
        raise HTTPException(status_code=400, detail="invalid filename (alphanumeric, -, _, . only; allowed extensions: md txt json html py)")
    target = (BASE_DIR / req.filename).resolve()
    if not str(target).startswith(str(BASE_DIR)):
        raise HTTPException(status_code=400, detail="path traversal not allowed")

    preview = {
        "path": str(target),
        "size_chars": len(req.content),
        "lines": req.content.count("\n") + 1,
        "preview_head": req.content[:300],
        "confirmed": req.confirmed,
    }

    if not req.confirmed:
        preview["status"] = "pending — set confirmed=true to write"
        return preview

    target.write_text(req.content, encoding="utf-8")
    preview["status"] = "written"
    return preview

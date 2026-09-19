from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "studybuddy.db"

UPLOAD_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="StudyBuddy AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProgressUpdate(BaseModel):
    xp: int = 0
    streak: int = 0
    cards_reviewed: int = 0
    quizzes_completed: int = 0


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = db()
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS materials (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            title TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            text TEXT NOT NULL,
            summary TEXT NOT NULL,
            concepts TEXT NOT NULL,
            flashcards TEXT NOT NULL,
            quiz TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            xp INTEGER NOT NULL DEFAULT 0,
            streak INTEGER NOT NULL DEFAULT 0,
            cards_reviewed INTEGER NOT NULL DEFAULT 0,
            quizzes_completed INTEGER NOT NULL DEFAULT 0
        );

        INSERT OR IGNORE INTO progress (id, xp, streak, cards_reviewed, quizzes_completed)
        VALUES (1, 0, 0, 0, 0);
        """
    )
    con.commit()
    con.close()


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 35]


def local_generate(text: str, title: str) -> dict[str, Any]:
    """Demo-mode synthesis that requires no external API."""
    sents = sentences(text)
    if not sents:
        sents = [text[:500] or "No readable text was found in this document."]

    # Select informative sentences for a concise summary.
    chosen = []
    for s in sents:
        if len(s) > 45 and s not in chosen:
            chosen.append(s)
        if len(chosen) == 5:
            break

    summary = " ".join(chosen)[:1800]

    # Lightweight concept extraction from frequent long words.
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{5,}", text.lower())
    stop = {
        "about","because","between","through","which","their","there","these",
        "those","using","system","example","different","should","would",
        "could","following","important","process","called","where","while",
        "student","students","chapter","figure","section"
    }
    freq: dict[str, int] = {}
    for w in words:
        if w not in stop:
            freq[w] = freq.get(w, 0) + 1
    concepts = [w.title() for w, _ in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:8]]

    # Create flashcards from sentences.
    cards = []
    for i, s in enumerate(chosen[:6]):
        key = concepts[i % len(concepts)] if concepts else "Key idea"
        cards.append({
            "id": i + 1,
            "front": f"What is the key idea behind {key}?",
            "back": s[:500],
            "difficulty": ["Easy", "Medium", "Hard"][i % 3]
        })

    # Quiz based on selected concepts.
    quiz = []
    for i, c in enumerate(concepts[:5]):
        correct = c
        distractors = [x for x in concepts if x != c][:3]
        while len(distractors) < 3:
            distractors.append(["Review", "Concept", "Topic"][len(distractors)])
        options = [correct] + distractors
        # deterministic rotation
        options = options[i % 4:] + options[:i % 4]
        quiz.append({
            "id": i + 1,
            "question": f"Which term is most directly associated with this study material?",
            "options": options,
            "answer": correct
        })

    return {
        "summary": summary,
        "concepts": concepts or ["Core Topic", "Key Principle", "Application"],
        "flashcards": cards,
        "quiz": quiz,
    }


async def llm_generate(text: str, title: str) -> dict[str, Any] | None:
    key = os.getenv("LLM_API_KEY")
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL")
    if not key or not model:
        return None

    prompt = f"""
You are StudyBuddy AI. Transform the following study material into structured active-learning content.

Return ONLY valid JSON with this exact shape:
{{
  "summary": "concise adaptive summary",
  "concepts": ["concept 1", "concept 2"],
  "flashcards": [
    {{"id": 1, "front": "question", "back": "answer", "difficulty": "Easy"}}
  ],
  "quiz": [
    {{"id": 1, "question": "question", "options": ["A","B","C","D"], "answer": "correct option"}}
  ]
}}

Create 5-8 concepts, 6 flashcards, and 5 quiz questions.
Title: {title}
Material:
{text[:30000]}
"""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            content = re.sub(r"^```(?:json)?|```$", "", content.strip()).strip()
            return json.loads(content)
    except Exception:
        return None


async def synthesize(text: str, title: str) -> dict[str, Any]:
    result = await llm_generate(text, title)
    return result if result else local_generate(text, title)


init_db()


@app.get("/")
async def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/app.js")
async def app_js():
    return FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")


@app.get("/styles.css")
async def styles():
    return FileResponse(FRONTEND_DIR / "styles.css", media_type="text/css")


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(FRONTEND_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "StudyBuddy AI"}


@app.post("/api/materials")
async def upload_material(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "A file is required.")

    suffix = Path(file.filename).suffix.lower()
    raw = await file.read()

    if suffix == ".pdf":
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}.pdf"
        temp_path.write_bytes(raw)
        try:
            reader = PdfReader(str(temp_path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        finally:
            temp_path.unlink(missing_ok=True)
    elif suffix in {".txt", ".md"}:
        text = raw.decode("utf-8", errors="ignore")
    else:
        raise HTTPException(415, "Supported formats: PDF, TXT, MD.")

    text = clean_text(text)
    if len(text) < 30:
        raise HTTPException(422, "The file does not contain enough readable text.")

    title = Path(file.filename).stem.replace("_", " ").replace("-", " ").title()
    generated = await synthesize(text, title)
    material_id = str(uuid.uuid4())

    con = db()
    con.execute(
        """INSERT INTO materials
        (id, filename, title, uploaded_at, text, summary, concepts, flashcards, quiz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            material_id,
            file.filename,
            title,
            datetime.utcnow().isoformat(),
            text[:100000],
            generated["summary"],
            json.dumps(generated["concepts"]),
            json.dumps(generated["flashcards"]),
            json.dumps(generated["quiz"]),
        ),
    )
    con.commit()
    con.close()

    return {
        "id": material_id,
        "title": title,
        "filename": file.filename,
        "pages_or_text": len(text),
        **generated,
    }


@app.get("/api/materials")
async def list_materials():
    con = db()
    rows = con.execute(
        "SELECT id, filename, title, uploaded_at FROM materials ORDER BY uploaded_at DESC"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


@app.get("/api/materials/{material_id}")
async def get_material(material_id: str):
    con = db()
    row = con.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404, "Material not found.")
    item = dict(row)
    item["concepts"] = json.loads(item["concepts"])
    item["flashcards"] = json.loads(item["flashcards"])
    item["quiz"] = json.loads(item["quiz"])
    item.pop("text", None)
    return item


@app.get("/api/progress")
async def get_progress():
    con = db()
    row = con.execute("SELECT * FROM progress WHERE id = 1").fetchone()
    con.close()
    return dict(row)


@app.post("/api/progress")
async def update_progress(update: ProgressUpdate):
    con = db()
    con.execute(
        """UPDATE progress
        SET xp = xp + ?, streak = MAX(streak, ?),
            cards_reviewed = cards_reviewed + ?,
            quizzes_completed = quizzes_completed + ?
        WHERE id = 1""",
        (max(update.xp, 0), max(update.streak, 0),
         max(update.cards_reviewed, 0), max(update.quizzes_completed, 0)),
    )
    con.commit()
    row = con.execute("SELECT * FROM progress WHERE id = 1").fetchone()
    con.close()
    return dict(row)

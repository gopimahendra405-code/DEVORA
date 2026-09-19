# StudyBuddy AI

StudyBuddy AI turns static study material (PDFs/notes) into active learning content: summaries, key concepts, flashcards, quizzes, and progress tracking.

## Architecture

- **FastAPI backend** — API, PDF extraction, learning-content generation
- **SQLite** — lightweight local persistence
- **LLM-ready pipeline** — optional OpenAI-compatible API; works in demo mode without an API key
- **Responsive Web + Mobile Companion UI** — one frontend adapts to desktop and mobile
- **PWA support** — installable on supported mobile browsers

## Quick start

### 1. Create a virtual environment

```bash
cd StudyBuddy_AI
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Start the server

```bash
uvicorn backend.main:app --reload
```

Open:

- http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

## Optional AI configuration

Without an API key, StudyBuddy AI uses a deterministic local demo generator so the complete application can still be demonstrated.

To connect an OpenAI-compatible LLM endpoint, create `.env`:

```env
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=your_model_name
```

The backend sends only the extracted study text to the configured endpoint.

## Demo flow

1. Upload a PDF.
2. StudyBuddy extracts its text.
3. The synthesis pipeline creates:
   - adaptive summary
   - key concepts
   - flashcards
   - multiple-choice quiz
4. Open **Learn** to review flashcards.
5. Complete the quiz and earn XP.
6. Progress is stored in SQLite.

## Project structure

```text
StudyBuddy_AI/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   ├── manifest.webmanifest
│   └── sw.js
├── data/
├── uploads/
├── .gitignore
└── README.md
```

## Hackathon pitch

> StudyBuddy AI transforms passive study materials into an active learning journey. Students upload PDFs or notes, and the platform extracts concepts and generates adaptive summaries, flashcards, and quizzes. A responsive web portal handles material processing while the mobile-friendly companion interface makes active recall available anywhere. Gamified XP and progress tracking encourage consistent practice and help students spend less time rereading and more time remembering.

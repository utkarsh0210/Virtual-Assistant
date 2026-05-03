# Bharvishya

> *"India's Future"* — A production-grade AI voice assistant powered by Gemini Pro

Rebuilt from scratch with a modern, modular architecture. Replaces the original `voiceCommand.py` with clean, extensible, production-ready code.

---

## What's New vs v1

| v1 (Old) | v2.0 (This) |
|---|---|
| Single monolithic `.py` file | Modular architecture (core + skills) |
| `if/elif` chain for intents | Gemini Pro LLM intent routing |
| `pyttsx3` (robotic voice) | `edge-tts` Microsoft Neural Voices |
| `text-davinci-003` (deprecated) | Gemini 1.5 Pro |
| No memory | SQLite persistent conversation history |
| Hardcoded Windows paths | Cross-platform (Windows, Mac, Linux) |
| Tkinter GUI | Modern browser-based UI via FastAPI |
| No plugin system | Extensible skill plugin architecture |

---

## Architecture

```
bharvishya/
├── main.py              # FastAPI app + WebSocket server
├── core/
│   ├── llm.py           # Gemini Pro orchestrator + intent routing
│   ├── memory.py        # SQLite conversation memory
│   ├── stt.py           # Speech-to-Text (Google/Whisper)
│   └── tts.py           # Text-to-Speech (edge-tts neural voices)
├── skills/
│   ├── registry.py      # Plugin registry + BaseSkill class
│   ├── web_search.py    # DuckDuckGo/Serper web search
│   ├── task_manager.py  # SQLite task & notes manager
│   ├── email_skill.py   # SMTP email via Gmail App Passwords
│   └── calendar_skill.py # Local/Google Calendar integration
├── ui/
│   └── index.html       # Single-file browser UI
├── data/                # Auto-created: SQLite databases
├── logs/                # Auto-created: application logs
├── .env.example         # Config template
└── requirements.txt
```

---

## Quick Start

### 1. Clone & Install

```bash
git clone <your-repo>
cd bharvishya
pip install -r requirements.txt
```

**System dependencies:**

- **Windows**: Install [PortAudio](http://www.portaudio.com/) for PyAudio, or: `pip install pipwin && pipwin install pyaudio`
- **macOS**: `brew install portaudio && pip install pyaudio`
- **Linux**: `sudo apt install portaudio19-dev python3-pyaudio`

### 2. Configure

```bash
cp .env.example .env
# Edit .env — at minimum set GEMINI_API_KEY
```

Get your free Gemini API key: https://aistudio.google.com/app/apikey

### 3. Run

```bash
# Load env vars and start
python -m dotenv -f .env run -- python main.py

# Or manually export:
export GEMINI_API_KEY=your_key_here
python main.py
```

### 4. Open

Navigate to **http://127.0.0.1:8765** in your browser.

---

## Skills

### 🔍 Web Search
- **DuckDuckGo** (default, no key needed)
- **Google Search** via [Serper.dev](https://serper.dev) (set `SERPER_API_KEY`, 2500 free/month)

**Voice commands:** `"Search for latest AI news"`, `"What is LangGraph?"`, `"Find recent news about India"`

### ✅ Task Manager
Persistent SQLite-backed tasks with priority levels.

**Voice commands:** `"Add task: review PR"`, `"Show my tasks"`, `"Complete task 1"`, `"Delete the meeting task"`

### 📧 Email
Sends emails via SMTP. Gmail App Passwords supported (no OAuth needed).

**Setup:** Enable Gmail 2FA → [Generate App Password](https://myaccount.google.com/apppasswords) → set in `.env`

**Voice commands:** `"Send email to john@example.com about the project update"`

### 📅 Calendar
Local SQLite calendar by default. Google Calendar support via service account credentials.

**Voice commands:** `"What's on my calendar today?"`, `"Add meeting tomorrow at 3pm"`, `"Show this week's events"`

---

## Adding Custom Skills

1. Create `skills/my_skill.py`
2. Inherit from `BaseSkill`
3. Add to `SkillRegistry.SKILL_MODULES`

```python
from skills.registry import BaseSkill

class Skill(BaseSkill):
    name = "my_skill"
    description = "What this skill does"
    actions = ["do_thing"]

    async def execute(self, action: str, params: dict):
        if action == "do_thing":
            return {"result": "done"}
```

---

## STT Options

| Backend | Quality | Internet | Setup |
|---|---|---|---|
| Google Speech (default) | Good | Required | None |
| Whisper (local) | Excellent | Offline | Set `USE_WHISPER=true`, install `faster-whisper` |

---

## TTS Voices

Change `TTS_VOICE` in `.env`. Some options:

| Voice | Description |
|---|---|
| `en-IN-PrabhatNeural` | Indian English Male (default) |
| `en-IN-NeerjaNeural` | Indian English Female |
| `en-US-GuyNeural` | US English Male |
| `hi-IN-MadhurNeural` | Hindi Male |

Full list: https://aka.ms/TTS-voices

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `WS` | `/ws` | Real-time chat + voice |
| `GET` | `/api/history` | Conversation history |
| `DELETE` | `/api/history` | Clear history |
| `GET` | `/api/tasks` | List tasks |
| `POST` | `/api/tasks` | Add task |
| `PATCH` | `/api/tasks/{id}/complete` | Complete task |
| `DELETE` | `/api/tasks/{id}` | Delete task |
| `GET` | `/api/skills` | List loaded skills |
| `GET` | `/health` | Health check |

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini 1.5 Pro |
| Backend | FastAPI + uvicorn |
| Real-time | WebSockets |
| STT | Google Speech Recognition / Whisper |
| TTS | edge-tts (Microsoft Neural) |
| Memory | SQLite via stdlib |
| UI | Vanilla HTML/CSS/JS |
| Web Search | DuckDuckGo API / Serper |

---

*Built by Utkarsh Gupta — Bharvishya v2.0, 2026*

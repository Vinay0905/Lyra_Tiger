# Lyra Tiger

Lyra Tiger is a local-first desktop assistant prototype built with FastAPI, LangGraph, pywebview, Groq, and a lightweight HTML/CSS/JS interface. It is organized as a phased build: backend setup, desktop UI shell, voice input/output, orchestration, browser bridge integration, vision, developer tools, and safety controls.

## Current Capabilities

- FastAPI backend with `/health`, `/command`, and `/voice_command`
- LangGraph orchestration for routing commands into chat, browser, vision, and developer paths
- Modular LLM client with provider fallback support
- Groq speech-to-text integration
- Local TTS support through macOS `say` or `pyttsx3`
- pywebview desktop shell with a Three.js orb UI
- Kimi WebBridge client scaffolding for browser automation
- Allowlisted workspace paths for developer/file operations

## Project Structure

```text
AI_Assistant/
├── docs/                 # Phase docs and architecture notes
├── src/                  # Backend, orchestration, skills, GUI shell
│   ├── main.py           # FastAPI app
│   ├── gui.py            # pywebview desktop window
│   ├── orchestrator.py   # LangGraph workflow
│   ├── llm.py            # LLM fallback client
│   ├── audio.py          # Recording and transcription
│   ├── tts.py            # Speech output
│   ├── nodes/            # LangGraph nodes
│   └── skills/           # Browser, vision, developer helpers
├── ui/                   # Desktop UI assets
├── pyproject.toml
├── uv.lock
└── README.md
```

## Setup

Install dependencies with `uv`:

```bash
uv sync
```

Create a local `.env` file. Do not commit this file.

```env
GROQ_API_KEY=your_groq_key_here
OPENAI_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=

LLM_FALLBACK_CHAIN=groq

GROQ_MODEL=llama-3.3-70b-versatile
GROQ_VISION_MODEL=llama-3.2-11b-vision-preview
OPENAI_MODEL=gpt-4o-mini
GEMINI_MODEL=gemini-1.5-flash
OPENROUTER_MODEL=meta-llama/llama-3-70b-instruct

HOST=127.0.0.1
PORT=8000
LYRA_DEBUG=False

APPROVED_WORKSPACE_DIRS=/Users/mast/Documents/VInayPrograming/AI_Assistant/workspace

WEBBRIDGE_HOST=127.0.0.1
WEBBRIDGE_PORT=10086
```

Create the local workspace folder:

```bash
mkdir -p workspace
```

## Run The Backend

```bash
uv run python -m src.main
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Text command test:

```bash
curl -X POST http://127.0.0.1:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text": "Search Google for Lyra constellation"}'
```

## Run The Desktop UI

```bash
uv run python -m src.gui
```

The GUI starts as a small `80x80` floating orb. Click the orb to expand the panel. Keep `LYRA_DEBUG=False` unless you intentionally want pywebview's Web Inspector.

## Voice Command

The voice route records microphone input, transcribes it, runs orchestration, and speaks the final response.

```bash
curl -X POST http://127.0.0.1:8000/voice_command
```

On macOS, microphone permissions may be required for the terminal app running the backend.

## Kimi WebBridge

Browser automation uses Kimi WebBridge on:

```text
127.0.0.1:10086
```

Install command used during local setup:

```bash
curl -fsSL https://kimi-web-img.moonshot.cn/webbridge/install.sh | bash
```

Check whether something is listening:

```bash
lsof -i :10086
```

Note: `/` and `/health` may return `404 page not found`; that does not necessarily mean the service is down. The bridge may expose only specific API/WebSocket routes.

## Development Notes

- Keep secrets in `.env`; commit only `.env.example`.
- `uv.lock` should be committed for reproducible installs.
- The app uses `LYRA_DEBUG`, not generic `DEBUG`, to avoid shell environment collisions.
- Some browser/voice/vision features require external services and macOS permissions.

## GitHub Setup

Repository:

```text
https://github.com/Vinay0905/Lyra_Tiger.git
```

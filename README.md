<p align="center">
  <img src="https://raw.githubusercontent.com/Vinay0905/Lyra_Tiger/main/LyraLogo.png" alt="Lyra Tiger Logo" width="200"/>
</p>

# Lyra Tiger

Lyra Tiger is a local-first, native-style macOS **menu-bar AI assistant**. It pairs a
**Tauri (Rust) shell** hosting a React 19 + Three.js UI with a **FastAPI + LangGraph**
Python "brain". The assistant lives in the menu bar (no Dock icon), drops down as a
frosted popover, and responds to voice or text with a local streaming voice.

## Architecture

```text
Lyra_Tiger/
├── src/                  # Python backend (FastAPI + LangGraph brain)
│   ├── main.py           # FastAPI app: /command, /command/stream, /voice_command, /tts, /history, /audit
│   ├── orchestrator.py   # LangGraph workflow + streaming pre-format runner
│   ├── agent_state.py    # Shared graph state (reducers, structured skill_result)
│   ├── llm.py            # Async httpx LLM client (buffered + token streaming, provider fallback)
│   ├── routing.py        # Tier-0 heuristic intent router
│   ├── cache.py          # TTL classification cache + LRU TTS cache
│   ├── memory.py         # aiosqlite conversation memory + unified audit store
│   ├── audio.py          # Async Groq Whisper transcription
│   ├── tts.py            # Local Kokoro-82M ONNX synthesis
│   ├── nodes/            # LangGraph nodes (classifier, browser, vision, developer, formatter)
│   └── skills/           # Browser (Kimi WebBridge), Vision (mss + Groq), Developer tools
├── src-tauri/            # Rust shell: tray icon, popover, global shortcut (⌥Space)
├── frontend/             # React 19 + Vite + Tailwind + Three.js UI
├── pyproject.toml
└── README.md
```

### Data flow

```text
UI (voice/text) ──► FastAPI ──► LangGraph (classify → skill → format)
                                   │
        streaming tokens ◄─────────┘  (SSE /command/stream)
        sentence-chunked TTS ◄──── /tts (cached, Kokoro ONNX)
```

## Backend

Install dependencies with `uv`:

```bash
uv sync
```

Create a local `.env` from `.env.example` (see that file for all keys). Then run:

```bash
uv run python -m src.main
```

Install the browser engine (Playwright) Chromium once (used by "bundled" mode
and as the CDP fallback):

```bash
uv run playwright install chromium
```

Endpoints:

- `GET  /health` — status + active browser mode
- `POST /command` — buffered `{ text, session_id? }`
- `POST /command/stream` — Server-Sent Events token stream
- `POST /voice_command` — multipart WAV upload (`?session_id=`)
- `POST /confirm` — resolve a gated action `{ session_id, approve, action }`
- `GET  /tts?text=...&voice=...` — streamed WAV (content-cached)
- `GET  /history?session_id=...`
- `GET  /audit?session_id=...`
- `GET  /metrics` — latency / breaker / cache telemetry

## Desktop shell

From `frontend/`:

```bash
npm install
```

Then, from the repo root, launch backend + Tauri together:

```bash
uv run python run.py
```

- Click the menu-bar icon **or press ⌥Space** to summon the popover.
- `⌘K` opens the command palette; `Esc` dismisses; the gear opens settings; the clock opens history.
- The window is a native **NSPanel** anchored beneath the tray icon (non-activating,
  floats over full-screen apps) and auto-hides on blur.

## Skills

1. **Browser** — owned Playwright engine (search / navigate / click / extract), policy-gated.
2. **Vision** — captures the screen (`mss`) and analyzes it with Groq vision.
3. **Developer** — clipboard read, file scaffolding, VS Code launch (allowlisted paths only,
   file writes require in-UI approval).

## Web engine (Chrome integration)

Two modes, set by `BROWSER_MODE` in `.env`:

- **`cdp` (default) — attach to your real Chrome.** Launch Chrome with a debugging port,
  then Lyra drives the browser you already use:

```bash
# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --user-data-dir="$HOME/Library/Application Support/Lyra/chrome-cdp"
```

  Set `CHROME_CDP_URL=http://127.0.0.1:9222` (the default).

- **`bundled` — Lyra launches its own Chromium** with an ephemeral profile (no setup;
  requires `playwright install chromium`).

All navigation passes a security policy: http/https only, no internal/loopback targets
(SSRF guard), optional host allow/deny lists (`BROWSER_ALLOWLIST` / `BROWSER_DENYLIST`),
downloads disabled, and a per-action time budget.

## Production packaging (Tauri sidecar)

For distribution, freeze the Python backend and ship it as a Tauri **sidecar**:

1. Build a single-file backend: `uv run pyinstaller --onefile -n lyra-backend src/main.py`
   (bundle the Kokoro weights via `LYRA_KOKORO_DIR` or PyInstaller `--add-data`).
2. Place the binary at `src-tauri/binaries/lyra-backend-<target-triple>`.
3. Register it under `bundle.externalBin` in `tauri.conf.json` and spawn it from
   Rust on startup (health-check + auto-restart), instead of `run.py`.
4. `npm run build` in `frontend/`, then `tauri build`.

## Development notes

- Keep secrets in `.env`; commit only `.env.example`.
- Conversation memory + audit trail persist to a single SQLite file (`LYRA_DB_PATH`).
- Kokoro weights download once on first `/tts`; bundle them for offline/first-run reliability.

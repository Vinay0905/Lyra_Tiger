# Lyra Tiger v2 — What Changed & How to Test (macOS)

This document summarizes the 8 enhancements + cleanup implemented from the
architecture blueprint, then gives a copy-paste test plan for your M4 MacBook.

---

## 1. Summary of changes

### Backend / Architecture

| ID | Enhancement | Key files |
|----|-------------|-----------|
| A1 | Async, non-blocking orchestration + structured `skill_result`; vision bypasses the formatter LLM | [src/llm.py](src/llm.py), [src/agent_state.py](src/agent_state.py), [src/nodes/*](src/nodes), [src/skills/*](src/skills) |
| A2 | End-to-end streaming via SSE `POST /command/stream` + sentence-chunked TTS | [src/main.py](src/main.py), [src/orchestrator.py](src/orchestrator.py) |
| A3 | Conversational memory + unified audit store (single SQLite file) | [src/memory.py](src/memory.py) |
| A4 | Tiered intent routing (heuristic → small → large) + TTL classify cache + content-hash TTS cache | [src/routing.py](src/routing.py), [src/cache.py](src/cache.py), [src/nodes/classifier.py](src/nodes/classifier.py) |

### UI / UX

| ID | Enhancement | Key files |
|----|-------------|-----------|
| U1 | Global shortcut **⌥Space** summon + Esc dismiss + summon-autofocus | [src-tauri/src/lib.rs](src-tauri/src/lib.rs), [frontend/src/App.tsx](frontend/src/App.tsx) |
| U2 | Streaming conversation transcript with markdown | [frontend/src/components/Transcript.tsx](frontend/src/components/Transcript.tsx), [frontend/src/hooks/useCommandStream.ts](frontend/src/hooks/useCommandStream.ts) |
| U3 | AudioWorklet capture (+ ScriptProcessor fallback), reduced-motion, hidden-window throttle, `-webkit-` prefixes | [frontend/public/pcm-recorder.js](frontend/public/pcm-recorder.js), [frontend/src/hooks/useVoiceCapture.ts](frontend/src/hooks/useVoiceCapture.ts), [frontend/src/components/OrbVisualizer.tsx](frontend/src/components/OrbVisualizer.tsx) |
| U4 | ⌘K command palette + persisted settings (endpoint/mic/voice/consent) | [frontend/src/components/CommandPalette.tsx](frontend/src/components/CommandPalette.tsx), [frontend/src/components/SettingsPanel.tsx](frontend/src/components/SettingsPanel.tsx), [frontend/src/store/useSettingsStore.ts](frontend/src/store/useSettingsStore.ts) |

### Cleanup

- Deleted legacy: `src/gui.py`, `src/hotkey.py`, root `main.py`, and the entire `ui/` folder.
- `requests` → `httpx` everywhere; dropped `pywebview` / `pynput` / `pyttsx3`.
- [README.md](README.md), [.env.example](.env.example), [pyproject.toml](pyproject.toml) updated; Kokoro weights can be bundled via `LYRA_KOKORO_DIR`; PyInstaller sidecar packaging documented.

### New backend endpoints

```text
POST /command          { text, session_id? }            # buffered
POST /command/stream   { text, session_id? }            # SSE token stream (A2)
POST /voice_command    multipart WAV  (?session_id=)     # transcribe + run
GET  /tts?text=...&voice=...                             # cached WAV (A4)
GET  /history?session_id=...                             # conversation memory (A3)
GET  /audit?session_id=...                               # unified audit trail (A3)
```

### Deviation to note (A3)

Conversational memory is implemented with a dedicated `aiosqlite` store + history
injection (single source of truth for memory **and** audit) rather than LangGraph's
`AsyncSqliteSaver` checkpointer. This avoids unbounded per-turn `action_logs` growth
and the bleeding-edge checkpointer API. Same user-facing outcome.

---

## 2. One-time setup on macOS

```bash
# From the repo root
cp .env.example .env            # then edit .env and set GROQ_API_KEY=...

# Python backend deps (pulls in httpx + aiosqlite, drops legacy pkgs)
uv sync

# Frontend deps (pulls in react-markdown + remark-gfm)
cd frontend && npm install && cd ..
```

Set at minimum in `.env`:

```env
GROQ_API_KEY=your_real_key
APPROVED_WORKSPACE_DIRS=/Users/<you>/Documents/AI_Assistant/sandbox
```

```bash
mkdir -p /Users/<you>/Documents/AI_Assistant/sandbox
```

---

## 3. Test the backend in isolation (no UI)

Start the API:

```bash
uv run python -m src.main
# → serving on http://127.0.0.1:8000
```

### 3.1 Health

```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```

Expect `status: healthy` and your allowlisted workspace count.

### 3.2 Buffered command + session memory (A1, A3)

```bash
# Turn 1 — capture the returned session_id
curl -s -X POST http://127.0.0.1:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text":"Hi Lyra, my name is Vinay."}' | python -m json.tool

# Turn 2 — reuse that session_id; Lyra should remember the name
curl -s -X POST http://127.0.0.1:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text":"What is my name?","session_id":"PASTE_SESSION_ID"}' | python -m json.tool
```

### 3.3 Streaming (A2)

You should see incremental `data:` events arrive over time, not all at once:

```bash
curl -N -X POST http://127.0.0.1:8000/command/stream \
  -H "Content-Type: application/json" \
  -d '{"text":"Give me three tips for focus.","session_id":"demo1"}'
```

Expect a stream like:

```text
data: {"type": "intent", "intent": "chat", "confidence": 0.95, "session_id": "demo1"}
data: {"type": "token", "text": "Three"}
data: {"type": "token", "text": " gentle"}
...
data: {"type": "done", "reply": "...", "route": "chat", "session_id": "demo1"}
```

### 3.4 Tiered routing + cache (A4)

```bash
# 'screenshot' should route via heuristic (vision), no LLM classify call
curl -s -X POST http://127.0.0.1:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text":"take a screenshot and explain it","session_id":"demo1"}' | python -m json.tool

# Repeat an identical query — 2nd /tts for the same text is served from cache (instant)
time curl -s "http://127.0.0.1:8000/tts?text=hello%20there" -o /tmp/a.wav
time curl -s "http://127.0.0.1:8000/tts?text=hello%20there" -o /tmp/b.wav   # much faster
afplay /tmp/a.wav
```

### 3.5 History + audit (A3)

```bash
curl -s "http://127.0.0.1:8000/history?session_id=demo1" | python -m json.tool
curl -s "http://127.0.0.1:8000/audit?session_id=demo1&limit=5" | python -m json.tool
# A single SQLite file now holds everything:
ls -la lyra_store.db
```

### 3.6 Voice (needs mic permission for the terminal)

```bash
# Provide any 16kHz mono WAV; server transcribes then runs the graph
curl -s -X POST "http://127.0.0.1:8000/voice_command?session_id=demo1" \
  -F "file=@/path/to/sample.wav" | python -m json.tool
```

---

## 4. Test the full desktop app (Rust shell + UI)

```bash
# Boots the FastAPI backend AND the Tauri dev window together
uv run python run.py
```

Then verify:

| Feature | How to check |
|---------|--------------|
| U1 global shortcut | Press **⌥Space** from any app → popover appears under the tray icon; press again or **Esc** → hides |
| U1 autofocus | On summon, the text input is focused so you can type immediately |
| U2 transcript | Send a few text commands → each user/assistant turn stacks in a scrollable list |
| U2 markdown | Ask "give me a bulleted list of 3 tips" → renders as real bullets/`code` |
| U2 + A2 streaming | The assistant reply "types out" and speech starts on the first sentence, not after the whole reply |
| U3 AudioWorklet | Open the Audit Trace panel (terminal icon) → log reads `Recording started (AudioWorklet).` |
| U3 reduced motion | System Settings → Accessibility → Display → **Reduce motion ON** → orb slows/stops rotating |
| U4 palette | Press **⌘K** → quick actions (New conversation, Screenshot & explain, Read clipboard, Search…) |
| U4 settings | Gear icon → change Voice / backend URL / mic; toggle "Allow screen capture"; reload persists them |
| U4 consent gate | With screen-capture consent OFF, the palette "Screenshot & explain" action is disabled |

### Quick smoke commands inside the app

- Type: `open github.com` → browser skill (needs Kimi WebBridge on `127.0.0.1:10086`).
- Type: `read my clipboard` → developer skill.
- ⌘K → **Screenshot & explain** (enable consent first) → vision skill.

---

## 5. macOS permissions (first run)

- **Microphone**: needed for voice. macOS will prompt on first record.
- **Screen Recording**: needed for the vision skill (`mss`). Grant it in
  System Settings → Privacy & Security → Screen Recording for your terminal / the Lyra app,
  then relaunch.

---

## 6. Production packaging (later)

See the "Production packaging (Tauri sidecar)" section in [README.md](README.md):
freeze the backend with PyInstaller, drop the binary in `src-tauri/binaries/`,
register it under `bundle.externalBin`, and spawn it from Rust instead of `run.py`.

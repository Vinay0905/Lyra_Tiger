# Lyra Tiger v3 (Industrial Uplift) — What Changed & How to Test (macOS)

This is the second wave of changes, on top of `WHATS_CHANGED.md`. It fixes the
menu-bar window anchoring, replaces the external Kimi WebBridge with an owned
Playwright web engine that drives your real Chrome, and hardens the backend and
UI to industrial grade.

---

## 1. Summary

### Logic / Backend

| ID | Enhancement | Key files |
|----|-------------|-----------|
| L1 | Owned Playwright web engine (attaches to your real Chrome via CDP; bundled Chromium fallback); Kimi removed | [src/skills/browser/](src/skills/browser) (`engine.py`, `playwright_adapter.py`, `extractor.py`, `policy.py`), [src/nodes/browser.py](src/nodes/browser.py) |
| L2 | Typed domain contracts: `Envelope[T]` + discriminated `SkillResult` union | [src/schemas.py](src/schemas.py) |
| L3 | Resilience + observability: timeout/backoff/circuit-breaker, structlog, `/metrics` | [src/resilience.py](src/resilience.py), [src/llm.py](src/llm.py), [src/main.py](src/main.py) |
| L4 | Governed skill registry + human-in-the-loop approval for side-effecting actions | [src/skills/registry.py](src/skills/registry.py), [src/orchestrator.py](src/orchestrator.py), [src/nodes/developer.py](src/nodes/developer.py) |

### Mac-Native Interface

| ID | Enhancement | Key files |
|----|-------------|-----------|
| UN1 | Window anchoring fix (on_tray_event cache) + NSPanel promotion + edge clamp + caret alignment | [src-tauri/src/lib.rs](src-tauri/src/lib.rs), [frontend/src/App.tsx](frontend/src/App.tsx) |
| UN2 | Token-based design system with light/dark auto-adapt + primitives | [frontend/src/index.css](frontend/src/index.css), [frontend/src/components/primitives.tsx](frontend/src/components/primitives.tsx) |
| UN3 | Connection state machine + `/health` polling + non-silent failure states | [frontend/src/hooks/useConnectionHealth.ts](frontend/src/hooks/useConnectionHealth.ts), [frontend/src/store/useAppStore.ts](frontend/src/store/useAppStore.ts) |
| UN4 | Rich result cards (URL chip / file reveal / Approve-Deny), per-message actions, searchable history | [frontend/src/components/ResultCard.tsx](frontend/src/components/ResultCard.tsx), [frontend/src/components/Transcript.tsx](frontend/src/components/Transcript.tsx), [frontend/src/components/HistoryDrawer.tsx](frontend/src/components/HistoryDrawer.tsx) |

### New / changed endpoints

```text
POST /confirm   { session_id, approve, action }   # resolve a gated action (L4)
GET  /metrics                                       # latency p50/p95, breaker, cache (L3)
GET  /health                                        # now reports active browser mode
```

### Removed

- `src/skills/webbridge.py` (Kimi WebBridge client) and all `WEBBRIDGE_*` config.

---

## 2. Why the old design fell short (and what replaced it)

- **Window centered instead of hanging:** the tray click handler never called
  `tauri_plugin_positioner::on_tray_event`, so `Position::TrayBottomCenter` had no
  cached tray rectangle and fell back to screen-center. Fixed by caching the rect,
  and promoting the window to a native **NSPanel** so it behaves like a status item.
- **Kimi WebBridge** was an unversioned, out-of-process, `curl | bash` daemon Lyra
  neither owned nor trusted. Replaced by an in-process, policy-gated Playwright
  engine Lyra launches, health-checks, and tears down itself.
- **Free-form dict/log plumbing** replaced by typed Pydantic contracts.
- **No fault policy / telemetry** replaced by circuit breakers + `/metrics`.
- **Ungoverned side effects** (file writes) now require explicit UI approval.

---

## 3. One-time setup on macOS

```bash
# Backend deps (adds playwright + structlog)
uv sync
uv run playwright install chromium      # for bundled mode / CDP fallback

# Frontend deps (adds @tauri-apps/plugin-opener)
cd frontend && npm install && cd ..

# Rust: tauri-nspanel (git v2) + opener plugin fetch on first build
```

Update `.env` (see `.env.example`) — new browser keys:

```env
BROWSER_MODE=cdp                         # cdp | bundled
CHROME_CDP_URL=http://127.0.0.1:9222
BROWSER_HEADLESS=False
BROWSER_ALLOWLIST=                       # empty = allow all except internal/denied
BROWSER_DENYLIST=
```

---

## 4. Test the window fix (UN1)

```bash
uv run python run.py
```

- Click the menu-bar icon: the popover must now **hang directly beneath the icon**,
  not appear at screen-center. Press **⌥Space**: same anchored placement.
- Move the icon near the right edge (or use the notch display): the panel should
  stay fully on-screen (edge clamp) and the caret should still point at the icon.
- Summon Lyra while another app is focused: it should appear **without deactivating**
  that app (NSPanel non-activating behavior) and float over full-screen apps.
- If it still centers: confirm `cargo build` picked up `tauri-nspanel` and that the
  `on_tray_event` line is present in [src-tauri/src/lib.rs](src-tauri/src/lib.rs).

---

## 5. Test the web engine (L1)

### Option A — attach to your real Chrome (CDP, default)

```bash
# 1. Launch Chrome with a debugging port
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Lyra/chrome-cdp"

# 2. Confirm the endpoint is up
curl -s http://127.0.0.1:9222/json/version | python -m json.tool

# 3. In Lyra, type:  open github.com   → your Chrome navigates
# 4. Type:  search google for tauri nspanel   → Chrome runs the search
```

### Option B — bundled Chromium

```env
BROWSER_MODE=bundled
```

```bash
uv run playwright install chromium
# In Lyra: open news.ycombinator.com  → a Lyra-managed Chromium opens
```

### Security policy checks

```bash
# Backend running (uv run python -m src.main). These should be BLOCKED:
curl -s -X POST http://127.0.0.1:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text":"open http://127.0.0.1:8000/health"}' | python -m json.tool   # internal IP → blocked
curl -s -X POST http://127.0.0.1:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text":"open file:///etc/passwd"}' | python -m json.tool             # file:// → blocked
```

The reply/audit trace should show "Blocked by security policy".

---

## 6. Test typed contracts + result cards (L2 + UN4)

```bash
# skill_result is now structured, not prose:
curl -s -X POST http://127.0.0.1:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text":"search google for playwright"}' | python -m json.tool
# → look for "skill_result": {"kind":"browser","action":"search","target":"...","ok":true,...}
```

In the desktop UI:
- A browser reply shows a clickable **URL chip**.
- Each assistant message has **Copy / Speak-again / Regenerate** controls.
- The **clock icon** (header) opens a searchable history drawer (backed by `/audit`);
  clicking an entry re-runs that command.

---

## 7. Test human-in-the-loop approval (L4)

```bash
# A file-writing request should NOT execute immediately:
curl -s -X POST http://127.0.0.1:8000/command \
  -H "Content-Type: application/json" \
  -d '{"text":"create a scaffold file","session_id":"demoL4"}' | python -m json.tool
# → response contains "pending_action": {"skill":"developer","operation":"scaffold",...}

# Approve it explicitly:
curl -s -X POST http://127.0.0.1:8000/confirm \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demoL4","approve":true,"action":{"skill":"developer","operation":"scaffold","payload":{"query":"create a scaffold file"}}}' | python -m json.tool
```

In the UI, the same flow renders inline **Approve / Deny** buttons under the message
(clipboard reads, being read-only, execute without a prompt).

---

## 8. Test resilience + metrics (L3)

```bash
curl -s http://127.0.0.1:8000/metrics | python -m json.tool
# → calls / failures / cache_hits / latency_ms {p50,p95} / breakers {llm.groq: "closed"}
```

- Temporarily set a bad `GROQ_API_KEY` and send a few commands: repeated failures should
  trip the breaker to `"open"` in `/metrics`, and requests fast-fail instead of hanging.

---

## 9. Test the design system (UN2) + connection states (UN3)

- Toggle macOS **System Settings → Appearance → Light/Dark**: the popover surface,
  text, and borders adapt automatically (token-driven, `prefers-color-scheme`).
- Stop the backend (`Ctrl-C`) while the UI is open: the status pill should move to
  **Reconnecting → Offline** rather than silently failing. Restart it → back to **Ready**.

---

## 10. Known runtime caveats (verify on the M4)

- **NSPanel API is version-sensitive.** `tauri-nspanel` is pinned to the git `v2`
  branch and uses macOS constants (`NONACTIVATING_PANEL_MASK = 1<<7`, collection-behavior
  bitflags `1|16|256`). If `cargo build` reports a method-name mismatch (e.g.
  `set_collection_behaviour`), it is a one-line rename against the pinned revision.
- **CDP requires the debugging port.** Without it, the engine auto-falls back to
  bundled Chromium (needs `playwright install chromium`).
- **Memory/audit** still use the `aiosqlite` store (single source of truth) rather than
  LangGraph's checkpointer — same behavior, bounded state.
- All Python compiles and the frontend passes lint here, but Rust + Playwright + NSPanel
  must be built and smoke-tested on macOS.

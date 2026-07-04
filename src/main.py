import io
import os
import json
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

import soundfile as sf
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.config import settings
from src.audio import transcribe_audio
from src.tts import TTSEngine
from src.llm import llm
from src.memory import store
from src.cache import tts_cache
from src.resilience import metrics
from src.orchestrator import compiled_agent, run_until_format
from src.nodes.formatter import build_formatter_prompt, SYSTEM_PERSONA
from src.nodes.developer import execute_developer_action
from src.skills.browser import get_browser_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.connect()
    yield
    await store.close()
    await llm.aclose()
    try:
        await get_browser_engine().aclose()
    except Exception:
        pass


app = FastAPI(
    title="Lyra Desktop Assistant Backend",
    version="2.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TTS engine is loaded lazily on first synthesis to avoid a heavy import-time cost.
_tts_engine: Optional[TTSEngine] = None


def _get_tts() -> TTSEngine:
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TTSEngine()
    return _tts_engine


# ── Models ─────────────────────────────────────────────────────────────────────
class CommandRequest(BaseModel):
    text: str
    session_id: Optional[str] = None


class CommandResponse(BaseModel):
    status: str
    reply: str
    route: str
    session_id: str
    transcription: Optional[str] = None
    skill_result: Optional[dict] = None
    pending_action: Optional[dict] = None


class ConfirmRequest(BaseModel):
    session_id: str
    approve: bool
    action: dict


async def _build_initial_state(query: str, session_id: str) -> dict:
    history = await store.get_history(session_id, limit=settings.history_turns)
    return {
        "session_id": session_id,
        "query": query,
        "intent": "chat",
        "confidence": 0.0,
        "history": history,
        "skill_result": None,
        "direct_response": False,
        "pending_action": None,
        "action_logs": ["Initiated request orchestration."],
        "final_response": "",
    }


async def _persist_turn(session_id: str, query_type: str, query: str, final_state: dict) -> None:
    await store.add_message(session_id, "user", query)
    await store.add_message(session_id, "assistant", final_state.get("final_response", ""))
    await store.log_audit(session_id, query_type, query, final_state)


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "browser_mode": settings.browser_mode,
        "browser_endpoint": settings.chrome_cdp_url if settings.browser_mode == "cdp" else "bundled",
        "allowlisted_workspaces": len(settings.approved_workspace_paths),
    }


# ── Buffered command (kept for compatibility / non-streaming clients) ──────────
@app.post("/command", response_model=CommandResponse)
async def handle_command(request: CommandRequest):
    query = request.text.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Command cannot be empty.")

    session_id = request.session_id or str(uuid.uuid4())
    initial_state = await _build_initial_state(query, session_id)

    try:
        final_state = await compiled_agent.ainvoke(initial_state)
        pending = final_state.get("pending_action")
        # Only persist a completed turn; a confirmation prompt is not a final turn.
        if not pending:
            await _persist_turn(session_id, "text", query, final_state)
        return CommandResponse(
            status="success",
            reply=final_state["final_response"],
            route=final_state["intent"],
            session_id=session_id,
            skill_result=final_state.get("skill_result"),
            pending_action=pending,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph Execution Error: {str(e)}")


@app.post("/confirm", response_model=CommandResponse)
async def handle_confirm(request: ConfirmRequest):
    """Resolve a human-in-the-loop gated action (L4)."""
    action = request.action or {}
    skill = action.get("skill")
    operation = action.get("operation", "")
    query = (action.get("payload") or {}).get("query", "")

    if not request.approve:
        reply = "Understood — I've cancelled that action."
        await store.add_message(request.session_id, "assistant", reply)
        return CommandResponse(status="success", reply=reply, route="developer",
                               session_id=request.session_id)

    try:
        if skill == "developer":
            result = await execute_developer_action(operation, query)
            reply = (
                f"Done. Created scaffold at {result.path}."
                if result.ok and result.path
                else f"The action could not be completed: {result.error}"
            )
            await store.add_message(request.session_id, "assistant", reply)
            return CommandResponse(status="success", reply=reply, route="developer",
                                   session_id=request.session_id, skill_result=result.model_dump())
        raise HTTPException(status_code=400, detail=f"Unknown skill for confirmation: {skill}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    return metrics.snapshot()


# ── Streaming command (A2): SSE token stream ───────────────────────────────────
def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/command/stream")
async def handle_command_stream(request: CommandRequest):
    query = request.text.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Command cannot be empty.")

    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator():
        collected = []
        intent = "chat"
        try:
            initial_state = await _build_initial_state(query, session_id)
            state = await run_until_format(initial_state)
            intent = state.get("intent", "chat")

            yield _sse({"type": "intent", "intent": intent,
                        "confidence": state.get("confidence", 0.0), "session_id": session_id})

            if state.get("direct_response") and state.get("final_response"):
                # Skill produced the answer already — stream it in sentence-sized chunks.
                text = state["final_response"]
                for chunk in _chunk_text(text):
                    collected.append(chunk)
                    yield _sse({"type": "token", "text": chunk})
                    await asyncio.sleep(0)
            else:
                prompt = build_formatter_prompt(state)
                async for token in llm.astream_chat_completion(prompt, SYSTEM_PERSONA):
                    collected.append(token)
                    yield _sse({"type": "token", "text": token})

            final_text = "".join(collected).strip()
            state["final_response"] = final_text
            pending = state.get("pending_action")
            # A confirmation prompt is not a completed turn — don't persist it.
            if not pending:
                await _persist_turn(session_id, "text-stream", query, state)
            yield _sse({
                "type": "done",
                "reply": final_text,
                "route": intent,
                "session_id": session_id,
                "skill_result": state.get("skill_result"),
                "pending_action": pending,
            })
        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _chunk_text(text: str, size: int = 24):
    """Yield word-ish chunks so a pre-computed answer still 'types' out."""
    words = text.split(" ")
    buf = []
    for w in words:
        buf.append(w)
        if sum(len(x) for x in buf) >= size:
            yield " ".join(buf) + " "
            buf = []
    if buf:
        yield " ".join(buf)


# ── Voice command ──────────────────────────────────────────────────────────────
@app.post("/voice_command", response_model=CommandResponse)
async def handle_voice_command(file: UploadFile = File(...), session_id: Optional[str] = None):
    sid = session_id or str(uuid.uuid4())
    temp_path = "temp_voice_command.wav"
    try:
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        transcription = await transcribe_audio(temp_path)
        if not transcription:
            raise HTTPException(status_code=400, detail="Could not capture speech.")
        print(f"[API] Transcribed input: '{transcription}'")

        initial_state = await _build_initial_state(transcription, sid)
        final_state = await compiled_agent.ainvoke(initial_state)
        await _persist_turn(sid, "voice", transcription, final_state)

        return CommandResponse(
            status="success",
            reply=final_state["final_response"],
            route=final_state["intent"],
            session_id=sid,
            transcription=transcription,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# ── TTS (with content-addressed cache, A4) ─────────────────────────────────────
@app.get("/tts")
async def get_tts(text: str, voice: Optional[str] = None):
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    engine = _get_tts()
    selected_voice = voice or engine.voice
    cache_key = tts_cache.make_key(text, selected_voice)

    cached = tts_cache.get(cache_key)
    if cached is not None:
        metrics.hit("tts")
        wav_bytes, _ = cached
        return StreamingResponse(io.BytesIO(wav_bytes), media_type="audio/wav")

    try:
        samples, sample_rate = await asyncio.to_thread(engine.generate, text, selected_voice)
        wav_io = io.BytesIO()
        sf.write(wav_io, samples, sample_rate, format="WAV", subtype="PCM_16")
        wav_bytes = wav_io.getvalue()
        tts_cache.set(cache_key, wav_bytes, sample_rate)
        return StreamingResponse(io.BytesIO(wav_bytes), media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS Synthesis Error: {str(e)}")


# ── History / Audit query API (A3) ─────────────────────────────────────────────
@app.get("/history")
async def get_history(session_id: str, limit: int = 20):
    return {"session_id": session_id, "messages": await store.get_history(session_id, limit)}


@app.get("/audit")
async def get_audit(session_id: Optional[str] = None, limit: int = 50):
    return {"entries": await store.get_audit(session_id, limit)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        reload_dirs=["src"] if settings.debug else None,
    )

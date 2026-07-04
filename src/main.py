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
from src.orchestrator import compiled_agent, run_until_format
from src.nodes.formatter import build_formatter_prompt, SYSTEM_PERSONA


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.connect()
    yield
    await store.close()
    await llm.aclose()


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
        "webbridge_endpoint": f"http://{settings.webbridge_host}:{settings.webbridge_port}",
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
        await _persist_turn(session_id, "text", query, final_state)
        return CommandResponse(
            status="success",
            reply=final_state["final_response"],
            route=final_state["intent"],
            session_id=session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph Execution Error: {str(e)}")


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
            await _persist_turn(session_id, "text-stream", query, state)
            yield _sse({"type": "done", "reply": final_text, "route": intent, "session_id": session_id})
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

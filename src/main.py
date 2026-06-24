from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import io
import soundfile as sf
from datetime import datetime
from src.config import settings
from src.audio import AudioRecorder, transcribe_audio
from src.tts import TTSEngine
from src.orchestrator import compiled_agent

app = FastAPI(
    title="Lyra Desktop Assistant Backend",
    version="1.0.0",
    debug=settings.debug
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate local recording/speaking blocks
recorder = AudioRecorder()
tts = TTSEngine()

def log_interaction(query_type: str, query: str, final_state: dict):
    timestamp = datetime.now().isoformat()
    intent = final_state.get("intent", "unknown")
    confidence = final_state.get("confidence", 0.0)
    reply = final_state.get("final_response", "")
    action_logs = final_state.get("action_logs", [])
    
    # 1. Write to structured lyra_audit.jsonl
    audit_entry = {
        "timestamp": timestamp,
        "query_type": query_type,
        "query": query,
        "intent": intent,
        "confidence": confidence,
        "reply": reply,
        "action_logs": action_logs
    }
    try:
        with open("lyra_audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[Logger Error] Failed to write to lyra_audit.jsonl: {e}")
        
    # 2. Write to human-readable lyra.log
    try:
        with open("lyra.log", "a", encoding="utf-8") as f:
            f.write("====================================================\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Query Type: {query_type.upper()}\n")
            f.write(f"User Query: {query}\n")
            f.write(f"Intent Classified: {intent} (confidence: {confidence:.2f})\n")
            f.write(f"Lyra Response: {reply}\n")
            f.write("Execution Log Trace:\n")
            for log in action_logs:
                f.write(f"  - {log}\n")
            f.write("====================================================\n\n")
    except Exception as e:
        print(f"[Logger Error] Failed to write to lyra.log: {e}")

class CommandRequest(BaseModel):
    text: str

class CommandResponse(BaseModel):
    status: str
    reply: str
    route: str

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "webbridge_endpoint": f"http://{settings.webbridge_host}:{settings.webbridge_port}",
        "allowlisted_workspaces": len(settings.approved_workspace_dirs)
    }

@app.post("/command", response_model=CommandResponse)
async def handle_command(request: CommandRequest):
    query = request.text.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Command cannot be empty.")
    
    # Initialize the default state variables
    initial_state = {
        "query": query,
        "intent": "chat",
        "confidence": 0.0,
        "history": [],
        "pending_action": None,
        "action_logs": ["Initiated request orchestration."],
        "final_response": ""
    }
    
    try:
        # Run state graph synchronously
        final_state = compiled_agent.invoke(initial_state)
        
        # Log structured audit metrics
        log_interaction("text", query, final_state)
        
        return CommandResponse(
            status="success",
            reply=final_state["final_response"],
            route=final_state["intent"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph Execution Error: {str(e)}")

@app.post("/voice_command", response_model=CommandResponse)
async def handle_voice_command(file: UploadFile = File(...)):
    import os
    temp_path = "temp_voice_command.wav"
    try:
        # Save the uploaded file to a temporary location
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Transcribe audio using Whisper
        transcription = transcribe_audio(temp_path)
        
        if not transcription:
            raise HTTPException(status_code=400, detail="Could not capture speech.")
            
        print(f"[API] Transcribed input: '{transcription}'")
        
        # Invoke compiled orchestrator graph with the transcription
        initial_state = {
            "query": transcription,
            "intent": "chat",
            "confidence": 0.0,
            "history": [],
            "pending_action": None,
            "action_logs": ["Initiated voice orchestration."],
            "final_response": ""
        }
        final_state = compiled_agent.invoke(initial_state)
        
        # Log structured audit metrics
        log_interaction("voice", transcription, final_state)
        
        return CommandResponse(
            status="success",
            reply=final_state["final_response"],
            route=final_state["intent"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

@app.get("/tts")
async def get_tts(text: str):
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    
    try:
        # Generate raw samples using our local Kokoro-ONNX TTS engine
        samples, sample_rate = tts.generate(text)
        
        # Save samples as a WAV file in memory
        wav_io = io.BytesIO()
        sf.write(wav_io, samples, sample_rate, format='WAV', subtype='PCM_16')
        wav_io.seek(0)
        
        return StreamingResponse(wav_io, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS Synthesis Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app", 
        host=settings.host, 
        port=settings.port, 
        reload=settings.debug,
        reload_dirs=["src"] if settings.debug else None
    )
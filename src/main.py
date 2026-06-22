from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
        return CommandResponse(
            status="success",
            reply=final_state["final_response"],
            route=final_state["intent"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph Execution Error: {str(e)}")

@app.post("/voice_command", response_model=CommandResponse)
async def handle_voice_command():
    try:
        # Record microphone audio
        wav_path = recorder.record()
        
        # Transcribe audio using Whisper
        transcription = transcribe_audio(wav_path)
        recorder.cleanup()
        
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
        
        # Play synthesized speech
        tts.speak(final_state["final_response"])
        
        return CommandResponse(
            status="success",
            reply=final_state["final_response"],
            route=final_state["intent"]
        )
        
    except Exception as e:
        recorder.cleanup()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=settings.debug)
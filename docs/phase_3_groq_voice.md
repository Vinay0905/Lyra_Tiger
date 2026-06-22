# Phase 3: Groq Integration (Voice In & Out)

In this phase, we build our voice processing layer: capturing microphone inputs using `sounddevice`, stopping recording automatically when silence is detected, sending audio to Groq Whisper for transcription, and outputting synthesized spoken text using macOS local utilities.

---

## 1. Directory Structure

At the end of this phase, your project tree should look exactly like this:
```text
AI_Assistant/
├── .env
├── pyproject.toml
├── uv.lock
├── ui/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── src/
    ├── __init__.py
    ├── audio.py
    ├── config.py
    ├── gui.py
    ├── llm.py
    ├── main.py
    └── tts.py
```

---

## 2. Step-by-Step File Creation

### Step 1: Create `src/audio.py`
Create a file named `src/audio.py` containing the audio recording and transcription routines:
```python
import os
import time
import requests
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
from src.config import settings

class AudioRecorder:
    """
    Handles recording audio from the default system microphone.
    Supports auto-termination using sound amplitude threshold metrics.
    """
    def __init__(self, sample_rate=16000, silence_threshold=0.03, silence_duration=1.5):
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.temp_file = "temp_voice.wav"

    def record(self) -> str:
        """
        Record audio from the microphone until silence is detected.
        Returns the absolute path to the recorded WAV file.
        """
        print("[Audio] Initializing recording. Speak now...")
        audio_data = []
        last_sound_time = time.time()
        block_size = int(self.sample_rate * 0.1) # 100ms blocks
        
        def callback(indata, frames, time_info, status):
            nonlocal last_sound_time
            rms = np.sqrt(np.mean(indata**2))
            audio_data.append(indata.copy())
            if rms > self.silence_threshold:
                last_sound_time = time.time()

        with sd.InputStream(samplerate=self.sample_rate, channels=1, 
                            blocksize=block_size, callback=callback):
            while True:
                sd.sleep(100)
                elapsed_silence = time.time() - last_sound_time
                if elapsed_silence > self.silence_duration:
                    print("[Audio] Silence detected. Finalizing recording...")
                    break
        
        if len(audio_data) > 0:
            recording = np.concatenate(audio_data, axis=0)
            wav.write(self.temp_file, self.sample_rate, recording)
            return os.path.abspath(self.temp_file)
        else:
            raise ValueError("No audio signals captured.")
            
    def cleanup(self):
        """Delete temporary voice files."""
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)

def transcribe_audio(file_path: str) -> str:
    """
    Transcribe WAV files using the Groq Whisper model (whisper-large-v3).
    """
    if not settings.groq_api_key:
        raise ValueError("Missing GROQ_API_KEY. Configure it inside your .env file.")
        
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "audio/wav")}
        data = {
            "model": "whisper-large-v3",
            "temperature": "0.0",
            "language": "en"
        }
        response = requests.post(url, headers=headers, files=files, data=data, timeout=15)
        
    if response.status_code != 200:
        raise RuntimeError(f"Whisper API call failed: {response.text}")
        
    return response.json().get("text", "").strip()
```

### Step 2: Create `src/tts.py`
Create a file named `src/tts.py` to handle speech synthesis:
```python
import sys
import subprocess

class TTSEngine:
    """
    Text-to-Speech Engine. Defaults to native OS utilities to minimize delay.
    """
    def __init__(self, rate=175):
        self.rate = rate
        self.is_mac = sys.platform == "darwin"

    def speak(self, text: str):
        print(f"[TTS] Speaking: {text}")
        clean_text = text.replace('"', '').replace("'", "").replace("*", "")
        
        if self.is_mac:
            # macOS built-in command 'say' runs locally and is near-instantaneous
            subprocess.run(["say", "-r", str(self.rate), clean_text])
        else:
            # Fallback for Windows/Linux
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty('rate', self.rate)
                engine.say(clean_text)
                engine.runAndWait()
            except ImportError:
                print("[TTS Warning] pyttsx3 not installed. Speech output disabled.")
```

### Step 3: Modify `src/main.py`
Replace the entire content of `src/main.py` with this updated version to wire in the audio recorder and TTS engines:
```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.config import settings
from src.audio import AudioRecorder, transcribe_audio
from src.tts import TTSEngine

app = FastAPI(
    title="Lyra Desktop Assistant Backend",
    version="1.0.0",
    debug=settings.debug
)

# Enable CORS for pywebview access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate engines
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
    query = request.text.strip().lower()
    if not query:
        raise HTTPException(status_code=400, detail="Command cannot be empty.")
    
    # Classify mock routes
    if "open" in query or "search" in query or "browser" in query:
        route = "browser"
        reply = f"Lyra: Routing command to Kimi WebBridge: '{request.text}'"
    elif "screen" in query or "see" in query or "explain" in query:
        route = "vision"
        reply = "Lyra: Launching screenshot capture."
    elif "file" in query or "write" in query or "scaffold" in query:
        route = "developer"
        reply = "Lyra: Invoking file scaffolding tools."
    else:
        route = "chat"
        reply = f"Lyra: Processing general response for '{request.text}'"
        
    return CommandResponse(
        status="success",
        reply=reply,
        route=route
    )

@app.post("/voice_command", response_model=CommandResponse)
async def handle_voice_command():
    """
    Summons the audio recorder, transcribes mic input via Groq Whisper,
    routes the query, and speaks the reply aloud.
    """
    try:
        # Step 1: Capture audio (stops when silence is detected)
        wav_path = recorder.record()
        
        # Step 2: Transcribe WAV using Groq Whisper API
        transcription = transcribe_audio(wav_path)
        recorder.cleanup() # Delete temp files
        
        if not transcription:
            raise HTTPException(status_code=400, detail="Could not capture speech.")
            
        print(f"[API] Transcribed input: '{transcription}'")
        
        # Step 3: Run router classification logic
        mock_req = CommandRequest(text=transcription)
        res = await handle_command(mock_req)
        
        # Step 4: Synthesize voice response
        tts.speak(res.reply)
        
        return res
        
    except Exception as e:
        recorder.cleanup()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=settings.debug)
```

---

## 3. Running & Verifying Phase 3
Start the FastAPI server:
```bash
uv run python -m src.main
```
Trigger the voice capture endpoint by making a POST request from a terminal:
```bash
curl -X POST http://127.0.0.1:8000/voice_command
```
1. Speak into your microphone immediately: *"Open GitHub"*
2. Stop talking for 1.5 seconds.
3. The server will detect the silence, transcribe the voice clip using Groq, print the output, speak the response aloud, and return the JSON response schema.

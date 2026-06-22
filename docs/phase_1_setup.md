# Phase 1: Environment Setup & Local Server Skeleton

In this phase, we initialize our project environment from scratch, set up dependency tracking with `uv`, construct our global settings models using `pydantic-settings`, implement a modular LLM client wrapper supporting API fallbacks (Groq, OpenAI, Gemini, OpenRouter), and build our FastAPI local server skeleton.

---

## 1. Directory Structure

At the end of this phase, your project tree should look exactly like this:
```text
AI_Assistant/
├── .env
├── pyproject.toml
├── uv.lock
└── src/
    ├── __init__.py
    ├── config.py
    ├── llm.py
    └── main.py
```

---

## 2. Step-by-Step File Creation

### Step 1: Initialize Project & Add Packages
Run these commands in your terminal:
```bash
# Initialize Python project
uv init --app

# Install required dependencies
uv add fastapi uvicorn pydantic pydantic-settings python-dotenv pynput sounddevice scipy requests pyperclip
```

### Step 2: Create `.env`
Create a file named `.env` in your root directory (`AI_Assistant/`) and add:
```env
# Primary LLM Provider API Keys
GROQ_API_KEY=gsk_your_groq_key_here
OPENAI_API_KEY=sk_your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here
OPENROUTER_API_KEY=your_openrouter_key_here

# LLM Fallback Chain Configuration (Comma-separated order of preference)
# Options: groq, openai, gemini, openrouter
LLM_FALLBACK_CHAIN=groq,openai,gemini

# Default Models to use per provider
GROQ_MODEL=llama3-70b-8192
GROQ_VISION_MODEL=llama-3.2-11b-vision-preview
OPENAI_MODEL=gpt-4o-mini
GEMINI_MODEL=gemini-1.5-flash
OPENROUTER_MODEL=meta-llama/llama-3-70b-instruct

# Local FastAPI Server configurations
HOST=127.0.0.1
PORT=8000
DEBUG=True

# Allowlisted Directories for Developer operations (Comma-separated absolute paths)
APPROVED_WORKSPACE_DIRS=/Users/mast/Documents/VInayPrograming/AI_Assistant/workspace

# Kimi WebBridge settings
WEBBRIDGE_HOST=127.0.0.1
WEBBRIDGE_PORT=10086
```

### Step 3: Create `src/config.py`
Create a file named `src/config.py` and write the complete validation schema code:
```python
import os
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Validates and stores system environment configuration parameters.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # API Keys
    groq_api_key: str = Field("", validation_alias="GROQ_API_KEY")
    openai_api_key: str = Field("", validation_alias="OPENAI_API_KEY")
    gemini_api_key: str = Field("", validation_alias="GEMINI_API_KEY")
    openrouter_api_key: str = Field("", validation_alias="OPENROUTER_API_KEY")

    # LLM Configurations
    llm_fallback_chain: List[str] = Field(default_factory=lambda: ["groq"], validation_alias="LLM_FALLBACK_CHAIN")
    groq_model: str = Field("llama3-70b-8192", validation_alias="GROQ_MODEL")
    groq_vision_model: str = Field("llama-3.2-11b-vision-preview", validation_alias="GROQ_VISION_MODEL")
    openai_model: str = Field("gpt-4o-mini", validation_alias="OPENAI_MODEL")
    gemini_model: str = Field("gemini-1.5-flash", validation_alias="GEMINI_MODEL")
    openrouter_model: str = Field("meta-llama/llama-3-70b-instruct", validation_alias="OPENROUTER_MODEL")

    # Local Server settings
    host: str = Field("127.0.0.1", validation_alias="HOST")
    port: int = Field(8000, validation_alias="PORT")
    debug: bool = Field(True, validation_alias="DEBUG")

    # Developer settings
    approved_workspace_dirs: List[str] = Field(default_factory=list, validation_alias="APPROVED_WORKSPACE_DIRS")

    # Kimi WebBridge settings
    webbridge_host: str = Field("127.0.0.1", validation_alias="WEBBRIDGE_HOST")
    webbridge_port: int = Field(10086, validation_alias="WEBBRIDGE_PORT")

    @field_validator("llm_fallback_chain", mode="before")
    @classmethod
    def parse_fallback_chain(cls, value: str) -> List[str]:
        if isinstance(value, str):
            return [v.strip().lower() for v in value.split(",") if v.strip()]
        return value

    @field_validator("approved_workspace_dirs", mode="before")
    @classmethod
    def parse_workspace_dirs(cls, value: str) -> List[str]:
        if isinstance(value, str):
            paths = [p.strip() for p in value.split(",") if p.strip()]
            return [os.path.abspath(os.path.expanduser(p)) for p in paths]
        return value

settings = Settings()
```

### Step 4: Create `src/llm.py`
Create a file named `src/llm.py` that implements our modular LLM wrapper with support for fallback APIs:
```python
import requests
from src.config import settings

class ModularLLMClient:
    """
    Unified client wrapper that routes completions through your preferred providers,
    falling back dynamically if keys are missing or requests fail.
    """
    def __init__(self):
        self.chain = settings.llm_fallback_chain

    def chat_completion(self, prompt: str, system_instruction: str = "") -> str:
        """Runs inference through fallback chain list until a success occurs."""
        errors = []
        for provider in self.chain:
            try:
                if provider == "groq" and settings.groq_api_key:
                    return self._call_groq(prompt, system_instruction)
                elif provider == "openai" and settings.openai_api_key:
                    return self._call_openai(prompt, system_instruction)
                elif provider == "gemini" and settings.gemini_api_key:
                    return self._call_gemini(prompt, system_instruction)
                elif provider == "openrouter" and settings.openrouter_api_key:
                    return self._call_openrouter(prompt, system_instruction)
            except Exception as e:
                err_msg = f"{provider.upper()} call failed: {str(e)}"
                print(f"[LLM Fallback] Warning: {err_msg}")
                errors.append(err_msg)
        
        raise RuntimeError(f"All LLM providers in chain failed: {'; '.join(errors)}")

    def _call_groq(self, prompt: str, system: str) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        payload = {"model": settings.groq_model, "messages": messages, "temperature": 0.2}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()

    def _call_openai(self, prompt: str, system: str) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": settings.openai_model, "messages": messages, "temperature": 0.2}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()

    def _call_gemini(self, prompt: str, system: str) -> str:
        # Google Gemini REST completion endpoint
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        headers = {"Content-Type": "application/json"}
        
        # Structure systemInstruction block
        contents = [{"parts": [{"text": prompt}]}]
        payload = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    def _call_openrouter(self, prompt: str, system: str) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": settings.openrouter_model, "messages": messages, "temperature": 0.2}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()

# Global LLM instance
llm = ModularLLMClient()
```

### Step 5: Create `src/main.py`
Create `src/main.py` to establish the API controller paths:
```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.config import settings

app = FastAPI(
    title="Lyra Desktop Assistant Backend",
    version="1.0.0",
    debug=settings.debug
)

# CORS wrapper setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
    # Mocking classification routes for pipeline validation
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
        reply = f"Lyra: '{request.text}' received."
        
    return CommandResponse(
        status="success",
        reply=reply,
        route=route
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=settings.debug)
```

---

## 3. Running & Verifying Phase 1
Start the backend web server with:
```bash
uv run python -m src.main
```
Verify the health check is active in another shell window:
```bash
curl http://127.0.0.1:8000/health
```
**Expected Response:**
```json
{"status":"healthy","webbridge_endpoint":"http://127.0.0.1:10086","allowlisted_workspaces":1}
```

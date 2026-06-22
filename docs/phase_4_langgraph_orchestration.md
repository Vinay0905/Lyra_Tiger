# Phase 4: Agentic State Machine (LangGraph Orchestrator)

In this phase, we construct the brain of Lyra: the LangGraph State Machine. You will learn how to define state variables, write classifier and response formatting nodes using our modular LLM interface with fallback services, build routing structures, and integrate the graph execution logic with the local API server.

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
    ├── agent_state.py
    ├── audio.py
    ├── config.py
    ├── gui.py
    ├── llm.py
    ├── main.py
    ├── orchestrator.py
    ├── tts.py
    └── nodes/
        ├── __init__.py
        ├── classifier.py
        └── formatter.py
```

---

## 2. Step-by-Step File Creation

### Step 1: Install LangGraph
Install LangGraph dependencies using `uv`:
```bash
uv add langgraph
```

### Step 2: Create `src/agent_state.py`
Create a file named `src/agent_state.py` to structure the state dictionary:
```python
from typing import TypedDict, List, Optional, Dict, Any

class AgentState(TypedDict):
    """
    State tracking schema passed between LangGraph nodes.
    """
    query: str
    intent: str
    confidence: float
    history: List[Dict[str, str]]
    pending_action: Optional[Dict[str, Any]]
    action_logs: List[str]
    final_response: str
```

### Step 3: Create `src/nodes/classifier.py`
Create a file named `src/nodes/classifier.py` to classify queries using our modular fallback LLM wrapper:
```python
import json
from src.agent_state import AgentState
from src.llm import llm

def classifier_node(state: AgentState) -> dict:
    query = state["query"]
    print(f"[Graph Node] Classifying: '{query}'")

    system_instruction = "You are the routing system for the Lyra Desktop Assistant. Output only valid JSON."
    prompt = f"""
    Analyze the user request and categorize it into exactly one of these intents:
    1. "browser": If the user wants to open websites, search online, scrape text, or navigate tabs.
    2. "vision": If they want to inspect their screen, analyze charts, explain desktop errors, or check screenshots.
    3. "developer": If they want to read the clipboard, create templates/files, or launch dev tools like VS Code.
    4. "chat": If they are greeting you, asking conversational questions, or if the request doesn't match the other categories.

    Output a valid JSON object matching this schema exactly:
    {{
        "intent": "browser" | "vision" | "developer" | "chat",
        "confidence": float (between 0.0 and 1.0)
    }}
    
    User Request: "{query}"
    """
    
    try:
        content = llm.chat_completion(prompt, system_instruction)
        
        # Clean potential markdown output formatting from other providers
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        parsed = json.loads(content.strip())
        return {
            "intent": parsed.get("intent", "chat"),
            "confidence": parsed.get("confidence", 0.0),
            "action_logs": [f"Parsed intent: {parsed.get('intent')} (conf: {parsed.get('confidence')})"]
        }
    except Exception as e:
        print(f"[Classifier Node Warning] LLM routing failed: {e}")
        return {
            "intent": "chat",
            "confidence": 1.0,
            "action_logs": [f"Classification error: {e}. Fallback to chat."]
        }
```

### Step 4: Create `src/nodes/formatter.py`
Create a file named `src/nodes/formatter.py` to format responses in Lyra's persona:
```python
from src.agent_state import AgentState
from src.llm import llm

def response_formatter_node(state: AgentState) -> dict:
    query = state["query"]
    intent = state["intent"]
    logs = "\n".join(state["action_logs"])
    
    print("[Graph Node] Formatting reply...")
    
    system_persona = """
    You are Lyra, a calm, highly intelligent female-presenting AI desktop assistant.
    Your tone is smooth, confident, and sophisticated. Use subtle starlight, astronomical,
    or musical resonance metaphors sparingly. Treat the user as a partner. Be concise.
    """

    prompt = f"""
    The user asked: "{query}"
    The system processed this via the '{intent}' skill module.
    Execution history logs:
    {logs}

    Formulate the final response speaking directly to the user. Make sure it sounds natural,
    concise, and captures Lyra's character. Do not include raw log syntax in your speech.
    """
    
    try:
        reply = llm.chat_completion(prompt, system_persona)
        return {"final_response": reply}
    except Exception as e:
        print(f"[Formatter Node Warning] LLM call failed: {e}")
        return {"final_response": "The resonance was disrupted. Let us try that again."}
```

### Step 5: Create `src/orchestrator.py`
Create a file named `src/orchestrator.py` to assemble and compile the LangGraph workflow:
```python
from langgraph.graph import StateGraph, END
from src.agent_state import AgentState
from src.nodes.classifier import classifier_node
from src.nodes.formatter import response_formatter_node

# Placeholder nodes for Skills (to be replaced in Phase 5 and 6)
def browser_skill_placeholder(state: AgentState) -> dict:
    print("[Graph Node] Entering Browser Placeholder...")
    return {"action_logs": ["Navigated to page via WebBridge placeholder"]}

def vision_skill_placeholder(state: AgentState) -> dict:
    print("[Graph Node] Entering Vision Placeholder...")
    return {"action_logs": ["Captured screenshot; explained error matrix"]}

def developer_skill_placeholder(state: AgentState) -> dict:
    print("[Graph Node] Entering Developer Placeholder...")
    return {"action_logs": ["Wrote scaffolding README to approved folder"]}

# Conditional routing rule
def route_intent(state: AgentState) -> str:
    intent = state["intent"]
    if intent == "browser":
        return "browser_skill"
    elif intent == "vision":
        return "vision_skill"
    elif intent == "developer":
        return "developer_skill"
    else:
        return "formatter"

# Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("classifier", classifier_node)
workflow.add_node("browser_skill", browser_skill_placeholder)
workflow.add_node("vision_skill", vision_skill_placeholder)
workflow.add_node("developer_skill", developer_skill_placeholder)
workflow.add_node("formatter", response_formatter_node)

workflow.set_entry_point("classifier")

workflow.add_conditional_edges(
    "classifier",
    route_intent,
    {
        "browser_skill": "browser_skill",
        "vision_skill": "vision_skill",
        "developer_skill": "developer_skill",
        "formatter": "formatter"
    }
)

workflow.add_edge("browser_skill", "formatter")
workflow.add_edge("vision_skill", "formatter")
workflow.add_edge("developer_skill", "formatter")
workflow.add_edge("formatter", END)

compiled_agent = workflow.compile()
```

### Step 6: Modify `src/main.py`
Replace the entire content of `src/main.py` with this updated script that runs the input query through the compiled state machine:
```python
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
```

---

## 3. Running & Verifying Phase 4
Start the FastAPI server:
```bash
uv run python -m src.main
```
Send a request to see the live classification and response formatter output (routing through Groq/OpenAI APIs):
```bash
curl -X POST -H "Content-Type: application/json" -d '{"text": "Search Google for Lyra constellation"}' http://127.0.0.1:8000/command
```
**Expected Response:**
```json
{
  "status": "success",
  "reply": "I've routed your search regarding the Lyra constellation through my browser core. Here are the parameters...",
  "route": "browser"
}
```
*(Notice how the response text has been formatted into Lyra's brand voice instead of a raw logs trace).*

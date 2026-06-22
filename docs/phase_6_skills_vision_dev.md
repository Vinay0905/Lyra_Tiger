# Phase 6: Screen Vision & Developer Command Skills

In this phase, we implement our two remaining nodes: **Screen Vision** (capturing desktop screenshots with `mss` and analyzing them with Llama 3.2 Vision on Groq) and **Developer Commands** (scaffolding code and reading clipboard text safely inside allowlisted directories).

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
    ├── nodes/
    │   ├── __init__.py
    │   ├── browser.py
    │   ├── classifier.py
    │   ├── developer.py
    │   ├── formatter.py
    │   └── vision.py
    └── skills/
        ├── __init__.py
        ├── developer.py
        ├── vision.py
        └── webbridge.py
```

---

## 2. Step-by-Step File Creation

### Step 1: Install Screenshot Dependencies
Ensure the native image utilities are loaded:
```bash
uv add mss
```

### Step 2: Create `src/skills/vision.py`
Create a file named `src/skills/vision.py` to capture screenshots and call Groq Llama 3.2 Vision model:
```python
import os
import base64
import requests
from mss import mss
from src.config import settings

class DesktopVisionClient:
    """
    Captures screenshots using mss and interacts with the
    Groq Llama 3.2 Vision API.
    """
    def __init__(self):
        self.screenshot_file = "temp_screen.png"

    def capture_screen(self) -> str:
        print("[Vision] Capturing primary monitor...")
        with mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.shot(output=self.screenshot_file)
            return os.path.abspath(sct_img)

    def analyze_screenshot(self, filepath: str, prompt: str) -> str:
        with open(filepath, "rb") as img_file:
            img_b64 = base64.b64encode(img_file.read()).decode("utf-8")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": settings.groq_vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.2
        }

        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def cleanup(self):
        if os.path.exists(self.screenshot_file):
            os.remove(self.screenshot_file)
```

### Step 3: Create `src/nodes/vision.py`
Create a file named `src/nodes/vision.py`:
```python
from src.agent_state import AgentState
from src.skills.vision import DesktopVisionClient

vision_client = DesktopVisionClient()

def vision_skill_node(state: AgentState) -> dict:
    logs = ["Initiating Screen Vision processing."]
    try:
        img_path = vision_client.capture_screen()
        logs.append("Screenshot captured successfully.")
        
        prompt = f"Analyze the screenshot. Explain what is shown on screen and resolve the user request: {state['query']}"
        analysis_result = vision_client.analyze_screenshot(img_path, prompt)
        
        logs.append("Analysis completed.")
        logs.append(f"Groq Vision Response:\n{analysis_result}")
    except Exception as e:
        logs.append(f"Vision capture error: {str(e)}")
    finally:
        vision_client.cleanup()
        
    return {
        "action_logs": logs
    }
```

### Step 4: Create `src/skills/developer.py`
Create a file named `src/skills/developer.py` to handle files, workspaces, and clipboards:
```python
import os
import subprocess
import pyperclip
from src.config import settings

class DevToolsClient:
    """
    Safely executes developer operations: clipboard read,
    writing boilerplate files, and launching applications inside approved folders.
    """
    def read_clipboard(self) -> str:
        print("[Dev Skill] Reading clipboard contents...")
        return pyperclip.paste()

    def _is_path_approved(self, path: str) -> bool:
        abs_target = os.path.abspath(path)
        for approved_dir in settings.approved_workspace_dirs:
            if abs_target.startswith(approved_dir):
                return True
        return False

    def write_scaffold(self, filename: str, content: str, folder_path: str) -> str:
        target_path = os.path.join(folder_path, filename)
        
        if not self._is_path_approved(target_path):
            raise PermissionError(
                f"Security block: path '{target_path}' is not within approved workspace paths."
            )
            
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"[Dev Skill] Scaffold file created: {target_path}")
        return target_path

    def launch_vs_code(self, folder_path: str):
        if not self._is_path_approved(folder_path):
            raise PermissionError("Access Denied: Path folder not approved.")
            
        print(f"[Dev Skill] Launching VS Code for: {folder_path}")
        # subprocess run without shell=True to prevent cmd injections
        subprocess.Popen(["code", folder_path], shell=False)
```

### Step 5: Create `src/nodes/developer.py`
Create a file named `src/nodes/developer.py`:
```python
from src.agent_state import AgentState
from src.skills.developer import DevToolsClient
from src.config import settings

dev_client = DevToolsClient()

def developer_skill_node(state: AgentState) -> dict:
    query = state["query"].lower()
    logs = ["Entering Developer Command Mode."]
    
    try:
        if "clipboard" in query:
            clipboard_text = dev_client.read_clipboard()
            logs.append(f"Successfully read clipboard text: '{clipboard_text[:150]}...'")
            logs.append(f"Full Clipboard Content:\n{clipboard_text}")
            
        elif "scaffold" in query or "create" in query or "file" in query:
            if not settings.approved_workspace_dirs:
                raise ValueError("No approved workspace directories specified in settings.")
                
            folder = settings.approved_workspace_dirs[0]
            
            # Simple markdown README scaffold
            filename = "README.md"
            content = f"# Scaffold Project\nGenerated by Lyra Desktop Assistant\nCommand context: {state['query']}"
            
            written_path = dev_client.write_scaffold(filename, content, folder)
            logs.append(f"Successfully generated scaffold file at: {written_path}")
            
            if "code" in query or "vscode" in query:
                dev_client.launch_vs_code(folder)
                logs.append("Triggered VS Code launch process.")
        else:
            logs.append("No matches found for specific developer commands.")
            
    except Exception as e:
        logs.append(f"Developer skill execution failed: {str(e)}")
        
    return {
        "action_logs": logs
    }
```

### Step 6: Modify `src/orchestrator.py`
Replace the entire content of `src/orchestrator.py` with the finalized orchestrator that incorporates all skills:
```python
from langgraph.graph import StateGraph, END
from src.agent_state import AgentState
from src.nodes.classifier import classifier_node
from src.nodes.formatter import response_formatter_node
from src.nodes.browser import browser_skill_node
from src.nodes.vision import vision_skill_node
from src.nodes.developer import developer_skill_node

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
workflow.add_node("browser_skill", browser_skill_node)
workflow.add_node("vision_skill", vision_skill_node)
workflow.add_node("developer_skill", developer_skill_node)
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

---

## 3. Running & Verifying Phase 6
Run the FastAPI backend:
```bash
uv run python -m src.main
```
Test the vision screenshot command:
```bash
curl -X POST -H "Content-Type: application/json" -d '{"text": "Analyze my screen and explain what is visible"}' http://127.0.0.1:8000/command
```
Ensure a screenshot file is created and cleaned up locally, that the API contacts the Groq Vision model, and that the returned response contains the visual breakdown of your active desktop screen.

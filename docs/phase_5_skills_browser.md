# Phase 5: Browser Skill Integration (Kimi WebBridge)

In this phase, we integrate the Kimi WebBridge client module into our LangGraph state machine. You will write the WebBridge HTTP client and update the orchestrator graph definition to route web queries through your active browser profile.

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
    │   └── formatter.py
    └── skills/
        ├── __init__.py
        └── webbridge.py
```

---

## 2. Step-by-Step File Creation

### Step 1: Create `src/skills/webbridge.py`
Create a file named `src/skills/webbridge.py` to communicate with the local daemon on port `10086`:
```python
import requests
from src.config import settings

class KimiWebBridgeClient:
    """
    Python client interfacing with the local Kimi WebBridge daemon API.
    Enables page navigation, DOM queries, element clicks, form fills,
    and accessibility snapshots.
    """
    def __init__(self):
        self.base_url = f"http://{settings.webbridge_host}:{settings.webbridge_port}"
        
    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}/api/{endpoint}"
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code != 200:
                raise RuntimeError(f"WebBridge error on {endpoint}: {response.text}")
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Could not connect to Kimi WebBridge daemon: {e}")

    def navigate(self, url: str) -> dict:
        print(f"[WebBridge] Navigating to: {url}")
        return self._post("navigate", {"url": url})

    def get_snapshot(self) -> dict:
        print("[WebBridge] Requesting accessibility snapshot...")
        return self._post("snapshot", {})

    def click(self, selector: str) -> dict:
        print(f"[WebBridge] Clicking element: {selector}")
        return self._post("click", {"selector": selector})

    def fill(self, selector: str, text: str) -> dict:
        print(f"[WebBridge] Filling element {selector} with value: {text}")
        return self._post("fill", {"selector": selector, "text": text})

    def get_screenshot(self) -> str:
        print("[WebBridge] Capturing page screenshot...")
        res = self._post("screenshot", {})
        return res.get("base64", "")
```

### Step 2: Create `src/nodes/browser.py`
Create a file named `src/nodes/browser.py`. This uses native `urllib.parse.quote` for URL-safe query generation:
```python
import re
import urllib.parse
from src.agent_state import AgentState
from src.skills.webbridge import KimiWebBridgeClient

# Instantiate global WebBridge client
webbridge = KimiWebBridgeClient()

def browser_skill_node(state: AgentState) -> dict:
    """
    Executes web browser actions using Kimi WebBridge.
    Extracts URLs from user queries or creates Google Search targets.
    """
    query = state["query"]
    logs = []
    
    # Simple regex to check for URLs in user query
    url_pattern = re.compile(r'(https?://[^\s]+)')
    match = url_pattern.search(query)
    
    if match:
        target_url = match.group(1)
        logs.append(f"Extracted target URL: {target_url}")
    else:
        # Generate Google search URL if no raw URL is passed
        clean_query = query.replace("search", "").replace("google", "").strip()
        search_term = urllib.parse.quote(clean_query)
        target_url = f"https://www.google.com/search?q={search_term}"
        logs.append(f"Synthesized Google Search URL: {target_url}")

    try:
        # Step 1: Open page
        webbridge.navigate(target_url)
        logs.append(f"WebBridge navigated successfully to: {target_url}")
        
        # Step 2: Retrieve structural content (snapshot)
        snapshot = webbridge.get_snapshot()
        page_title = snapshot.get("title", "Unknown Webpage")
        visible_text = snapshot.get("text", "")[:2500]  # Slice content to manage LLM token limits
        
        logs.append(f"Scraped title: '{page_title}'")
        logs.append(f"Scraped Webpage Content Snippet:\n{visible_text}")
        
    except Exception as e:
        logs.append(f"WebBridge execution failed: {str(e)}")
        
    return {
        "action_logs": logs
    }
```

### Step 3: Modify `src/orchestrator.py`
Replace the entire content of `src/orchestrator.py` with this version, integrating the active `browser_skill_node` and retaining placeholders for vision and developer skills:
```python
from langgraph.graph import StateGraph, END
from src.agent_state import AgentState
from src.nodes.classifier import classifier_node
from src.nodes.formatter import response_formatter_node
from src.nodes.browser import browser_skill_node

# Placeholder nodes for remaining Skills (replaced in Phase 6)
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
workflow.add_node("browser_skill", browser_skill_node) # Integrated active node
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

---

## 3. Running & Verifying Phase 5
1. Make sure your browser daemon is active (`kimi-webbridge status` displays `running: true`).
2. Run the server:
   ```bash
   uv run python -m src.main
   ```
3. Request a search command:
   ```bash
   curl -X POST -H "Content-Type: application/json" -d '{"text": "Search Google for Moonshot AI WebBridge"}' http://127.0.0.1:8000/command
   ```
4. Observe your active browser: a new tab should open in the background (or foreground depending on your browser focus settings) navigating to Google search, extraction logs will print to the console, and Lyra will reply summarizing the search results snippet.

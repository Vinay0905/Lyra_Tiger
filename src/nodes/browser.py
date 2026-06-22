import re
import json
import urllib.parse
from src.agent_state import AgentState
from src.skills.webbridge import KimiWebBridgeClient
from src.llm import llm

# Instantiate global WebBridge client
webbridge = KimiWebBridgeClient()

def clean_tree_representation(tree_data) -> str:
    """
    Serializes and truncates page tree data to prevent large payload errors (413) in LLM APIs.
    """
    if not tree_data:
        return ""
    if isinstance(tree_data, str):
        return tree_data[:3000]
    if isinstance(tree_data, dict):
        return json.dumps(tree_data, indent=2)[:3000]
    if isinstance(tree_data, list):
        lines = []
        for item in tree_data:
            if isinstance(item, dict):
                role = item.get("role") or item.get("type") or "element"
                name = item.get("name") or item.get("text") or item.get("label") or ""
                element_id = item.get("id") or item.get("elementId") or ""
                lines.append(f"[{role}] {element_id} {repr(name)}")
            else:
                lines.append(str(item))
        return "\n".join(lines)[:3000]
    return str(tree_data)[:3000]

def browser_skill_node(state: AgentState) -> dict:
    """
    Executes web browser actions using Kimi WebBridge.
    Runs a multi-step agent loop using the LLM to decide on actions
    (navigate, click, fill, done) based on the browser's accessibility tree.
    """
    query = state["query"]
    logs = ["Initiating browser orchestration loop."]
    
    max_steps = 5
    step_history = []
    
    # We will start by obtaining the current browser snapshot to see where we are
    current_url = ""
    current_title = ""
    current_tree = ""
    
    try:
        snapshot = webbridge.get_snapshot()
        current_url = snapshot.get("url", "")
        current_title = snapshot.get("title", "")
        raw_tree = snapshot.get("tree") or snapshot.get("text") or snapshot.get("content") or ""
        current_tree = clean_tree_representation(raw_tree)
        logs.append(f"Initial page state: Title: '{current_title}', URL: {current_url}")
    except Exception as e:
        logs.append(f"Failed to fetch initial page state: {e}")

    for step in range(1, max_steps + 1):
        logs.append(f"--- Browser Loop Step {step} ---")
        
        system_instruction = (
            "You are the browser agent controller for Lyra. "
            "Your job is to decide on the next browser action to satisfy the user's query. "
            "Output ONLY valid JSON matching the specified schema."
        )
        
        prompt = f"""
        User Query: "{query}"

        Current Browser State:
        - URL: {current_url}
        - Title: {current_title}
        - Simplified Page Tree (Accessibility / Text layout):
        {current_tree}

        Action History:
        {json.dumps(step_history, indent=2)}

        Decide on the next action. You can perform one of the following:
        1. "navigate": Open a specific URL. Useful to go directly to search pages or platforms (like youtube.com, github.com, google.com).
        2. "click": Click an element. Identify the element ID (e.g. "@e12") or CSS selector from the Page Tree.
        3. "fill": Type text into a form input or search bar. Identify the element ID (e.g. "@e15") and specify the text.
        4. "done": Exit the loop. Choose this once the user request has been fully completed (e.g. you navigated to and opened the correct video/page).

        Output a valid JSON object matching this schema exactly:
        {{
            "thought": "Brief explanation of what you see on the screen and what action you will take next",
            "action": "navigate" | "click" | "fill" | "done",
            "url": "string (only required for navigate)",
            "selector": "string (only required for click and fill, e.g. '@e25' or a valid CSS selector)",
            "text": "string (only required for fill)"
        }}
        """

        try:
            content = llm.chat_completion(prompt, system_instruction)
            
            # Clean markdown JSON wraps
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            decision = json.loads(content.strip())
            
            thought = decision.get("thought", "")
            action = decision.get("action", "done").lower()
            
            logs.append(f"Agent Thought: {thought}")
            
            if action == "done":
                logs.append("Agent declared task is complete.")
                break
                
            elif action == "navigate":
                url = decision.get("url")
                if not url:
                    raise ValueError("Navigate action missing 'url'")
                logs.append(f"Navigating to: {url}")
                webbridge.navigate(url)
                step_history.append({"step": step, "action": "navigate", "url": url, "thought": thought})
                
            elif action == "click":
                selector = decision.get("selector")
                if not selector:
                    raise ValueError("Click action missing 'selector'")
                logs.append(f"Clicking selector: {selector}")
                webbridge.click(selector)
                step_history.append({"step": step, "action": "click", "selector": selector, "thought": thought})
                
            elif action == "fill":
                selector = decision.get("selector")
                text = decision.get("text")
                if not selector or text is None:
                    raise ValueError("Fill action missing 'selector' or 'text'")
                logs.append(f"Filling selector {selector} with text: {text}")
                webbridge.fill(selector, text)
                step_history.append({"step": step, "action": "fill", "selector": selector, "text": text, "thought": thought})
                
            else:
                logs.append(f"Unknown action: '{action}'. Defaulting to done.")
                break

            # Update the page state for the next iteration
            snapshot = webbridge.get_snapshot()
            current_url = snapshot.get("url", "")
            current_title = snapshot.get("title", "")
            raw_tree = snapshot.get("tree") or snapshot.get("text") or snapshot.get("content") or ""
            current_tree = clean_tree_representation(raw_tree)
            logs.append(f"Updated page: '{current_title}', URL: {current_url}")

        except Exception as e:
            logs.append(f"Error during step {step} execution: {str(e)}")
            logs.append("Aborting browser loop due to error.")
            break
            
    return {
        "action_logs": logs
    }
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
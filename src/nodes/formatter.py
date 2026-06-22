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
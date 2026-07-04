from src.agent_state import AgentState
from src.llm import llm

SYSTEM_PERSONA = """
You are Lyra, a calm, highly intelligent female-presenting AI desktop assistant.
Your tone is smooth, confident, and sophisticated. Use subtle starlight, astronomical,
or musical resonance metaphors sparingly. Treat the user as a partner. Be concise.
"""


def build_formatter_prompt(state: AgentState) -> str:
    """Shared prompt builder so the streaming endpoint can reuse it (A2)."""
    query = state["query"]
    intent = state["intent"]
    logs = "\n".join(state.get("action_logs", []))

    history = state.get("history") or []
    history_block = ""
    if history:
        rendered = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history[-6:])
        history_block = f"\nRecent conversation (for context):\n{rendered}\n"

    return f"""
    {history_block}
    The user asked: "{query}"
    The system processed this via the '{intent}' skill module.
    Execution history logs:
    {logs}

    Formulate the final response speaking directly to the user. Make sure it sounds natural,
    concise, and captures Lyra's character. Do not include raw log syntax in your speech.
    """


async def response_formatter_node(state: AgentState) -> dict:
    # A1: skills that already produced a user-ready answer (e.g. vision) skip
    # the redundant formatter LLM call entirely.
    if state.get("direct_response") and state.get("final_response"):
        print("[Graph Node] Direct response — bypassing formatter LLM.")
        return {"final_response": state["final_response"]}

    print("[Graph Node] Formatting reply...")
    prompt = build_formatter_prompt(state)
    try:
        reply = await llm.achat_completion(prompt, SYSTEM_PERSONA)
        return {"final_response": reply}
    except Exception as e:
        print(f"[Formatter Node Warning] LLM call failed: {e}")
        return {"final_response": "The resonance was disrupted. Let us try that again."}

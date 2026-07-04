import json

from src.agent_state import AgentState
from src.llm import llm
from src.routing import heuristic_route
from src.cache import classify_cache
from src.resilience import metrics

_VALID_INTENTS = {"browser", "vision", "developer", "chat"}


def _parse_intent(content: str) -> dict:
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    parsed = json.loads(content.strip())
    intent = parsed.get("intent", "chat")
    if intent not in _VALID_INTENTS:
        intent = "chat"
    return {"intent": intent, "confidence": float(parsed.get("confidence", 0.0))}


async def _llm_classify(query: str, model: str) -> dict:
    system_instruction = "You are the routing system for the Lyra Desktop Assistant. Output only valid JSON."
    prompt = f"""
    Analyze the user request and categorize it into exactly one of these intents:
    1. "browser": open websites, search online, scrape text, or navigate tabs.
    2. "vision": inspect the screen, analyze charts, explain desktop errors, or check screenshots.
    3. "developer": read the clipboard, create templates/files, or launch dev tools like VS Code.
    4. "chat": greetings, conversational questions, or anything not matching the above.

    Output a valid JSON object matching this schema exactly:
    {{
        "intent": "browser" | "vision" | "developer" | "chat",
        "confidence": float (between 0.0 and 1.0)
    }}

    User Request: "{query}"
    """
    content = await llm.achat_completion(prompt, system_instruction, model=model)
    return _parse_intent(content)


async def classifier_node(state: AgentState) -> dict:
    """
    A4 tiered intent routing:
      Tier 0 — deterministic heuristic (no network).
      Tier 1 — small/fast model for ambiguous queries.
      Tier 2 — large model fallback on error.
    Results are memoized in a TTL cache keyed by the normalized query.
    """
    query = state["query"]
    cache_key = query.strip().lower()
    print(f"[Graph Node] Classifying: '{query}'")

    cached = classify_cache.get(cache_key)
    if cached is not None:
        metrics.hit("classify")
        return {
            "intent": cached["intent"],
            "confidence": cached["confidence"],
            "action_logs": [f"Intent (cached): {cached['intent']} (conf: {cached['confidence']})"],
        }

    # Tier 0 — heuristic
    heuristic = heuristic_route(query)
    if heuristic is not None:
        intent, confidence = heuristic
        classify_cache.set(cache_key, {"intent": intent, "confidence": confidence})
        return {
            "intent": intent,
            "confidence": confidence,
            "action_logs": [f"Intent (heuristic): {intent} (conf: {confidence:.2f})"],
        }

    # Tier 1 — small model
    try:
        from src.config import settings
        result = await _llm_classify(query, settings.groq_small_model)
        classify_cache.set(cache_key, result)
        return {
            "intent": result["intent"],
            "confidence": result["confidence"],
            "action_logs": [f"Intent (small model): {result['intent']} (conf: {result['confidence']})"],
        }
    except Exception as small_err:
        print(f"[Classifier] Small-model tier failed: {small_err}. Escalating to large model.")

    # Tier 2 — large model fallback
    try:
        from src.config import settings
        result = await _llm_classify(query, settings.primary_chat_model)
        classify_cache.set(cache_key, result)
        return {
            "intent": result["intent"],
            "confidence": result["confidence"],
            "action_logs": [f"Intent (large model): {result['intent']} (conf: {result['confidence']})"],
        }
    except Exception as e:
        print(f"[Classifier Node Warning] LLM routing failed: {e}")
        return {
            "intent": "chat",
            "confidence": 1.0,
            "action_logs": [f"Classification error: {e}. Fallback to chat."],
        }

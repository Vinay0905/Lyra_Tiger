from operator import add
from typing import TypedDict, List, Optional, Dict, Any, Annotated


class AgentState(TypedDict):
    """
    State tracking schema passed between LangGraph nodes.

    ``action_logs`` uses an additive reducer so every node appends to a single
    trace within one invocation (instead of overwriting the previous node's
    logs). ``history`` carries prior conversation turns loaded from the SQLite
    store for multi-turn context. ``skill_result`` is the structured output of a
    skill node, and ``direct_response`` lets a skill signal that it already
    produced a user-ready answer so the formatter LLM call can be skipped.
    """
    session_id: str
    query: str
    intent: str
    confidence: float
    history: List[Dict[str, str]]
    skill_result: Optional[Dict[str, Any]]
    direct_response: bool
    pending_action: Optional[Dict[str, Any]]
    action_logs: Annotated[List[str], add]
    final_response: str

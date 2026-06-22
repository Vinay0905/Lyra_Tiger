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
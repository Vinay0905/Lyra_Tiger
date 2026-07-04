from langgraph.graph import StateGraph, END

from src.agent_state import AgentState
from src.nodes.classifier import classifier_node
from src.nodes.formatter import response_formatter_node
from src.nodes.browser import browser_skill_node
from src.nodes.vision import vision_skill_node
from src.nodes.developer import developer_skill_node

_SKILL_NODES = {
    "browser": browser_skill_node,
    "vision": vision_skill_node,
    "developer": developer_skill_node,
}


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
        "formatter": "formatter",
    },
)

workflow.add_edge("browser_skill", "formatter")
workflow.add_edge("vision_skill", "formatter")
workflow.add_edge("developer_skill", "formatter")
workflow.add_edge("formatter", END)

compiled_agent = workflow.compile()


def _merge(state: dict, update: dict) -> dict:
    """Merge a node's partial output into the running state, honoring the
    additive semantics of ``action_logs`` used by the compiled graph."""
    for key, value in update.items():
        if key == "action_logs":
            state["action_logs"] = state.get("action_logs", []) + list(value)
        else:
            state[key] = value
    return state


async def run_until_format(initial_state: dict) -> dict:
    """
    Runs classification + the selected skill (everything except the formatter)
    so the streaming endpoint can stream the final reply token-by-token while
    still reusing the exact node logic (A2).
    """
    state = dict(initial_state)
    state = _merge(state, await classifier_node(state))

    intent = state.get("intent", "chat")
    skill = _SKILL_NODES.get(intent)
    if skill is not None:
        state = _merge(state, await skill(state))

    return state

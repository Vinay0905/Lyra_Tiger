from langgraph.graph import StateGraph, END

from src.agent_state import AgentState
from src.nodes.classifier import classifier_node
from src.nodes.formatter import response_formatter_node
from src.skills.registry import SKILL_REGISTRY, spec_for_intent


def route_intent(state: AgentState) -> str:
    """Route to the registered skill node for the intent, else the formatter."""
    spec = spec_for_intent(state["intent"])
    return spec.node_key if spec else "formatter"


workflow = StateGraph(AgentState)
workflow.add_node("classifier", classifier_node)
workflow.add_node("formatter", response_formatter_node)

# Nodes + edges are assembled from the registry (open/closed): registering a new
# SkillSpec is all that's needed to extend the graph.
_routing_map = {"formatter": "formatter"}
for spec in SKILL_REGISTRY.values():
    workflow.add_node(spec.node_key, spec.node)
    workflow.add_edge(spec.node_key, "formatter")
    _routing_map[spec.node_key] = spec.node_key

workflow.set_entry_point("classifier")
workflow.add_conditional_edges("classifier", route_intent, _routing_map)
workflow.add_edge("formatter", END)

compiled_agent = workflow.compile()


def _merge(state: dict, update: dict) -> dict:
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
    reusing the exact node logic (A2).
    """
    state = dict(initial_state)
    state = _merge(state, await classifier_node(state))

    spec = spec_for_intent(state.get("intent", "chat"))
    if spec is not None:
        state = _merge(state, await spec.node(state))

    return state

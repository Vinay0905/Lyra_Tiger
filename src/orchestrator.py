from langgraph.graph import StateGraph, END
from src.agent_state import AgentState
from src.nodes.classifier import classifier_node
from src.nodes.formatter import response_formatter_node
from src.nodes.browser import browser_skill_node
from src.nodes.vision import vision_skill_node
from src.nodes.developer import developer_skill_node

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
        "formatter": "formatter"
    }
)

workflow.add_edge("browser_skill", "formatter")
workflow.add_edge("vision_skill", "formatter")
workflow.add_edge("developer_skill", "formatter")
workflow.add_edge("formatter", END)

compiled_agent = workflow.compile()
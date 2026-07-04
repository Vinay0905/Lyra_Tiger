from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List

from src.agent_state import AgentState
from src.nodes.browser import browser_skill_node
from src.nodes.developer import developer_skill_node
from src.nodes.vision import vision_skill_node

SkillNode = Callable[[AgentState], Awaitable[dict]]


@dataclass(frozen=True)
class SkillSpec:
    """
    Declarative description of a skill (L4). Adding a skill is registration, not
    graph surgery — the orchestrator builds nodes/edges from this registry, so
    the graph is open for extension and closed for modification.
    """
    name: str
    intent: str
    node: SkillNode
    node_key: str
    permission_scopes: List[str] = field(default_factory=list)
    side_effecting: bool = False
    description: str = ""


SKILL_REGISTRY: Dict[str, SkillSpec] = {
    "browser": SkillSpec(
        name="Browser",
        intent="browser",
        node=browser_skill_node,
        node_key="browser_skill",
        permission_scopes=["net.navigate"],
        side_effecting=False,  # navigation itself is read-oriented; policy-gated
        description="Search, navigate, and extract web pages via the owned engine.",
    ),
    "vision": SkillSpec(
        name="Vision",
        intent="vision",
        node=vision_skill_node,
        node_key="vision_skill",
        permission_scopes=["screen.capture"],
        side_effecting=False,
        description="Capture and analyze the screen.",
    ),
    "developer": SkillSpec(
        name="Developer",
        intent="developer",
        node=developer_skill_node,
        node_key="developer_skill",
        permission_scopes=["fs.write", "process.launch", "clipboard.read"],
        side_effecting=True,  # file writes / process launch require approval
        description="Clipboard read, file scaffolding, and editor launch.",
    ),
}


def spec_for_intent(intent: str) -> SkillSpec | None:
    return SKILL_REGISTRY.get(intent)

from typing import Generic, List, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, Field

from src.skills.browser.engine import PageModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """
    Uniform result wrapper for every skill/integration boundary (L2).

    Carries success state, the typed payload, a normalized error, and telemetry
    so the orchestrator, formatter, and UI never parse free-form dicts.
    """
    ok: bool = True
    data: Optional[T] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    trace_id: str = ""


# ── Discriminated skill results ────────────────────────────────────────────────
class BrowserResult(BaseModel):
    kind: Literal["browser"] = "browser"
    action: str = "none"          # search | navigate | click | done
    target: str = ""              # URL or selector acted upon
    ok: bool = False
    page: Optional[PageModel] = None
    query: Optional[str] = None
    platform: Optional[str] = None


class VisionResult(BaseModel):
    kind: Literal["vision"] = "vision"
    analysis: str = ""
    screenshot_path: Optional[str] = None
    error: Optional[str] = None


class DeveloperResult(BaseModel):
    kind: Literal["developer"] = "developer"
    operation: str = "none"       # clipboard | scaffold | none
    ok: bool = False
    content: Optional[str] = None
    path: Optional[str] = None
    launched_vscode: bool = False
    error: Optional[str] = None


SkillResult = Union[BrowserResult, VisionResult, DeveloperResult]


class PendingAction(BaseModel):
    """A side-effecting action awaiting human approval (L4)."""
    skill: str
    operation: str
    description: str
    payload: dict = Field(default_factory=dict)

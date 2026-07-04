from typing import List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class InteractiveElement(BaseModel):
    """A single actionable element in the extracted page index."""
    ref: str = Field(..., description="Stable selector handle, e.g. '@e12'")
    role: str = Field("element", description="a | button | input | link | ...")
    name: str = Field("", description="Visible/accessible label")


class PageModel(BaseModel):
    """
    Typed representation of a page after extraction. Replaces the ad-hoc string
    tree previously flattened for the LLM: bounded, deterministic, LLM-friendly.
    """
    url: str = ""
    title: str = ""
    main_text: str = ""
    elements: List[InteractiveElement] = Field(default_factory=list)

    def to_prompt_block(self, max_elems: int = 40) -> str:
        lines = [f"[{e.role}] {e.ref} {e.name!r}" for e in self.elements[:max_elems]]
        return "\n".join(lines)


@runtime_checkable
class BrowserEngine(Protocol):
    """
    Port for any web-access backend. Lyra depends on this interface, not on a
    concrete vendor (Playwright today, swappable tomorrow). All methods are
    async and must be safe to call after a crash (the adapter re-initializes).
    """

    async def navigate(self, url: str) -> PageModel: ...

    async def snapshot(self) -> PageModel: ...

    async def click(self, ref: str) -> PageModel: ...

    async def fill(self, ref: str, text: str) -> PageModel: ...

    async def extract(self) -> PageModel: ...

    async def screenshot(self) -> bytes: ...

    async def aclose(self) -> None: ...

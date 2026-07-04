import json
import urllib.parse

from src.agent_state import AgentState
from src.llm import llm
from src.schemas import BrowserResult
from src.skills.browser import get_browser_engine
from src.skills.browser.engine import PageModel
from src.skills.browser.policy import PolicyError


def _parse_decision(content: str) -> dict:
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content.strip())


async def browser_skill_node(state: AgentState) -> dict:
    """
    Drives the owned Playwright engine. A single structured LLM call chooses one
    action (search / navigate / click / done); the outcome is returned as a
    typed BrowserResult carrying the extracted PageModel.
    """
    query = state["query"]
    logs = ["Initiating browser routing agent."]
    engine = get_browser_engine()
    result = BrowserResult()

    # Current page context (best-effort; empty if no page yet).
    page: PageModel = PageModel()
    try:
        page = await engine.snapshot()
        logs.append(f"Page state: '{page.title}' ({page.url})")
    except Exception as e:
        logs.append(f"No current page context: {e}")

    system_instruction = (
        "You are the browser routing agent for Lyra. Parse the user request into a "
        "single structured action. Output ONLY valid JSON matching the schema."
    )
    prompt = f"""
    Decide the best direct browser action.

    Current page: URL={page.url} Title={page.title}
    User Query: "{query}"

    Actions:
    1. "search"   → platform: google|youtube|wikipedia, payload: search term
    2. "navigate" → platform: direct, payload: fully-qualified URL
    3. "click"    → selector: an element ref from the index below
    4. "done"     → no action needed

    Interactive elements (for click):
    {page.to_prompt_block()}

    Output JSON exactly:
    {{
        "thought": "reasoning",
        "action": "search" | "navigate" | "click" | "done",
        "platform": "google" | "youtube" | "wikipedia" | "direct" | "none",
        "payload": "search term or URL",
        "selector": "element ref"
    }}
    """

    try:
        decision = _parse_decision(await llm.achat_completion(prompt, system_instruction))
        thought = decision.get("thought", "")
        action = decision.get("action", "done").lower()
        platform = decision.get("platform", "none").lower()
        payload = (decision.get("payload") or "").strip()
        selector = (decision.get("selector") or "").strip()
        logs.append(f"Agent thought: {thought}")
        result.action = action
        result.platform = platform

        if action == "search" and payload:
            enc = urllib.parse.quote(payload)
            if platform == "youtube":
                target = f"https://www.youtube.com/results?search_query={enc}"
            elif platform == "wikipedia":
                target = f"https://en.wikipedia.org/wiki/Special:Search?search={enc}"
            else:
                target = f"https://www.google.com/search?q={enc}"
            logs.append(f"Navigating to search: {target}")
            page = await engine.navigate(target)
            result.target, result.ok, result.query = target, True, payload

        elif action == "navigate" and payload:
            logs.append(f"Navigating to: {payload}")
            page = await engine.navigate(payload)
            result.target, result.ok = page.url or payload, True

        elif action == "click" and selector:
            logs.append(f"Clicking: {selector}")
            page = await engine.click(selector)
            result.target, result.ok = selector, True

        else:
            logs.append("No action needed ('done').")
            result.ok = True

        result.page = page

    except PolicyError as pe:
        logs.append(f"Blocked by security policy: {pe}")
        result.ok = False
    except Exception as e:
        logs.append(f"Browser routing error: {e}")
        # Safe fallback: a plain Google search for the raw query.
        try:
            clean = query.replace("search", "").replace("google", "").strip()
            target = f"https://www.google.com/search?q={urllib.parse.quote(clean)}"
            page = await engine.navigate(target)
            result = BrowserResult(action="search", target=target, ok=True, query=clean, page=page)
            logs.append(f"Fallback search: {target}")
        except Exception as err:
            logs.append(f"Fallback navigation failed: {err}")
            result.ok = False

    return {"action_logs": logs, "skill_result": result.model_dump()}

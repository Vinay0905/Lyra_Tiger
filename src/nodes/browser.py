import json
import asyncio
import urllib.parse

from src.agent_state import AgentState
from src.skills.webbridge import KimiWebBridgeClient
from src.llm import llm

webbridge = KimiWebBridgeClient()

# Post-action settle delay (seconds). Kept short and non-blocking via asyncio.
_SETTLE_DELAY = 2.0


def clean_tree_representation(tree_data) -> str:
    """
    Recursively flattens and formats page tree data to provide accurate selector IDs and text,
    excluding redundant nested static text nodes, preventing large payload errors in LLM APIs.
    """
    if not tree_data:
        return ""
    if isinstance(tree_data, str):
        return tree_data[:3000]
    if isinstance(tree_data, dict) and "tree" not in tree_data and "children" not in tree_data:
        return json.dumps(tree_data, indent=2)[:3000]

    lines = []

    def walk(node, parent_name="", depth=0):
        if isinstance(node, list):
            for child in node:
                walk(child, parent_name, depth)
        elif isinstance(node, dict):
            role = node.get("role") or node.get("type") or "element"
            name = (node.get("name") or node.get("text") or node.get("label") or "").strip()
            ref = node.get("ref") or node.get("id") or node.get("elementId") or ""

            is_redundant_text = (role in ("StaticText", "InlineTextBox", "image")) and (name == parent_name) and not ref
            should_print = (ref or name) and not is_redundant_text

            if should_print:
                ref_str = f" {ref}" if ref else ""
                name_str = f" {repr(name)}" if name else ""
                lines.append(f"{'  ' * depth}[{role}]{ref_str}{name_str}")

            children = node.get("children", [])
            if children:
                next_parent = name if name else parent_name
                next_depth = depth + 1 if should_print else depth
                walk(children, next_parent, next_depth)

    walk(tree_data)
    return "\n".join(lines)[:4000]


async def browser_skill_node(state: AgentState) -> dict:
    """
    Executes web browser actions using Kimi WebBridge. A single structured LLM
    call decides whether to search, navigate, or click, and the outcome is
    returned as a structured ``skill_result`` for the formatter.
    """
    query = state["query"]
    logs = ["Initiating browser routing agent."]
    result = {"action": "none", "target": "", "ok": False}

    current_url = ""
    current_title = ""
    current_tree = ""

    try:
        snapshot = await webbridge.get_snapshot()
        current_url = snapshot.get("url", "")
        current_title = snapshot.get("title", "")
        raw_tree = snapshot.get("tree") or snapshot.get("text") or snapshot.get("content") or ""
        current_tree = clean_tree_representation(raw_tree)
        logs.append(f"Initial page state: Title: '{current_title}', URL: {current_url}")
    except Exception as e:
        logs.append(f"Failed to fetch initial page state: {e}")

    system_instruction = (
        "You are the browser routing agent for Lyra. Your job is to parse the user request "
        "into a single structured action to execute. Output ONLY valid JSON matching the schema."
    )

    prompt = f"""
    Analyze the User Query and decide on the best direct browser action.

    Current page state:
    - URL: {current_url}
    - Title: {current_title}

    User Query: "{query}"

    Supported Actions:
    1. "search": search for something on Google, YouTube, or Wikipedia.
       - Set "platform" to "google", "youtube", or "wikipedia".
       - Set "payload" to the search term.
    2. "navigate": open a specific website directly.
       - Set "platform" to "direct".
       - Set "payload" to the fully-qualified URL.
    3. "click": click a link/element on the current page.
       - Set "platform" to "none".
       - Set "selector" to the element ID from the simplified page tree below.
    4. "done": no action needed.

    Simplified page tree (only relevant for "click" action):
    {current_tree}

    Output a valid JSON object matching this schema exactly:
    {{
        "thought": "Reasoning for your decision",
        "action": "search" | "navigate" | "click" | "done",
        "platform": "google" | "youtube" | "wikipedia" | "direct" | "none",
        "payload": "search term or target URL (only for search or navigate)",
        "selector": "element ID/selector (only for click)"
    }}
    """

    try:
        content = await llm.achat_completion(prompt, system_instruction)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        decision = json.loads(content.strip())
        thought = decision.get("thought", "")
        action = decision.get("action", "done").lower()
        platform = decision.get("platform", "none").lower()
        payload = decision.get("payload", "").strip()
        selector = decision.get("selector", "").strip()

        logs.append(f"Agent Thought: {thought}")
        result["action"] = action

        if action == "search" and payload:
            encoded_payload = urllib.parse.quote(payload)
            if platform == "youtube":
                target_url = f"https://www.youtube.com/results?search_query={encoded_payload}"
            elif platform == "wikipedia":
                target_url = f"https://en.wikipedia.org/wiki/Special:Search?search={encoded_payload}"
            else:
                target_url = f"https://www.google.com/search?q={encoded_payload}"
            logs.append(f"Navigating to {platform} search URL: {target_url}")
            await webbridge.navigate(target_url)
            await asyncio.sleep(_SETTLE_DELAY)
            result.update({"target": target_url, "ok": True, "query": payload, "platform": platform})

        elif action == "navigate" and payload:
            if not payload.startswith("http://") and not payload.startswith("https://"):
                payload = f"https://{payload}"
            logs.append(f"Navigating to direct URL: {payload}")
            await webbridge.navigate(payload)
            await asyncio.sleep(_SETTLE_DELAY)
            result.update({"target": payload, "ok": True})

        elif action == "click" and selector:
            logs.append(f"Clicking selector: {selector}")
            await webbridge.click(selector)
            await asyncio.sleep(_SETTLE_DELAY)
            result.update({"target": selector, "ok": True})

        else:
            logs.append("No routing action needed or declared 'done'.")

    except Exception as e:
        logs.append(f"Error during routing decision: {str(e)}")
        clean_query = query.replace("search", "").replace("google", "").strip()
        fallback_url = f"https://www.google.com/search?q={urllib.parse.quote(clean_query)}"
        logs.append(f"Falling back to direct Google Search URL: {fallback_url}")
        try:
            await webbridge.navigate(fallback_url)
            result.update({"action": "search", "target": fallback_url, "ok": True, "query": clean_query})
        except Exception as err:
            logs.append(f"Fallback navigation failed: {err}")

    return {"action_logs": logs, "skill_result": result}

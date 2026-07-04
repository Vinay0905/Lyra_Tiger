import re
from typing import Optional, Tuple

# ── Tier 0: deterministic heuristic keyword routing ────────────────────────────
# Each intent maps to a list of compiled patterns. A confident heuristic match
# short-circuits the LLM entirely, saving a network round trip on obvious verbs.

_INTENT_PATTERNS = {
    "vision": [
        r"\bscreenshot\b", r"\bscreen\b", r"\bmy display\b", r"\bwhat('| i)?s on (my |the )?screen\b",
        r"\bthis error\b", r"\banalyze (this|the) (chart|graph|image|screen)\b",
        r"\blook at (my|the) screen\b", r"\bread (my|the) screen\b",
    ],
    "browser": [
        r"\bopen (the )?(website|site|url|page|tab)\b", r"\bnavigate\b", r"\bgo to\b",
        r"\bsearch (google|youtube|the web|online|for)\b", r"\bgoogle\b", r"\byoutube\b",
        r"\bwikipedia\b", r"\bbrowse\b", r"\bhttps?://", r"\b[\w-]+\.(com|org|net|io|dev|ai)\b",
        r"\bclick (the|on)\b",
    ],
    "developer": [
        r"\bclipboard\b", r"\bscaffold\b", r"\bcreate (a )?(file|project|template|readme)\b",
        r"\bnew file\b", r"\bvs ?code\b", r"\blaunch (vs ?code|editor)\b", r"\bopen (vs ?code|the editor)\b",
    ],
}

_COMPILED = {
    intent: [re.compile(p, re.IGNORECASE) for p in patterns]
    for intent, patterns in _INTENT_PATTERNS.items()
}

# Greetings / small talk that clearly belong to chat.
_CHAT_HINTS = [
    re.compile(p, re.IGNORECASE)
    for p in (r"^\s*(hi|hey|hello|yo|good (morning|evening|afternoon))\b", r"\bhow are you\b", r"\bthank(s| you)\b")
]


def heuristic_route(query: str) -> Optional[Tuple[str, float]]:
    """
    Return ``(intent, confidence)`` when a deterministic match is found, else
    ``None`` so the caller can escalate to a model tier.

    Matching is scored per-intent; a single unambiguous winner is required to
    avoid mis-routing borderline queries.
    """
    q = (query or "").strip()
    if not q:
        return ("chat", 1.0)

    scores = {intent: 0 for intent in _COMPILED}
    for intent, patterns in _COMPILED.items():
        for pattern in patterns:
            if pattern.search(q):
                scores[intent] += 1

    total = sum(scores.values())
    if total == 0:
        if any(h.search(q) for h in _CHAT_HINTS):
            return ("chat", 0.95)
        return None

    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]
    # Require a clear winner (no tie between skill categories).
    ties = [i for i, s in scores.items() if s == best_score and s > 0]
    if len(ties) > 1:
        return None

    confidence = min(0.9, 0.6 + 0.1 * best_score)
    return (best_intent, confidence)

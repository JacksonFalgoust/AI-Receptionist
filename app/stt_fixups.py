"""Small, conservative fixes for known speech-to-text mishearings, applied
only in the context of the question the agent just asked."""

import re

_TEXT_MISHEARINGS = {"6", "six", "tex", "texts", "next", "tax", "tech", "techs"}
_ASKED_TEXT_OR_EMAIL = re.compile(r"\btext\b.*\bemail\b|\bemail\b.*\btext\b", re.IGNORECASE)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split())


def fix_choice(last_agent_text: str, user_text: str) -> str:
    """If the agent just asked "text or email?" and the caller's whole reply
    was heard as "6"/"Tex"/"next" etc., treat it as "Text."."""
    if not _ASKED_TEXT_OR_EMAIL.search(last_agent_text or ""):
        return user_text
    words = _norm(user_text).split()
    if words and words[0] in ("by", "a", "uh", "um"):
        words = words[1:]
    if len(words) == 1 and words[0] in _TEXT_MISHEARINGS:
        return "Text."
    return user_text
